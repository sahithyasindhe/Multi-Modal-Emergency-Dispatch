"""End-to-end multimodal analysis pipeline."""
from __future__ import annotations

import asyncio
from typing import Any, Optional

from backend.agent.workflow import run_agentic_workflow
from backend.database.repository import IncidentRepository as IncidentRepository
from backend.pipeline.fusion import fuse_entities
from backend.providers.asr import get_asr_provider
from backend.providers.vision import get_vision_provider
from backend.schemas.incident import (
    Incident,
    IncidentCreate,
    LocationEvidence,
    LocationInfo,
)
from backend.services.dedup import assign_clusters, find_cluster_match
from backend.services.facilities import nearest_facility
from backend.services.scenarios import MCI_CALLER_VARIANTS, get_scenario
from backend.utils.geo import h3_like_cell, new_id
from backend.utils.logging_utils import get_logger

logger = get_logger(__name__)


class IncidentStore:
    """In-memory store mirrored to SQLite for demo responsiveness."""

    def __init__(self) -> None:
        self.incidents: dict[str, Incident] = {}
        self.clusters: list = []
        self.repo = IncidentRepository()

    def upsert(self, incident: Incident) -> None:
        self.incidents[incident.incident_id] = incident
        self.repo.save_incident(incident)
        self._recluster()

    def _recluster(self) -> None:
        items = list(self.incidents.values())
        updated, clusters = assign_clusters(items)
        for inc in updated:
            self.incidents[inc.incident_id] = inc
        self.clusters = [c for c in clusters if c.caller_count >= 2]

    def list(self) -> list[Incident]:
        return sorted(
            self.incidents.values(),
            key=lambda x: (x.urgency.value if x.urgency else 0),
            reverse=True,
        )

    def get(self, incident_id: str) -> Optional[Incident]:
        return self.incidents.get(incident_id)


STORE = IncidentStore()


def process_location(
    lat: float,
    lon: float,
    address: str,
    landmark: str | None = None,
) -> LocationEvidence:
    fac = nearest_facility(lat, lon)
    loc = LocationInfo(
        lat=lat,
        lon=lon,
        address=address,
        landmark=landmark,
        landmark_refs=[landmark] if landmark else [],
        h3_cell=h3_like_cell(lat, lon),
        nearest_facility_id=fac.get("id"),
        nearest_facility_name=fac.get("name"),
        distance_m=fac.get("distance_m"),
    )
    return LocationEvidence(location=loc, provider="demo_geo", confidence=0.85)


async def analyze_incident_async(
    payload: IncidentCreate,
    audio_path: Optional[str] = None,
) -> Incident:
    return await asyncio.to_thread(analyze_incident, payload, audio_path)


def analyze_incident(
    payload: IncidentCreate,
    audio_path: Optional[str] = None,
) -> Incident:
    scenario_hint = None
    transcript = payload.transcript
    lat = payload.lat
    lon = payload.lon
    address = payload.address
    landmark = payload.landmark
    overrides = payload.visual_overrides

    if payload.scenario_id:
        scenario = get_scenario(payload.scenario_id)
        scenario_hint = scenario.get("scenario_hint")
        transcript = transcript or scenario["transcript"]
        lat = lat if lat is not None else scenario["lat"]
        lon = lon if lon is not None else scenario["lon"]
        address = address or scenario["address"]
        landmark = landmark or scenario.get("landmark")
        if overrides is None:
            overrides = scenario.get("visual_overrides")

    transcript = transcript or "Emergency reported. Details unclear."
    lat = lat if lat is not None else 37.7749
    lon = lon if lon is not None else -122.4194
    address = address or "Unknown DEMO address"

    asr = get_asr_provider()
    vision = get_vision_provider()
    audio_ev = asr.transcribe(audio_path=audio_path, transcript_hint=transcript)
    visual_ev = vision.analyze(
        image_b64=payload.image_b64,
        overrides=overrides,
        scenario_hint=scenario_hint,
    )
    loc_ev = process_location(lat, lon, address, landmark)

    incident_id = new_id("inc")
    incident = fuse_entities(audio_ev, visual_ev, loc_ev, incident_id=incident_id)

    match = find_cluster_match(incident, list(STORE.incidents.values()))
    if match and match.cluster_id:
        incident.cluster_id = match.cluster_id

    incident = run_agentic_workflow(incident)

    STORE.upsert(incident)
    STORE.repo.audit(
        "incident_analyzed",
        f"Analyzed {incident.incident_id} tier={incident.urgency.tier.value if incident.urgency else '?'}",
        incident_id=incident.incident_id,
        meta={"confidence": incident.extraction_confidence},
    )
    if incident.urgency:
        STORE.repo.save_triage(incident.incident_id, incident.urgency)
    if incident.resource_plan:
        STORE.repo.save_recommendation(
            incident.incident_id, incident.resource_plan.model_dump_json()
        )
    if incident.audio_evidence:
        STORE.repo.save_evidence(
            incident.incident_id, "audio", incident.audio_evidence.model_dump()
        )
    if incident.visual_evidence:
        STORE.repo.save_evidence(
            incident.incident_id, "vision", incident.visual_evidence.model_dump()
        )

    logger.info(
        "Pipeline complete %s score=%s",
        incident.incident_id,
        incident.urgency.value if incident.urgency else None,
    )
    return incident


