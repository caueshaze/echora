#!/usr/bin/env python3
"""Read-only Echora pre-deploy diagnostic.

The default mode only inventories backup files.  It never decrypts them.
Use --validate-backups explicitly for non-restoring GPG/pg_restore validation.
No Docker lifecycle command is used; only inspection and exec against an
already-running PostgreSQL container are allowed.
"""
from __future__ import annotations

import argparse
import os
import shlex
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


EXPECTED_DATABASE = os.environ.get("ECHORA_EXPECTED_DATABASE", "echora")
EXPECTED_DB_ROLE = os.environ.get("ECHORA_EXPECTED_DB_ROLE", "echora_owner")


@dataclass
class Result:
    name: str
    state: str  # OK, PENDING, BLOCKED
    detail: str


class Runner:
    def run(self, argv: Sequence[str], *, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
        # Never print argv: it may contain a compose env-file path or operator data.
        return subprocess.run(
            list(argv), input=input_text, text=True, capture_output=True, check=False
        )


class Diagnostic:
    def __init__(self, root: Path, runner: Runner | None = None):
        self.root = root
        self.runner = runner or Runner()
        self.results: list[Result] = []
        self.blocked = False

    def record(self, name: str, state: str, detail: str) -> None:
        self.results.append(Result(name, state, detail))
        print(f"[{state}] {name}: {detail}")
        if state == "BLOCKED":
            self.blocked = True

    def command(self, name: str, argv: Sequence[str], *, critical: bool = False) -> str | None:
        cp = self.runner.run(argv)
        if cp.returncode != 0:
            self.record(name, "BLOCKED" if critical else "PENDING", "comando falhou")
            return None
        return cp.stdout

    def psql(self, name: str, sql: str, *, critical: bool = False) -> str | None:
        env_file = self.root / "deploy" / "compose.env"
        compose_file = self.root / "compose.prod.yml"
        argv = [
            "docker", "compose", "--env-file", str(env_file), "-f", str(compose_file),
            "exec", "-T", "postgres", "psql", "-X", "-v", "ON_ERROR_STOP=1",
            "-A", "-t", "-F", "|", "-U", EXPECTED_DB_ROLE, "-d", EXPECTED_DATABASE,
            "-c", sql,
        ]
        out = self.command(name, argv, critical=critical)
        if out is not None:
            self.record(name, "OK", "consulta concluída")
        return out

    def inspect_host(self) -> None:
        self.command("git revision", ["git", "-C", str(self.root), "rev-parse", "--verify", "HEAD"], critical=True)
        status = self.command("git working tree", ["git", "-C", str(self.root), "status", "--short"])
        if status is not None:
            self.record("git working tree", "OK" if not status.strip() else "PENDING",
                        "limpo" if not status.strip() else "possui alterações")
        self.command("running containers", ["docker", "ps", "--no-trunc", "--format",
                                             "{{.ID}}|{{.Names}}|{{.Image}}|{{.Status}}"])
        self.command("Docker images", ["docker", "images", "--no-trunc", "--format",
                                       "{{.Repository}}|{{.Tag}}|{{.ID}}|{{.Digest}}"])

    def database_identity(self) -> bool:
        out = self.psql("PostgreSQL identity", "SELECT current_database(), current_user, session_user, current_setting('server_version');", critical=True)
        if out is None:
            return False
        fields = out.strip().split("|", 3)
        if len(fields) < 3 or fields[0] != EXPECTED_DATABASE or fields[1] != EXPECTED_DB_ROLE:
            self.record("PostgreSQL identity", "BLOCKED", "banco ou papel inesperado")
            return False
        self.record("PostgreSQL identity", "OK", "banco, papel e sessão confirmados")
        return True

    def object_inventory(self) -> dict[str, bool]:
        sql = """
SELECT 'maya_hmac_control', to_regclass('public.maya_hmac_control') IS NOT NULL
UNION ALL SELECT 'maya_questions', to_regclass('public.maya_questions') IS NOT NULL
UNION ALL SELECT 'alembic_version', to_regclass('public.alembic_version') IS NOT NULL
UNION ALL SELECT 'request_digest_version', EXISTS (
  SELECT 1 FROM information_schema.columns
  WHERE table_schema='public' AND table_name='maya_questions'
    AND column_name='request_digest_version'
);
"""
        out = self.psql("catalog object inventory", sql, critical=True)
        inventory: dict[str, bool] = {}
        if out is None:
            return inventory
        for line in out.splitlines():
            key, sep, value = line.partition("|")
            if sep:
                inventory[key] = value == "t"
                self.record(f"object {key}", "OK", "presente" if value == "t" else "ausente; consultas dependentes serão omitidas")
        return inventory

    def safe_schema_checks(self, inv: dict[str, bool]) -> None:
        if inv.get("alembic_version"):
            self.psql("Alembic revision", "SELECT version_num FROM public.alembic_version;", critical=True)
        else:
            self.record("Alembic revision", "PENDING", "alembic_version ausente")

        if inv.get("maya_questions") and inv.get("request_digest_version"):
            self.psql("digest counts", "SELECT request_digest_version, count(*) FROM public.maya_questions GROUP BY request_digest_version ORDER BY 1;")
        else:
            self.record("digest counts", "PENDING", "maya_questions ou request_digest_version ausente")

        if inv.get("maya_hmac_control"):
            self.psql("HMAC control state", "SELECT count(*), bool_and(length(key_identity)=64), bool_or(legacy_barrier) FROM public.maya_hmac_control;")
            self.psql("HMAC control constraints", """
SELECT conname, contype, convalidated, pg_get_constraintdef(oid)
FROM pg_constraint
WHERE conrelid = to_regclass('public.maya_hmac_control')
   OR conrelid = to_regclass('public.maya_questions');
""")
        else:
            self.record("HMAC control state", "PENDING", "maya_hmac_control ausente; pré-migração aceitável")

    def privilege_audit(self) -> None:
        sql = """
SELECT 'database' AS scope, current_database(),
       has_database_privilege('echora_app', current_database(), 'CONNECT'),
       has_database_privilege('echora_app', current_database(), 'CREATE')
UNION ALL SELECT 'schema', 'public',
       has_schema_privilege('echora_app','public','USAGE'),
       has_schema_privilege('echora_app','public','CREATE');
"""
        self.psql("echora_app database/schema privileges", sql, critical=True)
        self.psql("echora_app table privileges", """
SELECT c.oid::text, c.relname, pg_get_userbyid(c.relowner),
       has_table_privilege('echora_app', c.oid, 'SELECT'),
       has_table_privilege('echora_app', c.oid, 'INSERT'),
       has_table_privilege('echora_app', c.oid, 'UPDATE'),
       has_table_privilege('echora_app', c.oid, 'DELETE'),
       has_table_privilege('echora_app', c.oid, 'REFERENCES'),
       has_table_privilege('echora_app', c.oid, 'TRIGGER')
FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
WHERE n.nspname='public' AND c.relkind IN ('r','p');
""", critical=True)
        self.psql("relation ACLs", """
SELECT c.relname, pg_get_userbyid(c.relowner),
       COALESCE(c.relacl::text, '<default ACL>')
FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
WHERE n.nspname='public' AND c.relkind IN ('r','p');
""", critical=True)
        self.psql("echora_app column privileges", """
SELECT table_name, column_name, privilege_type, is_grantable
FROM information_schema.role_column_grants
WHERE grantee='echora_app' AND table_schema='public';
""", critical=True)
        self.psql("PUBLIC privileges", """
SELECT table_schema, table_name, privilege_type, is_grantable
FROM information_schema.table_privileges
WHERE grantee='PUBLIC' AND table_schema='public';
""", critical=True)
        self.psql("role memberships", """
SELECT member.rolname, parent.rolname, am.admin_option
FROM pg_auth_members am
JOIN pg_roles member ON member.oid=am.member
JOIN pg_roles parent ON parent.oid=am.roleid
WHERE member.rolname IN ('echora_app','echora_backup','echora_migrator')
   OR parent.rolname IN ('echora_app','echora_backup','echora_migrator');
""", critical=True)
        self.psql("HMAC control mutation privileges", """
SELECT
  to_regclass('public.maya_hmac_control') IS NOT NULL AS control_exists,
  CASE WHEN to_regclass('public.maya_hmac_control') IS NULL THEN NULL
       ELSE has_table_privilege('echora_app', to_regclass('public.maya_hmac_control'), 'INSERT') END AS app_insert,
  CASE WHEN to_regclass('public.maya_hmac_control') IS NULL THEN NULL
       ELSE has_table_privilege('echora_app', to_regclass('public.maya_hmac_control'), 'UPDATE') END AS app_update,
  CASE WHEN to_regclass('public.maya_hmac_control') IS NULL THEN NULL
       ELSE has_table_privilege('echora_app', to_regclass('public.maya_hmac_control'), 'DELETE') END AS app_delete,
  has_schema_privilege('echora_app','public','CREATE') AS app_schema_create,
  CASE WHEN to_regclass('public.maya_hmac_control') IS NULL THEN NULL
       ELSE pg_get_userbyid((SELECT relowner FROM pg_class WHERE oid=to_regclass('public.maya_hmac_control'))) = 'echora_app' END AS app_owns_control,
  CASE WHEN to_regclass('public.maya_questions') IS NULL THEN NULL
       ELSE pg_get_userbyid((SELECT relowner FROM pg_class WHERE oid=to_regclass('public.maya_questions'))) = 'echora_app' END AS app_owns_questions;
""", critical=True)

    def backups(self, validate: bool) -> None:
        directory = os.environ.get("ECHORA_BACKUP_DIR")
        if not directory:
            self.record("backup inventory", "PENDING", "ECHORA_BACKUP_DIR não definido")
            return
        files = sorted(Path(directory).glob("echora-*.dump.gpg"))
        self.record("backup inventory", "OK" if files else "PENDING", f"{len(files)} arquivo(s) encontrado(s)")
        for path in files:
            print(f"[INFO] backup file: {path.name} size={path.stat().st_size}")
        if not validate:
            self.record("backup decryption/validation", "PENDING", "não executado por padrão")
            return
        for path in files:
            # Explicit opt-in only. Neither command restores or modifies a database.
            gpg = self.runner.run(["gpg", "--batch", "--decrypt", str(path)])
            if gpg.returncode != 0:
                self.record(f"GPG {path.name}", "PENDING", "descriptografia não validada")
                continue
            self.record(f"GPG {path.name}", "OK", "payload descriptografado em memória do processo")
            restore_list = self.runner.run(["pg_restore", "--list"], input_text=gpg.stdout)
            self.record(f"pg_restore list {path.name}", "OK" if restore_list.returncode == 0 else "PENDING",
                        "dump legível" if restore_list.returncode == 0 else "dump não listado")

    def run(self, validate_backups: bool) -> int:
        self.inspect_host()
        if not self.database_identity():
            stop_check("identidade PostgreSQL não confirmada; diagnóstico interrompido")
            return 2
        inv = self.object_inventory()
        self.safe_schema_checks(inv)
        self.privilege_audit()
        self.backups(validate_backups)
        if self.blocked:
            stop_check("há verificações impeditivas")
            return 2
        return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default="/srv/echora")
    parser.add_argument("--validate-backups", action="store_true",
                        help="opta explicitamente por descriptografar e executar pg_restore --list; nunca restaura")
    args = parser.parse_args(argv)
    return Diagnostic(Path(args.root)).run(args.validate_backups)


if __name__ == "__main__":
    raise SystemExit(main())
