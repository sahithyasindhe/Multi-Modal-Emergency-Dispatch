"""Mock facilities, units, ETA — never contacts real emergency services."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from backend.config import get_settings
from backend.schemas.incident import ResourceUnit
from backend.utils.geo import haversine_m

DEFAULT_FACILITIES = [
    {"id": "fac_sf_gen", "name": "Metro General Hospital (DEMO)", "lat": 37.7562, "lon": -122.4058, "type": "hospital"},
    {"id": "fac_sf_trauma", "name": "Bay Trauma Center (DEMO)", "lat": 37.7825, "lon": -122.3928, "type": "trauma"},
    {"id": "fac_sf_fire1", "name": "Station 1 Fire/EMS (DEMO)", "lat": 37.7799, "lon": -122.4148, "type": "fire_station"},
    {"id": "fac_sf_hazmat", "name": "Regional HAZMAT Cache (DEMO)", "lat": 37.7300, "lon": -122.3900, "type": "hazmat"},
]

DEFAULT_UNITS = [
    {"unit_id": "M-12", "unit_type": "BLS", "status": "available", "capability": ["bls"], "lat": 37.77, "lon": -122.42},
    {"unit_id": "M-7", "unit_type": "ALS", "status": "available", "capability": ["als", "cardiac"], "lat": 37.78, "lon": -122.41},
    {"unit_id": "E-3", "unit_type": "ENGINE", "status": "available", "capability": ["fire", "rescue"], "lat": 37.775, "lon": -122.418},
    {"unit_id": "L-1", "unit_type": "LADDER", "status": "available", "capability": ["fire", "structure"], "lat": 37.77, "lon": -122.41},
    {"unit_id": "HZ-1", "unit_type": "HAZMAT", "status": "available", "capability": ["hazmat"], "lat": 37.73, "lon": -122.39},
    {"unit_id": "R-2", "unit_type": "RESCUE", "status": "busy", "capability": ["rescue", "extrication"], "lat": 37.76, "lon": -122.43},
    {"unit_id": "SQ-5", "unit_type": "ENGINE_STRIKE", "status": "available", "capability": ["fire", "mci"], "lat": 37.765, "lon": -122.40},
]


def load_facilities() -> list[dict[str, Any]]:
    path = get_settings().root_dir / "data" / "facilities" / "facilities.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return DEFAULT_FACILITIES


def load_units() -> list[dict[str, Any]]:
    path = get_settings().root_dir / "data" / "facilities" / "units.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return DEFAULT_UNITS


def check_unit_availability(unit_types: list[str] | None = None) -> list[ResourceUnit]:
    units = load_units()
    out = []
    for u in units:
        if u.get("status") != "available":
            continue
        if unit_types and u["unit_type"] not in unit_types:
            continue
        out.append(
            ResourceUnit(
                unit_id=u["unit_id"],
                unit_type=u["unit_type"],
                status=u["status"],
                eta_minutes=0.0,
                capability=u.get("capability", []),
            )
        )
    return out


def nearest_facility(lat: float, lon: float, facility_type: str | None = None) -> dict[str, Any]:
    facilities = load_facilities()
    best = None
    best_d = float("inf")
    for f in facilities:
        if facility_type and f.get("type") != facility_type:
            continue
        d = haversine_m(lat, lon, f["lat"], f["lon"])
        if d < best_d:
            best_d = d
            best = {**f, "distance_m": d}
    if best is None:
        # Fall back to any nearest.
        return nearest_facility(lat, lon, None) if facility_type else {
            "id": "fac_unknown",
            "name": "Unknown DEMO facility",
            "distance_m": 9999,
            "lat": lat,
            "lon": lon,
            "type": "unknown",
        }
    return best


def eta_compute(distance_m: float, traffic_factor: float = 1.2) -> float:
    # Assume average 35 km/h urban response for demo.
    hours = (distance_m / 1000.0) / 35.0
    return round(hours * 60.0 * traffic_factor, 1)


def trigger_hazmat_warning(incident_id: str) -> dict[str, Any]:
    return {
        "incident_id": incident_id,
        "warning": "DEMO HAZMAT WARNING — isolate area, upwind staging, request hazmat team. Not a real alert.",
        "sent": False,
        "demo": True,
    }


def send_sms_triage(phone: str, message: str) -> dict[str, Any]:
    # NEVER actually send SMS in this prototype.
    return {
        "sent": False,
        "demo": True,
        "to": "[REDACTED]",
        "message_preview": message[:120],
        "note": "SMS suppressed — research prototype only.",
    }
