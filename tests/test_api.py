"""API endpoint tests."""
from fastapi.testclient import TestClient

from backend.main import app
from backend.pipeline.orchestrator import STORE

client = TestClient(app)


def setup_function():
    STORE.incidents.clear()
    STORE.clusters.clear()


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "disclaimer" in body
    assert "model_mode" in body


def test_create_and_list_incident():
    r = client.post(
        "/incidents",
        json={
            "transcript": "Car accident two injured one unconscious smell gas",
            "lat": 37.78,
            "lon": -122.41,
            "address": "Demo Ave",
            "scenario_id": "vehicle_crash",
        },
    )
    assert r.status_code == 200
    inc = r.json()["incident"]
    assert inc["urgency"]["value"] >= 0
    assert inc["status"] == "pending_review"

    r2 = client.get("/incidents")
    assert r2.status_code == 200
    assert r2.json()["count"] >= 1


def test_approve_does_not_dispatch_externally():
    r = client.post("/simulation/run", json={"scenario_id": "cardiac"})
    assert r.status_code == 200
    iid = r.json()["incident"]["incident_id"]
    a = client.post(f"/incidents/{iid}/approve", json={"reason": "demo approve"})
    assert a.status_code == 200
    assert "No real emergency" in a.json()["note"]
    assert a.json()["incident"]["status"] == "approved"


def test_simulation_and_metrics():
    r = client.post("/simulation/run", json={"scenario_id": "hazmat_leak"})
    assert r.status_code == 200
    assert r.json()["incident"]["hazards"]["hazmat"] is True
    m = client.get("/metrics")
    assert m.status_code == 200
    assert m.json()["active_incidents"] >= 1


def test_protocol_search():
    r = client.get("/protocols/search", params={"q": "START immediate RED"})
    assert r.status_code == 200
    assert "evidence" in r.json()
    assert "DEMO" in (r.json().get("note") or "DEMO")
