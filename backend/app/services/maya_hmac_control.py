"""Shared HMAC identity and PostgreSQL legacy-write cutover controls."""
from __future__ import annotations
import hashlib
import hmac
from fastapi import Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Session
from ..core.config import Settings, get_settings
from ..core.database import get_session

BARRIER = 'ck_maya_questions_hmac_v2_only'
DOMAIN = b'echora/maya-idempotency/key-identity/v1'


class MayaControlError(Exception):
    pass


def key_identity(settings: Settings) -> str:
    return hmac.new(settings.idempotency_hmac_key_bytes(), DOMAIN, hashlib.sha256).hexdigest()


def check_maya_compatibility(db, settings: Settings):
    """Fail closed when the schema, stored identity, or cutover are inconsistent."""
    db.execute(text('SELECT request_digest_version FROM maya_questions WHERE 1=0'))
    row = db.execute(text('SELECT key_identity, legacy_barrier FROM maya_hmac_control WHERE id=1')).first()
    if row is None:
        if settings.is_production or settings.maya_idempotency_write_version == 'hmac-v2':
            raise MayaControlError('Referência HMAC não inicializada')
        if db.execute(text("SELECT 1 FROM maya_questions WHERE request_digest_version='hmac-v2' LIMIT 1")).first():
            raise MayaControlError('Referência HMAC ausente')
        return
    try:
        expected = key_identity(settings)
    except ValueError:
        raise MayaControlError('Chave HMAC indisponível') from None
    if not isinstance(row.key_identity, str) or not hmac.compare_digest(row.key_identity, expected):
        raise MayaControlError('Identidade HMAC incompatível')
    if row.legacy_barrier and settings.maya_idempotency_write_version != 'hmac-v2':
        raise MayaControlError('Escritor legado após corte')
    dialect = db.get_bind().dialect.name if isinstance(db, Session) else db.dialect.name
    if dialect == 'postgresql':
        present = bool(db.execute(text("""SELECT 1 FROM pg_catalog.pg_constraint c
           JOIN pg_catalog.pg_class t ON t.oid=c.conrelid JOIN pg_catalog.pg_namespace n ON n.oid=t.relnamespace
           WHERE n.nspname='public' AND t.relname='maya_questions' AND c.conname=:name
             AND c.contype='c' AND c.convalidated
             AND pg_catalog.pg_get_constraintdef(c.oid) = 'CHECK (((request_digest_version)::text = ''hmac-v2''::text))'
        """), {'name': BARRIER}).first())
        if bool(row.legacy_barrier) != present:
            raise MayaControlError('Barreira inconsistente')


def require_maya_compatibility(db: Session = Depends(get_session), settings: Settings = Depends(get_settings)):
    try:
        check_maya_compatibility(db, settings)
    except Exception:
        raise HTTPException(503, 'Serviço da Maya indisponível') from None


def _admin_transaction(connection: Connection):
    if connection.dialect.name != 'postgresql' or not connection.in_transaction():
        raise MayaControlError('Transação PostgreSQL explícita obrigatória')
    if connection.scalar(text('SHOW transaction_isolation')) != 'read committed':
        raise MayaControlError('Operação exige READ COMMITTED')
    connection.exec_driver_sql("SET LOCAL lock_timeout = '5s'")
    connection.exec_driver_sql('LOCK TABLE public.maya_questions IN ACCESS EXCLUSIVE MODE')
    connection.exec_driver_sql('LOCK TABLE public.maya_hmac_control IN EXCLUSIVE MODE')


def initialize_identity(connection: Connection, settings: Settings):
    """Explicit operator action; application role must have no insert privilege."""
    with connection.begin_nested():
        _admin_transaction(connection)
        settings._validate_idempotency_key_independence()
        identity = key_identity(settings)
        existing = connection.execute(text('SELECT key_identity FROM public.maya_hmac_control WHERE id=1')).first()
        if existing:
            if not hmac.compare_digest(existing.key_identity, identity):
                raise MayaControlError('Identidade HMAC já inicializada de forma diferente')
            return
        if connection.execute(text("SELECT 1 FROM public.maya_questions WHERE request_digest_version <> 'legacy-v1' LIMIT 1")).first():
            raise MayaControlError('Identidade não pode ser inicializada com digests não legados')
        connection.execute(text('INSERT INTO public.maya_hmac_control (id,key_identity,legacy_barrier) VALUES (1,:identity,false)'), {'identity': identity})


def activate_legacy_barrier(connection: Connection, settings: Settings):
    """Lock, verify zero legacy rows, and install an enforcement constraint atomically."""
    with connection.begin_nested():
        _admin_transaction(connection)
        check_maya_compatibility(connection, settings)
        if settings.maya_idempotency_write_version != 'hmac-v2':
            raise MayaControlError('Modo hmac-v2 obrigatório')
        row = connection.execute(text('SELECT legacy_barrier FROM public.maya_hmac_control WHERE id=1')).first()
        if not row:
            raise MayaControlError('Referência HMAC não inicializada')
        if row.legacy_barrier:
            return
        if connection.execute(text("SELECT 1 FROM public.maya_questions WHERE request_digest_version <> 'hmac-v2' LIMIT 1")).first():
            raise MayaControlError('Existem digests não migrados')
        connection.exec_driver_sql("ALTER TABLE public.maya_questions ADD CONSTRAINT ck_maya_questions_hmac_v2_only CHECK (request_digest_version = 'hmac-v2')")
        connection.exec_driver_sql('UPDATE public.maya_hmac_control SET legacy_barrier=true WHERE id=1')
        check_maya_compatibility(connection, settings)
