"""Provision the first global administrator in a serialized PostgreSQL transaction."""
import hashlib
from uuid import uuid4
from sqlalchemy import select, text
from sqlalchemy.orm import Session
from ..core.security import hash_password
from ..models import AuditEvent, User
from ..schemas.user import UserCreate
from .user_service import _validate_role_password


def bootstrap_admin(db: Session, *, email: str, full_name: str, password: str) -> str:
    if db.get_bind().dialect.name != 'postgresql':
        raise RuntimeError('O bootstrap requer PostgreSQL')
    payload = UserCreate(email=email, full_name=full_name, password=password, role='admin')
    if not payload.full_name.strip():
        raise ValueError('Nome obrigatório')
    _validate_role_password(password, 'admin', str(payload.email))
    db.execute(text("SELECT pg_advisory_xact_lock(hashtextextended('echora:first-admin', 0))"))
    if db.scalar(select(User.id).where(User.role == 'admin', User.school_id.is_(None)).limit(1)):
        raise ValueError('Já existe um administrador global')
    principal = db.scalar(text('SELECT session_user'))
    user = User(email=str(payload.email).lower(), full_name=payload.full_name.strip(), role='admin',
                hashed_password=hash_password(password), must_change_password=True)
    db.add(user)
    db.flush()
    db.add(AuditEvent(operation_id=str(uuid4()), actor_id='db:' + hashlib.sha256(principal.encode()).hexdigest()[:32],
                      actor_role='operator', action='bootstrap.admin_create', resource_type='user',
                      resource_id=user.id, school_id=None, result='success'))
    db.flush()
    return user.id
