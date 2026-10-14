"""
RAG subsystem with BM25 + dense retrieval + Reciprocal Rank Fusion.

All protocol documents in this repo are DEMO/synthetic excerpts —
never presented as official government protocols.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from rank_bm25 import BM25Okapi

from backend.config import get_settings
from backend.schemas.incident import Citation, ProtocolEvidence
from backend.utils.geo import tokenize
from backend.utils.logging_utils import get_logger

logger = get_logger(__name__)


@dataclass
class ProtocolChunk:
    document_id: str
    section: str
    title: str
    text: str
    citation_id: str
    is_demo: bool = True
    embedding: Optional[list[float]] = field(default=None, repr=False)


def _chunk_markdown(path: Path) -> list[ProtocolChunk]:
    text = path.read_text(encoding="utf-8")
    doc_id = path.stem.upper()
    is_demo = "DEMO" in doc_id or "demo" in path.name.lower() or True  # all bundled docs are demo
    chunks: list[ProtocolChunk] = []
    parts = re.split(r"(?m)^(#{1,3}\s+.+)$", text)
    # parts: [preamble, heading, body, heading, body, ...]
    if len(parts) == 1:
        section = "GENERAL"
        citation = f"[DEMO_PROTOCOL §{doc_id}-01]"
        chunks.append(
            ProtocolChunk(
                document_id=doc_id,
                section=section,
                title=path.stem,
                text=text.strip(),
                citation_id=citation,
                is_demo=is_demo,
            )
        )
        return chunks

    preamble = parts[0].strip()
    idx = 1
    sec_num = 1
    if preamble:
        citation = f"[DEMO_PROTOCOL §{doc_id}-{sec_num:02d}]"
        chunks.append(
            ProtocolChunk(
                document_id=doc_id,
                section=f"{doc_id}-{sec_num:02d}",
                title="Preamble",
                text=preamble,
                citation_id=citation,
                is_demo=True,
            )
        )
        sec_num += 1

    i = 1
    while i < len(parts) - 1:
        heading = parts[i].lstrip("#").strip()
        body = parts[i + 1].strip()
        i += 2
        if not body:
            continue
        section = f"{doc_id}-{sec_num:02d}"
        # Prefer explicit section tags like START-01 in heading.
        m = re.search(r"([A-Z]+-\d+)", heading)
        if m:
            section = m.group(1)
        citation = f"[DEMO_PROTOCOL §{section}]"
        chunks.append(
            ProtocolChunk(
                document_id=doc_id,
                section=section,
                title=heading,
                text=body,
                citation_id=citation,
                is_demo=True,
            )
        )
        sec_num += 1
    return chunks


class SimpleEmbedder:
    """Hashing / bag-of-words embedding fallback (no GPU required)."""

    def __init__(self, dim: int = 256) -> None:
        self.dim = dim
        self._st = None
        try:
            from sentence_transformers import SentenceTransformer

            self._st = SentenceTransformer("all-MiniLM-L6-v2")
            self.dim = self._st.get_sentence_embedding_dimension()
            logger.info("sentence-transformers loaded")
        except Exception as exc:
            logger.info("Using hashing embedder fallback: %s", exc)

    def embed(self, texts: list[str]) -> list[list[float]]:
        if self._st is not None:
            return self._st.encode(texts, show_progress_bar=False).tolist()
        import hashlib
        import math

        out: list[list[float]] = []
        for t in texts:
            vec = [0.0] * self.dim
            for tok in tokenize(t):
                h = int(hashlib.md5(tok.encode()).hexdigest(), 16)
                vec[h % self.dim] += 1.0
            norm = math.sqrt(sum(v * v for v in vec)) or 1.0
            out.append([v / norm for v in vec])
        return out


def rrf_fuse(rank_lists: list[list[int]], k: int = 60) -> list[tuple[int, float]]:
    scores: dict[int, float] = {}
    for ranking in rank_lists:
        for rank, idx in enumerate(ranking):
            scores[idx] = scores.get(idx, 0.0) + 1.0 / (k + rank + 1)
    return sorted(scores.items(), key=lambda x: x[1], reverse=True)


class ProtocolRAG:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.chunks: list[ProtocolChunk] = []
        self.bm25: Optional[BM25Okapi] = None
        self.embedder = SimpleEmbedder()
        self._chroma = None
        self._collection = None
        self.status = "uninitialized"
        self.load()

    def load(self) -> None:
        path = Path(self.settings.protocols_path)
        path.mkdir(parents=True, exist_ok=True)
        files = list(path.glob("*.md")) + list(path.glob("*.txt"))
        self.chunks = []
        for f in files:
            self.chunks.extend(_chunk_markdown(f))
        if not self.chunks:
            self.status = "empty"
            logger.warning("No protocol documents found in %s", path)
            return
        corpus = [tokenize(c.text + " " + c.title) for c in self.chunks]
        self.bm25 = BM25Okapi(corpus)
        embeddings = self.embedder.embed([c.text for c in self.chunks])
        for c, emb in zip(self.chunks, embeddings):
            c.embedding = emb
        self._init_chroma(embeddings)
        self.status = f"ready:{len(self.chunks)}_chunks"
        logger.info("RAG loaded %s chunks", len(self.chunks))

    def _init_chroma(self, embeddings: list[list[float]]) -> None:
        try:
            import chromadb
            from chromadb.config import Settings as ChromaSettings

            client = chromadb.PersistentClient(
                path=self.settings.chroma_path,
                settings=ChromaSettings(anonymized_telemetry=False),
            )
            self._chroma = client
            try:
                client.delete_collection("demo_protocols")
            except Exception:
                pass
            col = client.create_collection("demo_protocols", metadata={"hnsw:space": "cosine"})
            col.add(
                ids=[f"chunk_{i}" for i in range(len(self.chunks))],
                embeddings=embeddings,
                documents=[c.text for c in self.chunks],
                metadatas=[
                    {
                        "document_id": c.document_id,
                        "section": c.section,
                        "title": c.title,
                        "citation_id": c.citation_id,
                        "is_demo": True,
                    }
                    for c in self.chunks
                ],
            )
            self._collection = col
        except Exception as exc:
            logger.info("Chroma unavailable, using in-memory dense retrieval: %s", exc)
            self._collection = None

    def _dense_ranks(self, query: str, top_n: int = 20) -> list[int]:
        q = self.embedder.embed([query])[0]
        if self._collection is not None:
            res = self._collection.query(query_embeddings=[q], n_results=min(top_n, len(self.chunks)))
            ids = res.get("ids", [[]])[0]
            return [int(i.split("_")[1]) for i in ids]
        # In-memory cosine
        import math

        scored = []
        for i, c in enumerate(self.chunks):
            if not c.embedding:
                continue
            dot = sum(a * b for a, b in zip(q, c.embedding))
            scored.append((i, dot))
        scored.sort(key=lambda x: x[1], reverse=True)
        return [i for i, _ in scored[:top_n]]

    def _bm25_ranks(self, query: str, top_n: int = 20) -> list[int]:
        assert self.bm25 is not None
        scores = self.bm25.get_scores(tokenize(query))
        ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        return ranked[:top_n]

    def search(self, query: str, top_k: Optional[int] = None) -> ProtocolEvidence:
        if not self.chunks or self.bm25 is None:
            return ProtocolEvidence(
                summary="Insufficient protocol evidence — human review required.",
                retrieval_confidence=0.0,
                insufficient_evidence=True,
            )
        k = top_k or self.settings.rag_top_k
        bm = self._bm25_ranks(query)
        dense = self._dense_ranks(query)
        fused = rrf_fuse([bm, dense])
        citations: list[Citation] = []
        for idx, score in fused[:k]:
            c = self.chunks[idx]
            citations.append(
                Citation(
                    citation_id=c.citation_id,
                    document_id=c.document_id,
                    section=c.section,
                    title=c.title,
                    snippet=c.text[:400],
                    score=round(score, 4),
                    is_demo=True,
                )
            )
        conf = citations[0].score if citations else 0.0
        # Normalize rough RRF score to 0-1-ish for thresholding.
        norm_conf = min(1.0, conf * 30)
        if norm_conf < self.settings.rag_min_score or not citations:
            return ProtocolEvidence(
                citations=citations,
                summary="Insufficient protocol evidence — human review required.",
                retrieval_confidence=norm_conf,
                insufficient_evidence=True,
            )
        summary = (
            "Retrieved DEMO protocol excerpts (synthetic educational content only). "
            + " ".join(c.citation_id for c in citations)
        )
        return ProtocolEvidence(
            citations=citations,
            summary=summary,
            retrieval_confidence=norm_conf,
            insufficient_evidence=False,
        )


_rag_singleton: Optional[ProtocolRAG] = None


def get_rag() -> ProtocolRAG:
    global _rag_singleton
    if _rag_singleton is None:
        _rag_singleton = ProtocolRAG()
    return _rag_singleton
