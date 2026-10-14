"""Deterministic safety validator — no automatic dispatch."""
from __future__ import annotations

from backend.schemas.incident import (
    Incident,
    ResourcePlan,
    SafetyValidationResult,
    UrgencyTier,
)


def validate_safety(incident: Incident, plan: ResourcePlan | None = None) -> SafetyValidationResult:
    plan = plan or incident.resource_plan or ResourcePlan()
    urgency = incident.urgency
    violations: list[str] = []
    warnings: list[str] = []

    # Never auto-dispatch.
    warnings.append("No dispatch action can execute automatically — human approval required.")

    if urgency is None:
        violations.append("Missing urgency score")
    else:
        if urgency.tier in (UrgencyTier.RED, UrgencyTier.YELLOW):
            warnings.append("RED/YELLOW recommendation requires dispatcher confirmation.")

        # GREEN must not receive highest-priority resource set.
        if urgency.tier == UrgencyTier.GREEN:
            high_pri = [u for u in plan.recommended_units if u.unit_type in {"ALS", "HAZMAT", "HELI", "ENGINE_STRIKE"}]
            if high_pri:
                violations.append("GREEN incident must not receive highest-priority resource recommendation.")

        if urgency.tier == UrgencyTier.BLACK:
            warnings.append("BLACK/expectant classification — medical examiner / supervisor review.")

    if incident.hazards.hazmat:
        if not plan.hazmat_warning:
            violations.append("HAZMAT requires hazard warning on resource plan.")
        pe = incident.protocol_evidence
        if not pe or pe.insufficient_evidence or not pe.citations:
            violations.append("HAZMAT recommendation must have supporting protocol evidence.")

    if incident.extraction_confidence < 0.45:
        violations.append("Low extraction confidence requires human review.")
        warnings.append("Low confidence — do not treat AI output as authoritative.")

    if incident.conflicts:
        warnings.append("⚠ MODALITY CONFLICT present — review evidence before acting.")
        # Conflicts must be visible (enforced by UI); validator flags them.
        for c in incident.conflicts:
            warnings.append(f"Conflict on {c.field}: retained {c.retained}")

    if incident.protocol_evidence and incident.protocol_evidence.insufficient_evidence:
        warnings.append("Insufficient protocol evidence — human review required.")

    required = "APPROVE_OR_ESCALATE"
    if violations:
        required = "RESOLVE_VIOLATIONS_THEN_REVIEW"
    elif incident.extraction_confidence < 0.55 or incident.conflicts:
        required = "MANDATORY_HUMAN_REVIEW"

    return SafetyValidationResult(
        valid=len(violations) == 0,
        violations=violations,
        warnings=warnings,
        required_human_action=required,
    )
