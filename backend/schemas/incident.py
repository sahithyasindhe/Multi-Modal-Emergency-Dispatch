"""Pydantic schemas — canonical Incident Object and related models."""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UrgencyTier(str, Enum):
    RED = "RED"
    YELLOW = "YELLOW"
    GREEN = "GREEN"
    BLACK = "BLACK"


class IncidentType(str, Enum):
    VEHICLE_CRASH = "vehicle_crash"
    FIRE = "fire"
    FLOOD = "flood"
    STRUCTURAL_COLLAPSE = "structural_collapse"
    ASSAULT = "assault"
    MEDICAL = "medical"
    HAZMAT = "hazmat"
    MCI = "mci"
    OTHER = "other"


class SceneType(str, Enum):
    VEHICLE_CRASH = "vehicle_crash"
    FIRE = "fire"
    FLOOD = "flood"
    STRUCTURAL_COLLAPSE = "structural_collapse"
    ASSAULT = "assault"
    MEDICAL = "medical"
    HAZMAT = "hazmat"
    OTHER = "other"


class LocationInfo(BaseModel):
    lat: float = 37.7749
    lon: float = -122.4194
    address: str = "Unknown location"
    landmark: Optional[str] = None
    landmark_refs: list[str] = Field(default_factory=list)
    h3_cell: Optional[str] = None
    nearest_facility_id: Optional[str] = None
    nearest_facility_name: Optional[str] = None
    distance_m: Optional[float] = None


class Casualties(BaseModel):
    count_est: int = 0
    down_count: int = 0
    ambulatory: int = 0
    pediatric: int = 0
    elderly: int = 0
    deceased_est: int = 0


class Hazards(BaseModel):
    fire: bool = False
    hazmat: bool = False
    structural: bool = False
    electrical: bool = False
    water: bool = False
    fuel_leak: bool = False
    smoke: bool = False


class CallerState(BaseModel):
    conscious: bool = True
    panic_index: float = Field(0.0, ge=0.0, le=1.0)
    language: str = "en"
    on_scene: bool = True


class ProvenanceFlag(BaseModel):
    value: bool
    sources: list[str] = Field(default_factory=list)
    notes: str = ""


class ModalityConflict(BaseModel):
    field: str
    audio_says: str
    vision_says: str
    resolution: str
    retained: str
    confidence: float = 0.5


class AudioEvidence(BaseModel):
    transcript: str = ""
    language: str = "en"
    timestamps: list[dict[str, Any]] = Field(default_factory=list)
    panic_index: float = 0.0
    speech_rate_wpm: float = 0.0
    silence_ratio: float = 0.0
    rms_energy: float = 0.0
    pitch_mean: float = 0.0
    audio_events: list[str] = Field(default_factory=list)
    provider: str = "demo"
    confidence: float = 0.7


class VisualReport(BaseModel):
    scene_type: SceneType = SceneType.OTHER
    persons_visible: int = 0
    persons_down: int = 0
    vehicles_visible: int = 0
    fire_visible: bool = False
    smoke_present: bool = False
    water_rising: bool = False
    hazmat_placard: bool = False
    structural_damage: bool = False
    fuel_leak_visible: bool = False
    image_quality: str = "unknown"
    model_confidence: float = 0.5
    detections: list[dict[str, Any]] = Field(default_factory=list)
    provider: str = "demo"
    notes: str = ""


class LocationEvidence(BaseModel):
    location: LocationInfo = Field(default_factory=LocationInfo)
    provider: str = "demo"
    confidence: float = 0.8


class FeatureBreakdown(BaseModel):
    life_threat: float = 0.0
    casualty_load: float = 0.0
    hazard_risk: float = 0.0
    access: float = 0.0
    caller_state: float = 0.0


class UrgencyScore(BaseModel):
    value: float = Field(..., ge=0.0, le=100.0)
    tier: UrgencyTier
    feature_breakdown: FeatureBreakdown
    rules_triggered: list[str] = Field(default_factory=list)
    protocol_sources: list[str] = Field(default_factory=list)
    overrides_applied: list[str] = Field(default_factory=list)
    black_expectant: bool = False


