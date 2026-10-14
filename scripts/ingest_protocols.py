#!/usr/bin/env python3
"""Ingest protocol markdown/text files into the RAG index."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.rag.retriever import ProtocolRAG  # noqa: E402


def main() -> None:
    rag = ProtocolRAG()
    print(f"RAG status: {rag.status}")
    print(f"Chunks: {len(rag.chunks)}")
    for c in rag.chunks[:8]:
        print(f"  - {c.citation_id} | {c.title[:60]}")
    ev = rag.search("HAZMAT structural fire non-ambulatory casualties")
    print(f"Sample retrieval confidence: {ev.retrieval_confidence:.3f}")
    print(f"Citations: {[c.citation_id for c in ev.citations]}")
    if ev.insufficient_evidence:
        print(ev.summary)


if __name__ == "__main__":
    main()
