"""End-to-end simulation pipeline tests."""
from backend.pipeline.orchestrator import STORE, run_mci_simulation, run_simulation


def setup_function():
    STORE.incidents.clear()
    STORE.clusters.clear()


def test_simulation_pipeline_stages():
    result = run_simulation("vehicle_crash")
    assert "pipeline" in result
    assert result["pipeline"][0] == "INPUT"
    assert "HUMAN APPROVAL" in result["pipeline"]
    inc = result["incident"]
    assert inc["urgency"] is not None
    assert inc["resource_plan"] is not None
    assert inc["safety"] is not None
    assert inc["explanation"] is not None
    assert inc["status"] == "pending_review"


def test_modality_conflict_scenario():
    result = run_simulation("kitchen_vs_structural_fire")
    inc = result["incident"]
    assert len(inc["conflicts"]) >= 1


def test_mci_duplicate_clustering():
    result = run_mci_simulation(duplicate_count=6)
    assert result["caller_count"] == 6
    assert len(STORE.clusters) >= 1
    assert max(c.caller_count for c in STORE.clusters) >= 2
