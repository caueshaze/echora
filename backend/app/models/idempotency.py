"""Transactional markers for administrative retries; no response bodies are stored."""
from datetime import datetime
from sqlalchemy import DateTime, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from ..core.database import Base

class AdminOperation(Base):
    __tablename__ = 'admin_operations'
    __table_args__ = (UniqueConstraint('actor_id', 'key_digest', name='uq_admin_operation_actor_key'),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    actor_id: Mapped[str] = mapped_column(String(36), nullable=False)
    key_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    request_digest: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
