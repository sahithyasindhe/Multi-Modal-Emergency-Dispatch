"""Deterministic triage scoring tests."""
from backend.schemas.incident import (
    CallerState,
    Casualties,
    Hazards,
    Incident,
    IncidentType,
    LocationInfo,
)
from backend.triage.engine import classify_tier, urgency_score


def _base(**kwargs) -> Incident:
    data = dict(
        incident_id="t1",
        incident_type=IncidentType.OTHER,
        location=LocationInfo(lat=37.77, lon=-122.42, address="x", distance_m=500),
        casualties=Casualties(),
        hazards=Hazards(),
        caller_state=CallerState(panic_index=0.2, on_scene=True, conscious=True),
    )
    data.update(kwargs)
    return Incident(**data)


def test_green_low_severity():
    inc = _base(casualties=Casualties(count_est=1, ambulatory=1))
    score = urgency_score(inc)
    assert score.tier.value in {"GREEN", "YELLOW"}
    assert 0 <= score.value <= 100


def test_red_fire_and_down():
    inc = _base(
        incident_type=IncidentType.FIRE,
        hazards=Hazards(fire=True, structural=True),
        casualties=Casualties(count_est=3, down_count=1, ambulatory=2),
        caller_state=CallerState(panic_index=0.8, conscious=True, on_scene=True),
    )
    score = urgency_score(inc)
    assert score.value >= 75
    assert score.tier.value == "RED"


def test_override_non_ambulatory_min_90():
    inc = _base(
        casualties=Casualties(count_est=2, down_count=2, ambulatory=0),
        hazards=Hazards(),
    )
    score = urgency_score(inc)
    assert score.value >= 90
    assert any("90" in o for o in score.overrides_applied)


def test_override_hazmat_min_85():
    inc = _base(hazards=Hazards(hazmat=True), casualties=Casualties(count_est=0))
    score = urgency_score(inc)
    assert score.value >= 85
    assert any("HAZMAT" in o for o in score.overrides_applied)


def test_classify_tiers():
    assert classify_tier(80).value == "RED"
    assert classify_tier(60).value == "YELLOW"
    assert classify_tier(30).value == "GREEN"
    assert classify_tier(10, black_expectant=True).value == "BLACK"


def test_feature_breakdown_present():
    inc = _base(
        hazards=Hazards(fire=True),
        casualties=Casualties(count_est=2, down_count=1),
    )
    score = urgency_score(inc)
    assert score.feature_breakdown.life_threat > 0
    assert len(score.rules_triggered) > 0
