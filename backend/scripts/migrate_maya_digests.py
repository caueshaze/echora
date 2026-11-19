"""Exercise the digest migration only on an explicitly authorized disposable container."""
from __future__ import annotations
import hmac
import os
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool
from backend.app.core.config import Settings
from backend.app.services.maya_digest_migration import DigestMigrationError, migrate_legacy_digests
from backend.scripts.rotate_data_encryption import RotationError, authorized_instance, validate_database_url


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    if args == ['--help']:
        print('Uso: python -m backend.scripts.migrate_maya_digests --apply-test')
        return 0
    if args != ['--apply-test']:
        print('Argumentos inválidos: use --apply-test.', file=sys.stderr)
        return 2
    try:
        if any(os.environ.get(name) for name in ('PGHOSTADDR', 'PGSERVICE', 'PGSERVICEFILE', 'PGOPTIONS',
                                                  'PGDATABASE', 'PGHOST', 'PGPORT', 'PGUSER')):
            raise DigestMigrationError('Variáveis PostgreSQL de destino tornam a conexão ambígua')
        if not os.environ.get('DATA_ENCRYPTION_KEY') or not os.environ.get('MAYA_IDEMPOTENCY_HMAC_KEY'):
            raise DigestMigrationError('Chaves explícitas obrigatórias no ambiente')
        settings = Settings(_env_file=None)
        settings.idempotency_hmac_key_bytes()
        target = validate_database_url(os.environ.get('ECHORA_MAYA_DIGEST_DATABASE_URL', ''))
        instance = authorized_instance(target)
        connect_args = {} if 'connect_timeout' in target.query else {'connect_timeout': 10}
        engine = create_engine(target, poolclass=NullPool, hide_parameters=True, echo=False, connect_args=connect_args)
        try:
            with engine.connect() as connection, connection.begin():
                if connection.scalar(text('SELECT pg_catalog.current_database()')) != target.database:
                    raise DigestMigrationError('Banco não corresponde ao destino autorizado')
                actual = connection.scalar(text("SELECT pg_catalog.current_setting('echora.rotation_test_instance', true)"))
                directory = connection.scalar(text("SELECT pg_catalog.current_setting('data_directory')"))
                if (not isinstance(actual, str) or not hmac.compare_digest(actual, instance)
                        or directory != '/var/lib/postgresql/data' or authorized_instance(target) != instance):
                    raise DigestMigrationError('Instância PostgreSQL não corresponde ao destino autorizado')
                before, changed, after = migrate_legacy_digests(connection, settings)
            print(f"Antes: legados={before['legacy-v1']} dedicados={before['hmac-v2']}")
            print(f"Depois: legados={after['legacy-v1']} dedicados={after['hmac-v2']} alterados={changed}")
            return 0
        finally:
            engine.dispose()
    except (DigestMigrationError, RotationError) as exc:
        print(f'Migração recusada ou revertida: {exc}', file=sys.stderr)
        return 1
    except Exception:
        print('Migração recusada ou revertida: falha de configuração, conexão ou integridade.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
