"""Modality conflict / fusion tests."""
from backend.pipeline.fusion import fuse_entities
from backend.schemas.incident import (
    AudioEvidence,
    LocationEvidence,
    LocationInfo,
    SceneType,
    VisualReport,
)


def test_fire_severity_conflict_retained_max():
    audio = AudioEvidence(
        transcript="There's a small kitchen fire in my apartment. Smoke but under control.",
        panic_index=0.4,
        confidence=0.8,
    )
    vision = VisualReport(
        scene_type=SceneType.FIRE,
        fire_visible=True,
        smoke_present=True,
        structural_damage=True,
        persons_visible=3,
        model_confidence=0.8,
        notes="Major structural fire",
    )
    loc = LocationEvidence(location=LocationInfo(lat=37.77, lon=-122.42, address="Demo"))
    inc = fuse_entities(audio, vision, loc)
    assert any(c.field == "fire_severity" for c in inc.conflicts)
    assert inc.hazards.fire is True
    assert inc.hazards.structural is True
    assert "fire" in inc.hazard_provenance
    assert set(inc.hazard_provenance["fire"].sources) >= {"audio", "vision"}


def test_max_down_count_across_modalities():
    audio = AudioEvidence(
        transcript="One person is unconscious on the ground.",
        panic_index=0.5,
    )
    vision = VisualReport(
        scene_type=SceneType.VEHICLE_CRASH,
        persons_visible=4,
        persons_down=2,
    )
    loc = LocationEvidence(location=LocationInfo(lat=1, lon=2, address="x"))
    inc = fuse_entities(audio, vision, loc)
    assert inc.casualties.down_count >= 2
