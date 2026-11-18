"""Versioned AES-GCM for feedback, with lazy migration of legacy records."""
from __future__ import annotations

import base64
import binascii
import json
import logging
import os
import re
from typing import TYPE_CHECKING

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy import update
from sqlalchemy.orm import object_session

from .config import get_settings

if TYPE_CHECKING:
    from ..models import Feedback

LOGGER = logging.getLogger(__name__)


class FeedbackIntegrityError(ValueError):
    """A feedback could not be authenticated or decrypted."""


def _keys() -> tuple[str, dict[str, bytes]]:
    settings = get_settings()
    try:
        configured = json.loads(settings.data_encryption_keys)
        if not isinstance(configured, dict):
            raise ValueError('DATA_ENCRYPTION_KEYS deve ser um objeto JSON')
        keys = {'v1': settings.encryption_key_bytes()}
        for version, value in configured.items():
            if not isinstance(version, str) or not re.fullmatch(r'v[1-9][0-9]*', version) or not isinstance(value, str):
                raise ValueError('Versão de chave inválida')
            decoded = base64.b64decode(value, altchars=b'-_', validate=True)
            if len(decoded) != 32 or (settings.is_production and len(set(decoded)) < 16):
                raise ValueError('Cada chave versionada deve conter 32 bytes')
            keys[version] = decoded
        active = settings.data_encryption_active_key
        if active not in keys:
            raise ValueError('Versão ativa de chave inexistente')
        return active, keys
    except (ValueError, TypeError, binascii.Error) as exc:
        raise ValueError('Configuração de chaves de feedback inválida') from exc


def _aad(sender_id: str, target_type: str, target_id: str, is_anonymous: bool) -> bytes:
    return json.dumps([str(sender_id), target_type, str(target_id), bool(is_anonymous)], ensure_ascii=False, separators=(',', ':')).encode('utf-8')


def encrypt_feedback(text: str, *, sender_id: str, target_type: str, target_id: str, is_anonymous: bool) -> tuple[str, str]:
    active, keys = _keys()
    nonce = os.urandom(12)
    ciphertext = AESGCM(keys[active]).encrypt(nonce, text.encode('utf-8'), _aad(sender_id, target_type, target_id, is_anonymous))
    return f'{active}:{base64.b64encode(ciphertext).decode()}', base64.b64encode(nonce).decode()


def decrypt_feedback(feedback: Feedback) -> str:
    """Read authenticated data; migrate a legacy row after successful decryption."""
    from ..models import Feedback as FeedbackModel
    raw = feedback.content_encrypted
    active, keys = _keys()
    try:
        version, separator, encoded = raw.partition(':')
        if separator:
            if version not in keys:
                raise FeedbackIntegrityError('Versão de chave indisponível')
            key = keys[version]
            aad = _aad(feedback.sender_id, feedback.target_type, feedback.target_id, feedback.is_anonymous)
        else:
            encoded = raw
            key = get_settings().encryption_key_bytes()
            aad = None
        plaintext = AESGCM(key).decrypt(base64.b64decode(feedback.nonce, validate=True), base64.b64decode(encoded, validate=True), aad).decode('utf-8')
    except (InvalidTag, ValueError, UnicodeDecodeError, binascii.Error, TypeError) as exc:
        LOGGER.error('Falha de integridade AES-GCM no feedback id=%s', feedback.id)
        raise FeedbackIntegrityError('Não foi possível autenticar o feedback') from exc
    if not separator:
        session = object_session(feedback)
        if session is None or feedback.id is None:
            raise FeedbackIntegrityError('Não é possível migrar feedback fora de uma sessão')
        new_ciphertext, new_nonce = encrypt_feedback(plaintext, sender_id=feedback.sender_id,
                                                    target_type=feedback.target_type, target_id=feedback.target_id,
                                                    is_anonymous=feedback.is_anonymous)
        # Compare-and-swap prevents overwriting another migration or a concurrent edit.
        with session.get_bind().begin() as connection:
            connection.execute(update(FeedbackModel).where(FeedbackModel.id == feedback.id,
                               FeedbackModel.content_encrypted == raw, FeedbackModel.nonce == feedback.nonce,
                               FeedbackModel.sender_id == feedback.sender_id,
                               FeedbackModel.target_type == feedback.target_type,
                               FeedbackModel.target_id == feedback.target_id,
                               FeedbackModel.is_anonymous == feedback.is_anonymous)
                               .values(content_encrypted=new_ciphertext, nonce=new_nonce))
    return plaintext
