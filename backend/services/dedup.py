"""Incident deduplication / clustering."""
from __future__ import annotations

from datetime import timedelta

from backend.config import get_settings
from backend.schemas.incident import Incident, IncidentCluster
from backend.utils.geo import haversine_m, narrative_similarity, new_id


def find_cluster_match(incident: Incident, existing: list[Incident]) -> Incident | None:
    settings = get_settings()
    window = timedelta(minutes=settings.dedup_time_window_minutes)
    for other in existing:
        if other.incident_id == incident.incident_id:
            continue
        dt = abs((incident.timestamp - other.timestamp).total_seconds())
        if dt > window.total_seconds():
            continue
        dist = haversine_m(
            incident.location.lat,
            incident.location.lon,
            other.location.lat,
            other.location.lon,
        )
        if dist > settings.dedup_distance_meters:
            continue
        same_type = str(incident.incident_type) == str(other.incident_type)
        sim = narrative_similarity(incident.narrative_summary, other.narrative_summary)
        if same_type and sim >= settings.dedup_similarity_threshold:
            return other
        # Slightly lower threshold if very close geographically.
        if dist < settings.dedup_distance_meters * 0.4 and sim >= settings.dedup_similarity_threshold - 0.1:
            return other
    return None


def assign_clusters(incidents: list[Incident]) -> tuple[list[Incident], list[IncidentCluster]]:
    """Group incidents; mutate cluster_id / caller_count on copies conceptually in-place."""
    settings = get_settings()
    # Process oldest-first for stable clusters.
    ordered = sorted(incidents, key=lambda x: x.timestamp)
    clusters: dict[str, list[Incident]] = {}
    id_to_cluster: dict[str, str] = {}

    for inc in ordered:
        match = None
        for cid, members in clusters.items():
            m = find_cluster_match(inc, members)
            if m:
                match = cid
                break
        if match is None:
            cid = new_id("clu")
            clusters[cid] = [inc]
            id_to_cluster[inc.incident_id] = cid
            inc.cluster_id = cid
            inc.caller_count = 1
        else:
            members = clusters[match]
            # similarity vs primary
            primary = members[0]
            sim = narrative_similarity(inc.narrative_summary, primary.narrative_summary)
            members.append(inc)
            id_to_cluster[inc.incident_id] = match
            inc.cluster_id = match
            for m in members:
                m.caller_count = len(members)

    cluster_objs: list[IncidentCluster] = []
    for cid, members in clusters.items():
        if len(members) < 2:
            # Still assign cluster id but only surface multi-caller clusters in UI badges.
            primary = members[0]
            cluster_objs.append(
                IncidentCluster(
                    cluster_id=cid,
                    incident_ids=[primary.incident_id],
                    incident_type=primary.incident_type,
                    caller_count=1,
                    similarity=1.0,
                    location=primary.location,
                    primary_incident_id=primary.incident_id,
                    urgency_tier=primary.urgency.tier if primary.urgency else None,
                )
            )
            continue
        primary = max(members, key=lambda x: (x.urgency.value if x.urgency else 0, x.timestamp))
        sims = [
            narrative_similarity(m.narrative_summary, primary.narrative_summary)
            for m in members
            if m.incident_id != primary.incident_id
        ]
        avg_sim = sum(sims) / len(sims) if sims else 1.0
        for m in members:
            m.caller_count = len(members)
            m.cluster_id = cid
        cluster_objs.append(
            IncidentCluster(
                cluster_id=cid,
                incident_ids=[m.incident_id for m in members],
                incident_type=primary.incident_type,
                caller_count=len(members),
                similarity=round(avg_sim, 3),
                location=primary.location,
                primary_incident_id=primary.incident_id,
                urgency_tier=primary.urgency.tier if primary.urgency else None,
            )
        )
    return ordered, cluster_objs


def duplicate_likelihood(a: Incident, b: Incident) -> float:
    settings = get_settings()
    dist = haversine_m(a.location.lat, a.location.lon, b.location.lat, b.location.lon)
    geo = max(0.0, 1.0 - dist / settings.dedup_distance_meters)
    sim = narrative_similarity(a.narrative_summary, b.narrative_summary)
    type_bonus = 0.15 if str(a.incident_type) == str(b.incident_type) else 0.0
    return round(min(1.0, 0.45 * geo + 0.40 * sim + type_bonus), 3)
