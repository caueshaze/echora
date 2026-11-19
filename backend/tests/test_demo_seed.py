"""Integration checks use only an explicitly named, disposable loopback PostgreSQL database."""
import os
import subprocess
import sys
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from backend.app.api.v1.feedback import limiter, router
from backend.app.api.v1.admin.metrics import router as metrics_router
from backend.app.core.crypto import decrypt_feedback
from backend.app.core.database import get_session
from backend.app.core.security import get_current_user, verify_password
from backend.app.models import Feedback, School, User
from backend.app.schemas.user import UserPublic
from backend.scripts import seed_demo as seed

TEST_URL = os.getenv('ECHORA_DEMO_TEST_URL')
ACTOR = '00000000-0000-4000-8000-000000000001'


@unittest.skipUnless(TEST_URL, 'requires disposable ECHORA_DEMO_TEST_URL PostgreSQL database')
class DemoSeedTests(unittest.TestCase):
    def test_lifecycle_permissions_and_endpoints(self):
        url = make_url(TEST_URL)
        if url.host not in ('127.0.0.1', 'localhost', '::1') or url.database != 'echora_demo_test':
            self.fail('Tests require loopback PostgreSQL named echora_demo_test')
        engine = create_engine(TEST_URL)
        with Session(engine) as db, db.begin():
            if db.get(School, seed.SCHOOL_ID):
                self.fail('Test database must not contain a previous demo dataset')
            actor = db.get(User, ACTOR)
            if actor is None:
                db.add(User(id=ACTOR, email='operator@example.org', full_name='Operador de teste', role='admin', hashed_password='unchanged'))
            db.add(School(id=900001, name='Instituição externa fictícia'))
            db.add(User(id='outside', email='outside@example.org', full_name='Registro externo', role='gestor', school_id=900001, hashed_password='unchanged'))
        env = dict(os.environ, ECHORA_DEMO_DATABASE_URL=TEST_URL)
        preview = subprocess.run([sys.executable, '-m', 'backend.scripts.seed_demo', '--actor-id', ACTOR, '--dry-run'], env=env, capture_output=True, text=True)
        self.assertEqual(preview.returncode, 0, preview.stderr)
        self.assertIn('"feedbacks": 180', preview.stdout)
        with Session(engine) as db:
            self.assertIsNone(db.get(School, seed.SCHOOL_ID))
        with self.assertRaisesRegex(RuntimeError, 'falha simulada'):
            with Session(engine) as db, db.begin():
                with patch.object(seed, 'hash_password', return_value='isolated-test-hash'):
                    seed.create(db, ACTOR, fail_after='accounts')
        with Session(engine) as db:
            self.assertIsNone(db.get(School, seed.SCHOOL_ID))
            self.assertEqual(db.get(User, 'outside').hashed_password, 'unchanged')
        with Session(engine) as db, db.begin():
            report, credentials = seed.create(db, ACTOR)
            self.assertEqual(report['feedbacks'], 180)
            self.assertEqual(len(set(credentials.values())), 69)
            self.assertTrue(verify_password(credentials[seed.email('aluno', 0)], db.get(User, seed.uid('aluno', 0)).hashed_password))
            self.assertTrue(db.get(User, seed.uid('aluno', 0)).must_change_password)
        with Session(engine) as db, db.begin():
            report, credentials = seed.create(db, ACTOR)
            self.assertEqual((report, credentials), ({}, {}))
            self.assertEqual(db.scalar(select(func.count()).select_from(Feedback).where(Feedback.id.in_(seed.FEEDBACK_IDS))), 180)
            self.assertEqual(db.get(User, 'outside').hashed_password, 'unchanged')
            self.assertEqual(len({(f.created_at.year, f.created_at.month) for f in db.scalars(select(Feedback).where(Feedback.id.in_(seed.FEEDBACK_IDS)))}), 3)
            self.assertTrue(decrypt_feedback(db.get(Feedback, seed.FEEDBACK_IDS[0])))
            texts = [decrypt_feedback(f) for f in db.scalars(select(Feedback).where(Feedback.id.in_(seed.FEEDBACK_IDS)))]
            self.assertGreaterEqual(len(set(texts)), 120)
            labels = set(db.scalars(select(Feedback.sentiment_label).where(Feedback.id.in_(seed.FEEDBACK_IDS))))
            self.assertTrue({'positivo', 'negativo'} <= labels)
        app = FastAPI(); app.state.limiter = limiter
        app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
        limiter.reset(); app.include_router(router, prefix='/api/v1')
        app.include_router(metrics_router, prefix='/api/v1/admin')
        current = [None]
        app.dependency_overrides[get_current_user] = lambda: current[0]
        def session():
            with Session(engine) as db: yield db
        app.dependency_overrides[get_session] = session
        with TestClient(app) as client, patch('backend.app.core.llm._run_llm', return_value='Você pode conversar sobre os próximos passos.'):
            for role, index in [('aluno', 0), ('professor', 2), ('gestor', 0)]:
                with Session(engine) as db: current[0] = UserPublic.model_validate(db.get(User, seed.uid(role, index)))
                limiter.reset()
                result = client.get('/api/v1/feedback/summary/me')
                self.assertEqual(result.status_code, 200, result.text)
                self.assertIn('summary_text', result.json())
                limiter.reset()
                institution = client.get('/api/v1/feedback/summary/admin')
                self.assertEqual(institution.status_code, 200 if role == 'gestor' else 403, institution.text)
                if role == 'gestor':
                    listing = client.get('/api/v1/feedback/admin/all')
                    self.assertEqual(listing.status_code, 200, listing.text)
                    self.assertEqual(len(listing.json()), 180)
                    limiter.reset()
                    self.assertEqual(client.get('/api/v1/feedback/summary/admin', params={'school_id': 900001}).status_code, 403)
            with Session(engine) as db: current[0] = UserPublic.model_validate(db.get(User, ACTOR))
            metrics = client.get('/api/v1/admin/metrics/overview')
            self.assertEqual(metrics.status_code, 200, metrics.text)
            self.assertEqual(metrics.json()['counts']['total_feedbacks'], 180)
        with self.assertRaisesRegex(ValueError, 'referências externas'):
            with Session(engine) as db, db.begin():
                db.add(Feedback(sender_id='outside', target_type='user', target_id=seed.uid('aluno', 0),
                                content_encrypted='externo', nonce='n'))
                db.flush()
                seed.remove(db, ACTOR)
        with Session(engine) as db:
            self.assertIsNotNone(db.get(School, seed.SCHOOL_ID))
        with Session(engine) as db, db.begin():
            result = seed.remove(db, ACTOR)
            self.assertEqual(result['feedbacks'], 180)
        with Session(engine) as db, db.begin():
            self.assertIsNone(db.get(School, seed.SCHOOL_ID))
            self.assertEqual(db.get(User, 'outside').hashed_password, 'unchanged')
            db.delete(db.get(User, 'outside')); db.delete(db.get(School, 900001))
        engine.dispose()


if __name__ == '__main__': unittest.main()
