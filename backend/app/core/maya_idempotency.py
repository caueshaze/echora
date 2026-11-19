"""Versioned Maya request digests; inputs never leave process memory."""
from __future__ import annotations
import hashlib
import hmac
import json
import re
from .config import Settings

LEGACY = 'legacy-v1'
DEDICATED = 'hmac-v2'


def request_digest(settings: Settings, analysis_id: str, question: str, version: str) -> str:
    if version == LEGACY:
        key, domain = settings.encryption_key_bytes(), b'maya-question-v1:'
    elif version == DEDICATED:
        key, domain = settings.idempotency_hmac_key_bytes(), b'maya-question-v2:'
    else:
        raise ValueError('Versão de digest da Maya não suportada')
    payload = json.dumps([analysis_id, question], ensure_ascii=False).encode()
    return hmac.new(key, domain + payload, hashlib.sha256).hexdigest()


def matches_digest(settings: Settings, analysis_id: str, question: str, version: str, expected: str) -> bool:
    actual = request_digest(settings, analysis_id, question, version)
    return isinstance(expected, str) and bool(re.fullmatch(r'[0-9a-f]{64}', expected)) and hmac.compare_digest(actual, expected)
