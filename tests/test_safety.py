"""Safety validator tests."""
from backend.schemas.incident import (
    FeatureBreakdown,
    Hazards,
    Incident,
    IncidentType,
    LocationInfo,
    ModalityConflict,
    ProtocolEvidence,
    ResourcePlan,
    ResourceUnit,
    UrgencyScore,
    UrgencyTier,
)
from backend.safety.validator import validate_safety


def test_green_cannot_get_highest_priority():
    inc = Incident(
        incident_id="s1",
        incident_type=IncidentType.MEDICAL,
        location=LocationInfo(lat=1, lon=2, address="x"),
        urgency=UrgencyScore(
            value=30,
            tier=UrgencyTier.GREEN,
            feature_breakdown=FeatureBreakdown(),
        ),
        resource_plan=ResourcePlan(
            recommended_units=[
                ResourceUnit(unit_id="HZ-1", unit_type="HAZMAT", eta_minutes=5)
            ]
        ),
        extraction_confidence=0.8,
    )
    result = validate_safety(inc)
    assert result.valid is False
    assert any("GREEN" in v for v in result.violations)


def test_hazmat_requires_warning_and_citations():
    inc = Incident(
        incident_id="s2",
        hazards=Hazards(hazmat=True),
        urgency=UrgencyScore(
            value=90, tier=UrgencyTier.RED, feature_breakdown=FeatureBreakdown()
        ),
        resource_plan=ResourcePlan(hazmat_warning=False, recommended_units=[]),
        protocol_evidence=ProtocolEvidence(insufficient_evidence=True, citations=[]),
        extraction_confidence=0.8,
    )
    result = validate_safety(inc)
    assert result.valid is False
    assert any("HAZMAT" in v for v in result.violations)


def test_low_confidence_requires_review():
    inc = Incident(
        incident_id="s3",
        urgency=UrgencyScore(
            value=50, tier=UrgencyTier.YELLOW, feature_breakdown=FeatureBreakdown()
        ),
        resource_plan=ResourcePlan(
            recommended_units=[ResourceUnit(unit_id="M-1", unit_type="BLS")]
        ),
        extraction_confidence=0.2,
    )
    result = validate_safety(inc)
    assert result.valid is False
    assert any("confidence" in v.lower() for v in result.violations)


def test_conflicts_produce_warnings():
    inc = Incident(
        incident_id="s4",
        urgency=UrgencyScore(
            value=80, tier=UrgencyTier.RED, feature_breakdown=FeatureBreakdown()
        ),
        resource_plan=ResourcePlan(
            recommended_units=[ResourceUnit(unit_id="E-1", unit_type="ENGINE")]
        ),
        extraction_confidence=0.7,
        conflicts=[
            ModalityConflict(
                field="fire_severity",
                audio_says="small",
                vision_says="large",
                resolution="max",
                retained="vision",
            )
        ],
    )
    result = validate_safety(inc)
    assert any(
        "CONFLICT" in w or "Conflict" in w or "conflict" in w.lower()
        for w in result.warnings
    )
