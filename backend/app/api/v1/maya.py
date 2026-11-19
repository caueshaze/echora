"""Authorized history and contextual Maya conversations."""
from __future__ import annotations
from uuid import UUID
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session
from ...core.database import get_session
from ...core.security import get_current_user
from ...models.maya import MayaAnalysis
from ...schemas.user import UserPublic
from ...services import maya_service as service

from ...services.maya_hmac_control import require_maya_compatibility

router = APIRouter(prefix='/maya', tags=['Maya'], dependencies=[Depends(require_maya_compatibility)])


class QuestionInput(BaseModel):
    question: str = Field(min_length=1, max_length=2000)

    @field_validator('question')
    @classmethod
    def validate_question(cls, value):
        value = value.strip()
        if not value:
            raise ValueError('Informe uma pergunta')
        return value


@router.get('/analyses')
def list_analyses(offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=50),
                  user: UserPublic = Depends(get_current_user), db: Session = Depends(get_session)):
    rows = db.scalars(select(MayaAnalysis).where(service.permitted_query(user))
                      .order_by(MayaAnalysis.created_at.desc(), MayaAnalysis.id.desc()).offset(offset).limit(limit + 1)).all()
    return {'items': [service.analysis_response(row) for row in rows[:limit]], 'has_more': len(rows) > limit}


@router.get('/analyses/{analysis_id}')
def get_analysis(analysis_id: UUID, user: UserPublic = Depends(get_current_user), db: Session = Depends(get_session)):
    return service.analysis_response(service.get_analysis(db, user, str(analysis_id)), True)


@router.get('/quota')
def quota(user: UserPublic = Depends(get_current_user), db: Session = Depends(get_session)):
    return service.quota_status(db, user)


@router.get('/analyses/{analysis_id}/messages')
def get_messages(analysis_id: UUID, user: UserPublic = Depends(get_current_user), db: Session = Depends(get_session)):
    return {'items': service.messages(db, user, str(analysis_id)), 'quota': service.quota_status(db, user)}


@router.post('/analyses/{analysis_id}/questions')
def ask_question(analysis_id: UUID, payload: QuestionInput, idempotency_key: UUID = Header(alias='Idempotency-Key'),
                 user: UserPublic = Depends(get_current_user), db: Session = Depends(get_session)):
    try:
        result = service.ask(db, user, str(analysis_id), payload.question, str(idempotency_key))
    except RuntimeError:
        raise HTTPException(503, 'Não foi possível obter uma resposta da Maya. Tente novamente.') from None
    return {'message': result, 'quota': service.quota_status(db, user)}
