import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from backend.app.api.v1.feedback import router
from backend.app.api.v1.admin.users import router as users_router
from backend.app.api.v1.admin.schools import router as schools_router
from backend.app.core.database import Base, get_session
from backend.app.core.security import get_current_user
from backend.app.models import Feedback, TeacherAssignment, User
from backend.app.models.organization import Classroom, School, Subject
from backend.app.schemas.user import UserPublic


class FeedbackRecipientTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
        self.engine = engine
        Base.metadata.create_all(engine)
        self.db = Session(engine, expire_on_commit=False)
        self.db.add_all([School(id=1, name='Escola A'), School(id=2, name='Escola B')])
        self.db.add_all([Classroom(id=1, name='A1', school_id=1), Classroom(id=2, name='A2', school_id=1), Classroom(id=3, name='B1', school_id=2), Subject(id=1, name='Math', school_id=1)])
        users = [
            ('admin', 'admin', None, None), ('admin2', 'admin', None, None),
            ('manager', 'gestor', 1, None), ('manager2', 'gestor', 2, None),
            ('teacher', 'professor', 1, None), ('teacher2', 'professor', 1, None),
            ('student', 'aluno', 1, 1), ('student2', 'aluno', 1, 2),
            ('outside', 'aluno', 2, 3), ('orphan', 'aluno', None, None),
            ('no_class', 'aluno', 1, None),
        ]
        self.users = {}
        for identifier, role, school, classroom in users:
            user = User(id=identifier, email=f'{identifier}@example.com', full_name=identifier, role=role, school_id=school, classroom_id=classroom, hashed_password='x')
            self.users[identifier] = user
            self.db.add(user)
        self.db.add(TeacherAssignment(classroom_id=1, subject_id=1, teacher_id='teacher'))
        self.db.commit()
        self.sender = 'student'
        app = FastAPI()
        app.include_router(router, prefix='/api/v1')
        app.include_router(users_router, prefix='/api/v1/admin')
        app.include_router(schools_router, prefix='/api/v1/admin')
        app.dependency_overrides[get_current_user] = lambda: UserPublic.model_validate(self.users[self.sender])
        app.dependency_overrides[get_session] = lambda: self.db
        self.client = TestClient(app)
        self.patches = [
            patch('backend.app.api.v1.feedback.analyze_sentiment', return_value=('positivo', 0.9)),
            patch('backend.app.api.v1.feedback.encrypt_feedback', return_value=('cipher', 'nonce')),
            patch('backend.app.api.v1.feedback_utils.decrypt_feedback', return_value='feedback'),
        ]
        self.mocks = [p.start() for p in self.patches]

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.db.close()
        self.engine.dispose()

    def post(self, target, anonymous=False):
        return self.client.post('/api/v1/feedback', json={'target_type': 'user', 'target_id': target, 'content': 'feedback', 'is_anonymous': anonymous})

    def test_allowed_matrix_and_relationships(self):
        for sender, target in [('student', 'teacher'), ('student', 'manager'), ('teacher', 'student'), ('teacher', 'manager'), ('manager', 'student2'), ('manager', 'teacher'), ('admin', 'outside'), ('admin', 'admin2')]:
            with self.subTest(sender=sender, target=target):
                self.sender = sender
                response = self.post(target)
                self.assertEqual(response.status_code, 201, response.text)
                self.assertEqual(response.json()['target_id'], target)

    def test_rejected_targets_do_not_process_or_store(self):
        for sender, target in [('student', 'student'), ('student', 'student2'), ('student', 'outside'), ('student', 'teacher2'), ('student', 'manager2'), ('teacher', 'student2'), ('teacher', 'teacher2'), ('teacher', 'outside'), ('manager', 'manager2'), ('manager', 'admin'), ('orphan', 'manager'), ('no_class', 'teacher'), ('admin', 'admin')]:
            with self.subTest(sender=sender, target=target):
                self.sender = sender
                response = self.post(target, anonymous=True)
                self.assertEqual(response.status_code, 404, response.text)
                self.assertNotIn('@example.com', response.text)
        self.assertEqual(self.db.scalar(select(func.count()).select_from(Feedback)), 0)
        self.mocks[0].assert_not_called()
        self.mocks[1].assert_not_called()

    def test_recipient_list_uses_same_scope(self):
        for sender, role, expected in [('student', 'professor', {'teacher'}), ('student', 'aluno', set()), ('teacher', 'aluno', {'student'}), ('manager', 'aluno', {'student', 'student2', 'no_class'}), ('admin', 'aluno', {'student', 'student2', 'outside', 'orphan', 'no_class'})]:
            with self.subTest(sender=sender, role=role):
                self.sender = sender
                response = self.client.get('/api/v1/feedback/available/recipients', params={'role': role})
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual({user['id'] for user in response.json()}, expected)

    def test_school_and_user_directories_are_scoped_and_minimized(self):
        self.users['admin2'].school_id = 1
        self.db.commit()
        self.sender = 'manager'
        response = self.client.get('/api/v1/admin/schools')
        self.assertEqual(response.status_code, 200)
        self.assertEqual([school['id'] for school in response.json()], [1])
        response = self.client.get('/api/v1/admin/users')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(all(user['school_id'] == 1 and user['role'] != 'admin' for user in response.json()))
        for sender, role, expected in [('student', 'aluno', set()), ('student', 'professor', {'teacher'}), ('teacher', 'aluno', {'student'})]:
            self.sender = sender
            response = self.client.get('/api/v1/admin/users', params={'role': role})
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual({user['id'] for user in response.json()}, expected)
            self.assertTrue(all(set(user) == {'id', 'full_name', 'role'} for user in response.json()))
        self.sender = 'admin'
        self.assertEqual(len(self.client.get('/api/v1/admin/schools').json()), 2)
        response = self.client.get('/api/v1/admin/users')
        self.assertTrue(any(user['id'] == 'outside' for user in response.json()))
        self.sender = 'student'
        self.assertEqual(self.client.get('/api/v1/admin/schools').status_code, 403)
        self.assertEqual(self.client.get('/api/v1/admin/users').status_code, 403)


if __name__ == '__main__':
    unittest.main()
