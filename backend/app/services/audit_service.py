"""Audit events contain identifiers only, never request bodies or secrets."""

from uuid import uuid4
from sqlalchemy.orm import Session
from ..models import AuditEvent
from ..schemas.user import UserPublic


def record_event(db: Session, *, actor: UserPublic, action: str,
                 resource_type: str, resource_id: str | int | None,
                 school_id: int | None, operation_id: str | None = None,
                 result: str = "success") -> AuditEvent:
    event = AuditEvent(operation_id=operation_id or db.info.get('audit_operation_id') or str(uuid4()), actor_id=str(actor.id),
                       actor_role=actor.role, action=action, resource_type=resource_type,
                       resource_id=str(resource_id) if resource_id is not None else None,
                       school_id=school_id, result=result)
    db.add(event)
    return event
