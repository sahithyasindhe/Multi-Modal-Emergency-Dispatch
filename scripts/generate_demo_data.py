#!/usr/bin/env python3
"""Generate demo incident JSON and seed facilities if needed."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.services.scenarios import SCENARIOS  # noqa: E402


def main() -> None:
    out = ROOT / "data" / "demo_incidents"
    out.mkdir(parents=True, exist_ok=True)
    for sid, sc in SCENARIOS.items():
        path = out / f"{sid}.json"
        path.write_text(json.dumps(sc, indent=2), encoding="utf-8")
        print(f"Wrote {path}")
    print("Demo data ready.")
    print("Next: uvicorn backend.main:app --reload")
    print("Then: streamlit run frontend/app.py")


if __name__ == "__main__":
    main()
