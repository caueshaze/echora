import base64
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pydantic import ValidationError

from backend.app.core import config
from backend.app.core.config import Settings


class ProductionSettingsTests(unittest.TestCase):
    def setUp(self):
        self.key = bytes(range(32))
        self.values = {
            '_env_file': None,
            'app_env': 'production',
            'database_url': 'postgresql+psycopg://user:pass@localhost/db',
            'rate_limit_storage_uri': 'redis://localhost:6379/0',
            'secret_key': 'd1b3f29c80a4e75d947d670c5be839a23f91ca3e5b22a61f1cd8b9e05841ef72',
            'data_encryption_key': base64.b64encode(self.key).decode(),
        }

    def settings(self, **overrides):
        return Settings(**(self.values | overrides))

    def test_production_defaults_safe_and_valid_key_unchanged(self):
        settings = self.settings()
        self.assertTrue(settings.is_production)
        self.assertFalse(settings.debug)
        self.assertEqual(settings.encryption_key_bytes(), self.key)

    def test_production_rejects_unsafe_configuration(self):
        bad_values = [
            {'debug': True},
            {'rate_limit_storage_uri': ''},
            {'database_url': 'sqlite:///test.db'},
            {'cors_origins': '*'},
            {'cors_origins': 'https://*.example.org'},
            {'secret_key': 'change-me'},
            {'secret_key': 'SUBSTITUA_POR_UMA_CHAVE_HEX_ALEATORIA_DE_64_CARACTERES'},
            {'secret_key': 'a' * 64},
            {'secret_key': '0123456789abcdef0123456789abcdef'},
            {'data_encryption_key': ''},
            {'data_encryption_key': 'SUBSTITUA_POR_UMA_CHAVE_BASE64_DE_32_BYTES'},
            {'data_encryption_key': 'texto livre'},
            {'data_encryption_key': base64.b64encode(bytes(range(16))).decode()},
            {'data_encryption_key': base64.b64encode(bytes(range(24))).decode()},
            {'data_encryption_key': base64.b64encode(b'a' * 32).decode()},
            {'secret_key': self.key.hex()},
            {'secret_key': base64.b64encode(self.key).decode()},
        ]
        for bad in bad_values:
            with self.subTest(bad=bad), self.assertRaises(ValidationError):
                self.settings(**bad)

    def test_development_key_compatibility(self):
        settings = Settings(_env_file=None, app_env='development', secret_key='dev-secret', data_encryption_key='')
        with self.assertWarns(RuntimeWarning):
            self.assertEqual(len(settings.encryption_key_bytes()), 32)

    def test_root_production_env_selected_and_environment_has_priority(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / '.env.prod').write_text('\n'.join([
                'APP_ENV=production',
                'DATABASE_URL=' + self.values['database_url'],
                'RATE_LIMIT_STORAGE_URI=' + self.values['rate_limit_storage_uri'],
                'SECRET_KEY=' + self.values['secret_key'],
                'DATA_ENCRYPTION_KEY=' + self.values['data_encryption_key'],
                'PROJECT_NAME=from-file',
            ]))
            with patch.object(config, 'PROJECT_ROOT', root), patch.dict(os.environ, {'APP_ENV': 'production', 'PROJECT_NAME': 'from-env'}, clear=True):
                config.get_settings.cache_clear()
                try:
                    settings = config.get_settings()
                    self.assertEqual(settings.project_name, 'from-env')
                    self.assertEqual(settings.encryption_key_bytes(), self.key)
                finally:
                    config.get_settings.cache_clear()

    def test_production_does_not_fall_back_to_development_env(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / '.env').write_text('APP_ENV=development\nDEBUG=true\n')
            with patch.object(config, 'PROJECT_ROOT', root), patch.dict(os.environ, {'APP_ENV': 'production'}, clear=True):
                config.get_settings.cache_clear()
                try:
                    with self.assertRaises(ValidationError):
                        config.get_settings()
                finally:
                    config.get_settings.cache_clear()


if __name__ == '__main__':
    unittest.main()
