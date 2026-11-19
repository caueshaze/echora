"""Identity and cutover tests; PostgreSQL tests use a self-created disposable container."""
import base64
import os
import subprocess
import sys
import unittest
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.core.config import Settings
from backend.app.core.database import Base
from backend.app.main import create_app
from backend.app.services.maya_hmac_control import (
    MayaControlError, activate_legacy_barrier, check_maya_compatibility,
    initialize_identity, key_identity,
)
from backend.tests.test_maya_digest_migration import MayaDigestPostgresTests


def settings(byte):
    return Settings(_env_file=None, app_env='test', data_encryption_key=base64.b64encode(bytes(range(32))).decode(),
                    maya_idempotency_hmac_key=base64.b64encode(bytes(range(byte, byte+32))).decode(),
                    maya_idempotency_write_version='hmac-v2')


class ControlUnitTests(unittest.TestCase):
    def test_identity_and_schema_fail_closed(self):
        engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
        Base.metadata.create_all(engine)
        one, two = settings(42), settings(43)
        with engine.begin() as conn:
            with self.assertRaises(MayaControlError): check_maya_compatibility(conn, one)
            compatible = settings(42)
            compatible.maya_idempotency_write_version = 'legacy-v1'
            check_maya_compatibility(conn, compatible)
            compatible.app_env = 'production'
            with self.assertRaises(MayaControlError): check_maya_compatibility(conn, compatible)
            conn.execute(text('INSERT INTO maya_hmac_control VALUES (1,:identity,false)'), {'identity': key_identity(one)})
        with Session(engine) as first, Session(engine) as second:
            check_maya_compatibility(first, one)
            with self.assertRaises(MayaControlError): check_maya_compatibility(second, two)
        with engine.begin() as conn:
            conn.execute(text('ALTER TABLE maya_questions RENAME TO old_questions'))
            conn.execute(text('CREATE TABLE maya_questions (id TEXT)'))
        with Session(engine) as db:
            with self.assertRaises(Exception): check_maya_compatibility(db, one)
        engine.dispose()

    def test_readiness_schema_and_generic_errors(self):
        engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
        Base.metadata.create_all(engine)
        config = settings(42)
        with engine.begin() as conn:
            conn.execute(text('INSERT INTO maya_hmac_control VALUES (1,:identity,false)'), {'identity': key_identity(config)})
        with patch('backend.app.main.get_settings', return_value=config): app = create_app()
        from backend.app.core.config import get_settings
        from backend.app.core.database import get_session
        app.dependency_overrides[get_settings] = lambda: config
        def session_override():
            with Session(engine) as db:
                yield db
        app.dependency_overrides[get_session] = session_override
        with patch('backend.app.main._get_sessionmaker', return_value=sessionmaker(bind=engine)):
            client = TestClient(app)
            self.assertEqual(client.get('/health/ready').status_code, 200)
            with engine.begin() as conn:
                conn.execute(text('ALTER TABLE maya_questions RENAME TO old_questions'))
                conn.execute(text('CREATE TABLE maya_questions (id TEXT)'))
            response = client.get('/health/ready')
            self.assertEqual((response.status_code, response.json()), (503, {'status': 'unavailable'}))
            response = client.get('/api/v1/maya/analyses')
            self.assertEqual(response.status_code, 503)
            self.assertNotIn('request_digest_version', response.text)
        with patch('backend.app.main._get_sessionmaker', side_effect=RuntimeError('secret-value')):
            self.assertNotIn('secret-value', TestClient(app).get('/health/ready').text)
        engine.dispose()


