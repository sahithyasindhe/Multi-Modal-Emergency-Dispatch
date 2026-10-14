"""Demo emergency scenarios for live simulation mode."""
from __future__ import annotations

from typing import Any

SCENARIOS: dict[str, dict[str, Any]] = {
    "vehicle_crash": {
        "id": "vehicle_crash",
        "title": "Vehicle Crash — Fuel Leak",
        "transcript": (
            "There's been a bad car accident on Market Street near 5th! "
            "Three people are hurt, one isn't moving and looks unconscious. "
            "I smell gas leaking from one of the cars. Please hurry!!!"
        ),
        "lat": 37.7820,
        "lon": -122.4070,
        "address": "Market St & 5th St (DEMO)",
        "landmark": "Near Union Square",
        "scenario_hint": "vehicle_crash",
        "visual_overrides": None,
    },
    "apartment_fire": {
        "id": "apartment_fire",
        "title": "Apartment Fire — Possible Trapped",
        "transcript": (
            "Our apartment building is on fire! Heavy smoke on the third floor. "
            "I think someone is trapped upstairs. People are screaming and coming out. "
            "This is a big structural fire, not a small kitchen fire!"
        ),
        "lat": 37.7695,
        "lon": -122.4210,
        "address": "450 Hayes St (DEMO)",
        "landmark": "Hayes Valley apartments",
        "scenario_hint": "apartment_fire",
        # Intentional conflict: audio may say kitchen in some variants; vision structural.
        "visual_overrides": {
            "fire_visible": True,
            "smoke_present": True,
            "structural_damage": True,
            "persons_visible": 6,
            "persons_down": 1,
        },
    },
    "kitchen_vs_structural_fire": {
        "id": "kitchen_vs_structural_fire",
        "title": "Modality Conflict Demo — Kitchen vs Structural Fire",
        "transcript": (
            "There's a small kitchen fire in my apartment. We used the extinguisher. "
            "Some smoke but I think it's under control."
        ),
        "lat": 37.7710,
        "lon": -122.4190,
        "address": "200 Fell St (DEMO)",
        "landmark": "Residential block",
        "scenario_hint": "apartment_fire",
        "visual_overrides": {
            "scene_type": "fire",
            "fire_visible": True,
            "smoke_present": True,
            "structural_damage": True,
            "persons_visible": 4,
            "persons_down": 0,
            "notes": "Vision: large structural fire with facade involvement.",
        },
    },
    "flood": {
        "id": "flood",
        "title": "Urban Flood — Rising Water",
        "transcript": (
            "The water is rising fast on Embarcadero! Cars are stuck. "
            "Several people are stranded. Flooding is getting into buildings."
        ),
        "lat": 37.7955,
        "lon": -122.3937,
        "address": "Embarcadero & Folsom (DEMO)",
        "landmark": "Waterfront",
        "scenario_hint": "flood",
        "visual_overrides": None,
    },
    "hazmat_leak": {
        "id": "hazmat_leak",
        "title": "HAZMAT Truck Leak",
        "transcript": (
            "A tanker truck overturned on the freeway. There's a chemical smell and a cloud. "
            "I can see a hazmat placard on the side. People are coughing nearby."
        ),
        "lat": 37.7312,
        "lon": -122.3925,
        "address": "US-101 near Cesar Chavez (DEMO)",
        "landmark": "Freeway shoulder",
        "scenario_hint": "hazmat_leak",
        "visual_overrides": None,
    },
    "cardiac": {
        "id": "cardiac",
        "title": "Cardiac Emergency",
        "transcript": (
            "My father collapsed. He has chest pain and is barely conscious. "
            "He's 68. We need an ambulance right now."
        ),
        "lat": 37.7599,
        "lon": -122.4148,
        "address": "Mission District residence (DEMO)",
        "landmark": "Residential",
        "scenario_hint": "cardiac",
        "visual_overrides": {
            "persons_visible": 2,
            "persons_down": 1,
            "scene_type": "medical",
        },
    },
    "mci": {
        "id": "mci",
        "title": "Mass-Casualty Multi-Caller Event",
        "transcript": (
            "Multi-car pileup on the bridge approach! At least ten people injured, "
            "several not moving. Fuel is leaking. This is a mass casualty incident!"
        ),
        "lat": 37.8080,
        "lon": -122.4750,
        "address": "Golden Gate approach (DEMO)",
        "landmark": "Bridge approach",
        "scenario_hint": "mci",
        "visual_overrides": None,
    },
}


MCI_CALLER_VARIANTS = [
    "Big crash on the bridge! Lots of people hurt!",
    "I see multiple cars smashed. People are down on the roadway.",
    "Mass casualty accident near the bridge approach. Fuel smell.",
    "Please send everyone — pileup with many injured.",
    "I'm looking at a multi-vehicle collision. Several not moving.",
    "There's been a terrible accident. At least 10 casualties.",
    "Bridge approach crash. Smoke or steam from a vehicle.",
    "Calling about the same pileup — need ambulances and fire.",
    "People are screaming. Multiple victims on the ground.",
    "Duplicate report: major MVC with fuel leakage and unconscious victims.",
    "Still seeing the crash. Traffic stopped. Many injured.",
]


def list_scenarios() -> list[dict[str, str]]:
    return [{"id": s["id"], "title": s["title"]} for s in SCENARIOS.values()]


def get_scenario(scenario_id: str | None) -> dict[str, Any]:
    if scenario_id and scenario_id in SCENARIOS:
        return SCENARIOS[scenario_id]
    # default
    return SCENARIOS["vehicle_crash"]
