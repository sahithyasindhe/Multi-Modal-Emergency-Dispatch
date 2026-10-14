"""Incident schema validation tests."""
from backend.schemas.incident import (
    Casualties,
    FeatureBreakdown,
    Hazards,
    Incident,
    IncidentType,
    LocationInfo,
    UrgencyScore,
    UrgencyTier,
)


def test_incident_schema_minimal():
    inc = Incident(incident_id="inc_test01")
    assert inc.incident_id == "inc_test01"
    assert inc.incident_type == IncidentType.OTHER
    assert 0 <= inc.extraction_confidence <= 1


def test_incident_schema_full_roundtrip():
    inc = Incident(
        incident_id="inc_full",
        incident_type=IncidentType.FIRE,
        location=LocationInfo(lat=37.7, lon=-122.4, address="Demo St"),
        casualties=Casualties(count_est=3, down_count=1, ambulatory=2),
        hazards=Hazards(fire=True, smoke=True),
        narrative_summary="Demo fire",
        urgency=UrgencyScore(
            value=88,
            tier=UrgencyTier.RED,
            feature_breakdown=FeatureBreakdown(life_threat=80),
            rules_triggered=["Fire present"],
        ),
    )
    data = inc.model_dump()
    restored = Incident.model_validate(data)
    assert restored.urgency.tier == UrgencyTier.RED
    assert restored.hazards.fire is True
