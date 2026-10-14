"""FastAPI route handlers."""
from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect

from backend.config import get_settings
from backend.pipeline.orchestrator import (
    STORE,
    analyze_incident,
    component_status,
    run_mci_simulation,
    run_simulation,
)
from backend.rag.retriever import get_rag
from backend.schemas.incident import (
    ActionRequest,
    DispatcherAction,
    DispatcherActionType,
    HealthResponse,
    IncidentCreate,
    SimulationRequest,
    utcnow,
)
from backend.services.scenarios import list_scenarios

router = APIRouter()

DISCLAIMER = (
    "SENTINEL-911 is a research/educational decision-support prototype. "
    "It is NOT suitable for real emergency dispatch. AI recommends, human decides."
)


class ConnectionManager:
    def __init__(self) -> None:
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self.active.append(ws)

    def disconnect(self, ws: WebSocket) -> None:
        if ws in self.active:
            self.active.remove(ws)

    async def broadcast(self, message: dict[str, Any]) -> None:
        dead = []
        for ws in self.active:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


ws_manager = ConnectionManager()


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(
        status="ok",
        model_mode=settings.model_mode,
        demo_mode=settings.demo_mode,
        components=component_status(),
        disclaimer=DISCLAIMER,
    )


@router.get("/scenarios")
def scenarios() -> dict:
    return {"scenarios": list_scenarios(), "disclaimer": DISCLAIMER}


@router.post("/incidents")
def create_incident(payload: IncidentCreate) -> dict:
    incident = analyze_incident(payload)
    return {"incident": incident.model_dump(mode="json"), "disclaimer": DISCLAIMER}


@router.get("/incidents")
def list_incidents() -> dict:
    items = [i.model_dump(mode="json") for i in STORE.list()]
    return {"count": len(items), "incidents": items, "disclaimer": DISCLAIMER}


@router.get("/incidents/{incident_id}")
def get_incident(incident_id: str) -> dict:
    inc = STORE.get(incident_id)
    if not inc:
        # try DB
        inc = STORE.repo.get_incident(incident_id)
    if not inc:
        raise HTTPException(404, "Incident not found")
    return {"incident": inc.model_dump(mode="json"), "disclaimer": DISCLAIMER}


@router.post("/incidents/{incident_id}/analyze")
def reanalyze(incident_id: str) -> dict:
    inc = STORE.get(incident_id)
    if not inc:
        raise HTTPException(404, "Incident not found")
    payload = IncidentCreate(
        transcript=inc.audio_evidence.transcript if inc.audio_evidence else inc.narrative_summary,
        lat=inc.location.lat,
        lon=inc.location.lon,
        address=inc.location.address,
        landmark=inc.location.landmark,
    )
    # Create a fresh analysis linked by narrative (new id).
    new_inc = analyze_incident(payload)
    return {"incident": new_inc.model_dump(mode="json"), "disclaimer": DISCLAIMER}


def _apply_action(incident_id: str, action: DispatcherActionType, body: ActionRequest) -> dict:
    inc = STORE.get(incident_id)
    if not inc:
        raise HTTPException(404, "Incident not found")
    da = DispatcherAction(
        action=action,
        timestamp=utcnow(),
        changes=body.changes,
        reason=body.reason,
        actor=body.actor,
    )
    inc.dispatcher_actions.append(da)
    if action == DispatcherActionType.APPROVE:
        inc.status = "approved"
    elif action == DispatcherActionType.AMEND:
        inc.status = "amended"
        # Apply simple amendments to plan notes / score display only — never auto-dispatch.
        if "tier_override" in body.changes:
            inc.status = "amended_tier_noted"
        if "notes" in body.changes:
            if inc.resource_plan:
                inc.resource_plan.notes.append(str(body.changes["notes"]))
    elif action == DispatcherActionType.REJECT:
        inc.status = "rejected"
    elif action == DispatcherActionType.ESCALATE:
        inc.status = "escalated"
        inc.abstain = True
        inc.abstain_reason = body.reason or "Dispatcher escalated"

    STORE.upsert(inc)
    STORE.repo.save_action(incident_id, da)
    STORE.repo.audit(
        f"dispatcher_{action.value.lower()}",
        f"{action.value}: {body.reason}",
        incident_id=incident_id,
        meta=body.changes,
    )
    return {
        "incident": inc.model_dump(mode="json"),
        "action": da.model_dump(mode="json"),
        "note": "No real emergency services were contacted.",
        "disclaimer": DISCLAIMER,
    }


