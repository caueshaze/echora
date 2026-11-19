import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
import base64
import jwt

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from backend.app.api.v1.auth import router, limiter, _response
from backend.app.core.config import Settings, get_settings
from backend.app.core.database import Base, get_session
from backend.app.core.security import create_access_token, hash_password
from backend.app.models import AuthSession, User
from backend.app.models.organization import Classroom, School
from backend.app.schemas.user import UserPublic, UserUpdate
from backend.app.services.user_service import update_user


class AuthenticationSessionTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine, expire_on_commit=False)
        self.db.add_all([School(id=1, name='Escola'), Classroom(id=1, name='Turma', school_id=1)])
        self.manager = User(id='manager', email='manager@example.org', full_name='Manager', role='gestor', school_id=1, hashed_password=hash_password('secret123'))
        self.user = User(id='student', email='student@example.org', full_name='Student', role='aluno', school_id=1, classroom_id=1, hashed_password=hash_password('secret123'))
        self.db.add_all([self.user, self.manager])
        self.db.commit()
        self.settings = Settings(_env_file=None, app_env='test', secret_key='test-secret')
        app = FastAPI()
        limiter.reset()
        app.state.limiter = limiter
        app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
        app.include_router(router, prefix='/api/v1')
        app.dependency_overrides[get_session] = lambda: self.db
        app.dependency_overrides[get_settings] = lambda: self.settings
        self.client = TestClient(app, headers={'Origin': 'http://localhost:5173', 'X-Echora-CSRF': '1'})

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def login(self):
        result = self.client.post('/api/v1/auth/login', json={'email': self.user.email, 'password': 'secret123'})
        self.assertEqual(result.status_code, 200, result.text)
        return result.json()['access_token']

    def me(self, token):
        return self.client.get('/api/v1/auth/me', headers={'Authorization': 'Bearer ' + token})

    def test_rotation_and_logout_revocation(self):
        token = self.login()
        self.assertIn('HttpOnly', self.client.cookies.get('echora_refresh') and self.client.post('/api/v1/auth/login', json={'email': self.user.email, 'password': 'secret123'}).headers['set-cookie'])
        token = self.login()
        old = self.client.cookies.get('echora_refresh')
        self.assertEqual(self.me(token).status_code, 200)
        response = self.client.post('/api/v1/auth/refresh')
        self.assertEqual(response.status_code, 200, response.text)
        rotated = self.client.cookies.get('echora_refresh')
        self.assertNotEqual(old, rotated)
        self.assertEqual(self.client.post('/api/v1/auth/refresh', headers={'Cookie': f'echora_refresh={old}'}).status_code, 401)
        current = response.json()['access_token']
        self.assertEqual(self.client.post('/api/v1/auth/logout').status_code, 204)
        self.assertEqual(self.me(current).status_code, 401)
        self.assertEqual(self.client.post('/api/v1/auth/refresh', headers={'Cookie': f'echora_refresh={rotated}'}).status_code, 401)

    def test_absolute_expiry_and_legacy_token(self):
        token = self.login()
        session = self.db.query(AuthSession).filter_by(user_id=self.user.id).one()
        session.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        self.db.commit()
        self.assertEqual(self.me(token).status_code, 401)
        self.assertEqual(self.client.post('/api/v1/auth/refresh').status_code, 401)
        old_token = create_access_token(subject=self.user.id, role='aluno', settings=self.settings)
        self.assertEqual(self.me(old_token).status_code, 401)

    def test_production_cookie_and_token_are_bounded(self):
        settings = Settings(_env_file=None, app_env='production', database_url='postgresql://localhost/db',
                            rate_limit_storage_uri='redis://localhost:6379/0',
                            secret_key='0123456789abcdef' * 4,
                            data_encryption_key=base64.b64encode(bytes(range(32))).decode())
        deadline = datetime.now(timezone.utc) + timedelta(seconds=30)
        session = AuthSession(id='test-session', user_id=self.user.id, refresh_hash='x', expires_at=deadline)
        response = _response(self.user, session, 'secret', settings)
        cookie = response.headers['set-cookie']
        self.assertIn('HttpOnly', cookie)
        self.assertIn('Secure', cookie)
        self.assertIn('SameSite=strict', cookie)
        import json
        token = json.loads(response.body)['access_token']
        claims = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm], issuer=settings.jwt_issuer)
        self.assertLessEqual(claims['exp'], int(deadline.timestamp()))

    def test_password_reset_revokes_session(self):
        token = self.login()
        update_user(self.db, self.user.id, UserUpdate(password='newpass123'), UserPublic.model_validate(self.manager))
        self.assertEqual(self.me(token).status_code, 401)
        self.assertEqual(self.client.post('/api/v1/auth/refresh').status_code, 401)
        self.assertEqual(self.client.post('/api/v1/auth/login', json={'email': self.user.email, 'password': 'secret123'}).status_code, 401)
        self.assertEqual(self.client.post('/api/v1/auth/login', json={'email': self.user.email, 'password': 'newpass123'}).status_code, 200)

    def test_login_limit_and_cookie_origin(self):
        self.assertEqual(self.client.post('/api/v1/auth/login', headers={'Origin': 'https://evil.example'}, json={'email': self.user.email, 'password': 'secret123'}).status_code, 403)
        for _ in range(4):
            self.assertEqual(self.client.post('/api/v1/auth/login', json={'email': self.user.email, 'password': 'wrongpass'}).status_code, 401)
        self.assertEqual(self.client.post('/api/v1/auth/login', json={'email': self.user.email, 'password': 'wrongpass'}).status_code, 429)

    def test_cookie_endpoints_require_origin_and_csrf_header(self):
        self.login()
        for path in ('/api/v1/auth/refresh', '/api/v1/auth/logout'):
            for headers in ({'Origin': 'null', 'X-Echora-CSRF': '1'},
                            {'Origin': 'https://evil.example', 'X-Echora-CSRF': '1'},
                            {'Origin': 'http://localhost:5173', 'X-Echora-CSRF': ''},
                            {'Origin': '', 'X-Echora-CSRF': '1'}):
                with self.subTest(path=path, headers=headers):
                    self.assertEqual(self.client.post(path, headers=headers).status_code, 403)
        response = self.client.post('/api/v1/auth/refresh')
        self.assertEqual(response.status_code, 200)

    def test_same_origin_web_login(self):
        self.settings.cors_origins = 'http://testserver'
        response = self.client.post('/api/v1/auth/login',
                                    headers={'Origin': 'http://testserver', 'X-Echora-CSRF': '1'},
                                    json={'email': self.user.email, 'password': 'secret123'})
        self.assertEqual(response.status_code, 200)
        response = self.client.post('/api/v1/auth/refresh',
                                    headers={'Origin': 'http://testserver', 'X-Echora-CSRF': '1'})
        self.assertEqual(response.status_code, 200)
