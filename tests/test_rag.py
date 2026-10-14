"""RAG retrieval and citation tests."""
from backend.rag.retriever import ProtocolRAG, get_rag, rrf_fuse


def test_rrf_fuse_orders_overlap_higher():
    fused = rrf_fuse([[0, 1, 2], [1, 0, 3]])
    ids = [i for i, _ in fused]
    assert ids[0] in {0, 1}


def test_rag_loads_demo_protocols():
    rag = get_rag()
    assert len(rag.chunks) > 0
    assert "ready" in rag.status


def test_rag_citations_are_demo_labeled():
    rag = get_rag()
    ev = rag.search("HAZMAT chemical placard vapor cloud")
    assert ev.citations
    for c in ev.citations:
        assert c.is_demo is True
        assert "DEMO_PROTOCOL" in c.citation_id


def test_rag_low_confidence_structure():
    rag = ProtocolRAG()
    ev = rag.search("zzzzzz_not_in_kb_qqqqqq_xyz123")
    assert isinstance(ev.insufficient_evidence, bool)
    if ev.insufficient_evidence:
        assert "human review" in ev.summary.lower()
