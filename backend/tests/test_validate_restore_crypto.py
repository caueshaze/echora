import os
import unittest
from unittest.mock import patch

from scripts import validate_restore_crypto


class RestoreCryptoValidationTests(unittest.TestCase):
    def test_internal_restore_host_requires_explicit_allowlist(self):
        with patch.dict(os.environ, {"ECHORA_RESTORE_ALLOWED_HOST": "echora-restore-postgres"}, clear=True):
            target = validate_restore_crypto.restore_url(
                "postgresql://echora_restore_admin@echora-restore-postgres:5432/echora_restore_test"
            )
            self.assertEqual(target.host, "echora-restore-postgres")

    def test_internal_restore_host_mismatch_is_rejected(self):
        with patch.dict(os.environ, {"ECHORA_RESTORE_ALLOWED_HOST": "echora-restore-postgres"}, clear=True):
            with self.assertRaises(validate_restore_crypto.RotationError):
                validate_restore_crypto.restore_url(
                    "postgresql://echora_restore_admin@other:5432/echora_restore_test"
                )

    def test_production_database_is_rejected_before_connection(self):
        with patch.dict(os.environ, {
            "ECHORA_RESTORE_DATABASE_URL": "postgresql://user:password@127.0.0.1:5432/echora",
        }, clear=False), patch.object(validate_restore_crypto, "create_engine") as engine:
            self.assertEqual(validate_restore_crypto.main(), 2)
            engine.assert_not_called()

    def test_missing_target_is_pending_without_printing_credentials(self):
        with patch.dict(os.environ, {}, clear=True):
            with patch("builtins.print") as output:
                self.assertEqual(validate_restore_crypto.main(), 2)
                rendered = " ".join(str(call) for call in output.call_args_list)
                self.assertNotIn("password", rendered.lower())


if __name__ == "__main__":
    unittest.main()
