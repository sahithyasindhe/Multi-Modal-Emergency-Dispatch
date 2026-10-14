"""Shared geospatial and text utilities."""
from __future__ import annotations

import hashlib
import math
import re
import uuid
from typing import Iterable


def new_id(prefix: str = "inc") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in meters."""
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def h3_like_cell(lat: float, lon: float, resolution: int = 8) -> str:
    """
    Lightweight H3-like grid cell when h3 is unavailable.
    Resolution ~8 ≈ ~0.5km cells for demo clustering.
    """
    try:
        import h3  # type: ignore

        return h3.latlng_to_cell(lat, lon, resolution)
    except Exception:
        scale = 10 ** max(1, resolution - 5)
        return f"cell_{int(lat * scale)}_{int(lon * scale)}_r{resolution}"


def tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def jaccard_similarity(a: str, b: str) -> float:
    ta, tb = set(tokenize(a)), set(tokenize(b))
    if not ta and not tb:
        return 1.0
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def cosine_bag_similarity(a: str, b: str) -> float:
    """Simple TF cosine on token bags (no external model required)."""
    ta, tb = tokenize(a), tokenize(b)
    if not ta or not tb:
        return 0.0
    from collections import Counter

    ca, cb = Counter(ta), Counter(tb)
    keys = set(ca) | set(cb)
    dot = sum(ca[k] * cb[k] for k in keys)
    na = math.sqrt(sum(v * v for v in ca.values()))
    nb = math.sqrt(sum(v * v for v in cb.values()))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def narrative_similarity(a: str, b: str) -> float:
    return 0.4 * jaccard_similarity(a, b) + 0.6 * cosine_bag_similarity(a, b)


def clamp(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, x))


def stable_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def mean(values: Iterable[float], default: float = 0.0) -> float:
    vals = list(values)
    return sum(vals) / len(vals) if vals else default