def run_simulation(
    scenario_id: str | None = None,
    generate_duplicates: bool = False,
    duplicate_count: int = 10,
) -> dict[str, Any]:
    if generate_duplicates or scenario_id == "mci":
        return run_mci_simulation(duplicate_count=duplicate_count)

    scenario = get_scenario(scenario_id)
    incident = analyze_incident(
        IncidentCreate(
            scenario_id=scenario["id"],
            transcript=scenario["transcript"],
            lat=scenario["lat"],
            lon=scenario["lon"],
            address=scenario["address"],
            landmark=scenario.get("landmark"),
            visual_overrides=scenario.get("visual_overrides"),
        )
    )
    return {
        "scenario": scenario["id"],
        "title": scenario["title"],
        "incident": incident.model_dump(mode="json"),
        "pipeline": [
            "INPUT",
            "MULTIMODAL ANALYSIS",
            "INCIDENT OBJECT",
            "RAG RETRIEVAL",
            "TRIAGE SCORE",
            "RESOURCE PLAN",
            "SAFETY VALIDATION",
            "EXPLANATION",
            "HUMAN APPROVAL",
        ],
        "disclaimer": "RESEARCH/DEMO PROTOTYPE — not for real emergency dispatch.",
    }


def run_mci_simulation(duplicate_count: int = 10) -> dict[str, Any]:
    base = get_scenario("mci")
    incidents = []
    n = max(2, min(duplicate_count, len(MCI_CALLER_VARIANTS)))
    for i in range(n):
        jitter_lat = base["lat"] + (i * 0.00015)
        jitter_lon = base["lon"] + ((-1) ** i) * 0.00012
        transcript = (
            MCI_CALLER_VARIANTS[i % len(MCI_CALLER_VARIANTS)]
            + " "
            + base["transcript"][:80]
        )
        inc = analyze_incident(
            IncidentCreate(
                scenario_id="mci",
                transcript=transcript,
                lat=jitter_lat,
                lon=jitter_lon,
                address=base["address"],
                landmark=base.get("landmark"),
                visual_overrides=base.get("visual_overrides"),
                caller_id=f"caller_{i+1}",
            )
        )
        incidents.append(inc)

    clusters = [c.model_dump(mode="json") for c in STORE.clusters]
    return {
        "scenario": "mci",
        "title": base["title"],
        "incidents": [i.model_dump(mode="json") for i in incidents],
        "clusters": clusters,
        "caller_count": len(incidents),
        "pipeline": [
            "INPUT x N callers",
            "MULTIMODAL ANALYSIS",
            "DEDUP CLUSTERING",
            "RAG / TRIAGE / PLAN",
            "HUMAN APPROVAL",
        ],
        "disclaimer": "RESEARCH/DEMO PROTOTYPE — not for real emergency dispatch.",
    }


def component_status() -> dict[str, str]:
    from backend.config import get_settings
    from backend.rag.retriever import get_rag

    settings = get_settings()
    rag = get_rag()
    asr = get_asr_provider()
    vision = get_vision_provider()
    return {
        "asr": getattr(asr, "name", "unknown"),
        "vision": getattr(vision, "name", "unknown"),
        "rag": rag.status,
        "database": "sqlite",
        "model_mode": settings.model_mode,
        "llm": "demo" if settings.demo_mode else "openai-compatible",
    }
