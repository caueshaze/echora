"""Explicit transactional migration of Maya digests; never alters encrypted content."""
from __future__ import annotations
from collections import Counter
from contextlib import contextmanager

from sqlalchemy import text
from sqlalchemy.engine import Connection

from ..core.config import Settings
from ..core.crypto import FeedbackIntegrityError, decrypt_maya_content
from ..core.maya_idempotency import DEDICATED, LEGACY, matches_digest, request_digest


class DigestMigrationError(Exception):
    """Safe, non-sensitive migration failure."""


@contextmanager
def _questions(connection: Connection):
    result = connection.execute(text('''
        SELECT q.id, q.user_id, q.question_encrypted, q.question_nonce,
               q.request_digest, q.request_digest_version,
               c.analysis_id, c.user_id AS conversation_user_id, a.id AS existing_analysis_id
        FROM public.maya_questions AS q
        LEFT JOIN public.maya_conversations AS c ON c.id = q.conversation_id
        LEFT JOIN public.maya_analyses AS a ON a.id = c.analysis_id
        ORDER BY q.id
    ''').execution_options(stream_results=True))
    try:
        yield result.mappings().yield_per(100)
    finally:
        result.close()


def _authenticated_digest(row, settings: Settings):
    if not row['analysis_id'] or row['existing_analysis_id'] != row['analysis_id'] or row['conversation_user_id'] != row['user_id']:
        raise DigestMigrationError('Vínculo de conversa ou análise inválido')
    version = row['request_digest_version']
    if version not in (LEGACY, DEDICATED):
        raise DigestMigrationError('Versão de digest não reconhecida')
    try:
        question = decrypt_maya_content(row['question_encrypted'], row['question_nonce'],
                                        kind='question', record_id=str(row['id']), settings=settings)
        if not matches_digest(settings, row['analysis_id'], question, version, row['request_digest']):
            raise DigestMigrationError('Autenticação do digest legado ou dedicado falhou')
        return request_digest(settings, row['analysis_id'], question, DEDICATED)
    except (FeedbackIntegrityError, ValueError, TypeError):
        raise DigestMigrationError('Autenticação da pergunta ou configuração de chaves falhou') from None


def migrate_legacy_digests(connection: Connection, settings: Settings, *, after_update=None):
    """Run inside the caller's PostgreSQL transaction; exceptions must abort it.

    No commit is performed here. All writers must run compatible code and old
    instances must be drained before this operation is used.
    """
    if connection.dialect.name != 'postgresql' or not connection.in_transaction():
        raise DigestMigrationError('Transação PostgreSQL explícita obrigatória')
    # A savepoint guarantees that a caller catching an exception cannot commit
    # an incomplete conversion in the surrounding transaction.
    with connection.begin_nested():
        return _migrate_locked(connection, settings, after_update=after_update)


def _migrate_locked(connection: Connection, settings: Settings, *, after_update=None):
    if connection.scalar(text('SHOW transaction_isolation')) != 'read committed':
        raise DigestMigrationError('Migração exige isolamento READ COMMITTED')
    if settings.maya_idempotency_write_version != DEDICATED:
        raise DigestMigrationError('Gravação hmac-v2 deve estar ativada antes da migração')
    try:
        settings._validate_idempotency_key_independence()
    except ValueError:
        raise DigestMigrationError('Configuração de chave HMAC inválida ou não independente') from None
    connection.exec_driver_sql("SET LOCAL lock_timeout = '5s'")
    connection.exec_driver_sql('SET LOCAL row_security = off')
    connection.exec_driver_sql('LOCK TABLE public.maya_analyses, public.maya_conversations, public.maya_questions IN SHARE ROW EXCLUSIVE MODE')
    from .maya_hmac_control import check_maya_compatibility
    try:
        check_maya_compatibility(connection, settings)
    except Exception:
        raise DigestMigrationError('Identidade HMAC ou esquema incompatível') from None
    unsafe = connection.scalar(text('''
        SELECT EXISTS (
          SELECT 1 FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
          WHERE n.nspname='public' AND c.relname IN ('maya_questions','maya_conversations','maya_analyses')
            AND (c.relkind <> 'r'
              OR EXISTS (SELECT 1 FROM pg_catalog.pg_trigger t WHERE t.tgrelid=c.oid AND NOT t.tgisinternal)
              OR EXISTS (SELECT 1 FROM pg_catalog.pg_rewrite r WHERE r.ev_class=c.oid AND r.ev_type <> '1')
              OR EXISTS (SELECT 1 FROM pg_catalog.pg_attribute a WHERE a.attrelid=c.oid AND a.attgenerated <> '')
              OR EXISTS (SELECT 1 FROM pg_catalog.pg_inherits i WHERE i.inhrelid=c.oid OR i.inhparent=c.oid))
        )
    '''))
    if unsafe:
        raise DigestMigrationError('Estrutura do banco incompatível com uma migração segura')
    before = Counter({LEGACY: 0, DEDICATED: 0})
    with _questions(connection) as rows:
        for row in rows:
            _authenticated_digest(row, settings)
            before[row['request_digest_version']] += 1
    changed = 0
    stmt = text('''UPDATE public.maya_questions SET request_digest=:new_digest, request_digest_version=:new_version
                   WHERE id=:id AND request_digest=:old_digest AND request_digest_version=:old_version''')
    with _questions(connection) as rows:
        for row in rows:
            digest = _authenticated_digest(row, settings)
            if row['request_digest_version'] != LEGACY:
                continue
            result = connection.execute(stmt, {'new_digest': digest, 'new_version': DEDICATED,
                                              'id': row['id'], 'old_digest': row['request_digest'], 'old_version': LEGACY})
            if result.rowcount != 1:
                raise DigestMigrationError('Registro alterado durante a migração')
            changed += 1
            if after_update is not None:
                after_update()
    after = Counter({LEGACY: 0, DEDICATED: 0})
    with _questions(connection) as rows:
        for row in rows:
            _authenticated_digest(row, settings)
            after[row['request_digest_version']] += 1
    if after[LEGACY] or after[DEDICATED] != before[LEGACY] + before[DEDICATED] or changed != before[LEGACY]:
        raise DigestMigrationError('Verificação final dos digests falhou')
    return before, changed, after
