"""Entity fusion + modality conflict detection (safety-oriented max severity)."""
from __future__ import annotations

import re
from typing import Optional

from backend.schemas.incident import (
    AudioEvidence,
    Casualties,
    Hazards,
    Incident,
    IncidentType,
    LocationEvidence,
    LocationInfo,
    ModalityConflict,
    ProvenanceFlag,
    VisualReport,
)
from backend.utils.geo import h3_like_cell, new_id
from backend.utils.logging_utils import get_logger

logger = get_logger(__name__)

FIRE_AUDIO = re.compile(r"\b(fire|flames|burning|smoke)\b", re.I)
SMALL_FIRE = re.compile(r"\b(small|kitchen|stove|minor)\b.*\b(fire|flame)", re.I)
LARGE_FIRE = re.compile(r"\b(structural|building|apartment|house|major|large)\b.*\b(fire|flame)|fire.+(structural|building)", re.I)


def _incident_type_from_scene(scene: str, transcript: str) -> IncidentType:
    mapping = {
        "vehicle_crash": IncidentType.VEHICLE_CRASH,
        "fire": IncidentType.FIRE,
        "flood": IncidentType.FLOOD,
        "structural_collapse": IncidentType.STRUCTURAL_COLLAPSE,
        "assault": IncidentType.ASSAULT,
        "medical": IncidentType.MEDICAL,
        "hazmat": IncidentType.HAZMAT,
    }
    if scene in mapping:
        return mapping[scene]
    t = transcript.lower()
    if "hazmat" in t or "chemical" in t:
        return IncidentType.HAZMAT
    if "flood" in t or "water rising" in t:
        return IncidentType.FLOOD
    if "fire" in t:
        return IncidentType.FIRE
    if "crash" in t or "accident" in t or "collision" in t:
        return IncidentType.VEHICLE_CRASH
    if "chest pain" in t or "cardiac" in t or "not breathing" in t:
        return IncidentType.MEDICAL
    return IncidentType.OTHER


def extract_casualties_from_text(transcript: str) -> Casualties:
    c = Casualties()
    m = re.search(r"\b(\d+)\s+(people|persons|casualties|victims|injured)\b", transcript, re.I)
    if m:
        c.count_est = int(m.group(1))
    if re.search(r"\bunconscious|not moving|down\b", transcript, re.I):
        c.down_count = max(1, c.down_count)
    if re.search(r"\bchild|pediatric|kid\b", transcript, re.I):
        c.pediatric = max(1, c.pediatric)
    if re.search(r"\belderly|senior\b", transcript, re.I):
        c.elderly = max(1, c.elderly)
    if c.count_est == 0 and re.search(r"\binjured|hurt|bleeding\b", transcript, re.I):
        c.count_est = 1
    c.ambulatory = max(0, c.count_est - c.down_count)
    return c


