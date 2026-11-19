import unittest
import tempfile
from unittest.mock import patch
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from backend.app.core.database import Base
from backend.app.models import AuditEvent, User, School, Classroom
from backend.app.schemas.user import UserPublic, UserUpdate
from backend.app.services.audit_service import record_event
from backend.app.services.user_service import update_user
from backend.app.core.security import get_current_user
from backend.app.api.v1.admin.schools import router as schools_router


class AdminAuditTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite://')
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine, expire_on_commit=False)
        self.db.add_all([School(id=1, name='Escola'), Classroom(id=1, name='Turma', school_id=1)])
        self.db.add(User(id='student', email='student@example.org', full_name='Antes',
                         role='aluno', school_id=1, classroom_id=1, hashed_password='hash'))
        self.db.commit()
        self.actor = UserPublic(id='manager', email='manager@example.org', full_name='Gestor', role='gestor', school_id=1)

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_user_update_records_identifiers_without_sensitive_fields(self):
        update_user(self.db, 'student', UserUpdate(full_name='Depois', password='password-123'), self.actor)
        event = self.db.scalar(select(AuditEvent))
        self.assertEqual((event.action, event.resource_id, event.school_id), ('user.update', 'student', 1))
        values = str({key: value for key, value in vars(event).items() if not key.startswith('_')})
        for sensitive in ('password-123', 'student@example.org', 'Depois'):
            self.assertNotIn(sensitive, values)

    def test_audit_failure_prevents_update(self):
        with patch('backend.app.services.user_service.record_event', side_effect=RuntimeError('audit unavailable')):
            with self.assertRaises(RuntimeError):
                update_user(self.db, 'student', UserUpdate(full_name='Depois'), self.actor)
        self.db.rollback()
        self.assertEqual(self.db.get(User, 'student').full_name, 'Antes')
        self.assertIsNone(self.db.scalar(select(AuditEvent)))

    def test_duplicate_operation_is_rejected_by_database(self):
        kwargs = dict(actor=self.actor, action='user.update', resource_type='user',
                      resource_id='student', school_id=1, operation_id='operation-1')
        record_event(self.db, **kwargs)
        self.db.commit()
        record_event(self.db, **kwargs)
        with self.assertRaises(IntegrityError):
            self.db.commit()
        self.db.rollback()
        self.assertEqual(len(self.db.scalars(select(AuditEvent)).all()), 1)

    def test_denied_request_is_recorded_in_independent_transaction(self):
        with tempfile.TemporaryDirectory() as directory:
            engine = create_engine(f'sqlite:///{directory}/audit.db')
            Base.metadata.create_all(engine)
            factory = sessionmaker(bind=engine)
            actor = UserPublic(id='student', email='student@example.org', full_name='Aluno', role='aluno', school_id=1)
            def current_user(request: Request):
                request.state.audit_actor = actor
                return actor
            app = FastAPI()
            app.include_router(schools_router)
            app.dependency_overrides[get_current_user] = current_user
            with patch('backend.app.api.v1.admin.audit_route._get_sessionmaker', return_value=factory):
                response = TestClient(app).post('/schools', json={'name': 'Escola'})
            self.assertEqual(response.status_code, 403)
            with factory() as db:
                event = db.scalar(select(AuditEvent))
                self.assertEqual((event.actor_id, event.result), ('student', 'denied'))
            engine.dispose()

    def test_not_found_is_audited_without_changing_response(self):
        with tempfile.TemporaryDirectory() as directory:
            engine = create_engine(f'sqlite:///{directory}/audit.db')
            Base.metadata.create_all(engine)
            factory = sessionmaker(bind=engine)
            actor = UserPublic(id='admin', email='admin@example.org', full_name='Admin', role='admin')
            def current_user(request: Request):
                request.state.audit_actor = actor
                return actor
            def session():
                with factory() as db:
                    yield db
            from backend.app.core.database import get_session
            app = FastAPI()
            app.include_router(schools_router)
            app.dependency_overrides[get_current_user] = current_user
            app.dependency_overrides[get_session] = session
            with patch('backend.app.api.v1.admin.audit_route._get_sessionmaker', return_value=factory):
                response = TestClient(app).put('/schools/9999', json={'name': 'Escola'})
            self.assertEqual(response.status_code, 404)
            with factory() as db:
                self.assertEqual(db.scalar(select(AuditEvent)).result, 'denied')
            engine.dispose()
