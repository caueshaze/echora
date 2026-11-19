"""Remove fingerprints older than 90 days while retaining permanent retry tombstones."""
import hashlib
import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from sqlalchemy import create_engine, text, update
from sqlalchemy.orm import Session
from backend.app.models import AdminOperation, AuditEvent


def compact(db: Session) -> int:
    if db.get_bind().dialect.name != 'postgresql':
        raise RuntimeError('A compactação requer PostgreSQL')
    principal = db.scalar(text('SELECT session_user'))
    result = db.execute(update(AdminOperation).where(
        AdminOperation.created_at < datetime.now(timezone.utc) - timedelta(days=90),
        AdminOperation.request_digest.is_not(None)).values(request_digest=None))
    db.add(AuditEvent(operation_id=str(uuid4()), actor_id='db:' + hashlib.sha256(principal.encode()).hexdigest()[:32],
                      actor_role='operator', action='idempotency.compact', resource_type='admin_operations',
                      resource_id=None, school_id=None, result='success'))
    return result.rowcount


def main():
    url = os.environ.get('MIGRATION_DATABASE_URL')
    if not url:
        raise SystemExit('MIGRATION_DATABASE_URL é obrigatória')
    engine = create_engine(url, hide_parameters=True)
    try:
        with Session(engine) as db, db.begin():
            count = compact(db)
        print(f'Marcadores compactados: {count}')
    finally:
        engine.dispose()

if __name__ == '__main__':
    main()