class Citation(BaseModel):
    citation_id: str
    document_id: str
    section: str
    title: str
    snippet: str
    score: float
    is_demo: bool = True


class ProtocolEvidence(BaseModel):
    citations: list[Citation] = Field(default_factory=list)
    summary: str = ""
    retrieval_confidence: float = 0.0
    insufficient_evidence: bool = False


class ResourceUnit(BaseModel):
    unit_id: str
    unit_type: str
    status: str = "available"
    eta_minutes: float = 0.0
    capability: list[str] = Field(default_factory=list)


class ResourcePlan(BaseModel):
    recommended_units: list[ResourceUnit] = Field(default_factory=list)
    nearest_facility: Optional[str] = None
    nearest_facility_eta_min: Optional[float] = None
    hazmat_warning: bool = False
    sms_triage_draft: Optional[str] = None
    notes: list[str] = Field(default_factory=list)
    revision: int = 0


class SafetyValidationResult(BaseModel):
    valid: bool = True
    violations: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    required_human_action: str = "REVIEW"


class Explanation(BaseModel):
    why_tier: list[str] = Field(default_factory=list)
    protocol_citations: list[str] = Field(default_factory=list)
    deterministic_rules: list[str] = Field(default_factory=list)
    narrative: str = ""
    decision_line: str = ""


class DispatcherActionType(str, Enum):
    APPROVE = "APPROVE"
    AMEND = "AMEND"
    REJECT = "REJECT"
    ESCALATE = "ESCALATE"


class DispatcherAction(BaseModel):
    action: DispatcherActionType
    timestamp: datetime = Field(default_factory=utcnow)
    changes: dict[str, Any] = Field(default_factory=dict)
    reason: str = ""
    actor: str = "dispatcher"


class Incident(BaseModel):
    incident_id: str
    timestamp: datetime = Field(default_factory=utcnow)
    modality_sources: list[str] = Field(default_factory=list)
    incident_type: IncidentType = IncidentType.OTHER
    location: LocationInfo = Field(default_factory=LocationInfo)
    casualties: Casualties = Field(default_factory=Casualties)
    hazards: Hazards = Field(default_factory=Hazards)
    hazard_provenance: dict[str, ProvenanceFlag] = Field(default_factory=dict)
    caller_state: CallerState = Field(default_factory=CallerState)
    narrative_summary: str = ""
    extraction_confidence: float = 0.7
    conflicts: list[ModalityConflict] = Field(default_factory=list)
    audio_evidence: Optional[AudioEvidence] = None
    visual_evidence: Optional[VisualReport] = None
    location_evidence: Optional[LocationEvidence] = None
    urgency: Optional[UrgencyScore] = None
    protocol_evidence: Optional[ProtocolEvidence] = None
    resource_plan: Optional[ResourcePlan] = None
    safety: Optional[SafetyValidationResult] = None
    explanation: Optional[Explanation] = None
    cluster_id: Optional[str] = None
    caller_count: int = 1
    status: str = "pending_review"
    dispatcher_actions: list[DispatcherAction] = Field(default_factory=list)
    workflow_stage: str = "intake"
    abstain: bool = False
    abstain_reason: str = ""

    class Config:
        use_enum_values = False


class IncidentCluster(BaseModel):
    cluster_id: str
    incident_ids: list[str]
    incident_type: IncidentType
    caller_count: int
    similarity: float
    location: LocationInfo
    primary_incident_id: str
    urgency_tier: Optional[UrgencyTier] = None


class IncidentCreate(BaseModel):
    transcript: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    address: Optional[str] = None
    landmark: Optional[str] = None
    image_b64: Optional[str] = None
    visual_overrides: Optional[dict[str, Any]] = None
    scenario_id: Optional[str] = None
    caller_id: Optional[str] = None


class ActionRequest(BaseModel):
    reason: str = ""
    changes: dict[str, Any] = Field(default_factory=dict)
    actor: str = "dispatcher"


class SimulationRequest(BaseModel):
    scenario_id: Optional[str] = None
    generate_duplicates: bool = False
    duplicate_count: int = 10


class HealthResponse(BaseModel):
    status: str
    model_mode: str
    demo_mode: bool
    components: dict[str, str]
    disclaimer: str
