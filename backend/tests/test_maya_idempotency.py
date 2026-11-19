"""Versioned HMAC compatibility tests; network and provider calls are mocked."""
import base64
import hashlib
import hmac
import json
import os
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from uuid import uuid4

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from backend.app.core.config import Settings
from backend.app.core.database import Base
from backend.app.core.maya_idempotency import DEDICATED, LEGACY, matches_digest, request_digest
from backend.app.models import School, User
from backend.app.models.maya import MayaQuestion
from backend.app.schemas.user import UserPublic
from backend.app.services import maya_service


def enc(value): return base64.b64encode(value).decode()


class MayaHmacSettingsTests(unittest.TestCase):
    def setUp(self):
        self.aes, self.hmac = bytes(range(32)), bytes(range(32, 64))
        self.base = dict(_env_file=None, app_env='production', database_url='postgresql+psycopg://u:p@localhost/test',
                         rate_limit_storage_uri='redis://localhost:6379/0',
                         secret_key='d1b3f29c80a4e75d947d670c5be839a23f91ca3e5b22a61f1cd8b9e05841ef72',
                         data_encryption_key=enc(self.aes), maya_idempotency_hmac_key=enc(self.hmac))

    def test_production_rejects_missing_invalid_or_reused_key_without_leak(self):
        for value in ('', 'bad!', enc(b'x' * 32), enc(b'123'), enc(self.aes), enc(bytes.fromhex(self.base['secret_key']))):
            with self.subTest(case=len(value)), self.assertRaises(ValidationError) as ex:
                Settings(**(self.base | {'maya_idempotency_hmac_key': value}))
            if value: self.assertNotIn(value, str(ex.exception))
        with self.assertRaises(ValidationError):
            Settings(**(self.base | {'data_encryption_keys': '{"v2":"' + enc(self.hmac) + '"}'}))
        settings = Settings(**self.base)
        self.assertEqual(settings.idempotency_hmac_key_bytes(), self.hmac)
        self.assertNotIn(self.base['maya_idempotency_hmac_key'], repr(settings))
        self.assertNotIn('maya_idempotency_hmac_key', settings.model_dump())

    def test_legacy_compatible_dedicated_independent_and_domain_separated(self):
        settings = Settings(**self.base)
        old = request_digest(settings, 'analysis', 'pergunta', LEGACY)
        original = hmac.new(self.aes, b'maya-question-v1:' + json.dumps(['analysis', 'ação e educação'], ensure_ascii=False).encode(), hashlib.sha256).hexdigest()
        self.assertEqual(request_digest(settings, 'analysis', 'ação e educação', LEGACY), original)
        new = request_digest(settings, 'analysis', 'pergunta', DEDICATED)
        self.assertNotEqual(old, new)
        self.assertTrue(matches_digest(settings, 'analysis', 'pergunta', LEGACY, old))
        self.assertFalse(matches_digest(settings, 'analysis', 'outra', LEGACY, old))
        replaced = Settings(**(self.base | {'data_encryption_key': enc(bytes(range(64, 96)))}))
        self.assertEqual(new, request_digest(replaced, 'analysis', 'pergunta', DEDICATED))
        with patch.object(Settings, 'encryption_key_bytes', side_effect=AssertionError('AES não deve ser consultada')):
            self.assertEqual(new, request_digest(settings, 'analysis', 'pergunta', DEDICATED))
        with self.assertRaises(ValueError): request_digest(settings, 'analysis', 'pergunta', 'unknown')

    def test_dev_activation_still_requires_key(self):
        with self.assertRaises(ValidationError):
            Settings(_env_file=None, app_env='test', maya_idempotency_write_version='hmac-v2')
        self.assertEqual(Settings(_env_file=None, app_env='test').maya_idempotency_write_version, LEGACY)


class MayaHmacServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.engine = create_engine('sqlite:///' + self.temp.name + '/maya.db', connect_args={'timeout': 20})
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.settings = Settings(_env_file=None, app_env='test', data_encryption_key=enc(bytes(range(32))),
                                 maya_idempotency_hmac_key=enc(bytes(range(32,64))), maya_daily_question_limit=5)
        from backend.app.models.maya import MayaHmacControl
        from backend.app.services.maya_hmac_control import key_identity
        self.db.add(MayaHmacControl(id=1, key_identity=key_identity(self.settings), legacy_barrier=False))
        self.patches = [patch('backend.app.core.crypto.get_settings', return_value=self.settings),
                        patch('backend.app.services.maya_service.get_settings', return_value=self.settings)]
        for p in self.patches: p.start(); self.addCleanup(p.stop)
        self.db.add(School(id=1, name='Escola'))
        self.db.add(User(id='u1', email='u1@example.com', full_name='Teste', role='aluno', school_id=1, hashed_password='x'))
        self.db.commit()
        self.user = UserPublic(id='u1', email='u1@example.com', full_name='Teste', role='aluno', school_id=1)
        self.report = maya_service.create_analysis(self.db, self.user, 'Relatório', 'aluno', 1, {})
        self.report_id = self.report.id

    def tearDown(self):
        self.db.close(); self.engine.dispose(); self.temp.cleanup()

    def test_old_replay_new_version_and_conflicts(self):
        first_key, second_key = str(uuid4()), str(uuid4())
        with patch('backend.app.core.llm._run_openai', return_value='Resposta.') as model:
            first = maya_service.ask(self.db, self.user, self.report_id, 'Pergunta antiga', first_key)
            old = self.db.get(MayaQuestion, first['id'])
            self.assertEqual(old.request_digest_version, LEGACY)
            old_cipher, old_nonce = old.question_encrypted, old.question_nonce
            self.settings.maya_idempotency_write_version = DEDICATED
            self.assertEqual(maya_service.ask(self.db, self.user, self.report_id, 'Pergunta antiga', first_key)['id'], first['id'])
            with self.assertRaises(HTTPException) as conflict:
                maya_service.ask(self.db, self.user, self.report_id, 'Outro conteúdo', first_key)
            self.assertEqual(conflict.exception.status_code, 409)
            second = maya_service.ask(self.db, self.user, self.report_id, 'Pergunta nova', second_key)
            self.assertEqual(self.db.get(MayaQuestion, second['id']).request_digest_version, DEDICATED)
            self.assertEqual((old.question_encrypted, old.question_nonce), (old_cipher, old_nonce))
            self.assertEqual(model.call_count, 2)
            self.assertEqual(maya_service.quota_status(self.db, self.user)['remaining'], 3)

    def test_simultaneous_replay_of_dedicated_request_reserves_once(self):
        self.settings.maya_idempotency_write_version = DEDICATED
        key = str(uuid4()); started, release = threading.Event(), threading.Event()
        def provider(*args, **kwargs):
            started.set()
            if not release.wait(5): raise RuntimeError('test timeout')
            return 'Resposta.'
        def ask():
            with Session(self.engine) as db:
                try: return maya_service.ask(db, self.user, self.report_id, 'Pergunta', key)
                except HTTPException as exc: return exc.status_code
        with patch('backend.app.core.llm._run_openai', side_effect=provider) as model, ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(ask)
            try:
                self.assertTrue(started.wait(5))
                self.assertEqual(pool.submit(ask).result(timeout=5), 409)
            finally: release.set()
            self.assertEqual(first.result(timeout=5)['answer'], 'Resposta.')
            self.assertEqual(model.call_count, 1)
        self.assertEqual(maya_service.quota_status(self.db, self.user)['remaining'], 4)

    def test_unknown_version_fails_closed_without_consuming(self):
        key = str(uuid4())
        with patch('backend.app.core.llm._run_openai', return_value='Resposta.'):
            result = maya_service.ask(self.db, self.user, self.report_id, 'Pergunta', key)
        self.db.get(MayaQuestion, result['id']).request_digest_version = 'invalid'
        self.db.commit()
        with self.assertRaises(HTTPException) as ex:
            maya_service.ask(self.db, self.user, self.report_id, 'Pergunta', key)
        self.assertEqual(ex.exception.status_code, 503)
        self.assertEqual(maya_service.quota_status(self.db, self.user)['remaining'], 4)


class MayaSchemaMigrationTests(unittest.TestCase):
    def test_schema_upgrade_keeps_legacy_writers_and_refuses_unsafe_downgrade(self):
        from alembic import command
        from alembic.config import Config
        from pathlib import Path
        root = Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory() as directory:
            url = 'sqlite:///' + directory + '/isolated.db'
            engine = create_engine(url)
            with engine.begin() as conn:
                conn.execute(text('CREATE TABLE maya_questions (id text primary key, request_digest text not null)'))
                conn.execute(text("INSERT INTO maya_questions VALUES ('old', 'old-digest')"))
            cfg = Config(str(root / 'alembic.ini'))
            cfg.set_main_option('script_location', str(root / 'migrations'))
            # Avoid Alembic's fileConfig disabling unrelated in-process loggers.
            cfg.config_file_name = None
            with patch.dict(os.environ, {'MIGRATION_DATABASE_URL': url}):
                command.stamp(cfg, 'a7d41e6b2c90')
                command.upgrade(cfg, 'b7c84f219c20')
                with engine.begin() as conn:
                    self.assertEqual(conn.scalar(text("SELECT request_digest_version FROM maya_questions WHERE id='old'")), LEGACY)
                    conn.execute(text("INSERT INTO maya_questions (id, request_digest) VALUES ('old-writer', 'd')"))
                    self.assertEqual(conn.scalar(text("SELECT request_digest_version FROM maya_questions WHERE id='old-writer'")), LEGACY)
                    conn.execute(text("UPDATE maya_questions SET request_digest_version='hmac-v2' WHERE id='old'"))
                with self.assertRaisesRegex(RuntimeError, 'Downgrade recusado'):
                    command.downgrade(cfg, 'a7d41e6b2c90')
                with engine.connect() as conn:
                    self.assertEqual(conn.scalar(text("SELECT request_digest_version FROM maya_questions WHERE id='old'")), DEDICATED)
            engine.dispose()


if __name__ == '__main__': unittest.main()
