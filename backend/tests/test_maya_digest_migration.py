"""PostgreSQL tests create their own disposable tmpfs-backed container."""
import base64
import io
import json
import os
import subprocess
import sys
from pathlib import Path
import contextlib
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from threading import Event
from unittest.mock import patch
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session
from backend.app.core.config import Settings
from backend.app.core.crypto import encrypt_maya_content
from backend.app.core.database import Base
from backend.app.core.maya_idempotency import DEDICATED, LEGACY, request_digest
from backend.app.models import School, User
from backend.app.models.maya import MayaAnalysis, MayaConversation, MayaQuestion
from backend.app.schemas.user import UserPublic
from backend.app.services import maya_service
from backend.app.services.maya_digest_migration import DigestMigrationError, migrate_legacy_digests
from backend.scripts import migrate_maya_digests


def b64(value): return base64.b64encode(value).decode()


@unittest.skipUnless(os.getenv('ECHORA_ROTATION_RUN_PODMAN') == '1', 'requires a new disposable Podman container')
class MayaDigestPostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from backend.tests.test_data_encryption_rotation import RotationPostgresTests
        cls.container_fixture = RotationPostgresTests
        cls.container_fixture.setUpClass()
        cls.engine = cls.container_fixture.engine

    @classmethod
    def tearDownClass(cls):
        cls.container_fixture.tearDownClass()

    def setUp(self):
        Base.metadata.drop_all(self.engine)
        Base.metadata.create_all(self.engine)
        fixture = self.container_fixture
        env = dict(fixture.container_env, ECHORA_ROTATION_PODMAN_CONTAINER_ID=fixture.container_id,
                   ECHORA_ROTATION_INSTANCE=fixture.instance)
        self.envpatch = patch.dict(os.environ, env, clear=True); self.envpatch.start(); self.addCleanup(self.envpatch.stop)
        self.settings = Settings(_env_file=None, app_env='test', data_encryption_key=b64(bytes(range(32))),
                                 maya_idempotency_hmac_key=b64(bytes(range(32,64))),
                                 maya_idempotency_write_version=DEDICATED)
        for path in ('backend.app.core.crypto.get_settings', 'backend.app.services.maya_service.get_settings'):
            p = patch(path, return_value=self.settings); p.start(); self.addCleanup(p.stop)
        from backend.app.services.maya_hmac_control import initialize_identity
        with self.engine.begin() as conn:
            initialize_identity(conn, self.settings)
        self.user = UserPublic(id='u1', email='u1@example.com', full_name='Teste', role='aluno', school_id=1)
        self.aid, self.cid = str(uuid4()), str(uuid4())
        self.qids = [str(uuid4()) for _ in range(3)]
        self.keys = [str(uuid4()) for _ in range(3)]
        with Session(self.engine) as db:
            db.add(School(id=1, name='Teste'))
            db.add(User(id='u1', email='u1@example.com', full_name='Teste', role='aluno', school_id=1, hashed_password='x'))
            db.commit()
            cipher, nonce = encrypt_maya_content('relatório', kind='analysis', record_id=self.aid)
            db.add(MayaAnalysis(id=self.aid, requester_id='u1', school_id=1, kind='aluno',
                                content_encrypted=cipher, nonce=nonce, feedback_count=0, status='completed'))
            db.add(MayaConversation(id=self.cid, analysis_id=self.aid, user_id='u1'))
            db.flush()
            for index, qid in enumerate(self.qids):
                question = f'pergunta-{index}'
                encrypted, qnonce = encrypt_maya_content(question, kind='question', record_id=qid)
                answer, anonce = (encrypt_maya_content('resposta', kind='answer', record_id=qid) if index != 1 else (None, None))
                version = LEGACY if index < 2 else DEDICATED
                db.add(MayaQuestion(id=qid, conversation_id=self.cid, user_id='u1', request_key=self.keys[index],
                                    request_digest=request_digest(self.settings, self.aid, question, version),
                                    request_digest_version=version, question_encrypted=encrypted, question_nonce=qnonce,
                                    answer_encrypted=answer, answer_nonce=anonce, status='pending' if index == 1 else 'completed',
                                    reservation_id='reservation' if index == 1 else None, quota_date=date(2026,1,1)))
            db.commit()

    def snapshot(self):
        with self.engine.connect() as conn:
            return [dict(x) for x in conn.execute(text('SELECT * FROM public.maya_questions ORDER BY id')).mappings()]

    def test_migrates_atomically_without_touching_ciphertexts_or_reservations(self):
        before = self.snapshot()
        with self.engine.begin() as conn:
            counts, changed, after = migrate_legacy_digests(conn, self.settings)
        self.assertEqual((counts[LEGACY], counts[DEDICATED], changed, after[DEDICATED]), (2, 1, 2, 3))
        migrated = self.snapshot()
        for old, new in zip(before, migrated):
            self.assertEqual({k:v for k,v in old.items() if k not in ('request_digest', 'request_digest_version')},
                             {k:v for k,v in new.items() if k not in ('request_digest', 'request_digest_version')})
        with Session(self.engine) as db, patch('backend.app.core.llm._run_openai') as provider:
            self.assertEqual(maya_service.ask(db, self.user, self.aid, 'pergunta-0', self.keys[0])['answer'], 'resposta')
            with self.assertRaises(HTTPException) as conflict:
                maya_service.ask(db, self.user, self.aid, 'outra', self.keys[0])
            self.assertEqual(conflict.exception.status_code, 409)
            with self.assertRaises(HTTPException) as pending:
                maya_service.ask(db, self.user, self.aid, 'pergunta-1', self.keys[1])
            self.assertEqual(pending.exception.status_code, 409)
            provider.assert_not_called()
        with self.engine.begin() as conn:
            self.assertEqual(migrate_legacy_digests(conn, self.settings)[1], 0)
        self.assertEqual(migrated, self.snapshot())

    def test_failure_after_update_rolls_back_even_if_caller_catches(self):
        before = self.snapshot()
        def fail(): raise DigestMigrationError('falha simulada')
        with self.engine.begin() as conn:
            with self.assertRaises(DigestMigrationError): migrate_legacy_digests(conn, self.settings, after_update=fail)
        self.assertEqual(before, self.snapshot())

    def test_legacy_write_mode_blocks_migration(self):
        before = self.snapshot()
        self.settings.maya_idempotency_write_version = LEGACY
        with self.assertRaises(DigestMigrationError), self.engine.begin() as conn:
            migrate_legacy_digests(conn, self.settings)
        self.assertEqual(before, self.snapshot())

    def test_invalid_old_digest_and_tampered_question_abort_without_changes(self):
        for field, value in [('request_digest', '0'*64), ('question_nonce', 'AAAAAAAAAAAAAAAA')]:
            with self.subTest(field=field):
                with self.engine.begin() as conn:
                    conn.execute(text('UPDATE public.maya_questions SET ' + field + '=:value WHERE id=:id'),
                                 {'value': value, 'id': self.qids[0]})
                before = self.snapshot()
                with self.assertRaises(DigestMigrationError), self.engine.begin() as conn:
                    migrate_legacy_digests(conn, self.settings)
                self.assertEqual(before, self.snapshot())
                if field == 'request_digest':
                    restored = request_digest(self.settings, self.aid, 'pergunta-0', LEGACY)
                else:
                    # Regenerate a valid pair using the original plaintext, never touching other rows.
                    restored, nonce = encrypt_maya_content('pergunta-0', kind='question', record_id=self.qids[0])
                    with self.engine.begin() as conn:
                        conn.execute(text('UPDATE public.maya_questions SET question_encrypted=:cipher, question_nonce=:nonce WHERE id=:id'),
                                     {'cipher': restored, 'nonce': nonce, 'id': self.qids[0]})
                    continue
                with self.engine.begin() as conn:
                    conn.execute(text('UPDATE public.maya_questions SET request_digest=:digest WHERE id=:id'), {'digest': restored, 'id': self.qids[0]})

    def test_concurrent_writer_is_blocked_by_postgres_table_lock(self):
        started, release = Event(), Event()
        def after_update():
            started.set()
            if not release.wait(8): raise DigestMigrationError('tempo esgotado')
        def worker():
            with self.engine.begin() as conn:
                return migrate_legacy_digests(conn, self.settings, after_update=after_update)
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(worker)
            try:
                self.assertTrue(started.wait(8))
                with self.engine.connect() as conn:
                    with self.assertRaises(DBAPIError) as blocked:
                        with conn.begin():
                            conn.exec_driver_sql("SET LOCAL lock_timeout='200ms'")
                            conn.execute(text("UPDATE public.maya_questions SET status='failed' WHERE id=:id"), {'id': self.qids[1]})
                    self.assertEqual(blocked.exception.orig.sqlstate, '55P03')
            finally: release.set()
            self.assertEqual(future.result(timeout=10)[1], 2)

    def test_concurrent_dedicated_retries_consume_only_one_question(self):
        started, release, key = Event(), Event(), str(uuid4())
        def provider(*args, **kwargs):
            started.set()
            if not release.wait(8): raise RuntimeError('tempo esgotado')
            return 'resposta gerada'
        def ask():
            with Session(self.engine) as db:
                try: return maya_service.ask(db, self.user, self.aid, 'pergunta simultânea', key)
                except HTTPException as exc: return exc.status_code
        with patch('backend.app.core.llm._run_openai', side_effect=provider) as model, ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(ask)
            try:
                self.assertTrue(started.wait(8))
                self.assertEqual(pool.submit(ask).result(timeout=8), 409)
            finally: release.set()
            self.assertEqual(first.result(timeout=10)['answer'], 'resposta gerada')
            self.assertEqual(model.call_count, 1)
        with Session(self.engine) as db:
            self.assertEqual(maya_service.quota_status(db, self.user)['remaining'], 4)
            rows = db.scalars(select(MayaQuestion).where(MayaQuestion.request_key == key)).all()
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0].request_digest_version, DEDICATED)

    def test_corrupted_dedicated_digest_also_aborts_all_updates(self):
        with self.engine.begin() as conn:
            conn.execute(text("UPDATE public.maya_questions SET request_digest=:digest WHERE id=:id"),
                         {'digest': 'f' * 64, 'id': self.qids[2]})
        before = self.snapshot()
        with self.assertRaises(DigestMigrationError), self.engine.begin() as conn:
            migrate_legacy_digests(conn, self.settings)
        self.assertEqual(before, self.snapshot())

    def test_wrapper_requires_authorized_container_and_hides_secret(self):
        fixture = self.container_fixture
        target = fixture.url.render_as_string(hide_password=False)
        env = dict(fixture.container_env, APP_ENV='test', DATA_ENCRYPTION_KEY=b64(bytes(range(32))),
                   MAYA_IDEMPOTENCY_HMAC_KEY=b64(bytes(range(32,64))), MAYA_IDEMPOTENCY_WRITE_VERSION=DEDICATED,
                   ECHORA_MAYA_DIGEST_DATABASE_URL=target,
                   ECHORA_ROTATION_PODMAN_CONTAINER_ID=fixture.container_id, ECHORA_ROTATION_INSTANCE=fixture.instance)
        out, err = io.StringIO(), io.StringIO()
        with patch.dict(os.environ, env, clear=True), contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            self.assertEqual(migrate_maya_digests.main(['--apply-test']), 0)
        self.assertIn('alterados=2', out.getvalue())
        for secret in (fixture.password, target, env['DATA_ENCRYPTION_KEY'], env['MAYA_IDEMPOTENCY_HMAC_KEY'], 'pergunta-0'):
            self.assertNotIn(secret, out.getvalue() + err.getvalue())
        env['ECHORA_ROTATION_INSTANCE'] = '0' * 32
        with patch.dict(os.environ, env, clear=True), contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            self.assertEqual(migrate_maya_digests.main(['--apply-test']), 1)

    def test_postgres_schema_upgrade_preserves_old_writer_default(self):
        root = Path(__file__).resolve().parents[2]
        with self.engine.begin() as conn:
            conn.exec_driver_sql('ALTER TABLE public.maya_questions DROP COLUMN request_digest_version')
            conn.exec_driver_sql('DROP TABLE IF EXISTS public.alembic_version')
        env = dict(self.container_fixture.container_env, APP_ENV='test',
                   MIGRATION_DATABASE_URL=self.container_fixture.url.render_as_string(hide_password=False))
        try:
            for args in (['stamp', 'a7d41e6b2c90'], ['upgrade', 'b7c84f219c20']):
                run = subprocess.run([sys.executable, '-m', 'alembic', *args], cwd=root, env=env,
                                     capture_output=True, text=True, timeout=30)
                self.assertEqual(run.returncode, 0, 'alembic failed in disposable database')
            with self.engine.connect() as conn:
                self.assertEqual(conn.scalar(text("SELECT count(*) FROM public.maya_questions WHERE request_digest_version='legacy-v1'")), 3)
                self.assertEqual(conn.scalar(text("SELECT column_default FROM information_schema.columns WHERE table_schema='public' AND table_name='maya_questions' AND column_name='request_digest_version'")), "'legacy-v1'::character varying")
            with self.engine.begin() as conn:
                conn.execute(text("UPDATE public.maya_questions SET request_digest_version='hmac-v2' WHERE id=:id"), {'id': self.qids[0]})
            downgrade = subprocess.run([sys.executable, '-m', 'alembic', 'downgrade', 'a7d41e6b2c90'], cwd=root,
                                       env=env, capture_output=True, text=True, timeout=30)
            self.assertNotEqual(downgrade.returncode, 0)
            with self.engine.connect() as conn:
                self.assertEqual(conn.scalar(text('SELECT request_digest_version FROM public.maya_questions WHERE id=:id'),
                                             {'id': self.qids[0]}), DEDICATED)
        finally:
            with self.engine.begin() as conn:
                conn.exec_driver_sql('DROP TABLE IF EXISTS public.alembic_version')


if __name__ == '__main__': unittest.main()
