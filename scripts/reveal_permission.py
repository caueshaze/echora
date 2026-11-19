"""Operate school-scoped reveal grants with an operator-only database credential.

Run as a module: python -m scripts.reveal_permission grant|revoke USER_ID SCHOOL_ID PERMISSION OPERATOR_ID
MIGRATION_DATABASE_URL must identify a restricted operator connection; never use the app account.
"""
import argparse
import os
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session
from backend.app.models import AuditEvent, RevealPermission, School, User
from backend.app.services.reveal_lock import lock_permission
from uuid import uuid4
import hashlib


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['grant', 'revoke'])
    parser.add_argument('user_id')
    parser.add_argument('school_id', type=int)
    parser.add_argument('permission', choices=['reveal_request', 'reveal_approve'])
    parser.add_argument('operator_id', nargs='?', help='identificador adicional (não usado como identidade autenticada)')
    args = parser.parse_args()
    url = os.environ.get('MIGRATION_DATABASE_URL')
    if not url:
        parser.error('MIGRATION_DATABASE_URL é obrigatória')
    engine = create_engine(url, hide_parameters=True)
    try:
        with engine.connect() as connection:
            if connection.dialect.name != 'postgresql':
                raise ValueError('Conexão PostgreSQL operacional é obrigatória')
            principal = connection.scalar(text('SELECT session_user'))
        operator_id = 'db:' + hashlib.sha256(principal.encode()).hexdigest()[:32]
        try:
            with Session(engine) as db, db.begin():
                lock_permission(db, args.user_id, args.school_id, args.permission)
                user = db.get(User, args.user_id)
                if not user or user.role != 'admin' or not db.get(School, args.school_id):
                    raise ValueError('Administrador ou unidade inexistente')
                grant = db.scalar(select(RevealPermission).where(RevealPermission.user_id == args.user_id,
                    RevealPermission.school_id == args.school_id, RevealPermission.permission == args.permission).with_for_update())
                if args.action == 'grant':
                    if grant:
                        raise ValueError('Permissão já concedida')
                    db.add(RevealPermission(user_id=args.user_id, school_id=args.school_id, permission=args.permission))
                else:
                    if not grant:
                        raise ValueError('Permissão não encontrada')
                    db.delete(grant)
                db.add(AuditEvent(operation_id=str(uuid4()), actor_id=operator_id, actor_role='operator',
                                  action=f'reveal.permission.{args.action}.{args.permission}', resource_type='user',
                                  resource_id=args.user_id, school_id=args.school_id, result='success'))
        except ValueError:
            with Session(engine) as db, db.begin():
                db.add(AuditEvent(operation_id=str(uuid4()), actor_id=operator_id, actor_role='operator',
                                  action=f'reveal.permission.{args.action}.{args.permission}', resource_type='user',
                                  resource_id=args.user_id, school_id=args.school_id, result='denied'))
            raise
    finally:
        engine.dispose()


if __name__ == '__main__':
    main()
