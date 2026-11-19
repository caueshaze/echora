"""Readiness reports dependency failure without exposing its details."""
import unittest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from backend.app.core.config import Settings
from backend.app.main import create_app


class DeployReadinessTests(unittest.TestCase):
    def test_readiness_success_and_failure_are_generic(self):
        settings = Settings(_env_file=None, app_env='test', rate_limit_storage_uri='redis://localhost:6379/0')
        with patch('backend.app.main.get_settings', return_value=settings):
            app = create_app()
        session_factory = MagicMock()
        redis_client = MagicMock()
        with patch('backend.app.main._get_sessionmaker', return_value=session_factory), \
             patch('backend.app.main.redis.Redis.from_url', return_value=redis_client):
            response = TestClient(app).get('/health/ready')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'status': 'ok'})
        redis_client.ping.assert_called_once()
        session_factory.return_value.__enter__.return_value.execute.assert_called_once()

        with patch('backend.app.main._get_sessionmaker', side_effect=RuntimeError('/private/database-secret')):
            response = TestClient(app).get('/health/ready')
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {'status': 'unavailable'})
        self.assertNotIn('secret', response.text)
