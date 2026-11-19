"""Rotation checks. PostgreSQL tests create and destroy their own isolated container.

Set ECHORA_ROTATION_RUN_PODMAN=1 to run them. No existing database URL is used.
"""
from __future__ import annotations
import base64
import contextlib
import hashlib
import hmac
import io
import json
import os
import secrets
import subprocess
import sys
import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from threading import Event
from unittest.mock import patch
from uuid import uuid4
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from fastapi import HTTPException
from sqlalchemy import create_engine, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from backend.app.core.config import Settings
from backend.app.core.crypto import _aad, _keys, decrypt_feedback, decrypt_maya_content, encrypt_feedback, encrypt_maya_content
from backend.app.core.database import Base
from backend.app.models import Feedback, School, User
from backend.app.models.maya import MayaAnalysis, MayaConversation, MayaQuestion
from backend.app.schemas.user import UserPublic
from backend.app.services import maya_service
from backend.scripts import rotate_data_encryption as rotation


def b64(value):
    return base64.b64encode(value).decode('ascii')


class RotationUnitTests(unittest.TestCase):
    def setUp(self):
        self.v1, self.v2 = bytes(range(32)), bytes(range(32, 64))
        self.settings = Settings(_env_file=None, app_env='test', data_encryption_key=b64(self.v1),
                                 data_encryption_keys=json.dumps({'v2': b64(self.v2)}))

    def test_key_versions_must_be_unambiguous(self):
        invalid = ['{"v1":"' + b64(self.v1) + '"}',
                   '{"v2":"' + b64(self.v2) + '","v2":"' + b64(self.v2) + '"}',
                   json.dumps({'v02': b64(self.v2)}), json.dumps({'v2': 'invalid'}),
                   json.dumps({'v2': b64(b'short')}), json.dumps({'v2': b64(self.v1)}),
                   json.dumps({'v2': b64(self.v2), 'v3': b64(self.v2)}), '[]']
        for configured in invalid:
            with self.subTest(case=invalid.index(configured)):
                self.settings.data_encryption_keys = configured
                with self.assertRaises(ValueError) as exc: _keys(self.settings)
                self.assertNotIn(configured, str(exc.exception))
        self.settings.data_encryption_keys = json.dumps({'v1': b64(self.v1)})
        with self.assertRaisesRegex(ValueError, 'não pode redefinir a versão v1'):
            _keys(self.settings)
        self.settings.data_encryption_keys = '{}'
        self.settings.data_encryption_active_key = 'v2'
        with self.assertRaises(ValueError): _keys(self.settings)

    def test_invalid_targets_rejected_before_connecting(self):
        invalid = ['', 'sqlite:///echora_restore_test', 'postgresql://u:p@localhost/echora',
                   'postgresql://u:p@localhost/echora_restore_', 'postgresql://u:p@localhost/other',
                   'postgresql://u:p@localhost/echora_restore_test?host=other',
                   'postgresql://u:p@localhost/echora_restore_test?options=-csearch_path%3Devil',
                   'postgresql://u:p@/echora_restore_test', 'postgresql://u:p@localhost/echora_restore_test#fragment']
        for target in invalid:
            with self.subTest(case=invalid.index(target)), patch.object(rotation, 'create_engine') as factory:
                with self.assertRaises(rotation.RotationError): rotation.run_rotation(target, self.settings, apply=False)
                factory.assert_not_called()
        self.assertEqual(rotation.validate_database_url('postgresql://u:p@127.0.0.1:5432/echora_restore_test').database, 'echora_restore_test')

    def test_remote_host_and_missing_explicit_port_are_rejected(self):
        for target in ('postgresql://u:p@localhost:5432/echora_restore_test',
                       'postgresql://u:p@192.0.2.10:5432/echora_restore_test',
                       'postgresql://u:p@127.0.0.1/echora_restore_test'):
            with self.subTest(target=target), patch.object(rotation, 'create_engine') as factory:
                with self.assertRaises(rotation.RotationError): rotation.run_rotation(target, self.settings, apply=False)
                factory.assert_not_called()

    def test_container_identity_must_match_before_database_connection(self):
        from sqlalchemy.engine import make_url
        target = make_url('postgresql://u:p@127.0.0.1:45678/echora_restore_test')
        container_id, instance = 'a' * 64, 'b' * 32
        env = {'ECHORA_ROTATION_PODMAN_CONTAINER_ID': container_id, 'ECHORA_ROTATION_INSTANCE': instance}
        cases = [
            ['c' * 64, True, 'disposable', instance, {'5432/tcp': [{'HostIp': '127.0.0.1', 'HostPort': '45678'}]}],
            [container_id, False, 'disposable', instance, {'5432/tcp': [{'HostIp': '127.0.0.1', 'HostPort': '45678'}]}],
            [container_id, True, 'production', instance, {'5432/tcp': [{'HostIp': '127.0.0.1', 'HostPort': '45678'}]}],
            [container_id, True, 'disposable', 'c' * 32, {'5432/tcp': [{'HostIp': '127.0.0.1', 'HostPort': '45678'}]}],
            [container_id, True, 'disposable', instance, {'5432/tcp': [{'HostIp': '0.0.0.0', 'HostPort': '45678'}]}],
            [container_id, True, 'disposable', instance, {'5432/tcp': [{'HostIp': '127.0.0.1', 'HostPort': '45679'}]}],
        ]
        for values in cases:
            result = subprocess.CompletedProcess([], 0, stdout='\n'.join(json.dumps(x) for x in [*values, True, [], {'/var/lib/postgresql/data': 'rw'}, False]))
            with self.subTest(case=cases.index(values)), patch.dict(os.environ, env, clear=True), \
                 patch.object(rotation.subprocess, 'run', return_value=result), patch.object(rotation, 'create_engine') as factory:
                with self.assertRaises(rotation.RotationError):
                    rotation.run_rotation(str(target), self.settings, apply=True)
                factory.assert_not_called()
        with patch.dict(os.environ, {}, clear=True), patch.object(rotation, 'create_engine') as factory:
            with self.assertRaises(rotation.RotationError): rotation.run_rotation(str(target), self.settings, apply=False)
            factory.assert_not_called()
        with patch.dict(os.environ, {**env, 'CONTAINER_HOST': 'ssh://remote.invalid'}, clear=True), \
             patch.object(rotation.subprocess, 'run') as inspect, patch.object(rotation, 'create_engine') as factory:
            with self.assertRaises(rotation.RotationError): rotation.run_rotation(str(target), self.settings, apply=False)
            inspect.assert_not_called(); factory.assert_not_called()
        good = [container_id, True, 'disposable', instance,
                {'5432/tcp': [{'HostIp': '127.0.0.1', 'HostPort': '45678'}]}, False, [], {'/var/lib/postgresql/data': 'rw'}, False]
        result = subprocess.CompletedProcess([], 0, stdout='\n'.join(json.dumps(x) for x in good))
        with patch.dict(os.environ, env, clear=True), patch.object(rotation.subprocess, 'run', return_value=result), \
             patch.object(rotation, 'create_engine') as factory:
            with self.assertRaises(rotation.RotationError): rotation.run_rotation(str(target), self.settings, apply=False)
            factory.assert_not_called()
        for mounts, tmpfs, privileged in [([{'Type': 'bind'}], {'/var/lib/postgresql/data': 'rw'}, False),
                                          ([], {}, False), ([], {'/var/lib/postgresql/data': 'rw'}, True)]:
            values = [container_id, True, 'disposable', instance,
                      {'5432/tcp': [{'HostIp': '127.0.0.1', 'HostPort': '45678'}]}, True, mounts, tmpfs, privileged]
            result = subprocess.CompletedProcess([], 0, stdout='\n'.join(json.dumps(x) for x in values))
            with self.subTest(mounts=mounts, tmpfs=tmpfs, privileged=privileged), \
                 patch.dict(os.environ, env, clear=True), patch.object(rotation.subprocess, 'run', return_value=result), \
                 patch.object(rotation, 'create_engine') as factory:
                with self.assertRaises(rotation.RotationError): rotation.run_rotation(str(target), self.settings, apply=False)
                factory.assert_not_called()

    def test_rejects_missing_or_identical_keys(self):
        for update in ({'data_encryption_keys': '{}'}, {'data_encryption_key': ''},
                       {'data_encryption_keys': json.dumps({'v2': b64(self.v1)})}):
            with self.subTest(keys=list(update)):
                with self.assertRaises(rotation.RotationError): rotation.rotation_keys(self.settings.model_copy(update=update))

    def test_model_encryption_column_inventory_detects_uncovered_fields(self):
        columns = {(table.name, column.name) for table in Base.metadata.tables.values() for column in table.columns}
        self.assertEqual(rotation.uncovered_encrypted_columns(columns), set())
        augmented = columns | {('future_records', 'private_encrypted'), ('future_records', 'private_nonce')}
        self.assertEqual(rotation.uncovered_encrypted_columns(augmented),
                         {('future_records', 'private_encrypted'), ('future_records', 'private_nonce')})

    def test_safe_cli_never_prints_arguments_or_secrets(self):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            self.assertEqual(rotation.main(['--database-password', 'private-secret']), 2)
        self.assertNotIn('private-secret', out.getvalue() + err.getvalue())
        with patch.dict(os.environ, {'PGOPTIONS': 'sensitive-value'}, clear=True), contextlib.redirect_stderr(err):
            self.assertEqual(rotation.main(['--apply']), 1)
        self.assertNotIn('sensitive-value', err.getvalue())

    def test_cli_import_does_not_start_app_or_create_logs(self):
        root = str(Path(__file__).resolve().parents[2])
        with tempfile.TemporaryDirectory() as directory:
            env = dict(os.environ, PYTHONPATH=root, LOG_DIR=os.path.join(directory, 'logs'), PYTHONDONTWRITEBYTECODE='1')
            run = subprocess.run([sys.executable, '-c',
                "import backend.scripts.rotate_data_encryption, sys; assert 'backend.app.main' not in sys.modules"],
                cwd=directory, env=env, capture_output=True, text=True, timeout=20)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(run.stdout, '')
            self.assertFalse(os.path.exists(os.path.join(directory, 'logs')))

    def test_public_app_exports_remain_available(self):
        root = str(Path(__file__).resolve().parents[2])
        with tempfile.TemporaryDirectory() as directory:
            env = dict(os.environ, PYTHONPATH=root, LOG_DIR=os.path.join(directory, 'logs'), PYTHONDONTWRITEBYTECODE='1',
                       APP_ENV='test', DATABASE_URL='sqlite:///:memory:', SECRET_KEY='test-only',
                       DATA_ENCRYPTION_KEY=b64(self.v1), DATA_ENCRYPTION_KEYS='{}', DATA_ENCRYPTION_ACTIVE_KEY='v1')
            run = subprocess.run([sys.executable, '-c',
                "from backend.app import app, create_app; from fastapi import FastAPI; assert isinstance(app, FastAPI); assert callable(create_app)"],
                cwd=directory, env=env, capture_output=True, text=True, timeout=20)
            self.assertEqual(run.returncode, 0, run.stderr)

    def test_pure_decryption_rejects_corruption_and_preserves_legacy_aad(self):
        spec = rotation.FIELDS[0]
        row = {'sender_id': 'a', 'target_type': 'user', 'target_id': 'b', 'is_anonymous': False, 'id': 1}
        nonce = os.urandom(12)
        legacy = b64(AESGCM(self.v1).encrypt(nonce, b'private-example', None))
        decoded = rotation._decode(legacy, b64(nonce), spec, row, {'v1': self.v1, 'v2': self.v2})
        self.assertEqual(decoded[0:3], ('legacy', b'private-example', _aad('a', 'user', 'b', False)))
        cipher = 'v1:' + b64(AESGCM(self.v1).encrypt(nonce, b'private-example', decoded[2]))
        for value, bad_nonce, keys, bad_row in [
            (cipher[:-2] + 'AA', b64(nonce), {'v1': self.v1, 'v2': self.v2}, row),
            (cipher, b64(os.urandom(12)), {'v1': self.v1, 'v2': self.v2}, row),
            (cipher, b64(nonce), {'v1': self.v2, 'v2': self.v1}, row),
            ('v9:' + cipher[3:], b64(nonce), {'v1': self.v1, 'v2': self.v2}, row),
            (cipher, b64(nonce), {'v1': self.v1, 'v2': self.v2}, {**row, 'target_id': 'changed'}),
            (cipher, b64(b'short'), {'v1': self.v1, 'v2': self.v2}, row),
        ]:
            with self.assertRaises(rotation.RotationError) as exc:
                rotation._decode(value, bad_nonce, spec, bad_row, keys)
            self.assertNotIn('private-example', str(exc.exception))


