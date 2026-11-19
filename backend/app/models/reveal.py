"""School-scoped exceptional access to anonymous authorship."""
from datetime import datetime
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from ..core.database import Base


class RevealPermission(Base):
    __tablename__ = 'reveal_permissions'
    __table_args__ = (UniqueConstraint('user_id', 'school_id', 'permission', name='uq_reveal_permission'),
                      CheckConstraint("permission IN ('reveal_request', 'reveal_approve')", name='ck_reveal_permission'))
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    school_id: Mapped[int] = mapped_column(ForeignKey('schools.id', ondelete='CASCADE'), nullable=False)
    permission: Mapped[str] = mapped_column(String(32), nullable=False)


class RevealRequest(Base):
    __tablename__ = 'reveal_requests'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    feedback_id: Mapped[int] = mapped_column(ForeignKey('feedbacks.id', ondelete='CASCADE'), nullable=False)
    school_id: Mapped[int] = mapped_column(ForeignKey('schools.id', ondelete='CASCADE'), nullable=False)
    requester_id: Mapped[str] = mapped_column(String(36), ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    approver_id: Mapped[str | None] = mapped_column(String(36), ForeignKey('users.id', ondelete='SET NULL'))
    threat: Mapped[str] = mapped_column(Text, nullable=False)
    necessity: Mapped[str] = mapped_column(Text, nullable=False)
    proportionality: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default='pending')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
