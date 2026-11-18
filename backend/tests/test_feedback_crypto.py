import base64
import json
import os
import tempfile
import unittest
from unittest.mock import patch

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.app.core.config import Settings
from backend.app.core.crypto import FeedbackIntegrityError, decrypt_feedback, encrypt_feedback
from backend.app.core.database import Base
from backend.app.models import Feedback, User


class FeedbackCryptoTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.engine = create_engine('sqlite:///' + self.temp.name + '/test.db')
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine, expire_on_commit=False)
        self.settings = Settings(_env_file=None, app_env='test', data_encryption_key=base64.b64encode(bytes(range(32))).decode())
        self.override = patch('backend.app.core.crypto.get_settings', return_value=self.settings)
        self.override.start()
        self.db.add(User(id='author', email='author@example.com', full_name='Author', role='admin', hashed_password='x'))
        self.db.commit()

    def tearDown(self):
        self.override.stop()
        self.db.close()
        self.engine.dispose()
        self.temp.cleanup()

    def add_record(self, cipher, nonce):
        fb = Feedback(sender_id='author', target_type='user', target_id='target', is_anonymous=True, content_encrypted=cipher, nonce=nonce)
        self.db.add(fb)
        self.db.commit()
        return fb

    def test_legacy_migrates_and_authenticates_metadata(self):
        nonce = os.urandom(12)
        old = base64.b64encode(AESGCM(self.settings.encryption_key_bytes()).encrypt(nonce, b'conteudo legado', None)).decode()
        fb = self.add_record(old, base64.b64encode(nonce).decode())
        self.assertEqual(decrypt_feedback(fb), 'conteudo legado')
        self.db.expire_all()
        self.assertTrue(fb.content_encrypted.startswith('v1:'))
        self.assertEqual(decrypt_feedback(fb), 'conteudo legado')
        fb.target_id = 'outro'
        with self.assertRaises(FeedbackIntegrityError):
            decrypt_feedback(fb)

    def test_versions_and_corruption(self):
        old, nonce = encrypt_feedback('segredo', sender_id='author', target_type='user', target_id='target', is_anonymous=True)
        fb = self.add_record(old, nonce)
        self.settings.data_encryption_keys = json.dumps({'v2': base64.b64encode(os.urandom(32)).decode()})
        self.settings.data_encryption_active_key = 'v2'
        self.assertEqual(decrypt_feedback(fb), 'segredo')
        new, new_nonce = encrypt_feedback('novo', sender_id='author', target_type='user', target_id='target', is_anonymous=True)
        self.assertTrue(new.startswith('v2:'))
        fb.content_encrypted, fb.nonce = new, new_nonce
        self.assertEqual(decrypt_feedback(fb), 'novo')
        fb.nonce = base64.b64encode(os.urandom(12)).decode()
        with self.assertRaises(FeedbackIntegrityError):
            decrypt_feedback(fb)
