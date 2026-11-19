"""Run one explicitly authorized Maya HMAC production cutover phase.

This is an operator tool, not an application startup hook and not a disposable
restore helper.  It never runs Alembic or grants; those are separate gates.
"""
from __future__ import annotations

import argparse
import os
from urllib.parse import unquote

from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.pool import NullPool

from backend.app.core.config import Settings
from backend.app.services.maya_digest_migration import migrate_legacy_digests
from backend.app.services.maya_hmac_control import (
    activate_legacy_barrier,
    initialize_identity,
)

ADMIN_URL_ENV = "ECHORA_MAYA_HMAC_ADMIN_DATABASE_URL"
APP_ROLE = "echora_app"
TARGET_DATABASE = "echora"
APPROVAL_ENV = "ECHORA_MAYA_HMAC_PRODUCTION_APPROVAL"


class ProductionCutoverError(RuntimeError):
    """Safe, non-sensitive operator error."""


def validate_admin_url(raw: str) -> URL:
    """Validate the explicit operator URL without exposing its credentials."""
    if not raw or not raw.strip():
        raise ProductionCutoverError(f"{ADMIN_URL_ENV} é obrigatória")
    try:
        url = make_url(raw.strip())
    except Exception as exc:
        raise ProductionCutoverError("URL administrativa inválida") from exc
    if not url.drivername.startswith("postgresql"):
        raise ProductionCutoverError("A conexão administrativa deve ser PostgreSQL")
    if url.database != TARGET_DATABASE:
        raise ProductionCutoverError("O banco alvo deve ser exatamente echora")
    if not url.host or not url.username:
        raise ProductionCutoverError("A URL administrativa deve identificar host e usuário")
    if unquote(url.username) == APP_ROLE:
        raise ProductionCutoverError("echora_app não pode executar o cutover HMAC")
    return url


def validate_invocation(phase: str, settings: Settings, raw_url: str,
                        approval: str, confirmed: bool) -> URL:
    if phase not in {"initialize", "backfill", "barrier"}:
        raise ProductionCutoverError("Fase HMAC inválida")
    if not settings.is_production:
        raise ProductionCutoverError("O executor exige APP_ENV=production")
    if approval != "YES" or not confirmed:
        raise ProductionCutoverError(
            f"Autorização explícita exigida: {APPROVAL_ENV}=YES e --confirm-production"
        )
    try:
        settings._validate_idempotency_key_independence()
    except ValueError:
        raise ProductionCutoverError("As chaves de produção são inválidas ou não independentes") from None
    if phase == "initialize" and settings.maya_idempotency_write_version != "legacy-v1":
        raise ProductionCutoverError("initialize exige modo de escrita legacy-v1")
    if phase in {"backfill", "barrier"} and settings.maya_idempotency_write_version != "hmac-v2":
        raise ProductionCutoverError(f"{phase} exige modo de escrita hmac-v2")
    return validate_admin_url(raw_url)


def verify_database_identity(connection) -> None:
    row = connection.execute(text(
        "SELECT current_database(), current_user, session_user"
    )).one()
    database, current_user, session_user = row
    if database != TARGET_DATABASE:
        raise ProductionCutoverError("A identidade do banco não corresponde a echora")
    if current_user == APP_ROLE or session_user == APP_ROLE:
        raise ProductionCutoverError("A sessão está usando echora_app")


def run_phase(connection, phase: str, settings: Settings):
    verify_database_identity(connection)
    if phase == "initialize":
        initialize_identity(connection, settings)
        return None
    if phase == "backfill":
        return migrate_legacy_digests(connection, settings)
    activate_legacy_barrier(connection, settings)
    return None


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("initialize", "backfill", "barrier"))
    parser.add_argument("--confirm-production", action="store_true")
    args = parser.parse_args(argv)

    settings = Settings(_env_file=None)
    url = validate_invocation(
        args.phase, settings, os.environ.get(ADMIN_URL_ENV, ""),
        os.environ.get(APPROVAL_ENV, ""), args.confirm_production,
    )
    engine = create_engine(
        url, hide_parameters=True, poolclass=NullPool,
        connect_args={"connect_timeout": 10},
    )
    try:
        with engine.begin() as connection:
            result = run_phase(connection, args.phase, settings)
        if result is None:
            print(f"PASS phase={args.phase}")
        else:
            before, changed, after = result
            print(f"PASS phase=backfill changed={changed} legacy_before={before['legacy-v1']} legacy_after={after['legacy-v1']}")
        return 0
    except Exception as exc:
        # Deliberately avoid printing driver messages: they can contain URLs.
        print(f"FAIL phase={args.phase}: {exc.__class__.__name__}")
        return 1
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
