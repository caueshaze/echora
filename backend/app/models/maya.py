"""Encrypted Maya analyses and per-user contextual questions."""
from datetime import date, datetime
from uuid import uuid4
from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, false, func
from sqlalchemy.orm import Mapped, mapped_column
from ..core.database import Base


def new_id() -> str:
    return str(uuid4())


class MayaAnalysis(Base):
    __tablename__ = 'maya_analyses'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    requester_id: Mapped[str | None] = mapped_column(ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    school_id: Mapped[int | None] = mapped_column(ForeignKey('schools.id'), nullable=True, index=True)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    content_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    nonce: Mapped[str] = mapped_column(String(32), nullable=False)
    feedback_count: Mapped[int] = mapped_column(Integer, nullable=False)
    period_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    period_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default='completed')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)


class MayaConversation(Base):
    __tablename__ = 'maya_conversations'
    __table_args__ = (UniqueConstraint('analysis_id', 'user_id', name='uq_maya_conversation_analysis_user'),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    analysis_id: Mapped[str] = mapped_column(ForeignKey('maya_analyses.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class MayaQuestion(Base):
    __tablename__ = 'maya_questions'
    __table_args__ = (UniqueConstraint('user_id', 'request_key', name='uq_maya_question_user_key'),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    conversation_id: Mapped[str] = mapped_column(ForeignKey('maya_conversations.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    request_key: Mapped[str] = mapped_column(String(64), nullable=False)
    request_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    request_digest_version: Mapped[str] = mapped_column(String(16), nullable=False, server_default='legacy-v1')
    question_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    question_nonce: Mapped[str] = mapped_column(String(32), nullable=False)
    answer_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer_nonce: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    reservation_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    quota_date: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class MayaDailyQuota(Base):
    __tablename__ = 'maya_daily_quotas'
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), primary_key=True)
    quota_date: Mapped[date] = mapped_column(Date, primary_key=True)
    consumed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class MayaHmacControl(Base):
    __tablename__ = 'maya_hmac_control'
    __table_args__ = (CheckConstraint('id = 1', name='ck_maya_hmac_control_singleton'),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key_identity: Mapped[str] = mapped_column(String(64), nullable=False)
    legacy_barrier: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=false())
