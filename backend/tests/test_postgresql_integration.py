"""Integration checks; set ECHORA_TEST_POSTGRES_URL only for an isolated test DB."""
import os
import base64
from datetime import datetime, timedelta, timezone
import unittest
from unittest.mock import patch
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import Session

from backend.app.api.v1.admin.triggers import router as triggers_router
from backend.app.api.v1.feedback import router as feedback_router
from backend.app.core import database
from backend.app.core.database import get_session
from backend.app.core.security import get_current_user, hash_password
from backend.app.core.config import Settings, get_settings
from backend.app.core.crypto import decrypt_feedback
from backend.app.api.v1.auth import router as auth_router, limiter
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from backend.app.models import Feedback, User
from backend.app.models.organization import Classroom, School, Subject
from backend.app.schemas.user import UserPublic


@unittest.skipUnless(os.getenv('ECHORA_TEST_POSTGRES_URL'), 'requires isolated PostgreSQL test database')
class PostgreSQLIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(os.environ['ECHORA_TEST_POSTGRES_URL'])
        self.db = Session(self.engine, expire_on_commit=False)
        suffix = uuid4().hex
        school = School(name='postgres-test-' + suffix)
        self.db.add(school)
        self.db.flush()
        self.school = school.id
        self.manager = User(id=str(uuid4()), email=f'{suffix}@example.org', full_name='Manager', role='gestor', school_id=school.id, hashed_password=hash_password('password-123456'))
        self.target = User(id=str(uuid4()), email=f'{suffix}a@example.org', full_name='Target', role='aluno', school_id=school.id, hashed_password='x')
        self.subject = Subject(name='Subject', school_id=school.id)
        self.classroom = Classroom(name='Classroom', school_id=school.id)
        self.db.add_all([self.manager, self.target, self.subject, self.classroom])
        self.db.flush()
        self.db.add_all([Feedback(sender_id=self.manager.id, target_type=kind, target_id=target, content_encrypted='cipher', nonce='nonce') for kind, target in [('user', self.target.id), ('subject', str(self.subject.id)), ('class', str(self.classroom.id))]])
        self.db.commit()
        app = FastAPI()
        app.include_router(feedback_router, prefix='/api/v1')
        app.include_router(triggers_router, prefix='/api/v1/admin')
        app.include_router(auth_router, prefix='/api/v1')
        app.state.limiter = limiter
        limiter.reset()
        app.dependency_overrides[get_settings] = lambda: Settings(_env_file=None, app_env='test', secret_key='test-secret')
        app.dependency_overrides[get_current_user] = lambda: UserPublic.model_validate(self.manager)
        app.dependency_overrides[get_session] = lambda: self.db
        self.client = TestClient(app, headers={'Origin': 'http://localhost:5173', 'X-Echora-CSRF': '1'})
        self.decrypt = patch('backend.app.api.v1.feedback_utils.decrypt_feedback', return_value='test')
        self.decrypt.start()
        self.keyword = 'test-' + suffix

    def tearDown(self):
        self.decrypt.stop()
        self.db.rollback()
        fixture_url = os.environ.get('ECHORA_TEST_ADMIN_POSTGRES_URL')
        fixture_engine = create_engine(fixture_url) if fixture_url else self.engine
        with fixture_engine.begin() as connection:
            connection.execute(text('DELETE FROM trigger_keywords WHERE school_id = :id'), {'id': self.school})
            connection.execute(text('DELETE FROM feedbacks WHERE sender_id = :id'), {'id': self.manager.id})
            connection.execute(text('DELETE FROM auth_sessions WHERE user_id = :id'), {'id': self.manager.id})
            connection.execute(text('DELETE FROM users WHERE school_id = :id'), {'id': self.school})
            connection.execute(text('DELETE FROM subjects WHERE school_id = :id'), {'id': self.school})
            connection.execute(text('DELETE FROM classrooms WHERE school_id = :id'), {'id': self.school})
            connection.execute(text('DELETE FROM schools WHERE id = :id'), {'id': self.school})
        self.db.close()
        if fixture_engine is not self.engine:
            fixture_engine.dispose()
        self.engine.dispose()

    def test_trigger_and_mixed_feedback_targets(self):
        url = '/api/v1/admin/trigger_keywords'
        first = self.client.post(url, json={'keyword': self.keyword})
        self.assertEqual(first.status_code, 201, first.text)
        self.assertEqual(self.client.post(url, json={'keyword': self.keyword}).status_code, 409)
        response = self.client.get('/api/v1/feedback/admin/all')
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual({item['target_type'] for item in response.json()}, {'user', 'subject', 'class'})

    def test_auth_session_login_refresh_and_logout(self):
        # Other tests override get_current_user; real authentication needs its dependency.
        self.client.app.dependency_overrides.pop(get_current_user)
        response = self.client.post('/api/v1/auth/login', json={'email': self.manager.email, 'password': 'password-123456'})
        self.assertEqual(response.status_code, 200, response.text)
        token = response.json()['access_token']
        self.assertEqual(self.client.get('/api/v1/auth/me', headers={'Authorization': 'Bearer ' + token}).status_code, 200)
        response = self.client.post('/api/v1/auth/refresh')
        self.assertEqual(response.status_code, 200, response.text)
        token = response.json()['access_token']
        self.assertEqual(self.client.post('/api/v1/auth/logout').status_code, 204)
        self.assertEqual(self.client.get('/api/v1/auth/me', headers={'Authorization': 'Bearer ' + token}).status_code, 401)

    def test_legacy_encryption_is_migrated_in_postgres(self):
        key = bytes(range(32))
        settings = Settings(_env_file=None, app_env='test', data_encryption_key=base64.b64encode(key).decode())
        iv = os.urandom(12)
        fb = Feedback(sender_id=self.manager.id, target_type='user', target_id=self.target.id, content_encrypted=base64.b64encode(AESGCM(key).encrypt(iv, b'legacy', None)).decode(), nonce=base64.b64encode(iv).decode())
        self.db.add(fb)
        self.db.commit()
        with patch('backend.app.core.crypto.get_settings', return_value=settings):
            self.assertEqual(decrypt_feedback(fb), 'legacy')
            self.db.refresh(fb)
            self.assertTrue(fb.content_encrypted.startswith('v1:'))
            self.assertEqual(decrypt_feedback(fb), 'legacy')

    def test_runtime_connection_needs_no_ddl(self):
        with self.engine.connect() as connection:
            with self.assertRaises(ProgrammingError):
                connection.execute(text('CREATE TABLE echora_should_be_denied (id integer)'))
        with patch.object(database, 'SessionLocal', None), patch.object(database, '_engine', None), patch.object(database, '_build_engine', return_value=self.engine):
            factory = database._get_sessionmaker()
            with factory() as session:
                self.assertEqual(session.execute(text('SELECT 1')).scalar_one(), 1)

    def test_runtime_cannot_change_or_delete_audit_events(self):
        for statement in ('UPDATE audit_events SET result = result', 'DELETE FROM audit_events'):
            with self.engine.connect() as connection:
                with self.assertRaises(ProgrammingError):
                    connection.execute(text(statement))

    def test_feedback_admin_delete_requires_idempotency_key(self):
        feedback = self.db.query(Feedback).filter_by(sender_id=self.manager.id).first()
        path = f'/api/v1/feedback/admin/{feedback.id}'
        self.assertEqual(self.client.delete(path).status_code, 400)
        headers = {'Idempotency-Key': str(uuid4())}
        self.assertEqual(self.client.delete(path, headers=headers).status_code, 204)
        self.assertEqual(self.client.delete(path, headers=headers).status_code, 409)
