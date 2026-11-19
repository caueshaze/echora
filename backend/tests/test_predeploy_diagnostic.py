import subprocess
import unittest
from pathlib import Path
from unittest.mock import Mock

from scripts.diagnose_predeploy import Diagnostic


class FakeRunner:
    def __init__(self, outputs=None, failures=None):
        self.outputs = outputs or {}
        self.failures = failures or set()
        self.calls = []

    def run(self, argv, *, input_text=None):
        self.calls.append((list(argv), input_text))
        key = argv[0] if argv else ""
        if key in self.failures:
            return subprocess.CompletedProcess(argv, 1, "", "secret must not leak")
        return subprocess.CompletedProcess(argv, 0, self.outputs.get(key, ""), "")


class PredeployDiagnosticTests(unittest.TestCase):
    def test_missing_objects_are_reported_without_dependent_queries(self):
        runner = FakeRunner({"docker": "maya_hmac_control|f\nmaya_questions|t\nalembic_version|f\nrequest_digest_version|f\n"})
        diag = Diagnostic(Path("/tmp/echora"), runner)
        inv = diag.object_inventory()
        diag.safe_schema_checks(inv)
        names = [r.name for r in diag.results]
        self.assertIn("object maya_hmac_control", names)
        self.assertIn("digest counts", names)
        self.assertTrue(any(r.state == "PENDING" for r in diag.results))
        self.assertFalse(any("SELECT request_digest_version" in " ".join(call[0]) for call in runner.calls))

    def test_identity_mismatch_is_blocking_and_stops_run(self):
        runner = FakeRunner({"docker": "other_db|echora_owner|echora_owner|16\n"})
        diag = Diagnostic(Path("/tmp/echora"), runner)
        self.assertFalse(diag.database_identity())
        self.assertTrue(diag.blocked)

    def test_connection_failure_is_blocking_for_identity(self):
        runner = FakeRunner(failures={"docker"})
        diag = Diagnostic(Path("/tmp/echora"), runner)
        self.assertFalse(diag.database_identity())
        self.assertTrue(diag.blocked)

    def test_unexpected_app_privileges_are_visible_in_catalog_queries(self):
        runner = FakeRunner({"docker": ""})
        diag = Diagnostic(Path("/tmp/echora"), runner)
        diag.privilege_audit()
        sql = "\n".join(" ".join(call[0]) for call in runner.calls)
        self.assertIn("has_table_privilege('echora_app'", sql)
        self.assertIn("role_column_grants", sql)
        self.assertIn("grantee='PUBLIC'", sql)
        self.assertIn("pg_auth_members", sql)
        self.assertIn("maya_hmac_control", sql)

    def test_default_backup_mode_never_runs_gpg_or_pg_restore(self):
        runner = FakeRunner({"docker": ""})
        diag = Diagnostic(Path("/definitely/missing"), runner)
        diag.backups(validate=False)
        commands = [call[0][0] for call in runner.calls]
        self.assertNotIn("gpg", commands)
        self.assertNotIn("pg_restore", commands)

    def test_sql_error_is_recorded_without_raw_error_output(self):
        runner = FakeRunner(failures={"docker"})
        diag = Diagnostic(Path("/tmp/echora"), runner)
        diag.psql("catalog", "SELECT 1", critical=False)
        self.assertEqual(diag.results[-1].state, "PENDING")
        self.assertNotIn("secret must not leak", " ".join(r.detail for r in diag.results))


if __name__ == "__main__":
    unittest.main()
