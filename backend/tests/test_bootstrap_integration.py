"""Bootstrap integration checks against a disposable migrated PostgreSQL database."""
import os
import unittest
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import create_engine, delete, select
from sqlalchemy.orm import sessionmaker
from backend.app.api.v1.auth import router as auth_router, limiter
from backend.app.api.v1.admin import router as admin_router
from backend.app.core.config import Settings, get_settings
from backend.app.core.database import get_session
from backend.app.models import AuditEvent, AuthSession, RevealPermission, User
from backend.app.services.bootstrap_service import bootstrap_admin


@unittest.skipUnless(os.getenv('ECHORA_TEST_ADMIN_POSTGRES_URL'), 'requires isolated PostgreSQL fixture owner')
class BootstrapIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(os.environ['ECHORA_TEST_ADMIN_POSTGRES_URL'])
        self.factory = sessionmaker(bind=self.engine, expire_on_commit=False)
        self.email = str(uuid4()) + '@example.org'
        with self.factory() as db:
            if db.scalar(select(User.id).where(User.role == 'admin', User.school_id.is_(None))):
                self.fail('bootstrap tests require an empty isolated database without a global administrator')

    def tearDown(self):
        with self.factory.begin() as db:
            ids = db.scalars(select(User.id).where(User.email == self.email)).all()
            db.execute(delete(AuthSession).where(AuthSession.user_id.in_(ids)))
            db.execute(delete(User).where(User.id.in_(ids)))
        self.engine.dispose()

    def provision(self):
        with self.factory.begin() as db:
            return bootstrap_admin(db, email=self.email, full_name='Administrador', password='Temporaria-segura-123')

    def test_concurrent_bootstrap_only_one_succeeds(self):
        def create(_):
            try:
                return self.provision()
            except ValueError:
                return None
        with ThreadPoolExecutor(max_workers=2) as pool:
            result = list(pool.map(create, range(2)))
        self.assertEqual(sum(value is not None for value in result), 1)
        with self.factory() as db:
            user = db.scalar(select(User).where(User.email == self.email))
            self.assertTrue(user.must_change_password)
            self.assertFalse(db.scalars(select(RevealPermission).where(RevealPermission.user_id == user.id)).all())
            self.assertEqual(len(db.scalars(select(AuditEvent).where(AuditEvent.action == 'bootstrap.admin_create', AuditEvent.resource_id == user.id)).all()), 1)
        with self.assertRaises(ValueError):
            self.provision()

    def test_password_change_blocks_privilege_and_revokes_session(self):
        self.provision()
        app = FastAPI(); app.include_router(auth_router, prefix='/api/v1'); app.include_router(admin_router, prefix='/api/v1')
        app.state.limiter = limiter; app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler); limiter.reset()
        def session():
            with self.factory() as db: yield db
        app.dependency_overrides[get_session] = session
        app.dependency_overrides[get_settings] = lambda: Settings(_env_file=None, app_env='test', secret_key='test-secret')
        client = TestClient(app, headers={'Origin': 'http://localhost:5173', 'X-Echora-CSRF': '1'})
        response = client.post('/api/v1/auth/login', json={'email': self.email, 'password': 'Temporaria-segura-123'})
        self.assertEqual(response.status_code, 200, response.text)
        token = response.json()['access_token']; headers = {'Authorization': 'Bearer ' + token}
        self.assertTrue(client.get('/api/v1/auth/me', headers=headers).json()['must_change_password'])
        self.assertEqual(client.get('/api/v1/admin/schools', headers=headers).status_code, 403)
        self.assertEqual(client.post('/api/v1/auth/change-password', headers=headers, json={'current_password': 'Temporaria-segura-123', 'new_password': 'Nova-senha-segura-456'}).status_code, 204)
        self.assertEqual(client.get('/api/v1/auth/me', headers=headers).status_code, 401)
        response = client.post('/api/v1/auth/login', json={'email': self.email, 'password': 'Nova-senha-segura-456'})
        self.assertEqual(response.status_code, 200, response.text)
        headers = {'Authorization': 'Bearer ' + response.json()['access_token']}
        self.assertFalse(client.get('/api/v1/auth/me', headers=headers).json()['must_change_password'])
        self.assertEqual(client.get('/api/v1/admin/schools', headers=headers).status_code, 200)

    def test_failed_audit_rolls_back_bootstrap(self):
        with patch('backend.app.services.bootstrap_service.AuditEvent', side_effect=RuntimeError('audit unavailable')):
            with self.assertRaises(RuntimeError):
                self.provision()
        with self.factory() as db:
            self.assertIsNone(db.scalar(select(User).where(User.email == self.email)))

    def test_password_policy_rejects_weak_bootstrap_password(self):
        with self.assertRaises(ValidationError):
            with self.factory.begin() as db:
                bootstrap_admin(db, email=self.email, full_name='Administrador', password='short')
        with self.factory() as db:
            self.assertIsNone(db.scalar(select(User).where(User.email == self.email)))
