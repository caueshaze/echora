import os
import unittest
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.app.api.v1.admin.metrics import get_admin_metrics_health
from backend.app.core import llm
from backend.app.core.config import Settings
from backend.app.core.database import _build_engine
from backend.app.core.logging import SecureTimedRotatingFileHandler
from backend.app.main import create_app
from backend.app.schemas.feedback import FeedbackCreate
from backend.app.schemas.predict import PredictBatchRequest, PredictItem
from backend.app.schemas.user import UserCreate, UserPublic, UserUpdate


class SecurityControlsTests(unittest.TestCase):
    def test_model_request_has_output_limit_and_no_temperature(self):
        settings = Settings(_env_file=None, openai_api_key='test-key', summary_model='gpt-5-nano')
        response = MagicMock(status_code=200)
        response.json.return_value = {'choices': [{'message': {'content': 'Uma resposta de teste suficientemente clara.'}}]}
        client = MagicMock()
        client.__enter__.return_value.post.return_value = response
        with patch.object(llm, 'get_settings', return_value=settings), patch.object(llm.httpx, 'Client', return_value=client), patch.object(llm, '_post_process_summary', side_effect=lambda x: x):
            llm._run_openai('texto já filtrado', max_new_tokens=123)
        payload = client.__enter__.return_value.post.call_args.kwargs['json']
        self.assertEqual(payload['max_completion_tokens'], 123)
        self.assertFalse(payload['store'])
        self.assertNotIn('temperature', payload)

    def test_common_personal_identifiers_are_redacted(self):
        redacted = llm._redact_personal_data('Enviar para pessoa@example.com ou (11) 99999-9999 CPF 123.456.789-10')
        for value in ('pessoa@example.com', '99999-9999', '123.456.789-10'):
            self.assertNotIn(value, redacted)

    def test_summary_redacts_known_name_before_model(self):
        with patch.object(llm, '_fetch_feedbacks', return_value=[object()]), \
             patch.object(llm, '_decrypt_and_bucket', return_value=(['Maria Silva: maria@example.org'], [], [])), \
             patch.object(llm, '_run_llm', return_value='Resumo') as model:
            llm._summarize_feedbacks(None, None, 'Maria Silva', 'professor')
        prompt = model.call_args.args[0]
        self.assertNotIn('Maria Silva', prompt)
        self.assertNotIn('maria@example.org', prompt)

    def test_health_does_not_call_model(self):
        engine = create_engine('sqlite://')
        admin = UserPublic(id='admin', email='admin@example.org', full_name='Admin', role='admin')
        with Session(engine) as db, patch.object(llm, 'measure_llm_latency', side_effect=AssertionError('paid call')), patch('backend.app.api.v1.admin.metrics._measure_onnx_latency', return_value=None):
            self.assertIsNone(get_admin_metrics_health(admin, db).gemma_latency_ms)
        engine.dispose()

    def test_limits_and_password_validation(self):
        with self.assertRaises(ValidationError):
            FeedbackCreate(target_type='user', target_id='x', content='a' * 4001)
        with self.assertRaises(ValidationError):
            PredictBatchRequest(items=[PredictItem(texto='abc')] * 51)
        with self.assertRaises(ValidationError):
            UserUpdate(password='á' * 37)
        with self.assertRaises(ValidationError):
            UserCreate(email='a@example.org', full_name='A', role='aluno', password='1234567890')
        self.assertEqual(UserUpdate(password='  long password  ').password, '  long password  ')

    def test_sql_logging_disabled_and_api_headers(self):
        settings = Settings(_env_file=None, app_env='test', debug=True)
        engine = _build_engine(settings)
        self.assertFalse(engine.echo)
        self.assertTrue(engine.hide_parameters)
        engine.dispose()
        response = TestClient(create_app()).get('/api/not-found')
        self.assertEqual(response.headers['cache-control'], 'no-store')
        self.assertEqual(response.headers['x-frame-options'], 'DENY')
        self.assertEqual(response.headers['x-content-type-options'], 'nosniff')

    def test_log_file_permissions_and_security_copy(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'app.log'
            path.touch(mode=0o644)
            handler = SecureTimedRotatingFileHandler(str(path))
            handler.close()
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        root = Path(__file__).resolve().parents[2]
        for page in ('Login.tsx', 'Aluno.tsx'):
            self.assertNotIn('criptografia de ponta a ponta', (root / 'frontend/src/pages' / page).read_text())

    @unittest.skipUnless(os.getenv('ECHORA_TEST_REDIS_URL'), 'requires isolated Redis test instance')
    def test_redis_is_shared_across_storage_instances(self):
        from fastapi import FastAPI, Request, Response
        from slowapi import Limiter, _rate_limit_exceeded_handler
        from slowapi.errors import RateLimitExceeded
        from slowapi.util import get_remote_address
        from limits.storage import storage_from_string
        from uuid import uuid4
        first = storage_from_string(os.environ['ECHORA_TEST_REDIS_URL'])
        second = storage_from_string(os.environ['ECHORA_TEST_REDIS_URL'])
        key = 'echora-test-' + uuid4().hex
        self.assertEqual(first.incr(key, expiry=60), 1)
        self.assertEqual(second.incr(key, expiry=60), 2)
        first.clear(key)
        route = '/' + key
        def make_app():
            limiter = Limiter(key_func=get_remote_address, storage_uri=os.environ['ECHORA_TEST_REDIS_URL'])
            app = FastAPI()
            app.state.limiter = limiter
            app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
            @app.get(route)
            @limiter.limit('2/minute')
            def limited(request: Request, response: Response):
                return {'ok': True}
            return TestClient(app)
        one, two = make_app(), make_app()
        self.assertEqual(one.get(route).status_code, 200)
        self.assertEqual(two.get(route).status_code, 200)
        self.assertEqual(one.get(route).status_code, 429)
