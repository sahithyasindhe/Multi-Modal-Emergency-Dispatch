"""
Deterministic triage / urgency scoring.

CRITICAL: The LLM never assigns urgency_score. Features are extracted by AI;
this pure Python function computes the score with inspectable rules.
"""
from __future__ import annotations

from backend.schemas.incident import (
    FeatureBreakdown,
    Incident,
    UrgencyScore,
    UrgencyTier,
)
from backend.utils.geo import clamp


def _life_threat(incident: Incident) -> tuple[float, list[str]]:
    score = 0.0
    rules: list[str] = []
    h = incident.hazards
    c = incident.casualties
    caller = incident.caller_state

    if h.fire:
        score += 55
        rules.append("Fire present (+55 life_threat)")
    if h.smoke and not h.fire:
        score += 25
        rules.append("Smoke without confirmed fire (+25 life_threat)")
    if c.down_count > 0:
        score += min(50, 20 + c.down_count * 10)
        rules.append(f"Non-ambulatory/down casualties x{c.down_count}")
    if not caller.conscious:
        score += 40
        rules.append("Caller/patient unconscious (+40 life_threat)")
    if c.deceased_est > 0:
        score += 15
        rules.append("Possible deceased reported (+15)")
    return clamp(score), rules


def _casualty_load(incident: Incident) -> tuple[float, list[str]]:
    c = incident.casualties
    score = min(100.0, c.count_est * 12 + c.pediatric * 15 + c.elderly * 8 + c.down_count * 10)
    rules = [f"Casualty load from est={c.count_est}, ped={c.pediatric}, elderly={c.elderly}"]
    return clamp(score), rules


def _hazard_risk(incident: Incident) -> tuple[float, list[str]]:
    h = incident.hazards
    score = 0.0
    rules: list[str] = []
    if h.hazmat:
        score += 70
        rules.append("HAZMAT indicator")
    if h.structural:
        score += 45
        rules.append("Structural hazard")
    if h.water:
        score += 40
        rules.append("Water/flood hazard")
    if h.electrical:
        score += 35
        rules.append("Electrical hazard")
    if h.fuel_leak:
        score += 30
        rules.append("Fuel leak")
    return clamp(score), rules


def _access(incident: Incident) -> tuple[float, list[str]]:
    dist = incident.location.distance_m
    if dist is None:
        return 40.0, ["Access unknown — default moderate (40)"]
    # Farther / harder access → higher access-risk contribution.
    if dist > 5000:
        return 80.0, [f"Remote access ~{dist:.0f}m"]
    if dist > 2000:
        return 55.0, [f"Elevated access distance ~{dist:.0f}m"]
    if dist > 800:
        return 35.0, [f"Moderate access ~{dist:.0f}m"]
    return 20.0, [f"Near facility ~{dist:.0f}m"]


def _caller_state_score(incident: Incident) -> tuple[float, list[str]]:
    cs = incident.caller_state
    score = cs.panic_index * 70
    rules = [f"Panic index {cs.panic_index:.2f}"]
    if cs.on_scene:
        score += 20
        rules.append("Caller on scene (+20)")
    return clamp(score), rules


def classify_tier(value: float, black_expectant: bool = False) -> UrgencyTier:
    if black_expectant:
        return UrgencyTier.BLACK
    if value >= 75:
        return UrgencyTier.RED
    if value >= 50:
        return UrgencyTier.YELLOW
    return UrgencyTier.GREEN


def urgency_score(incident: Incident) -> UrgencyScore:
    """Deterministic urgency scoring with inspectable overrides."""
    life, r1 = _life_threat(incident)
    cas, r2 = _casualty_load(incident)
    haz, r3 = _hazard_risk(incident)
    acc, r4 = _access(incident)
    call, r5 = _caller_state_score(incident)

    raw = 0.40 * life + 0.25 * cas + 0.20 * haz + 0.10 * acc + 0.05 * call
    value = clamp(raw)
    rules = r1 + r2 + r3 + r4 + r5
    overrides: list[str] = []

    # Deterministic safety-oriented overrides (inspectable).
    ambulatory_ok = incident.casualties.ambulatory >= incident.casualties.count_est and incident.casualties.down_count == 0
    if incident.casualties.down_count > 0 and not ambulatory_ok:
        if value < 90:
            overrides.append("OVERRIDE: down_count > 0 and non-ambulatory → minimum score 90")
            value = 90.0

    if incident.hazards.hazmat and value < 85:
        overrides.append("OVERRIDE: HAZMAT → minimum score 85")
        value = 85.0

    if incident.hazards.fire and incident.casualties.count_est >= 3 and value < 80:
        overrides.append("OVERRIDE: fire + multi-casualty → minimum score 80")
        value = 80.0

    black = incident.casualties.deceased_est > 0 and incident.casualties.count_est == incident.casualties.deceased_est
    if black:
        overrides.append("BLACK/expectant classification: all reported deceased")

    tier = classify_tier(value, black_expectant=black)
    protocol_sources: list[str] = []
    if incident.protocol_evidence:
        protocol_sources = [c.citation_id for c in incident.protocol_evidence.citations]

    return UrgencyScore(
        value=round(value, 1),
        tier=tier,
        feature_breakdown=FeatureBreakdown(
            life_threat=round(life, 1),
            casualty_load=round(cas, 1),
            hazard_risk=round(haz, 1),
            access=round(acc, 1),
            caller_state=round(call, 1),
        ),
        rules_triggered=rules,
        protocol_sources=protocol_sources,
        overrides_applied=overrides,
        black_expectant=black,
    )