@router.post("/incidents/{incident_id}/approve")
def approve(incident_id: str, body: ActionRequest) -> dict:
    return _apply_action(incident_id, DispatcherActionType.APPROVE, body)


@router.post("/incidents/{incident_id}/amend")
def amend(incident_id: str, body: ActionRequest) -> dict:
    return _apply_action(incident_id, DispatcherActionType.AMEND, body)


@router.post("/incidents/{incident_id}/reject")
def reject(incident_id: str, body: ActionRequest) -> dict:
    return _apply_action(incident_id, DispatcherActionType.REJECT, body)


@router.post("/incidents/{incident_id}/escalate")
def escalate(incident_id: str, body: ActionRequest) -> dict:
    return _apply_action(incident_id, DispatcherActionType.ESCALATE, body)


@router.post("/simulation/run")
def simulation_run(body: SimulationRequest) -> dict:
    result = run_simulation(
        scenario_id=body.scenario_id,
        generate_duplicates=body.generate_duplicates,
        duplicate_count=body.duplicate_count,
    )
    return result


@router.post("/simulation/mci")
def simulation_mci(body: SimulationRequest) -> dict:
    return run_mci_simulation(duplicate_count=body.duplicate_count or 10)


@router.get("/clusters")
def get_clusters() -> dict:
    return {
        "clusters": [c.model_dump(mode="json") for c in STORE.clusters],
        "disclaimer": DISCLAIMER,
    }


@router.get("/protocols/search")
def protocol_search(q: str, top_k: int = 5) -> dict:
    rag = get_rag()
    evidence = rag.search(q, top_k=top_k)
    return {
        "query": q,
        "evidence": evidence.model_dump(mode="json"),
        "note": "All bundled sources are DEMO/synthetic educational excerpts.",
        "disclaimer": DISCLAIMER,
    }


@router.get("/metrics")
def metrics() -> dict:
    incidents = STORE.list()
    tiers = {"RED": 0, "YELLOW": 0, "GREEN": 0, "BLACK": 0}
    for i in incidents:
        if i.urgency:
            tiers[i.urgency.tier.value] = tiers.get(i.urgency.tier.value, 0) + 1
    return {
        "active_incidents": len(incidents),
        "tiers": tiers,
        "duplicate_clusters": len(STORE.clusters),
        "pending_review": sum(1 for i in incidents if i.status == "pending_review"),
        "components": component_status(),
        "disclaimer": DISCLAIMER,
    }


@router.get("/audit")
def audit_log(limit: int = 50) -> dict:
    return {"events": STORE.repo.list_audit(limit=limit), "disclaimer": DISCLAIMER}


@router.websocket("/ws/incidents")
async def ws_incidents(websocket: WebSocket) -> None:
    await ws_manager.connect(websocket)
    try:
        await websocket.send_json(
            {
                "type": "hello",
                "message": "Connected to SENTINEL-911 demo stream",
                "disclaimer": DISCLAIMER,
            }
        )
        while True:
            # Push periodic snapshot; also accept ping messages.
            try:
                msg = await asyncio.wait_for(websocket.receive_text(), timeout=5.0)
                if msg == "ping":
                    await websocket.send_json({"type": "pong"})
            except asyncio.TimeoutError:
                snapshot = {
                    "type": "snapshot",
                    "count": len(STORE.incidents),
                    "incidents": [i.model_dump(mode="json") for i in STORE.list()[:20]],
                    "clusters": [c.model_dump(mode="json") for c in STORE.clusters],
                }
                await websocket.send_json(snapshot)
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception:
        ws_manager.disconnect(websocket)
