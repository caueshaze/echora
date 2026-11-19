"""Exceptional, school-scoped and single-use access to anonymous authorship."""
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ....core.database import get_session
from ....core.security import require_role
from ....models import Feedback, RevealPermission, RevealRequest, User
from ....schemas.user import UserPublic
from ....services.audit_service import record_event
from ....services.reveal_lock import lock_permission
from ..feedback_utils import _get_feedback_target_school_id
from .audit_route import AuditedAdminRoute

router = APIRouter(prefix='/reveals', route_class=AuditedAdminRoute)


class CreateReveal(BaseModel):
    feedback_id: int = Field(gt=0)
    school_id: int = Field(gt=0)
    threat: str = Field(min_length=20, max_length=2000)
    necessity: str = Field(min_length=20, max_length=2000)
    proportionality: str = Field(min_length=20, max_length=2000)


def _deny():
    raise HTTPException(status_code=403, detail='Operação não autorizada')


def _permission(db: Session, user_id: str, school_id: int, permission: str):
    lock_permission(db, user_id, school_id, permission)
    grant = db.scalar(select(RevealPermission).where(
        RevealPermission.user_id == user_id, RevealPermission.school_id == school_id,
        RevealPermission.permission == permission))
    if grant is None:
        _deny()


def _feedback(db: Session, feedback_id: int, school_id: int) -> Feedback:
    feedback = db.get(Feedback, feedback_id)
    if not feedback or not feedback.is_anonymous:
        _deny()
    sender = db.get(User, feedback.sender_id)
    if not sender or sender.school_id != school_id or _get_feedback_target_school_id(db, feedback) != school_id:
        _deny()
    return feedback


def _request(db: Session, request_id: UUID) -> RevealRequest:
    entry = db.scalar(select(RevealRequest).where(RevealRequest.id == str(request_id)).with_for_update())
    if entry is None:
        _deny()
    return entry


def _audit(db: Session, actor: UserPublic, action: str, entry: RevealRequest):
    record_event(db, actor=actor, action=action, resource_type='reveal_request',
                 resource_id=entry.id, school_id=entry.school_id)


@router.post('', status_code=201)
def create_reveal(payload: CreateReveal, response: Response, actor: UserPublic = Depends(require_role('admin')), db: Session = Depends(get_session)):
    response.headers['Cache-Control'] = 'no-store'
    _permission(db, actor.id, payload.school_id, 'reveal_request')
    _feedback(db, payload.feedback_id, payload.school_id)
    if any(len(value.strip()) < 20 for value in (payload.threat, payload.necessity, payload.proportionality)):
        raise HTTPException(status_code=422, detail='Justificativa incompleta')
    entry = RevealRequest(id=str(uuid4()), feedback_id=payload.feedback_id, school_id=payload.school_id,
                          requester_id=actor.id, threat=payload.threat.strip(), necessity=payload.necessity.strip(),
                          proportionality=payload.proportionality.strip(), status='pending')
    db.add(entry)
    _audit(db, actor, 'reveal.request', entry)
    db.commit()
    return {'id': entry.id, 'status': entry.status}


@router.get('/{request_id}')
def get_reveal(request_id: UUID, response: Response, actor: UserPublic = Depends(require_role('admin')), db: Session = Depends(get_session)):
    response.headers['Cache-Control'] = 'no-store'
    entry = _request(db, request_id)
    if actor.id == entry.requester_id:
        _permission(db, actor.id, entry.school_id, 'reveal_request')
    else:
        _permission(db, actor.id, entry.school_id, 'reveal_approve')
    _feedback(db, entry.feedback_id, entry.school_id)
    return {'id': entry.id, 'feedback_id': entry.feedback_id, 'school_id': entry.school_id,
            'requester_id': entry.requester_id, 'status': entry.status, 'threat': entry.threat,
            'necessity': entry.necessity, 'proportionality': entry.proportionality, 'expires_at': entry.expires_at}


@router.post('/{request_id}/decision/{decision}')
def decide_reveal(request_id: UUID, decision: str, response: Response, actor: UserPublic = Depends(require_role('admin')), db: Session = Depends(get_session)):
    response.headers['Cache-Control'] = 'no-store'
    if decision not in ('approve', 'reject'):
        _deny()
    entry = _request(db, request_id)
    if actor.id == entry.requester_id or entry.status != 'pending':
        _deny()
    _permission(db, entry.requester_id, entry.school_id, 'reveal_request')
    _permission(db, actor.id, entry.school_id, 'reveal_approve')
    requester = db.get(User, entry.requester_id)
    if not requester or requester.role != 'admin':
        _deny()
    _feedback(db, entry.feedback_id, entry.school_id)
    entry.approver_id = actor.id
    entry.status = 'approved' if decision == 'approve' else 'rejected'
    if decision == 'approve':
        entry.expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
    _audit(db, actor, 'reveal.' + decision, entry)
    db.commit()
    return {'id': entry.id, 'status': entry.status, 'expires_at': entry.expires_at}


@router.post('/{request_id}/identity')
def reveal_identity(request_id: UUID, response: Response, actor: UserPublic = Depends(require_role('admin')), db: Session = Depends(get_session)):
    response.headers['Cache-Control'] = 'no-store'
    entry = _request(db, request_id)
    _permission(db, actor.id, entry.school_id, 'reveal_request')
    if entry.requester_id != actor.id or not entry.approver_id or entry.approver_id == actor.id:
        _deny()
    approver = db.get(User, entry.approver_id)
    if not approver or approver.role != 'admin':
        _deny()
    _permission(db, entry.approver_id, entry.school_id, 'reveal_approve')
    feedback = _feedback(db, entry.feedback_id, entry.school_id)
    now = datetime.now(timezone.utc)
    result = db.execute(update(RevealRequest).where(RevealRequest.id == entry.id,
        RevealRequest.status == 'approved', RevealRequest.expires_at > now,
        RevealRequest.consumed_at.is_(None)).values(status='consumed', consumed_at=now))
    if result.rowcount != 1:
        _deny()
    sender = db.get(User, feedback.sender_id)
    _audit(db, actor, 'reveal.identity', entry)
    identity = {'id': sender.id, 'full_name': sender.full_name, 'email': sender.email}
    db.commit()
    return identity
