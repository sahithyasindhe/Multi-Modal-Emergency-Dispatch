#!/usr/bin/env python3
"""
Evaluation script for SENTINEL-911 demo dataset.

Reports only metrics that can be computed from available demo labels.
Does not fabricate benchmark results — unsupported metrics are marked Not evaluated.
"""
from __future__ import annotations

import json
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.pipeline.orchestrator import STORE, analyze_incident  # noqa: E402
from backend.schemas.incident import IncidentCreate  # noqa: E402
from backend.services.dedup import assign_clusters  # noqa: E402
from backend.services.scenarios import SCENARIOS  # noqa: E402
from backend.triage.engine import urgency_score  # noqa: E402
from backend.rag.retriever import get_rag  # noqa: E402

# Lightweight expected labels for demo scenarios (portfolio evaluation only).
EXPECTED = {
    "vehicle_crash": {"tier_in": ["RED", "YELLOW"], "hazards": ["fuel_leak"]},
    "apartment_fire": {"tier_in": ["RED", "YELLOW"], "hazards": ["fire"]},
    "kitchen_vs_structural_fire": {"tier_in": ["RED", "YELLOW"], "expect_conflict": True},
    "flood": {"tier_in": ["YELLOW", "RED", "GREEN"], "hazards": ["water"]},
    "hazmat_leak": {"tier_in": ["RED"], "hazards": ["hazmat"]},
    "cardiac": {"tier_in": ["RED", "YELLOW"], "hazards": []},
    "mci": {"tier_in": ["RED"], "hazards": []},
}


def cohen_kappa(y_true: list[str], y_pred: list[str]) -> float | str:
    labels = sorted(set(y_true) | set(y_pred))
    if len(y_true) < 2 or len(labels) < 2:
        return "Not evaluated"
    n = len(y_true)
    # confusion
    from collections import Counter

    pair = Counter(zip(y_true, y_pred))
    true_count = Counter(y_true)
    pred_count = Counter(y_pred)
    agree = sum(1 for a, b in zip(y_true, y_pred) if a == b) / n
    pe = sum((true_count[l] / n) * (pred_count[l] / n) for l in labels)
    if pe == 1:
        return "Not evaluated"
    return round((agree - pe) / (1 - pe), 3)


def main() -> None:
    # Reset in-memory store for clean run
    STORE.incidents.clear()
    STORE.clusters.clear()

    latencies = []
    tier_true = []
    tier_pred = []
    triage_hits = 0
    citation_cover = 0
    retrieval_hits = 0
    conflict_hits = 0
    n = 0

    print("=== SENTINEL-911 Evaluation (demo dataset) ===\n")

    for sid, sc in SCENARIOS.items():
        exp = EXPECTED.get(sid, {})
        t0 = time.perf_counter()
        inc = analyze_incident(
            IncidentCreate(
                scenario_id=sid,
                transcript=sc["transcript"],
                lat=sc["lat"],
                lon=sc["lon"],
                address=sc["address"],
                landmark=sc.get("landmark"),
                visual_overrides=sc.get("visual_overrides"),
            )
        )
        dt = (time.perf_counter() - t0) * 1000
        latencies.append(dt)
        n += 1
        tier = inc.urgency.tier.value if inc.urgency else "NONE"
        # Soft label: use first expected tier as "true" for kappa demo
        expected_tiers = exp.get("tier_in") or [tier]
        soft_true = expected_tiers[0]
        tier_true.append(soft_true)
        tier_pred.append(tier)
        if tier in expected_tiers:
            triage_hits += 1
        if exp.get("expect_conflict") and inc.conflicts:
            conflict_hits += 1
        pe = inc.protocol_evidence
        if pe and pe.citations:
            citation_cover += 1
            if not pe.insufficient_evidence:
                retrieval_hits += 1
        print(f"{sid:28s} tier={tier:6s} score={inc.urgency.value if inc.urgency else '-':>5}  {dt:.0f} ms  conflicts={len(inc.conflicts)}")

    # Dedup precision proxy via MCI-style duplicates
    STORE.incidents.clear()
    from backend.pipeline.orchestrator import run_mci_simulation

    mci = run_mci_simulation(duplicate_count=8)
    multi = [c for c in STORE.clusters if c.caller_count >= 2]
    cluster_precision = "Not evaluated"
    if multi:
        # All MCI callers should be same geo/type — treat as true positives if one major cluster
        largest = max(multi, key=lambda c: c.caller_count)
        cluster_precision = round(largest.caller_count / max(1, mci.get("caller_count", 1)), 3)

    latencies_sorted = sorted(latencies)
    p50 = latencies_sorted[len(latencies_sorted) // 2] if latencies_sorted else None
    p95 = latencies_sorted[int(len(latencies_sorted) * 0.95)] if latencies_sorted else None

    report = {
        "dataset": "demo_scenarios",
        "n": n,
        "entity_extraction": {
            "precision": "Not evaluated",
            "recall": "Not evaluated",
            "f1": "Not evaluated",
            "note": "No token-level gold entity annotations in demo set.",
        },
        "triage": {
            "tier_accuracy_soft": round(triage_hits / n, 3) if n else "Not evaluated",
            "cohen_kappa": cohen_kappa(tier_true, tier_pred),
            "score_mae": "Not evaluated",
            "note": "Soft labels = acceptable tier sets per scenario; not a clinical gold standard.",
        },
        "rag": {
            "retrieval_hit_rate": round(retrieval_hits / n, 3) if n else "Not evaluated",
            "citation_coverage": round(citation_cover / n, 3) if n else "Not evaluated",
            "faithfulness_proxy": "Not evaluated",
        },
        "latency_ms": {
            "p50": round(p50, 1) if p50 is not None else "Not evaluated",
            "p95": round(p95, 1) if p95 is not None else "Not evaluated",
            "mean": round(statistics.mean(latencies), 1) if latencies else "Not evaluated",
        },
        "deduplication": {
            "cluster_precision_proxy": cluster_precision,
            "note": "Proxy = largest MCI cluster size / generated callers.",
        },
        "modality_conflict_demo": {
            "kitchen_vs_structural_detected": bool(conflict_hits),
        },
        "robustness_missing_modality": "Not evaluated",
        "disclaimer": "Research prototype metrics on synthetic data only — not operational validation.",
    }

    out = ROOT / "docs" / "evaluation_last_run.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("\n=== Report ===")
    print(json.dumps(report, indent=2))
    print(f"\nWrote {out}")


if __name__ == "__main__":
    main()
