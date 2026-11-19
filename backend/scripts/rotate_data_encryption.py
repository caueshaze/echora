"""Rotate encrypted fields only in explicitly named disposable PostgreSQL databases.

This tool has no production override. Credentials and keys are accepted only
through the environment; output intentionally excludes record IDs and data.
"""
from __future__ import annotations

import base64
import binascii
import hmac
import json
import os
import re
import subprocess
import sys
from collections import Counter
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Callable

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, make_url
from sqlalchemy.pool import NullPool

from backend.app.core.config import Settings
from backend.app.core.crypto import _aad, _keys


class RotationError(Exception):
    """An expected failure that is safe to report without sensitive data."""


@dataclass(frozen=True)
class FieldSpec:
    table: str
    cipher: str
    nonce: str
    kind: str
    nullable: bool = False


FIELDS = (
    FieldSpec('feedbacks', 'content_encrypted', 'nonce', 'feedback'),
    FieldSpec('maya_analyses', 'content_encrypted', 'nonce', 'analysis'),
    FieldSpec('maya_questions', 'question_encrypted', 'question_nonce', 'question'),
    FieldSpec('maya_questions', 'answer_encrypted', 'answer_nonce', 'answer', True),
)

_SENSITIVE_COLUMN_NAME = re.compile(r'(^nonce$|_nonce$|_encrypted$|^encrypted_|(^|_)ciphertext$)', re.IGNORECASE)
_COVERED_COLUMNS = frozenset((spec.table, column) for spec in FIELDS for column in (spec.cipher, spec.nonce))


def uncovered_encrypted_columns(columns):
    """Detect likely encrypted/nonce columns by convention, without inspecting values."""
    candidates = {(table, column) for table, column in columns if _SENSITIVE_COLUMN_NAME.search(column)}
    return candidates - _COVERED_COLUMNS


def _validate_field_inventory(connection: Connection):
    columns = connection.execute(text("""
        SELECT c.relname, a.attname
        FROM pg_catalog.pg_class c
        JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
        JOIN pg_catalog.pg_attribute a ON a.attrelid = c.oid
        WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p')
          AND a.attnum > 0 AND NOT a.attisdropped
    """)).all()
    if uncovered_encrypted_columns(columns):
        raise RotationError('Possíveis campos criptografados fora do inventário de rotação')


def validate_database_url(raw: str):
    """Return a parsed target, or fail closed before making any connection."""
    if not raw or raw != raw.strip():
        raise RotationError('URL de rotação ausente ou inválida')
    try:
        url = make_url(raw)
        if url.drivername not in ('postgresql', 'postgresql+psycopg'):
            raise ValueError
        if not url.database or not re.fullmatch(r'echora_restore_[a-z0-9_]+', url.database):
            raise ValueError
        if url.host != '127.0.0.1' or not url.username or url.port is None:
            raise ValueError
        if set(url.query) - {'sslmode', 'connect_timeout'}:
            raise ValueError
        if any(not isinstance(value, str) for value in url.query.values()):
            raise ValueError
        if 'sslmode' in url.query and url.query['sslmode'] not in ('disable', 'allow', 'prefer', 'require', 'verify-ca', 'verify-full'):
            raise ValueError
        if 'connect_timeout' in url.query and not re.fullmatch(r'[1-9][0-9]*', url.query['connect_timeout']):
            raise ValueError
        if url.port is not None and not 1 <= url.port <= 65535:
            raise ValueError
        return url.set(drivername='postgresql+psycopg')
    except Exception:
        raise RotationError('URL de rotação inválida ou banco não permitido') from None


