#!/usr/bin/env python3
"""Read-only AES-GCM validation for an isolated restored Echora database.

Required environment variables are consumed but never printed:
ECHORA_RESTORE_DATABASE_URL, DATA_ENCRYPTION_KEY, DATA_ENCRYPTION_KEYS,
DATA_ENCRYPTION_ACTIVE_KEY.
"""
from __future__ import annotations

import os
import sys
import argparse
import re

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.pool import NullPool

from backend.app.core.config import Settings
from backend.app.core.crypto import _keys
from backend.scripts.rotate_data_encryption import (
    RotationError,
    _scan,
)


class AESConfigurationError(ValueError):
    """The supplied AES configuration is absent, partial, or invalid."""


def settings_from_key_values(values):
    """Build the exact Settings/_keys configuration supported by the app."""
    if len(values) != 3:
        raise AESConfigurationError("configuração AES incompleta")
    key_v1, key_ring, active = (value.strip() for value in values)
    if not key_v1:
        raise AESConfigurationError("DATA_ENCRYPTION_KEY obrigatória")
    if bool(key_ring) != bool(active):
        raise AESConfigurationError("configuração AES parcial")
    if not key_ring and not active:
        key_ring, active = "{}", "v1"
    try:
        settings = Settings(
            _env_file=None,
            data_encryption_key=key_v1,
            data_encryption_keys=key_ring,
            data_encryption_active_key=active,
        )
        _, keys = _keys(settings)
        return settings, keys
    except Exception:
        raise AESConfigurationError("configuração AES inválida") from None


def restore_url(raw_url: str):
    """Allow only a named restore database on the explicitly supplied host."""
    try:
        target = make_url(raw_url)
        allowed_host = os.environ.get("ECHORA_RESTORE_ALLOWED_HOST", "")
        if target.drivername not in ("postgresql", "postgresql+psycopg"):
            raise ValueError
        if not target.database or not re.fullmatch(r"echora_restore_[a-z0-9_]+", target.database):
            raise ValueError
        if target.database == "echora" or not target.host or target.host != allowed_host:
            raise ValueError
        if target.port is None or not 1 <= target.port <= 65535:
            raise ValueError
        if set(target.query) - {"connect_timeout"}:
            raise ValueError
        return target.set(drivername="postgresql+psycopg")
    except Exception:
        raise RotationError("destino descartável ausente ou inválido") from None


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--keys-stdin", action="store_true",
                        help="lê DATA_ENCRYPTION_KEY, DATA_ENCRYPTION_KEYS e ACTIVE_KEY de três linhas de stdin")
    args = parser.parse_args([] if argv is None else argv)
    if args.keys_stdin:
        values = [sys.stdin.readline().rstrip("\n") for _ in range(3)]
        try:
            settings, keys = settings_from_key_values(values)
        except AESConfigurationError:
            print("VALIDATION_FAILED: configuração AES inválida", file=sys.stderr)
            return 1
    else:
        settings = None
        keys = None
    raw_url = os.environ.get("ECHORA_RESTORE_DATABASE_URL", "")
    try:
        target = restore_url(raw_url)
        if target.database == "echora":
            raise RotationError("banco de produção não é permitido")
        if settings is None:
            settings = Settings(_env_file=None)
            _, keys = _keys(settings)
        engine = create_engine(
            target,
            poolclass=NullPool,
            hide_parameters=True,
            connect_args={"connect_timeout": 10},
        )
        try:
            with engine.connect() as connection:
                actual_db = connection.scalar(text("SELECT current_database()"))
                if actual_db != target.database or actual_db == "echora":
                    raise RotationError("identidade do banco restaurado não corresponde ao destino")
                counts = _scan(connection, keys)
        finally:
            engine.dispose()
        for version in ("legacy", "v1", "v2", "null"):
            print(f"{version}={counts.get(version, 0)}")
        print(f"total={sum(counts.values())}")
        return 0
    except RotationError as exc:
        print(f"VALIDATION_PENDING: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        if hasattr(exc, "errors"):
            fields = ",".join(".".join(str(part) for part in error.get("loc", ())) for error in exc.errors())
            print(f"VALIDATION_FAILED: {type(exc).__name__} fields={fields}", file=sys.stderr)
        else:
            print(f"VALIDATION_FAILED: {type(exc).__name__}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
