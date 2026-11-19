import base64
import unittest
from unittest.mock import Mock, patch

from sqlalchemy import text

from backend.app.core.config import Settings
from backend.app.services.maya_digest_migration import DigestMigrationError
from scripts.migrate_maya_hmac_production import (
    APP_ROLE, ProductionCutoverError, run_phase, validate_admin_url,
    validate_invocation,
)


def prod_settings(mode="legacy-v1"):
    return Settings(
        _env_file=None, app_env="production",
        secret_key="A9!echora-production-secret-2026-key",
        data_encryption_key=base64.b64encode(bytes(range(32))).decode(),
        maya_idempotency_hmac_key=base64.b64encode(bytes(range(32, 64))).decode(),
        maya_idempotency_write_version=mode,
        rate_limit_storage_uri="redis://localhost/0",
        database_url="postgresql+psycopg://unused@db/echora",
    )


class ProductionExecutorTests(unittest.TestCase):
    def test_admin_url_rejects_app_role_and_wrong_database(self):
        with self.assertRaises(ProductionCutoverError):
            validate_admin_url("postgresql://echora_app@db/echora")
        with self.assertRaises(ProductionCutoverError):
            validate_admin_url("postgresql://operator@db/other")

    def test_authorization_and_phase_mode_are_explicit(self):
        with self.assertRaises(ProductionCutoverError):
            validate_invocation("initialize", prod_settings("hmac-v2"),
                                "postgresql://operator@db/echora", "YES", True)
        with self.assertRaises(ProductionCutoverError):
            validate_invocation("backfill", prod_settings(),
                                "postgresql://operator@db/echora", "YES", True)
        with self.assertRaises(ProductionCutoverError):
            validate_invocation("barrier", prod_settings("hmac-v2"),
                                "postgresql://operator@db/echora", "NO", True)

    def test_identity_is_checked_before_phase_function(self):
        connection = Mock()
        connection.execute.return_value.one.return_value = ("other", "operator", "operator")
        with self.assertRaises(ProductionCutoverError):
            run_phase(connection, "initialize", prod_settings())
        connection.execute.assert_called_once()

    def test_app_role_is_rejected_even_when_current_user_differs(self):
        connection = Mock()
        connection.execute.return_value.one.return_value = ("echora", "operator", APP_ROLE)
        with self.assertRaises(ProductionCutoverError):
            run_phase(connection, "barrier", prod_settings("hmac-v2"))

    @patch("scripts.migrate_maya_hmac_production.activate_legacy_barrier")
    def test_barrier_reuses_existing_service(self, activate):
        connection = Mock()
        connection.execute.return_value.one.return_value = ("echora", "operator", "operator")
        run_phase(connection, "barrier", prod_settings("hmac-v2"))
        activate.assert_called_once_with(connection, unittest.mock.ANY)

    @patch("scripts.migrate_maya_hmac_production.migrate_legacy_digests")
    def test_backfill_reuses_existing_service(self, migrate):
        connection = Mock()
        connection.execute.return_value.one.return_value = ("echora", "operator", "operator")
        migrate.return_value = ({"legacy-v1": 1}, 1, {"legacy-v1": 0})
        self.assertEqual(run_phase(connection, "backfill", prod_settings("hmac-v2"))[1], 1)
        migrate.assert_called_once_with(connection, unittest.mock.ANY)


if __name__ == "__main__":
    unittest.main()
