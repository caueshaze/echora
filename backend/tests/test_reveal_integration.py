"""Use only an isolated PostgreSQL database migrated to head."""
import os
import hashlib
import subprocess
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from uuid import uuid4
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, delete, select, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import ProgrammingError
from backend.app.api.v1.admin.reveals import router
from backend.app.api.v1.admin import router as admin_router
from backend.app.api.v1.feedback_utils import _serialize_feedback
from backend.app.core.database import get_session
from backend.app.core.security import get_current_user
from backend.app.models import AdminOperation, AuditEvent, Feedback, RevealPermission, RevealRequest, School, User
from backend.app.schemas.user import UserPublic


@unittest.skipUnless(os.getenv('ECHORA_TEST_POSTGRES_URL') and os.getenv('ECHORA_TEST_ADMIN_POSTGRES_URL'),
                     'requires isolated PostgreSQL test database and fixture owner')
class RevealIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(os.environ['ECHORA_TEST_POSTGRES_URL'])
        self.factory = sessionmaker(bind=self.engine, expire_on_commit=False)
        self.fixture_engine = create_engine(os.environ['ECHORA_TEST_ADMIN_POSTGRES_URL'])
        self.fixture_factory = sessionmaker(bind=self.fixture_engine, expire_on_commit=False)
        self.a, self.b, self.student = (str(uuid4()) for _ in range(3))
        with self.fixture_factory.begin() as db:
            school = School(name='reveal-test-' + uuid4().hex)
            db.add(school); db.flush(); self.school = school.id
            db.add_all([User(id=self.a, email=self.a+'@example.org', full_name='Admin A', role='admin', hashed_password='x'),
                        User(id=self.b, email=self.b+'@example.org', full_name='Admin B', role='admin', hashed_password='x'),
                        User(id=self.student, email=self.student+'@example.org', full_name='Aluno', role='aluno', school_id=self.school, hashed_password='x')])
            db.flush()
            feedback = Feedback(sender_id=self.student, target_type='user', target_id=self.student, is_anonymous=True, content_encrypted='x', nonce='x')
            db.add(feedback); db.flush(); self.feedback = feedback.id
            db.add_all([RevealPermission(user_id=self.a, school_id=self.school, permission='reveal_request'),
                        RevealPermission(user_id=self.b, school_id=self.school, permission='reveal_approve')])
        app = FastAPI(); app.include_router(router); app.include_router(admin_router)
        def session():
            with self.factory() as db: yield db
        def user(request: Request):
            with self.factory() as db:
                item = db.get(User, request.headers.get('x-test-user'))
                result = UserPublic.model_validate(item)
                request.state.audit_actor = result
                return result
        app.dependency_overrides[get_session] = session
        app.dependency_overrides[get_current_user] = user
        self.client = TestClient(app)
        self.patch = patch('backend.app.api.v1.admin.audit_route._get_sessionmaker', return_value=self.factory)
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        with self.fixture_factory.begin() as db:
            db.execute(delete(RevealRequest).where(RevealRequest.school_id == self.school))
            db.execute(delete(RevealPermission).where(RevealPermission.school_id == self.school))
            db.execute(delete(Feedback).where(Feedback.id == self.feedback))
            db.execute(delete(User).where(User.id.in_([self.a, self.b, self.student])))
            db.execute(delete(School).where(School.id == self.school))
        self.engine.dispose()
        self.fixture_engine.dispose()

    def create(self):
        body = {'school_id': self.school, 'feedback_id': self.feedback,
                'threat': 'Ameaça concreta de dano à segurança',
                'necessity': 'Necessário para impedir dano iminente',
                'proportionality': 'Consulta individual limitada a este caso'}
        response = self.client.post('/reveals', headers={'x-test-user': self.a}, json=body)
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()['id']

    def test_approval_single_use_and_audit(self):
        request_id = self.create()
        self.assertEqual(self.client.post(f'/reveals/{request_id}/decision/approve', headers={'x-test-user': self.a}).status_code, 403)
        self.assertEqual(self.client.post(f'/reveals/{request_id}/decision/approve', headers={'x-test-user': self.b}).status_code, 200)
        def consume(_):
            return self.client.post(f'/reveals/{request_id}/identity', headers={'x-test-user': self.a})
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(consume, range(2)))
        self.assertEqual(sorted(response.status_code for response in results), [200, 403])
        self.assertEqual(next(response for response in results if response.status_code == 200).json()['id'], self.student)
        with self.fixture_factory() as db:
            events = db.scalars(select(AuditEvent).where(AuditEvent.resource_id == request_id)).all()
            self.assertEqual({event.action for event in events}, {'reveal.request', 'reveal.approve', 'reveal.identity'})
            self.assertNotIn(self.student, str([(event.action, event.resource_id) for event in events]))

    def test_expiry_revocation_and_transaction_failure(self):
        request_id = self.create()
        self.assertEqual(self.client.post(f'/reveals/{request_id}/decision/approve', headers={'x-test-user': self.b}).status_code, 200)
        with self.fixture_factory.begin() as db:
            entry = db.get(RevealRequest, request_id); entry.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        self.assertEqual(self.client.post(f'/reveals/{request_id}/identity', headers={'x-test-user': self.a}).status_code, 403)
        with self.fixture_factory.begin() as db:
            entry = db.get(RevealRequest, request_id); entry.expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
            db.execute(delete(RevealPermission).where(RevealPermission.user_id == self.b))
        self.assertEqual(self.client.post(f'/reveals/{request_id}/identity', headers={'x-test-user': self.a}).status_code, 403)
        with self.fixture_factory.begin() as db:
            db.add(RevealPermission(user_id=self.b, school_id=self.school, permission='reveal_approve'))
        with patch('backend.app.api.v1.admin.reveals.record_event', side_effect=RuntimeError('audit unavailable')):
            with self.assertRaises(RuntimeError):
                self.client.post(f'/reveals/{request_id}/identity', headers={'x-test-user': self.a})
        with self.factory() as db:
            self.assertEqual(db.get(RevealRequest, request_id).status, 'approved')

    def test_scope_permissions_rejection_and_24_hour_expiry(self):
        body = {'school_id': self.school + 99999, 'feedback_id': self.feedback,
                'threat': 'Ameaça concreta de dano à segurança',
                'necessity': 'Necessário para impedir dano iminente',
                'proportionality': 'Consulta individual limitada a este caso'}
        self.assertEqual(self.client.post('/reveals', headers={'x-test-user': self.a}, json=body).status_code, 403)
        body['school_id'] = self.school
        self.assertEqual(self.client.post('/reveals', headers={'x-test-user': self.student}, json=body).status_code, 403)
        request_id = self.create()
        self.assertEqual(self.client.post(f'/reveals/{request_id}/decision/reject', headers={'x-test-user': self.b}).status_code, 200)
        self.assertEqual(self.client.post(f'/reveals/{request_id}/identity', headers={'x-test-user': self.a}).status_code, 403)
        request_id = self.create()
        before = datetime.now(timezone.utc)
        result = self.client.post(f'/reveals/{request_id}/decision/approve', headers={'x-test-user': self.b})
        expires = datetime.fromisoformat(result.json()['expires_at'].replace('Z', '+00:00'))
        self.assertGreaterEqual(expires, before + timedelta(hours=24))
        self.assertLess(expires, datetime.now(timezone.utc) + timedelta(hours=24, seconds=2))
        with self.fixture_factory.begin() as db:
            db.execute(delete(RevealPermission).where(RevealPermission.user_id == self.a))
        self.assertEqual(self.client.post(f'/reveals/{request_id}/identity', headers={'x-test-user': self.a}).status_code, 403)

    def test_common_serialization_masks_admin_view(self):
        with self.factory() as db:
            feedback = db.get(Feedback, self.feedback)
            feedback.target_id = 'other'
            actor = UserPublic.model_validate(db.get(User, self.a))
            with patch('backend.app.api.v1.feedback_utils.decrypt_feedback', return_value='texto'):
                result = _serialize_feedback(feedback, viewer=actor)
            self.assertEqual(result.sender_id, 'anonymous')
            self.assertIsNone(result.sender_email)
            self.assertIsNone(result.sender_school_id)
            self.assertNotIn(self.student, result.model_dump_json())

    def test_operator_grants_and_revokes_and_application_cannot_grant(self):
        with self.engine.connect() as conn:
            with self.assertRaises(ProgrammingError):
                conn.execute(delete(RevealPermission))
        env = dict(os.environ, MIGRATION_DATABASE_URL=os.environ['ECHORA_TEST_ADMIN_POSTGRES_URL'])
        command = ['.venv/bin/python', '-m', 'scripts.reveal_permission']
        for action in ('grant', 'revoke'):
            result = subprocess.run(command + [action, self.b, str(self.school), 'reveal_request', 'operator-test'],
                                    env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
        with self.fixture_factory() as db:
            principal = db.scalar(text('SELECT session_user'))
        operator_id = 'db:' + hashlib.sha256(principal.encode()).hexdigest()[:32]
        with self.fixture_factory() as db:
            events = db.scalars(select(AuditEvent).where(AuditEvent.actor_id == operator_id,
                                                         AuditEvent.school_id == self.school)).all()
            self.assertEqual({event.action for event in events},
                             {'reveal.permission.grant.reveal_request', 'reveal.permission.revoke.reveal_request'})

    def test_admin_idempotency_concurrency_and_mismatch(self):
        key = str(uuid4())
        keyword = 'idem-' + uuid4().hex
        headers = {'x-test-user': self.a, 'Idempotency-Key': key}
        payload = {'keyword': keyword, 'school_id': self.school}
        def send(_):
            return self.client.post('/admin/trigger_keywords', headers=headers, json=payload)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(send, range(2)))
        self.assertEqual(sorted(item.status_code for item in results), [201, 409])
        result = self.client.post('/admin/trigger_keywords', headers=headers,
                                  json={'keyword': keyword + '-different', 'school_id': self.school})
        self.assertEqual(result.status_code, 409)
        with self.fixture_factory() as db:
            events = db.scalars(select(AuditEvent).where(AuditEvent.action == 'trigger.create',
                                                         AuditEvent.school_id == self.school)).all()
            self.assertEqual(len(events), 1)
            marker = db.scalar(select(AdminOperation).where(AdminOperation.id == events[0].operation_id))
            self.assertIsNotNone(marker)
            self.assertNotIn(keyword, str(vars(marker)))
            marker_id = marker.id
        from scripts.compact_admin_operations import compact
        with self.fixture_factory.begin() as db:
            db.get(AdminOperation, marker_id).created_at = datetime.now(timezone.utc) - timedelta(days=91)
        with self.fixture_factory.begin() as db:
            self.assertGreaterEqual(compact(db), 1)
        with self.factory() as db:
            self.assertIsNone(db.get(AdminOperation, marker_id).request_digest)
        self.assertEqual(self.client.post('/admin/trigger_keywords', headers=headers, json=payload).status_code, 409)
        from backend.app.models import TriggerKeyword
        with self.fixture_factory.begin() as db:
            db.execute(delete(TriggerKeyword).where(TriggerKeyword.school_id == self.school))

    def test_failed_audit_rolls_back_retry_marker_and_operation(self):
        from backend.app.models import TriggerKeyword
        key = str(uuid4())
        keyword = 'failure-' + uuid4().hex
        headers = {'x-test-user': self.a, 'Idempotency-Key': key}
        payload = {'keyword': keyword, 'school_id': self.school}
        with patch('backend.app.api.v1.admin.triggers.record_event', side_effect=RuntimeError('audit unavailable')):
            with self.assertRaises(RuntimeError):
                self.client.post('/admin/trigger_keywords', headers=headers, json=payload)
        with self.factory() as db:
            self.assertIsNone(db.scalar(select(TriggerKeyword).where(TriggerKeyword.keyword == keyword)))
        self.assertEqual(self.client.post('/admin/trigger_keywords', headers=headers, json=payload).status_code, 201)
        with self.fixture_factory.begin() as db:
            db.execute(delete(TriggerKeyword).where(TriggerKeyword.school_id == self.school))

    def test_key_is_required_and_identity_cannot_be_replayed(self):
        body = {'keyword': 'missing-' + uuid4().hex, 'school_id': self.school}
        self.assertEqual(self.client.post('/admin/trigger_keywords', headers={'x-test-user': self.a}, json=body).status_code, 400)
        request_id = self.create()
        self.assertEqual(self.client.post(f'/reveals/{request_id}/decision/approve', headers={'x-test-user': self.b}).status_code, 200)
        path = f'/admin/reveals/{request_id}/identity'
        self.assertEqual(self.client.post(path, headers={'x-test-user': self.a}).status_code, 400)
        headers = {'x-test-user': self.a, 'Idempotency-Key': str(uuid4())}
        self.assertEqual(self.client.post(path, headers=headers).status_code, 200)
        self.assertEqual(self.client.post(path, headers=headers).status_code, 403)
