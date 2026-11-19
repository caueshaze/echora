"""Serialize application permission checks with the operator grant procedure."""
from sqlalchemy import text
from sqlalchemy.orm import Session


def lock_permission(db: Session, user_id: str, school_id: int, permission: str) -> None:
    if db.get_bind().dialect.name == 'postgresql':
        key = f'echora:reveal:{user_id}:{school_id}:{permission}'
        db.execute(text('SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))'), {'key': key})