def authorized_instance(target):
    """Pin a locally inspected disposable Podman container and its loopback port."""
    container_id = os.environ.get('ECHORA_ROTATION_PODMAN_CONTAINER_ID', '')
    instance = os.environ.get('ECHORA_ROTATION_INSTANCE', '')
    if not re.fullmatch(r'[0-9a-f]{64}', container_id) or not re.fullmatch(r'[0-9a-f]{32}', instance):
        raise RotationError('Identificação explícita do contêiner descartável obrigatória')
    if any(os.environ.get(name) for name in ('CONTAINER_HOST', 'CONTAINER_CONNECTION', 'CONTAINER_SSHKEY',
                                              'DOCKER_HOST', 'PODMAN_CONNECTION')):
        raise RotationError('Configuração remota de contêiner não permitida')
    template = ('{{json .ID}}\n{{json .State.Running}}\n'
                '{{json (index .Config.Labels "io.echora.rotation-purpose")}}\n'
                '{{json (index .Config.Labels "io.echora.rotation-instance")}}\n'
                '{{json .NetworkSettings.Ports}}\n{{json .HostConfig.AutoRemove}}\n'
                '{{json .Mounts}}\n{{json .HostConfig.Tmpfs}}\n{{json .HostConfig.Privileged}}')
    try:
        result = subprocess.run(['podman', '--remote=false', 'container', 'inspect', '--format', template, container_id],
                                capture_output=True, text=True, timeout=10, check=True)
        fields = result.stdout.splitlines()
        if len(fields) != 9:
            raise ValueError
        inspected_id, running, purpose, label, ports, auto_remove, mounts, tmpfs, privileged = (json.loads(field) for field in fields)
        mappings = ports.get('5432/tcp') if isinstance(ports, dict) else None
        if (inspected_id != container_id or running is not True or auto_remove is not True or privileged is not False
                or mounts != [] or not isinstance(tmpfs, dict) or '/var/lib/postgresql/data' not in tmpfs
                or purpose != 'disposable'
                or label != instance or not isinstance(mappings, list) or len(mappings) != 1
                or mappings[0].get('HostIp') != '127.0.0.1'
                or mappings[0].get('HostPort') != str(target.port)):
            raise ValueError
        return instance
    except Exception:
        raise RotationError('Contêiner, identificação ou porta não correspondem ao destino autorizado') from None


def rotation_keys(settings: Settings):
    """Require an explicitly supplied, valid AES-256 v1 and a distinct v2."""
    try:
        if not settings.data_encryption_key:
            raise ValueError
        raw_v1 = base64.b64decode(settings.data_encryption_key, altchars=b'-_', validate=True)
        _, keys = _keys(settings)
        if len(raw_v1) != 32 or 'v2' not in keys or not hmac.compare_digest(raw_v1, keys['v1']):
            raise ValueError
        if len(keys['v2']) != 32 or hmac.compare_digest(keys['v1'], keys['v2']):
            raise ValueError
        return keys
    except Exception:
        raise RotationError('Chaves v1 e v2 ausentes, inválidas ou ambíguas') from None


def _decode(raw: str, nonce: str, spec: FieldSpec, row, keys: dict[str, bytes]):
    if raw is None or nonce is None:
        if spec.nullable and raw is None and nonce is None:
            return None
        raise RotationError('Campo criptografado ou nonce ausente')
    try:
        version, separator, ciphertext = raw.partition(':')
        if not separator:
            if spec.kind != 'feedback':
                raise ValueError
            version, ciphertext = 'legacy', raw
        if version not in ('legacy', 'v1', 'v2'):
            raise RotationError('Versão de criptografia desconhecida')
        key = keys['v1'] if version == 'legacy' else keys[version]
        nonce_bytes = base64.b64decode(nonce, validate=True)
        ciphertext_bytes = base64.b64decode(ciphertext, validate=True)
        if len(nonce_bytes) != 12 or len(ciphertext_bytes) < 16:
            raise ValueError
        if spec.kind == 'feedback':
            aad = _aad(row['sender_id'], row['target_type'], row['target_id'], row['is_anonymous'])
            original_aad = None if version == 'legacy' else aad
        else:
            aad = json.dumps(['maya', spec.kind, str(row['id'])], separators=(',', ':')).encode('utf-8')
            original_aad = aad
        plaintext = AESGCM(key).decrypt(nonce_bytes, ciphertext_bytes, original_aad)
        plaintext.decode('utf-8')
        return version, plaintext, aad, nonce_bytes
    except RotationError:
        raise
    except (InvalidTag, ValueError, KeyError, TypeError, UnicodeError, binascii.Error):
        raise RotationError('Formato, chave, AAD ou integridade AES-GCM inválidos') from None