def fuse_entities(
    audio: Optional[AudioEvidence],
    vision: Optional[VisualReport],
    location: Optional[LocationEvidence],
    incident_id: Optional[str] = None,
) -> Incident:
    transcript = audio.transcript if audio else ""
    conflicts: list[ModalityConflict] = []
    provenance: dict[str, ProvenanceFlag] = {}

    # --- Fire conflict handling (key research feature) ---
    audio_fire = bool(audio and FIRE_AUDIO.search(transcript))
    vision_fire = bool(vision and (vision.fire_visible or vision.smoke_present))
    audio_small = bool(audio and SMALL_FIRE.search(transcript))
    vision_major = bool(vision and vision.fire_visible and vision.structural_damage)

    fire = audio_fire or vision_fire
    fire_sources = []
    if audio_fire:
        fire_sources.append("audio")
    if vision_fire:
        fire_sources.append("vision")
    provenance["fire"] = ProvenanceFlag(value=fire, sources=fire_sources)

    if audio_small and vision_major:
        conflicts.append(
            ModalityConflict(
                field="fire_severity",
                audio_says="Small kitchen / minor fire implied by transcript",
                vision_says="Major structural fire indicators (fire + structural damage)",
                resolution="Higher-severity observation retained for safety-oriented scoring",
                retained="vision:major_structural_fire",
                confidence=0.7,
            )
        )

    hazmat = bool(
        (vision and vision.hazmat_placard)
        or (audio and re.search(r"\bhazmat|chemical|toxic|placard\b", transcript, re.I))
    )
    provenance["hazmat"] = ProvenanceFlag(
        value=hazmat,
        sources=[s for s, cond in [("vision", vision and vision.hazmat_placard), ("audio", audio and "hazmat" in transcript.lower())] if cond],
    )

    structural = bool(vision and vision.structural_damage)
    water = bool(vision and vision.water_rising) or bool(audio and re.search(r"\bflood|rising water\b", transcript, re.I))
    fuel = bool(vision and vision.fuel_leak_visible) or bool(audio and re.search(r"\bfuel|gas leak|smell gas\b", transcript, re.I))
    smoke = bool(vision and vision.smoke_present) or bool(audio and re.search(r"\bsmoke\b", transcript, re.I))

    hazards = Hazards(
        fire=fire if not (audio_small and vision_major) else True,
        hazmat=hazmat,
        structural=structural or vision_major,
        electrical=bool(audio and re.search(r"\belectric|wires|power.?line\b", transcript, re.I)),
        water=water,
        fuel_leak=fuel,
        smoke=smoke,
    )

    # Casualties: take max of modalities (safety-oriented).
    text_cas = extract_casualties_from_text(transcript)
    vis_down = vision.persons_down if vision else 0
    vis_count = vision.persons_visible if vision else 0
    casualties = Casualties(
        count_est=max(text_cas.count_est, vis_count),
        down_count=max(text_cas.down_count, vis_down),
        pediatric=text_cas.pediatric,
        elderly=text_cas.elderly,
        ambulatory=0,
        deceased_est=text_cas.deceased_est,
    )
    casualties.ambulatory = max(0, casualties.count_est - casualties.down_count)

    if text_cas.down_count != vis_down and vision and audio:
        conflicts.append(
            ModalityConflict(
                field="persons_down",
                audio_says=f"Transcript suggests down_count≈{text_cas.down_count}",
                vision_says=f"Vision persons_down={vis_down}",
                resolution="Maximum down_count retained",
                retained=str(casualties.down_count),
                confidence=0.65,
            )
        )

    loc = location.location if location else LocationInfo()
    if loc.h3_cell is None:
        loc.h3_cell = h3_like_cell(loc.lat, loc.lon)

    scene = vision.scene_type.value if vision and hasattr(vision.scene_type, "value") else (vision.scene_type if vision else "other")
    itype = _incident_type_from_scene(str(scene), transcript)

    narrative_bits = []
    if transcript:
        narrative_bits.append(transcript[:240])
    if vision and vision.notes:
        narrative_bits.append(vision.notes[:160])
    narrative = " | ".join(narrative_bits) or "No narrative available."

    confidences = []
    if audio:
        confidences.append(audio.confidence)
    if vision:
        confidences.append(vision.model_confidence)
    if location:
        confidences.append(location.confidence)
    if conflicts:
        # Conflicts reduce confidence.
        avg_conf = (sum(confidences) / len(confidences) if confidences else 0.6) * 0.85
    else:
        avg_conf = sum(confidences) / len(confidences) if confidences else 0.6

    modalities = []
    if audio:
        modalities.append("audio")
    if vision:
        modalities.append("vision")
    if location:
        modalities.append("location")

    from backend.schemas.incident import CallerState

    caller = CallerState(
        conscious=not bool(re.search(r"\bunconscious|passed out\b", transcript, re.I)),
        panic_index=audio.panic_index if audio else 0.3,
        language=audio.language if audio else "en",
        on_scene=True,
    )

    return Incident(
        incident_id=incident_id or new_id("inc"),
        modality_sources=modalities,
        incident_type=itype,
        location=loc,
        casualties=casualties,
        hazards=hazards,
        hazard_provenance=provenance,
        caller_state=caller,
        narrative_summary=narrative,
        extraction_confidence=round(avg_conf, 3),
        conflicts=conflicts,
        audio_evidence=audio,
        visual_evidence=vision,
        location_evidence=location,
    )
