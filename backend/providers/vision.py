"""Vision providers — YOLO/VLM when available, deterministic demo otherwise."""
from __future__ import annotations

import base64
import io
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Optional

from backend.config import get_settings
from backend.schemas.incident import SceneType, VisualReport
from backend.utils.logging_utils import get_logger

logger = get_logger(__name__)


class VisionProvider(ABC):
    name: str = "base"

    @abstractmethod
    def analyze(
        self,
        image_path: Optional[str] = None,
        image_b64: Optional[str] = None,
        overrides: Optional[dict[str, Any]] = None,
        scenario_hint: Optional[str] = None,
    ) -> VisualReport:
        raise NotImplementedError


SCENARIO_VISUALS: dict[str, dict[str, Any]] = {
    "vehicle_crash": {
        "scene_type": SceneType.VEHICLE_CRASH,
        "persons_visible": 3,
        "persons_down": 1,
        "vehicles_visible": 2,
        "fire_visible": False,
        "smoke_present": False,
        "fuel_leak_visible": True,
        "structural_damage": False,
        "notes": "Two vehicles collided; one person appears non-ambulatory.",
    },
    "apartment_fire": {
        "scene_type": SceneType.FIRE,
        "persons_visible": 4,
        "persons_down": 0,
        "vehicles_visible": 0,
        "fire_visible": True,
        "smoke_present": True,
        "structural_damage": True,
        "notes": "Visible flames and heavy smoke from multi-story structure.",
    },
    "flood": {
        "scene_type": SceneType.FLOOD,
        "persons_visible": 5,
        "persons_down": 0,
        "water_rising": True,
        "notes": "Street flooding with water approaching doorways.",
    },
    "hazmat_leak": {
        "scene_type": SceneType.HAZMAT,
        "persons_visible": 2,
        "persons_down": 0,
        "vehicles_visible": 1,
        "hazmat_placard": True,
        "smoke_present": True,
        "notes": "Tanker with placard; vapor cloud near vehicle.",
    },
    "cardiac": {
        "scene_type": SceneType.MEDICAL,
        "persons_visible": 2,
        "persons_down": 1,
        "notes": "Adult down; bystander performing CPR.",
    },
    "mci": {
        "scene_type": SceneType.VEHICLE_CRASH,
        "persons_visible": 12,
        "persons_down": 4,
        "vehicles_visible": 4,
        "fuel_leak_visible": True,
        "structural_damage": False,
        "notes": "Multi-vehicle mass casualty scene.",
    },
}


class DemoVisionProvider(VisionProvider):
    name = "demo"

    def analyze(
        self,
        image_path: Optional[str] = None,
        image_b64: Optional[str] = None,
        overrides: Optional[dict[str, Any]] = None,
        scenario_hint: Optional[str] = None,
    ) -> VisualReport:
        base = SCENARIO_VISUALS.get(scenario_hint or "vehicle_crash", SCENARIO_VISUALS["vehicle_crash"]).copy()
        report = VisualReport(
            scene_type=base.get("scene_type", SceneType.OTHER),
            persons_visible=int(base.get("persons_visible", 0)),
            persons_down=int(base.get("persons_down", 0)),
            vehicles_visible=int(base.get("vehicles_visible", 0)),
            fire_visible=bool(base.get("fire_visible", False)),
            smoke_present=bool(base.get("smoke_present", False)),
            water_rising=bool(base.get("water_rising", False)),
            hazmat_placard=bool(base.get("hazmat_placard", False)),
            structural_damage=bool(base.get("structural_damage", False)),
            fuel_leak_visible=bool(base.get("fuel_leak_visible", False)),
            image_quality="demo_synthetic",
            model_confidence=0.72,
            detections=[],
            provider=self.name,
            notes=str(base.get("notes", "")),
        )
        if overrides:
            data = report.model_dump()
            data.update(overrides)
            report = VisualReport.model_validate(data)
        if image_path or image_b64:
            report.image_quality = "user_provided_unanalyzed_demo"
            report.notes += " | Image received; demo analyzer used (no GPU/YOLO)."
        return report