@unittest.skipUnless(os.getenv('ECHORA_ROTATION_RUN_PODMAN') == '1', 'requires a newly created disposable Podman container')
class RotationPostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.container = 'echora-rotation-test-' + uuid4().hex
        cls.database = 'echora_restore_test_' + uuid4().hex
        cls.instance = uuid4().hex
        cls.password = secrets.token_urlsafe(24)
        cls.container_env = dict(os.environ)
        for name in ('CONTAINER_HOST', 'CONTAINER_CONNECTION', 'CONTAINER_SSHKEY', 'DOCKER_HOST', 'PODMAN_CONNECTION'):
            cls.container_env.pop(name, None)
        env = dict(cls.container_env, POSTGRES_PASSWORD=cls.password, POSTGRES_DB=cls.database)
        try:
            created = subprocess.run(['podman', '--remote=false', 'run', '-d', '--rm', '--pull=never', '--name', cls.container,
                            '--label', 'io.echora.rotation-purpose=disposable',
                            '--label', 'io.echora.rotation-instance=' + cls.instance,
                            '--tmpfs', '/var/lib/postgresql/data:rw,size=256m',
                            '-e', 'POSTGRES_PASSWORD', '-e', 'POSTGRES_DB', '-p', '127.0.0.1::5432',
                            'docker.io/library/postgres:16.16-alpine3.24', 'postgres',
                            '-c', 'echora.rotation_test_instance=' + cls.instance], env=env, check=True, capture_output=True, text=True, timeout=60)
            cls.container_id = created.stdout.strip()
            result = subprocess.run(['podman', '--remote=false', 'port', cls.container, '5432/tcp'], env=cls.container_env, check=True, capture_output=True, text=True, timeout=10)
            port = int(result.stdout.strip().rsplit(':', 1)[1])
            from sqlalchemy.engine import URL
            cls.url = URL.create('postgresql+psycopg', username='postgres', password=cls.password,
                                 host='127.0.0.1', port=port, database=cls.database)
            cls.engine = create_engine(cls.url, poolclass=NullPool, hide_parameters=True)
            deadline = time.monotonic() + 30
            while True:
                try:
                    with cls.engine.connect() as conn:
                        if conn.scalar(text('SELECT current_database()')) != cls.database: raise RuntimeError('Banco inesperado')
                    break
                except Exception:
                    if time.monotonic() >= deadline: raise RuntimeError('PostgreSQL de teste indisponível') from None
                    time.sleep(.2)
        except Exception:
            if hasattr(cls, 'engine'):
                cls.engine.dispose()
            subprocess.run(['podman', '--remote=false', 'rm', '-f', cls.container], env=cls.container_env, capture_output=True, timeout=15)
            raise

    @classmethod
    def tearDownClass(cls):
        try:
            cls.engine.dispose()
        finally:
            subprocess.run(['podman', '--remote=false', 'rm', '-f', cls.container], env=cls.container_env, capture_output=True, timeout=15, check=True)

    def setUp(self):
        # This engine always points at the container/database created by setUpClass.
        Base.metadata.drop_all(self.engine)
        Base.metadata.create_all(self.engine)
        self.v1, self.v2 = bytes(range(32)), bytes(range(32, 64))
        self.settings = Settings(_env_file=None, app_env='test', data_encryption_key=b64(self.v1),
                                 data_encryption_keys=json.dumps({'v2': b64(self.v2)}), data_encryption_active_key='v1')
        self.patcher = patch('backend.app.core.crypto.get_settings', return_value=self.settings)
        self.patcher.start(); self.addCleanup(self.patcher.stop)
        self.service_patch = patch('backend.app.services.maya_service.get_settings', return_value=self.settings)
        self.service_patch.start(); self.addCleanup(self.service_patch.stop)
        instance_env = dict(self.container_env, ECHORA_ROTATION_PODMAN_CONTAINER_ID=self.container_id,
                            ECHORA_ROTATION_INSTANCE=self.instance)
        self.instance_patch = patch.dict(os.environ, instance_env, clear=True)
        self.instance_patch.start(); self.addCleanup(self.instance_patch.stop)
        self.key = str(uuid4())
        self.user = UserPublic(id='u1', email='u1@example.com', full_name='Teste', role='aluno', school_id=1)
        with Session(self.engine) as db:
            db.add(School(id=1, name='Escola'))
            db.add(User(id='u1', email='u1@example.com', full_name='Teste', role='aluno', school_id=1, hashed_password='x'))
            db.commit()
            cipher, nonce = encrypt_feedback('texto-feedback', sender_id='u1', target_type='user', target_id='u1', is_anonymous=False)
            db.add(Feedback(id=10, sender_id='u1', target_type='user', target_id='u1', is_anonymous=False,
                            content_encrypted=cipher, nonce=nonce, sentiment_label='positivo'))
            legacy_nonce = os.urandom(12)
            db.add(Feedback(id=11, sender_id='u1', target_type='user', target_id='u1', is_anonymous=True,
                            content_encrypted=b64(AESGCM(self.v1).encrypt(legacy_nonce, b'texto-legado', None)),
                            nonce=b64(legacy_nonce), sentiment_label='neutro'))
            aid, cid, qid, qid2 = [str(uuid4()) for _ in range(4)]
            self.aid, self.qid = aid, qid
            ac, an = encrypt_maya_content('texto-relatorio', kind='analysis', record_id=aid)
            qc, qn = encrypt_maya_content('pergunta-teste', kind='question', record_id=qid)
            ans, ansn = encrypt_maya_content('resposta-teste', kind='answer', record_id=qid)
            self.settings.data_encryption_active_key = 'v2'
            q2c, q2n = encrypt_maya_content('outra-pergunta', kind='question', record_id=qid2)
            self.settings.data_encryption_active_key = 'v1'
            digest = hmac.new(self.v1, b'maya-question-v1:' + json.dumps([aid, 'pergunta-teste'], ensure_ascii=False).encode(), hashlib.sha256).hexdigest()
            db.add(MayaAnalysis(id=aid, requester_id='u1', school_id=1, kind='aluno', content_encrypted=ac, nonce=an,
                                feedback_count=2, status='completed'))
            db.add(MayaConversation(id=cid, analysis_id=aid, user_id='u1')); db.flush()
            db.add_all([MayaQuestion(id=qid, conversation_id=cid, user_id='u1', request_key=self.key, request_digest=digest,
                                   question_encrypted=qc, question_nonce=qn, answer_encrypted=ans, answer_nonce=ansn,
                                   status='completed', quota_date=date(2026, 1, 2)),
                        MayaQuestion(id=qid2, conversation_id=cid, user_id='u1', request_key=str(uuid4()), request_digest='0'*64,
                                   question_encrypted=q2c, question_nonce=q2n, status='pending', quota_date=date(2026, 1, 2))])
            db.commit()

    def run_rotate(self, apply=False, **kwargs):
        return rotation.run_rotation(self.url.render_as_string(hide_password=False), self.settings, apply=apply, **kwargs)

    def snapshot(self):
        with self.engine.connect() as conn:
            return {table: [dict(row) for row in conn.execute(text('SELECT * FROM public.' + table + ' ORDER BY id')).mappings()]
                    for table in ('feedbacks', 'maya_analyses', 'maya_questions')}

    def test_full_rotation_metadata_aad_idempotence_and_replay(self):
        before = self.snapshot()
        counts, changed, result = self.run_rotate()
        self.assertEqual((counts['v1'], counts['v2'], counts['legacy'], counts['null']), (4, 1, 1, 1))
        self.assertEqual(changed, 0); self.assertEqual(before, self.snapshot())
        _, changed, after = self.run_rotate(apply=True)
        self.assertEqual(changed, 5); self.assertEqual((after['v1'], after['v2'], after['legacy']), (0, 6, 0))
        rotated = self.snapshot()
        for table in before:
            for old, new in zip(before[table], rotated[table]):
                encrypted_columns = {'content_encrypted', 'nonce', 'question_encrypted', 'question_nonce', 'answer_encrypted', 'answer_nonce'}
                self.assertEqual({k:v for k,v in old.items() if k not in encrypted_columns},
                                 {k:v for k,v in new.items() if k not in encrypted_columns})
                for key in ('nonce', 'question_nonce', 'answer_nonce'):
                    if key in new and new[key] is not None:
                        self.assertEqual(len(base64.b64decode(new[key])), 12)
                        self.assertLessEqual(len(new[key]), 32 if table != 'feedbacks' else 255)
        with Session(self.engine) as db, patch('backend.app.core.llm._run_openai') as model:
            self.assertEqual(decrypt_feedback(db.get(Feedback, 10)), 'texto-feedback')
            self.assertEqual(decrypt_feedback(db.get(Feedback, 11)), 'texto-legado')
            self.assertEqual(decrypt_maya_content(db.get(MayaAnalysis, self.aid).content_encrypted, db.get(MayaAnalysis, self.aid).nonce, kind='analysis', record_id=self.aid), 'texto-relatorio')
            self.assertEqual(maya_service.ask(db, self.user, self.aid, 'pergunta-teste', self.key)['answer'], 'resposta-teste')
            with self.assertRaises(HTTPException) as conflict:
                maya_service.ask(db, self.user, self.aid, 'pergunta-diferente', self.key)
            self.assertEqual(conflict.exception.status_code, 409)
            model.assert_not_called()
        self.assertEqual(self.run_rotate(apply=True)[1], 0)
        self.assertEqual(rotated, self.snapshot())

    def _assert_integrity_failure_preserves_records(self, expression):
        with self.engine.begin() as conn:
            conn.execute(text('UPDATE public.feedbacks SET ' + expression + ' WHERE id=10'))
        before = self.snapshot()
        with self.assertRaises(rotation.RotationError): self.run_rotate(apply=True)
        self.assertEqual(before, self.snapshot())

    def test_unknown_version_preserves_records(self):
        self._assert_integrity_failure_preserves_records("content_encrypted='v9:AAAA'")

    def test_corrupt_nonce_preserves_records(self):
        self._assert_integrity_failure_preserves_records("nonce='AAAA'")

    def test_corrupt_ciphertext_preserves_records(self):
        self._assert_integrity_failure_preserves_records("content_encrypted=content_encrypted || 'A'")

    def test_corrupt_aad_preserves_records(self):
        self._assert_integrity_failure_preserves_records("target_id='tampered'")

    def test_wrong_key_preserves_records(self):
        before = self.snapshot()
        wrong = self.settings.model_copy(update={'data_encryption_key': b64(bytes(range(64,96)))})
        with self.assertRaises(rotation.RotationError): rotation.run_rotation(self.url.render_as_string(hide_password=False), wrong, apply=True)
        self.assertEqual(before, self.snapshot())

    def test_rollback_after_first_update(self):
        before = self.snapshot()
        original = rotation._migrate
        def fail_after_first(): raise rotation.RotationError('falha simulada')
        with patch.object(rotation, '_migrate', side_effect=lambda conn, keys, **kw: original(conn, keys, after_update=fail_after_first)):
            with self.assertRaises(rotation.RotationError): self.run_rotate(apply=True)
        self.assertEqual(before, self.snapshot())

    def test_null_answer_requires_null_nonce(self):
        with self.engine.begin() as conn:
            conn.execute(text("UPDATE public.maya_questions SET answer_nonce='AAAAAAAAAAAAAAAA' WHERE answer_encrypted IS NULL"))
        before = self.snapshot()
        with self.assertRaises(rotation.RotationError): self.run_rotate(apply=True)
        self.assertEqual(before, self.snapshot())

    def test_cli_reports_counts_without_plaintext_secrets_or_url(self):
        target = self.url.render_as_string(hide_password=False)
        env = dict(self.container_env, APP_ENV='test', DATA_ENCRYPTION_KEY=b64(self.v1),
               DATA_ENCRYPTION_KEYS=json.dumps({'v2': b64(self.v2)}), ECHORA_ROTATION_DATABASE_URL=target,
               ECHORA_ROTATION_PODMAN_CONTAINER_ID=self.container_id, ECHORA_ROTATION_INSTANCE=self.instance)
        out, err = io.StringIO(), io.StringIO()
        with patch.dict(os.environ, env, clear=True), contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            self.assertEqual(rotation.main(['--dry-run']), 0)
        combined = out.getvalue() + err.getvalue()
        self.assertIn('v1=4', combined)
        for secret in (self.password, target, b64(self.v1), b64(self.v2), 'texto-feedback', 'pergunta-teste', 'resposta-teste'):
            self.assertNotIn(secret, combined)
        with self.engine.begin() as conn:
            conn.execute(text("UPDATE public.feedbacks SET content_encrypted='v9:AAAA' WHERE id=10"))
        out, err = io.StringIO(), io.StringIO()
        with patch.dict(os.environ, env, clear=True), contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            self.assertEqual(rotation.main(['--apply']), 1)
        for secret in (self.password, target, b64(self.v1), b64(self.v2), 'texto-feedback', 'pergunta-teste'):
            self.assertNotIn(secret, out.getvalue() + err.getvalue())

    def test_rejects_unexpected_triggers(self):
        with self.engine.begin() as conn:
            conn.exec_driver_sql("CREATE FUNCTION public.rotation_test_trigger() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RETURN NEW; END $$")
            conn.exec_driver_sql('CREATE TRIGGER rotation_test BEFORE UPDATE ON public.feedbacks FOR EACH ROW EXECUTE FUNCTION public.rotation_test_trigger()')
        before = self.snapshot()
        with self.assertRaises(rotation.RotationError): self.run_rotate(apply=True)
        self.assertEqual(before, self.snapshot())
        with self.engine.begin() as conn:
            conn.exec_driver_sql('DROP TRIGGER rotation_test ON public.feedbacks')
            conn.exec_driver_sql('DROP FUNCTION public.rotation_test_trigger()')

    def test_rejects_generated_columns(self):
        with self.engine.begin() as conn:
            conn.exec_driver_sql('ALTER TABLE public.feedbacks ADD COLUMN generated_size integer GENERATED ALWAYS AS (length(content_encrypted)) STORED')
        before = self.snapshot()
        with self.assertRaises(rotation.RotationError): self.run_rotate(apply=True)
        self.assertEqual(before, self.snapshot())

    def test_wrong_database_identity_and_read_only(self):
        with patch.object(rotation.Connection, 'scalar', return_value='echora'):
            with self.assertRaises(rotation.RotationError): self.run_rotate()
        before = self.snapshot()
        def try_write(conn, keys):
            conn.execute(text("UPDATE public.feedbacks SET target_id='forbidden' WHERE id=10"))
        with patch.object(rotation, '_scan', side_effect=try_write):
            with self.assertRaises(DBAPIError) as readonly: self.run_rotate()
        self.assertEqual(readonly.exception.orig.sqlstate, '25006')
        self.assertEqual(before, self.snapshot())

    def test_wrong_server_marker_rejected_before_scanning(self):
        before = self.snapshot()
        with patch.object(rotation, 'authorized_instance', return_value='0' * 32), \
             patch.object(rotation, '_scan') as scan:
            with self.assertRaises(rotation.RotationError): self.run_rotate(apply=True)
            scan.assert_not_called()
        self.assertEqual(before, self.snapshot())

    def test_wrong_postgres_data_directory_rejected_before_scanning(self):
        before = self.snapshot()
        with patch.object(rotation.Connection, 'scalar', side_effect=[self.database, self.instance, '/other/data']), \
             patch.object(rotation, '_scan') as scan:
            with self.assertRaises(rotation.RotationError): self.run_rotate(apply=True)
            scan.assert_not_called()
        self.assertEqual(before, self.snapshot())

    def test_unknown_encrypted_columns_reject_without_changes(self):
        with self.engine.begin() as conn:
            conn.exec_driver_sql('CREATE TABLE public.rotation_future (id integer, secret_encrypted text, secret_nonce text)')
        try:
            before = self.snapshot()
            with self.assertRaises(rotation.RotationError): self.run_rotate(apply=True)
            self.assertEqual(before, self.snapshot())
        finally:
            with self.engine.begin() as conn: conn.exec_driver_sql('DROP TABLE public.rotation_future')

    def test_unknown_encrypted_column_in_existing_table_is_rejected(self):
        with self.engine.begin() as conn:
            conn.exec_driver_sql('ALTER TABLE public.feedbacks ADD COLUMN extra_encrypted text')
        before = self.snapshot()
        with self.assertRaises(rotation.RotationError): self.run_rotate(apply=True)
        self.assertEqual(before, self.snapshot())

    def test_streaming_cursor_updates_across_multiple_batches(self):
        from psycopg import ServerCursor
        records = []
        for index in range(257):
            plaintext = f'texto-em-lote-{index}'
            cipher, nonce = encrypt_feedback(plaintext, sender_id='u1', target_type='user', target_id='u1', is_anonymous=False)
            records.append(Feedback(id=1000 + index, sender_id='u1', target_type='user', target_id='u1',
                                    is_anonymous=False, content_encrypted=cipher, nonce=nonce))
        with Session(self.engine) as db:
            db.add_all(records); db.commit()
        with self.engine.connect() as conn:
            result = conn.execute(text('SELECT id FROM public.feedbacks ORDER BY id').execution_options(stream_results=True))
            try:
                self.assertIsInstance(result.cursor, ServerCursor)
            finally:
                result.close()
        original = self.snapshot()
        _, changed, after = self.run_rotate(apply=True)
        self.assertEqual(changed, 262)
        self.assertEqual(after['v2'], 263)
        with Session(self.engine) as db:
            for index in range(257):
                self.assertEqual(decrypt_feedback(db.get(Feedback, 1000 + index)), f'texto-em-lote-{index}')
        updated = self.snapshot()
        self.assertEqual([r['id'] for r in updated['feedbacks']], [r['id'] for r in original['feedbacks']])
        self.assertEqual(self.run_rotate(apply=True)[1], 0)
        self.assertEqual(updated, self.snapshot())

    def test_streaming_update_rollback_after_multiple_batches(self):
        with Session(self.engine) as db:
            for index in range(150):
                cipher, nonce = encrypt_feedback('teste-lote', sender_id='u1', target_type='user', target_id='u1', is_anonymous=False)
                db.add(Feedback(id=1000 + index, sender_id='u1', target_type='user', target_id='u1',
                                is_anonymous=False, content_encrypted=cipher, nonce=nonce))
            db.commit()
        before = self.snapshot()
        original, updates = rotation._migrate, 0
        def fail_after_batch():
            nonlocal updates
            updates += 1
            if updates == 120: raise rotation.RotationError('falha após múltiplos lotes')
        with patch.object(rotation, '_migrate', side_effect=lambda conn, keys, **kw: original(conn, keys, after_update=fail_after_batch)):
            with self.assertRaises(rotation.RotationError): self.run_rotate(apply=True)
        self.assertEqual(updates, 120)
        self.assertEqual(before, self.snapshot())

    def test_writer_is_blocked_while_apply_holds_locks(self):
        started, release = Event(), Event()
        original = rotation._migrate
        def wait_after_update():
            started.set()
            if not release.wait(8): raise rotation.RotationError('tempo esgotado')
        def wrapped(conn, keys, **kw): return original(conn, keys, after_update=wait_after_update)
        with patch.object(rotation, '_migrate', side_effect=wrapped):
            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(self.run_rotate, True)
                try:
                    self.assertTrue(started.wait(8))
                    with self.engine.connect() as conn:
                        with self.assertRaises(DBAPIError) as blocked:
                            with conn.begin():
                                conn.exec_driver_sql("SET LOCAL lock_timeout='200ms'")
                                conn.execute(text("UPDATE public.feedbacks SET target_id='blocked' WHERE id=10"))
                        self.assertEqual(blocked.exception.orig.sqlstate, '55P03')
                finally:
                    release.set()
                self.assertEqual(future.result(timeout=10)[1], 5)
        self.assertEqual(self.snapshot()['feedbacks'][0]['target_id'], 'u1')

    def test_writer_committed_before_lock_is_included(self):
        cipher, nonce = encrypt_feedback('atualização-anterior', sender_id='u1', target_type='user', target_id='u1', is_anonymous=False)
        with self.engine.connect() as writer:
            transaction = writer.begin()
            writer.execute(text('UPDATE public.feedbacks SET content_encrypted=:cipher, nonce=:nonce WHERE id=10'),
                           {'cipher': cipher, 'nonce': nonce})
            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(self.run_rotate, True)
                try:
                    deadline = time.monotonic() + 3
                    while time.monotonic() < deadline:
                        with self.engine.connect() as observer:
                            waiting = observer.scalar(text("SELECT EXISTS (SELECT 1 FROM pg_stat_activity WHERE datname=current_database() AND wait_event_type='Lock' AND query LIKE 'LOCK TABLE public.feedbacks%')"))
                        if waiting: break
                        time.sleep(.03)
                    self.assertTrue(waiting, 'rotação não chegou ao bloqueio esperado')
                finally:
                    transaction.commit()
                self.assertEqual(future.result(timeout=10)[1], 5)
        with Session(self.engine) as db:
            self.assertEqual(decrypt_feedback(db.get(Feedback, 10)), 'atualização-anterior')


if __name__ == '__main__': unittest.main()