@unittest.skipUnless(os.getenv('ECHORA_ROTATION_RUN_PODMAN') == '1', 'requires disposable Podman')
class ControlPostgresTests(MayaDigestPostgresTests):
    def clear_questions(self):
        with self.engine.begin() as conn:
            conn.execute(text('DELETE FROM maya_questions'))

    def insert_old(self, conn):
        conn.execute(text("""INSERT INTO maya_questions
            (id, conversation_id, user_id, request_key, request_digest, question_encrypted,
             question_nonce, status, quota_date)
            VALUES (:id,:conversation,'u1',:key,'digest','cipher','nonce','completed','2026-01-01')"""),
            {'id': str(uuid4()), 'conversation': self.cid, 'key': str(uuid4())})

    def test_identity_mismatch_and_existing_legacy_refuse_cutover(self):
        with self.engine.begin() as conn:
            initialize_identity(conn, self.settings)
            with self.assertRaises(MayaControlError): initialize_identity(conn, settings(43))
            with self.assertRaises(MayaControlError): check_maya_compatibility(conn, settings(43))
            with self.assertRaises(MayaControlError): activate_legacy_barrier(conn, self.settings)
            self.assertEqual(conn.scalar(text('SELECT count(*) FROM maya_questions')), 3)
            self.assertFalse(conn.scalar(text('SELECT legacy_barrier FROM maya_hmac_control')))

    def test_rollback_and_old_writer_after_commit(self):
        self.clear_questions()
        with self.engine.connect() as before, self.engine.connect() as operator:
            old_tx = before.begin()
            before.execute(text('SELECT 1'))
            tx = operator.begin()
            activate_legacy_barrier(operator, self.settings)
            tx.rollback()
            self.insert_old(before)
            old_tx.commit()
        self.clear_questions()
        with self.engine.connect() as before:
            old_tx = before.begin()
            before.execute(text('SELECT 1'))
            with self.engine.begin() as operator:
                activate_legacy_barrier(operator, self.settings)
            with self.assertRaises(DBAPIError) as exc: self.insert_old(before)
            self.assertEqual(exc.exception.orig.sqlstate, '23514')
            old_tx.rollback()
        with self.engine.begin() as conn:
            check_maya_compatibility(conn, self.settings)
            bad = settings(32); bad.maya_idempotency_write_version = 'legacy-v1'
            with self.assertRaises(MayaControlError): check_maya_compatibility(conn, bad)

    def test_concurrent_writer_is_blocked_then_rejected(self):
        self.clear_questions()
        locked, release = Event(), Event()
        def activate():
            with self.engine.begin() as conn:
                activate_legacy_barrier(conn, self.settings)
                locked.set()
                self.assertTrue(release.wait(4))
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(activate)
            try:
                self.assertTrue(locked.wait(4))
                with self.engine.begin() as conn:
                    conn.exec_driver_sql("SET LOCAL lock_timeout='200ms'")
                    with self.assertRaises(DBAPIError) as exc: self.insert_old(conn)
                    self.assertEqual(exc.exception.orig.sqlstate, '55P03')
            finally:
                release.set()
            future.result()
        with self.engine.begin() as conn:
            with self.assertRaises(DBAPIError) as exc: self.insert_old(conn)
            self.assertEqual(exc.exception.orig.sqlstate, '23514')

    def test_inflight_legacy_commit_prevents_cutover(self):
        self.clear_questions()
        with self.engine.connect() as writer:
            tx = writer.begin()
            self.insert_old(writer)
            started = Event()
            def activate():
                with self.engine.begin() as conn:
                    started.set()
                    with self.assertRaises(MayaControlError): activate_legacy_barrier(conn, self.settings)
            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(activate)
                self.assertTrue(started.wait(3))
                tx.commit()
                future.result()
        with self.engine.connect() as conn:
            self.assertEqual(conn.scalar(text('SELECT count(*) FROM maya_questions')), 1)
            self.assertFalse(conn.scalar(text('SELECT legacy_barrier FROM maya_hmac_control')))

    def test_application_role_cannot_initialize_or_remove_barrier(self):
        self.clear_questions()
        role = 'maya_test_' + uuid4().hex
        try:
            with self.engine.begin() as conn:
                conn.exec_driver_sql(f'CREATE ROLE {role} NOLOGIN')
                conn.exec_driver_sql(f'GRANT USAGE ON SCHEMA public TO {role}')
                conn.exec_driver_sql(f'GRANT SELECT ON maya_hmac_control, maya_questions TO {role}')
            with self.engine.begin() as conn:
                conn.exec_driver_sql(f'SET LOCAL ROLE {role}')
                with self.assertRaises(DBAPIError) as exc:
                    conn.execute(text('DELETE FROM maya_hmac_control'))
                self.assertEqual(exc.exception.orig.sqlstate, '42501')
            with self.engine.begin() as conn:
                conn.exec_driver_sql(f'SET LOCAL ROLE {role}')
                with self.assertRaises(DBAPIError) as exc:
                    conn.exec_driver_sql('ALTER TABLE maya_questions ADD CONSTRAINT unauthorized CHECK (true)')
                self.assertEqual(exc.exception.orig.sqlstate, '42501')
        finally:
            with self.engine.begin() as conn:
                conn.exec_driver_sql(f'DROP OWNED BY {role}')
                conn.exec_driver_sql(f'DROP ROLE {role}')

    def test_control_schema_upgrade_keeps_old_writers(self):
        root = Path(__file__).resolve().parents[2]
        with self.engine.begin() as conn:
            conn.exec_driver_sql('DROP TABLE maya_hmac_control')
            conn.exec_driver_sql('DROP TABLE IF EXISTS alembic_version')
        env = dict(self.container_fixture.container_env, APP_ENV='test',
                   MIGRATION_DATABASE_URL=self.container_fixture.url.render_as_string(hide_password=False))
        try:
            for args in (['stamp', 'b7c84f219c20'], ['upgrade', 'd4c765128fa2']):
                result = subprocess.run([sys.executable, '-m', 'alembic', *args], cwd=root,
                                        env=env, capture_output=True, timeout=30)
                self.assertEqual(result.returncode, 0, 'migration failed on disposable database')
            with self.engine.begin() as conn:
                self.assertEqual(conn.scalar(text('SELECT count(*) FROM maya_hmac_control')), 0)
                self.insert_old(conn)
                self.assertEqual(conn.scalar(text("SELECT count(*) FROM maya_questions WHERE request_digest_version='legacy-v1'")), 3)
        finally:
            with self.engine.begin() as conn:
                conn.exec_driver_sql('DROP TABLE IF EXISTS alembic_version')