@contextmanager
def _rows(connection: Connection, spec: FieldSpec):
    extra = ', sender_id, target_type, target_id, is_anonymous' if spec.kind == 'feedback' else ''
    query = text(f'SELECT id, {spec.cipher} AS ciphertext, {spec.nonce} AS nonce{extra} FROM public.{spec.table} ORDER BY id')
    result = connection.execute(query.execution_options(stream_results=True))
    try:
        yield result.mappings().yield_per(100)
    finally:
        result.close()


def _scan(connection: Connection, keys: dict[str, bytes]) -> Counter:
    counts = Counter({'v1': 0, 'v2': 0, 'legacy': 0, 'null': 0})
    for spec in FIELDS:
        with _rows(connection, spec) as rows:
            for row in rows:
                value = _decode(row['ciphertext'], row['nonce'], spec, row, keys)
                counts[value[0] if value else 'null'] += 1
    return counts


def _migrate(connection: Connection, keys: dict[str, bytes], *, after_update: Callable[[], None] | None = None) -> int:
    """Called only under the table locks; update encrypted columns exclusively."""
    changed = 0
    for spec in FIELDS:
        update = text(f'UPDATE public.{spec.table} SET {spec.cipher} = :new_cipher, {spec.nonce} = :new_nonce '
                      f'WHERE id = :id AND {spec.cipher} = :old_cipher AND {spec.nonce} = :old_nonce')
        with _rows(connection, spec) as rows:
            for row in rows:
                value = _decode(row['ciphertext'], row['nonce'], spec, row, keys)
                if value is None or value[0] == 'v2':
                    continue
                _, plaintext, aad, old_nonce = value
                nonce = os.urandom(12)
                while nonce == old_nonce:
                    nonce = os.urandom(12)
                cipher = AESGCM(keys['v2']).encrypt(nonce, plaintext, aad)
                if AESGCM(keys['v2']).decrypt(nonce, cipher, aad) != plaintext:
                    raise RotationError('Verificação da nova criptografia falhou')
                result = connection.execute(update, {'new_cipher': 'v2:' + base64.b64encode(cipher).decode('ascii'),
                                          'new_nonce': base64.b64encode(nonce).decode('ascii'), 'id': row['id'],
                                          'old_cipher': row['ciphertext'], 'old_nonce': row['nonce']})
                if result.rowcount != 1:
                    raise RotationError('Registro alterado durante a operação')
                changed += 1
                if after_update is not None:
                    after_update()
    return changed


def _validate_tables(connection: Connection):
    """Reject schema features that could change additional data during updates."""
    rows = connection.execute(text("""
        SELECT c.relname, c.relkind,
          EXISTS (SELECT 1 FROM pg_catalog.pg_trigger t WHERE t.tgrelid = c.oid AND NOT t.tgisinternal) AS custom_trigger,
          EXISTS (SELECT 1 FROM pg_catalog.pg_rewrite r WHERE r.ev_class = c.oid AND r.ev_type <> '1') AS custom_rule,
          EXISTS (SELECT 1 FROM pg_catalog.pg_attribute a WHERE a.attrelid = c.oid AND a.attgenerated <> '') AS generated,
          EXISTS (SELECT 1 FROM pg_catalog.pg_inherits i WHERE i.inhrelid = c.oid OR i.inhparent = c.oid) AS inherited
        FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public' AND c.relname IN ('feedbacks', 'maya_analyses', 'maya_questions')
    """)).mappings().all()
    if len(rows) != 3 or any(r['relkind'] != 'r' or r['custom_trigger'] or r['custom_rule'] or r['generated'] or r['inherited'] for r in rows):
        raise RotationError('Estrutura do banco incompatível com uma rotação segura')