class YOLOVisionProvider(VisionProvider):
    name = "yolov8"

    def __init__(self) -> None:
        self._model = None
        try:
            from ultralytics import YOLO

            self._model = YOLO("yolov8n.pt")
            logger.info("YOLOv8n loaded")
        except Exception as exc:
            logger.warning("YOLO unavailable: %s", exc)
            self._model = None

    @property
    def available(self) -> bool:
        return self._model is not None

    def analyze(
        self,
        image_path: Optional[str] = None,
        image_b64: Optional[str] = None,
        overrides: Optional[dict[str, Any]] = None,
        scenario_hint: Optional[str] = None,
    ) -> VisualReport:
        if self._model is None:
            return DemoVisionProvider().analyze(image_path, image_b64, overrides, scenario_hint)

        path = image_path
        tmp = None
        if image_b64 and not path:
            from PIL import Image

            raw = base64.b64decode(image_b64.split(",")[-1])
            img = Image.open(io.BytesIO(raw)).convert("RGB")
            tmp = Path("data/images/_tmp_upload.jpg")
            tmp.parent.mkdir(parents=True, exist_ok=True)
            img.save(tmp)
            path = str(tmp)

        if not path:
            return DemoVisionProvider().analyze(None, None, overrides, scenario_hint)

        results = self._model(path, verbose=False)
        persons = 0
        vehicles = 0
        detections = []
        for r in results:
            names = r.names
            for box in r.boxes:
                cls_id = int(box.cls[0])
                label = names.get(cls_id, str(cls_id))
                conf = float(box.conf[0])
                detections.append({"label": label, "confidence": conf})
                if label == "person":
                    persons += 1
                if label in {"car", "truck", "bus", "motorcycle"}:
                    vehicles += 1

        demo = DemoVisionProvider().analyze(path, None, overrides, scenario_hint)
        return VisualReport(
            scene_type=demo.scene_type,
            persons_visible=max(persons, demo.persons_visible if scenario_hint else persons),
            persons_down=demo.persons_down,
            vehicles_visible=max(vehicles, demo.vehicles_visible if scenario_hint else vehicles),
            fire_visible=demo.fire_visible,
            smoke_present=demo.smoke_present,
            water_rising=demo.water_rising,
            hazmat_placard=demo.hazmat_placard,
            structural_damage=demo.structural_damage,
            fuel_leak_visible=demo.fuel_leak_visible,
            image_quality="yolo_analyzed",
            model_confidence=0.8,
            detections=detections,
            provider=self.name,
            notes=demo.notes + " | YOLO object counts applied.",
        )


class VLMVisionProvider(VisionProvider):
    """Optional OpenAI-compatible VLM; always returns validated VisualReport."""

    name = "vlm"

    def analyze(
        self,
        image_path: Optional[str] = None,
        image_b64: Optional[str] = None,
        overrides: Optional[dict[str, Any]] = None,
        scenario_hint: Optional[str] = None,
    ) -> VisualReport:
        settings = get_settings()
        if not settings.openai_api_key:
            return DemoVisionProvider().analyze(image_path, image_b64, overrides, scenario_hint)
        # For MVP portfolio: validate structure via demo + optional override notes.
        # Full VLM HTTP call can be enabled later without changing call sites.
        report = DemoVisionProvider().analyze(image_path, image_b64, overrides, scenario_hint)
        report.provider = self.name
        report.notes += " | VLM path stubbed to validated schema (API key present)."
        return VisualReport.model_validate(report.model_dump())


def get_vision_provider() -> VisionProvider:
    settings = get_settings()
    if settings.model_mode == "demo":
        return DemoVisionProvider()
    yolo = YOLOVisionProvider()
    if yolo.available:
        return yolo
    if settings.openai_api_key:
        return VLMVisionProvider()
    return DemoVisionProvider()
