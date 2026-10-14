"""Repository helpers for incident persistence and audit."""
from __future__ import annotations

import json
from typing import Optional

from backend.config import get_settings
from backend.database.models import (
    AuditLogRow,
    DispatcherActionRow,
    EvidenceRow,
    IncidentRow,
    RecommendationRow,
    TriageScoreRow,
    get_session,
    init_db,
)
from backend.schemas.incident import DispatcherAction, Incident, UrgencyScore
from backend.utils.logging_utils import get_logger

logger = get_logger(__name__)


class IncidentRepository:
    def __init__(self) -> None:
        init_db()
        self.settings = get_settings()

    def save_incident(self, incident: Incident) -> None:
        if not self.settings.persist_incidents:
            return
        session = get_session()
        try:
            row = session.query(IncidentRow).filter_by(incident_id=incident.incident_id).first()
            payload = incident.model_dump_json()
            if row is None:
                row = IncidentRow(
                    incident_id=incident.incident_id,
                    cluster_id=incident.cluster_id,
                    timestamp=incident.timestamp,
                    incident_type=str(incident.incident_type.value if hasattr(incident.incident_type, "value") else incident.incident_type),
                    status=incident.status,
                    payload_json=payload,
                    urgency_value=incident.urgency.value if incident.urgency else None,
                    urgency_tier=str(incident.urgency.tier.value) if incident.urgency else None,
                    caller_count=incident.caller_count,
                    lat=incident.location.lat,
                    lon=incident.location.lon,
                    narrative=incident.narrative_summary,
                )
                session.add(row)
            else:
                row.cluster_id = incident.cluster_id
                row.status = incident.status
                row.payload_json = payload
                row.urgency_value = incident.urgency.value if incident.urgency else None
                row.urgency_tier = str(incident.urgency.tier.value) if incident.urgency else None
                row.caller_count = incident.caller_count
                row.narrative = incident.narrative_summary
            session.commit()
        except Exception as exc:
            session.rollback()
            logger.exception("Failed to save incident: %s", exc)
        finally:
            session.close()

    def get_incident(self, incident_id: str) -> Optional[Incident]:
        session = get_session()
        try:
            row = session.query(IncidentRow).filter_by(incident_id=incident_id).first()
            if not row:
                return None
            return Incident.model_validate_json(row.payload_json)
        finally:
            session.close()

    def list_incidents(self) -> list[Incident]:
        session = get_session()
        try:
            rows = session.query(IncidentRow).order_by(IncidentRow.timestamp.desc()).all()
            return [Incident.model_validate_json(r.payload_json) for r in rows]
        finally:
            session.close()

    def save_evidence(self, incident_id: str, modality: str, payload: dict) -> None:
        if not self.settings.persist_incidents:
            return
        session = get_session()
        try:
            session.add(
                EvidenceRow(
                    incident_id=incident_id,
                    modality=modality,
                    payload_json=json.dumps(payload),
                )
            )
            session.commit()
        except Exception:
            session.rollback()
        finally:
            session.close()

    def save_triage(self, incident_id: str, urgency: UrgencyScore) -> None:
        if not self.settings.persist_incidents:
            return
        session = get_session()
        try:
            session.add(
                TriageScoreRow(
                    incident_id=incident_id,
                    value=urgency.value,
                    tier=str(urgency.tier.value),
                    breakdown_json=urgency.feature_breakdown.model_dump_json(),
                    rules_json=json.dumps(urgency.rules_triggered + urgency.overrides_applied),
                )
            )
            session.commit()
        except Exception:
            session.rollback()
        finally:
            session.close()

    def save_recommendation(self, incident_id: str, plan_json: str) -> None:
        if not self.settings.persist_incidents:
            return
        session = get_session()
        try:
            session.add(RecommendationRow(incident_id=incident_id, plan_json=plan_json))
            session.commit()
        except Exception:
            session.rollback()
        finally:
            session.close()

    def save_action(self, incident_id: str, action: DispatcherAction) -> None:
        session = get_session()
        try:
            session.add(
                DispatcherActionRow(
                    incident_id=incident_id,
                    action=str(action.action.value),
                    reason=action.reason,
                    changes_json=json.dumps(action.changes),
                    actor=action.actor,
                    created_at=action.timestamp,
                )
            )
            session.commit()
        except Exception:
            session.rollback()
        finally:
            session.close()

    def audit(self, event_type: str, message: str, incident_id: str | None = None, meta: dict | None = None) -> None:
        session = get_session()
        try:
            session.add(
                AuditLogRow(
                    incident_id=incident_id,
                    event_type=event_type,
                    message=message,
                    meta_json=json.dumps(meta or {}),
                    demo_mode=self.settings.demo_mode,
                )
            )
            session.commit()
        except Exception:
            session.rollback()
        finally:
            session.close()

    def list_audit(self, limit: int = 100) -> list[dict]:
        session = get_session()
        try:
            rows = (
                session.query(AuditLogRow)
                .order_by(AuditLogRow.created_at.desc())
                .limit(limit)
                .all()
            )
            return [
                {
                    "incident_id": r.incident_id,
                    "event_type": r.event_type,
                    "message": r.message,
                    "meta": json.loads(r.meta_json or "{}"),
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                    "demo_mode": r.demo_mode,
                }
                for r in rows
            ]
        finally:
            session.close()