def run_rotation(raw_url: str, settings: Settings, *, apply: bool):
    if any(os.environ.get(name) for name in ('PGHOSTADDR', 'PGSERVICE', 'PGSERVICEFILE', 'PGOPTIONS',
                                              'PGDATABASE', 'PGHOST', 'PGPORT', 'PGUSER')):
        raise RotationError('Variáveis PostgreSQL de destino tornam a conexão ambígua')
    target = validate_database_url(raw_url)
    keys = rotation_keys(settings)
    instance = authorized_instance(target)
    connect_args = {} if 'connect_timeout' in target.query else {'connect_timeout': 10}
    if not apply:
        # Enforce read-only from the very first transaction, including driver setup.
        connect_args['options'] = '-c default_transaction_read_only=on'
    engine = create_engine(target, poolclass=NullPool, hide_parameters=True, echo=False,
                           connect_args=connect_args)
    try:
        with engine.connect() as connection:
            with connection.begin():
                if apply:
                    # A fresh snapshot after obtaining the locks includes writers that
                    # committed while this transaction was waiting for those locks.
                    connection.exec_driver_sql('SET TRANSACTION ISOLATION LEVEL READ COMMITTED')
                else:
                    connection.exec_driver_sql('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
                connection.exec_driver_sql("SET LOCAL lock_timeout = '5s'")
                connection.exec_driver_sql('SET LOCAL row_security = off')
                if connection.scalar(text('SELECT pg_catalog.current_database()')) != target.database:
                    raise RotationError('Identidade do banco não corresponde ao alvo solicitado')
                actual_instance = connection.scalar(text("SELECT pg_catalog.current_setting('echora.rotation_test_instance', true)"))
                if not isinstance(actual_instance, str) or not hmac.compare_digest(actual_instance, instance):
                    raise RotationError('Identidade da instância PostgreSQL não corresponde ao contêiner autorizado')
                data_directory = connection.scalar(text("SELECT pg_catalog.current_setting('data_directory')"))
                if data_directory != '/var/lib/postgresql/data':
                    raise RotationError('Diretório de dados PostgreSQL não está no tmpfs descartável')
                if authorized_instance(target) != instance:
                    raise RotationError('Contêiner autorizado mudou durante a conexão')
                if not apply and connection.scalar(text('SHOW transaction_read_only')) != 'on':
                    raise RotationError('Transação somente leitura não confirmada')
                if apply:
                    connection.exec_driver_sql('LOCK TABLE public.feedbacks, public.maya_analyses, public.maya_questions IN SHARE ROW EXCLUSIVE MODE')
                else:
                    connection.exec_driver_sql('LOCK TABLE public.feedbacks, public.maya_analyses, public.maya_questions IN ACCESS SHARE MODE')
                _validate_tables(connection)
                _validate_field_inventory(connection)
                before = _scan(connection, keys)
                if not apply:
                    return before, 0, before.copy()
                changed = _migrate(connection, keys)
                after = _scan(connection, keys)
                if after['v1'] or after['legacy'] or after['v2'] != before['v1'] + before['v2'] + before['legacy'] or after['null'] != before['null']:
                    raise RotationError('Verificação final de integridade falhou')
                return before, changed, after
    finally:
        engine.dispose()


def main(argv=None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if args == ['--help']:
        print('Uso: python -m backend.scripts.rotate_data_encryption --dry-run | --apply')
        print('Configure URL, ID do contêiner, identificação da instância e chaves no ambiente; consulte a documentação.')
        return 0
    if args not in (['--dry-run'], ['--apply']):
        print('Argumentos inválidos: escolha --dry-run ou --apply.', file=sys.stderr)
        return 2
    try:
        if not os.environ.get('DATA_ENCRYPTION_KEY') or not os.environ.get('DATA_ENCRYPTION_KEYS'):
            raise RotationError('Chaves explícitas obrigatórias no ambiente')
        settings = Settings(_env_file=None)
        before, changed, after = run_rotation(os.environ.get('ECHORA_ROTATION_DATABASE_URL', ''), settings,
                                               apply=args == ['--apply'])
        print(f"Antes: v1={before['v1']} v2={before['v2']} legado={before['legacy']} nulos={before['null']}")
        print(f"Depois: v1={after['v1']} v2={after['v2']} legado={after['legacy']} nulos={after['null']} alterados={changed}")
        print('Integridade verificada; ' + ('transação concluída.' if args == ['--apply'] else 'dry-run somente leitura.'))
        return 0
    except RotationError as exc:
        print(f'Rotação recusada ou revertida: {exc}', file=sys.stderr)
        return 1
    except Exception:
        print('Rotação recusada ou revertida: falha de configuração, conexão ou integridade.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
