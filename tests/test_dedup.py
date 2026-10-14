"""Deduplication / clustering tests."""
from datetime import datetime, timedelta, timezone

from backend.schemas.incident import Incident, IncidentType, LocationInfo
from backend.services.dedup import assign_clusters, duplicate_likelihood, find_cluster_match


def _inc(iid, lat, lon, narrative, minutes_ago=0, itype=IncidentType.VEHICLE_CRASH):
    return Incident(
        incident_id=iid,
        timestamp=datetime.now(timezone.utc) - timedelta(minutes=minutes_ago),
        incident_type=itype,
        location=LocationInfo(lat=lat, lon=lon, address="demo"),
        narrative_summary=narrative,
    )


def test_find_cluster_match_nearby_similar():
    a = _inc(
        "a",
        37.8080,
        -122.4750,
        "Multi-car pileup on bridge approach many injured fuel leak casualties",
    )
    b = _inc(
        "b",
        37.8081,
        -122.4751,
        "Multi-car pileup on bridge approach many injured fuel leak casualties reported",
    )
    match = find_cluster_match(b, [a])
    assert match is not None
    assert match.incident_id == "a"


def test_no_match_far_away():
    a = _inc("a", 37.8080, -122.4750, "Crash with injuries")
    b = _inc("b", 34.05, -118.25, "Crash with injuries")
    assert find_cluster_match(b, [a]) is None


def test_assign_clusters_groups():
    items = [
        _inc("a", 37.8080, -122.4750, "Bridge pileup many casualties fuel"),
        _inc("b", 37.80805, -122.47502, "Bridge pileup many casualties fuel leak"),
        _inc("c", 37.8081, -122.4751, "Mass casualty crash on bridge approach"),
    ]
    _updated, clusters = assign_clusters(items)
    multi = [c for c in clusters if c.caller_count >= 2]
    assert len(multi) >= 1
    assert multi[0].caller_count >= 2


def test_duplicate_likelihood_high_for_similar():
    a = _inc("a", 37.77, -122.42, "Apartment fire smoke trapped")
    b = _inc("b", 37.7701, -122.4201, "Apartment fire heavy smoke person trapped")
    assert duplicate_likelihood(a, b) > 0.5
