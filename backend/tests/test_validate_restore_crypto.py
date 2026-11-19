import os
import unittest
import base64
import json
from unittest.mock import patch

from scripts import validate_restore_crypto
from backend.app.core.crypto import _aad
from backend.scripts.rotate_data_encryption import FIELDS, RotationError, _decode
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class RestoreCryptoValidationTests(unittest.TestCase):
    def test_legacy_configuration_uses_application_defaults(self):
        v1 = base64.b64encode(bytes(range(32))).decode()
        settings, keys = validate_restore_crypto.settings_from_key_values([v1, "", ""])
        self.assertEqual(settings.data_encryption_keys, "{}")
        self.assertEqual(settings.data_encryption_active_key, "v1")
        self.assertEqual(set(keys), {"v1"})

    def test_versioned_configuration_is_accepted(self):
        v1 = base64.b64encode(bytes(range(32))).decode()
        v2 = base64.b64encode(bytes(range(32, 64))).decode()
        _, keys = validate_restore_crypto.settings_from_key_values([v1, json.dumps({"v2": v2}), "v2"])
        self.assertEqual(set(keys), {"v1", "v2"})

    def test_partial_configuration_is_rejected(self):
        v1 = base64.b64encode(bytes(range(32))).decode()
        with self.assertRaises(validate_restore_crypto.AESConfigurationError):
            validate_restore_crypto.settings_from_key_values([v1, '{"v2":"x"}', ""])
        with self.assertRaises(validate_restore_crypto.AESConfigurationError):
            validate_restore_crypto.settings_from_key_values([v1, "", "v2"])

    def test_wrong_aes_key_fails_real_gcm_validation(self):
        key = bytes(range(32))
        wrong = bytes(range(32, 64))
        nonce = bytes.fromhex("00112233445566778899aabb")
        aad = _aad("u1", "school", "1", False)
        cipher = AESGCM(key).encrypt(nonce, b"fixture", aad)
        raw = "v1:" + base64.b64encode(cipher).decode()
        row = {"sender_id": "u1", "target_type": "school", "target_id": "1", "is_anonymous": False}
        with self.assertRaises(RotationError):
            _decode(raw, base64.b64encode(nonce).decode(), FIELDS[0], row, {"v1": wrong})

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
