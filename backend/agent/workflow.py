"""Controlled agentic decision workflow (explicit state machine, max 2 revisions)."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable

from backend.config import get_settings
from backend.providers.llm import get_llm_provider
from backend.rag.retriever import get_rag
from backend.safety.validator import validate_safety
from backend.schemas.incident import (
    Explanation,
    Incident,
    ResourcePlan,
    ResourceUnit,
    UrgencyTier,
)
from backend.services.facilities import (
    check_unit_availability,
    eta_compute,
    nearest_facility,
    send_sms_triage,
    trigger_hazmat_warning,
)
from backend.triage.engine import urgency_score
from backend.utils.logging_utils import get_logger

logger = get_logger(__name__)


class Stage(str, Enum):
    RETRIEVE_PROTOCOL = "retrieve_protocol"
    SCORE_URGENCY = "score_urgency"
    PLAN_RESOURCES = "plan_resources"
    SAFETY_VALIDATOR = "safety_validator"
    REVISE_PLAN = "revise_plan"
    EXPLAIN = "explain"
    HUMAN_APPROVAL = "human_approval"
    ABSTAIN = "abstain"
    DONE = "done"


@dataclass
class GraphState:
    incident: Incident
    revision_attempts: int = 0
    stage: Stage = Stage.RETRIEVE_PROTOCOL
    log: list[str] = field(default_factory=list)
    tools_called: list[str] = field(default_factory=list)


def _plan_for(incident: Incident, conservative: bool = False) -> ResourcePlan:
    lat, lon = incident.location.lat, incident.location.lon
    tier = incident.urgency.tier if incident.urgency else UrgencyTier.GREEN
    wanted: list[str] = ["BLS"]
    notes: list[str] = []

    if tier in (UrgencyTier.YELLOW, UrgencyTier.RED):
        wanted.append("ALS")
    if incident.hazards.fire or incident.hazards.smoke:
        wanted.extend(["ENGINE", "LADDER"])
    if incident.hazards.hazmat:
        wanted.append("HAZMAT")
    if incident.casualties.count_est >= 5 or tier == UrgencyTier.RED:
        wanted.append("RESCUE")
    if incident.casualties.count_est >= 10:
        wanted.append("ENGINE_STRIKE")

    if conservative and tier == UrgencyTier.GREEN:
        wanted = ["BLS"]
        notes.append("Conservative revision: stripped high-priority units for GREEN.")

    available = check_unit_availability(None)
    selected: list[ResourceUnit] = []
    for w in wanted:
        matches = [
            u
            for u in available
            if u.unit_type == w and u.unit_id not in {s.unit_id for s in selected}
        ]
        if not matches:
            matches = [
                u
                for u in check_unit_availability([w])
                if u.unit_id not in {s.unit_id for s in selected}
            ]
        if matches:
            selected.append(matches[0])

    fac_type = (
        "hazmat"
        if incident.hazards.hazmat
        else ("trauma" if tier == UrgencyTier.RED else "hospital")
    )
    fac = nearest_facility(lat, lon, fac_type if fac_type != "hospital" else None)
    if fac_type == "hospital":
        fac = nearest_facility(lat, lon, "hospital")
    eta = eta_compute(fac.get("distance_m", 2000))
    for u in selected:
        u.eta_minutes = round(eta * 0.6 + 2.0, 1)

    haz_warn = False
    if incident.hazards.hazmat:
        trigger_hazmat_warning(incident.incident_id)
        haz_warn = True
        notes.append("HAZMAT warning flagged (demo only — not transmitted).")

    sms = None
    if incident.caller_state.on_scene and tier != UrgencyTier.GREEN:
        sms_result = send_sms_triage(
            "000-000-0000",
            "DEMO: Stay safe, help is being coordinated. Not a real message.",
        )
        sms = sms_result.get("message_preview")

    incident.location.nearest_facility_id = fac.get("id")
    incident.location.nearest_facility_name = fac.get("name")
    incident.location.distance_m = fac.get("distance_m")

    return ResourcePlan(
        recommended_units=selected,
        nearest_facility=fac.get("name"),
        nearest_facility_eta_min=eta,
        hazmat_warning=haz_warn,
        sms_triage_draft=sms,
        notes=notes,
        revision=0,
    )


def _build_explanation(incident: Incident) -> Explanation:
    why: list[str] = []
    if incident.urgency:
        fb = incident.urgency.feature_breakdown
        why.append(f"Life threat component {fb.life_threat:.0f}/100")
        why.append(f"Casualty load component {fb.casualty_load:.0f}/100")
        if incident.casualties.down_count:
            why.append(f"{incident.casualties.down_count} non-ambulatory casualties detected.")
        if incident.hazards.fire:
            why.append("Fire/smoke indicators present.")
        if incident.hazards.structural:
            why.append("Structural hazard detected.")
        if incident.hazards.hazmat:
            why.append("HAZMAT indicator detected.")
        for o in incident.urgency.overrides_applied:
            why.append(o)

    citations: list[str] = []
    if incident.protocol_evidence:
        citations = [c.citation_id for c in incident.protocol_evidence.citations]

    rules = incident.urgency.rules_triggered if incident.urgency else []
    decision = ""
    if incident.urgency:
        decision = f"{incident.urgency.value:.0f}/100 — {incident.urgency.tier.value}"

    llm = get_llm_provider()
    narrative = llm.generate(
        system=(
            "You are a demo explainability assistant. Never claim real 911 authority. "
            "Cite only provided DEMO citations."
        ),
        user=f"Features: {why}\nCitations: {citations}\nRules: {rules}\nWrite 2 short sentences.",
    )

    return Explanation(
        why_tier=why,
        protocol_citations=citations,
        deterministic_rules=rules
        + (incident.urgency.overrides_applied if incident.urgency else []),
        narrative=narrative,
        decision_line=decision,
    )


class DecisionWorkflow:
    """Explicit state-machine equivalent to a LangGraph graph. No autonomous loops."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.max_revisions = self.settings.max_revision_attempts

    def run(self, incident: Incident) -> Incident:
        state = GraphState(incident=incident)
        handlers: dict[Stage, Callable[[GraphState], Stage]] = {
            Stage.RETRIEVE_PROTOCOL: self._retrieve,
            Stage.SCORE_URGENCY: self._score,
            Stage.PLAN_RESOURCES: self._plan,
            Stage.SAFETY_VALIDATOR: self._safety,
            Stage.REVISE_PLAN: self._revise,
            Stage.EXPLAIN: self._explain,
            Stage.HUMAN_APPROVAL: self._human,
            Stage.ABSTAIN: self._abstain,
        }

        guard = 0
        while state.stage not in (Stage.DONE,) and guard < 20:
            guard += 1
            handler = handlers.get(state.stage)
            if handler is None:
                break
            state.stage = handler(state)

        state.incident.workflow_stage = state.stage.value
        return state.incident

    def _retrieve(self, state: GraphState) -> Stage:
        inc = state.incident
        rag = get_rag()
        query = (
            f"{inc.incident_type} casualties {inc.casualties.count_est} "
            f"fire={inc.hazards.fire} hazmat={inc.hazards.hazmat} "
            f"structural={inc.hazards.structural} water={inc.hazards.water} "
            f"{inc.narrative_summary}"
        )
        evidence = rag.search(query)
        inc.protocol_evidence = evidence
        state.log.append(
            f"RAG: conf={evidence.retrieval_confidence:.2f} cites={len(evidence.citations)}"
        )
        state.tools_called.append("retrieve_protocol")
        return Stage.SCORE_URGENCY

    def _score(self, state: GraphState) -> Stage:
        inc = state.incident
        inc.urgency = urgency_score(inc)
        state.log.append(f"Score={inc.urgency.value} tier={inc.urgency.tier.value}")
        return Stage.PLAN_RESOURCES

    def _plan(self, state: GraphState) -> Stage:
        inc = state.incident
        plan = _plan_for(inc, conservative=False)
        plan.revision = state.revision_attempts
        inc.resource_plan = plan
        state.tools_called.extend(
            ["check_unit_availability", "nearest_facility", "eta_compute"]
        )
        if inc.hazards.hazmat:
            state.tools_called.append("trigger_hazmat_warning")
        return Stage.SAFETY_VALIDATOR

    def _safety(self, state: GraphState) -> Stage:
        inc = state.incident
        result = validate_safety(inc, inc.resource_plan)
        inc.safety = result
        state.log.append(f"Safety valid={result.valid} violations={result.violations}")
        if result.valid:
            return Stage.EXPLAIN
        if state.revision_attempts < self.max_revisions:
            return Stage.REVISE_PLAN
        return Stage.ABSTAIN

    def _revise(self, state: GraphState) -> Stage:
        state.revision_attempts += 1
        inc = state.incident
        plan = _plan_for(inc, conservative=True)
        if inc.hazards.hazmat:
            plan.hazmat_warning = True
            trigger_hazmat_warning(inc.incident_id)
        plan.revision = state.revision_attempts
        plan.notes.append(
            f"Revision attempt {state.revision_attempts}/{self.max_revisions}"
        )
        inc.resource_plan = plan
        state.log.append(f"Revised plan attempt={state.revision_attempts}")
        return Stage.SAFETY_VALIDATOR

    def _explain(self, state: GraphState) -> Stage:
        state.incident.explanation = _build_explanation(state.incident)
        return Stage.HUMAN_APPROVAL

    def _human(self, state: GraphState) -> Stage:
        state.incident.status = "pending_review"
        state.incident.workflow_stage = Stage.HUMAN_APPROVAL.value
        state.log.append("Awaiting human approval — AI recommends, human decides.")
        return Stage.DONE

    def _abstain(self, state: GraphState) -> Stage:
        inc = state.incident
        inc.abstain = True
        inc.abstain_reason = (
            "Safety validation failed after max revisions — escalate to human."
        )
        inc.status = "escalated"
        inc.explanation = _build_explanation(inc)
        if inc.safety:
            inc.safety.required_human_action = "ESCALATE_TO_HUMAN"
        state.log.append("ABSTAIN + ESCALATE TO HUMAN")
        return Stage.DONE


def run_agentic_workflow(incident: Incident) -> Incident:
    return DecisionWorkflow().run(incident)
