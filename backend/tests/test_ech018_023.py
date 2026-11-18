import base64
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.app.api.v1.predict import router as predict_router
from backend.app.api.v1 import predict as predict_module
from backend.app.core.config import PROJECT_ROOT, Settings
from backend.app.core.security import get_current_user
from backend.app.main import create_app
from backend.app.schemas.user import UserPublic


class ECH018023Tests(unittest.TestCase):
    def production_settings(self):
        return Settings(_env_file=None, app_env='production',
                        database_url='postgresql+psycopg://user:pass@localhost/db',
                        rate_limit_storage_uri='redis://localhost:6379/0',
                        secret_key='d1b3f29c80a4e75d947d670c5be839a23f91ca3e5b22a61f1cd8b9e05841ef72',
                        data_encryption_key=base64.b64encode(bytes(range(32))).decode())

    def test_docs_off_in_production_and_on_in_development(self):
        for settings, expected in [(self.production_settings(), 404),
                                   (Settings(_env_file=None, app_env='development'), 200)]:
            with patch('backend.app.main.get_settings', return_value=settings):
                app = create_app()
            client = TestClient(app)
            for path in ['/docs', '/redoc', '/openapi.json']:
                self.assertEqual(client.get(path).status_code, expected, path)

    def test_prediction_routes_require_auth_and_hide_internal_details(self):
        app = FastAPI()
        app.include_router(predict_router, prefix='/api/v1')
        unauthenticated = TestClient(app)
        self.assertEqual(unauthenticated.get('/api/v1/predict/health').status_code, 401)
        self.assertEqual(unauthenticated.get('/api/v1/predict/version').status_code, 401)
        app.dependency_overrides[get_current_user] = lambda: UserPublic(
            id='admin', email='admin@example.org', full_name='Admin', role='admin')
        client = TestClient(app)
        with patch('backend.app.api.v1.predict.load_model', side_effect=RuntimeError('/srv/private/model.joblib')):
            response = client.post('/api/v1/predict/predict_batch', json={'items': [{'texto': 'mensagem teste'}]})
        self.assertEqual(response.status_code, 500)
        self.assertNotIn('/srv/private', response.text)
        self.assertNotIn('Traceback', response.text)
        with patch('backend.app.api.v1.predict.load_model', side_effect=RuntimeError('/srv/private/model.joblib')):
            response = client.post('/api/v1/predict/predict', json={'texto': 'mensagem teste'})
        self.assertEqual(response.status_code, 500)
        self.assertNotIn('model.joblib', response.text)
        self.assertEqual(client.get('/api/v1/predict/health').json(), {'status': 'ok'})
        self.assertNotIn('model_path', client.get('/api/v1/predict/version').text)

    def test_production_rejects_remote_http_and_accepts_https(self):
        base = {'_env_file': None, 'app_env': 'production',
                'database_url': 'postgresql+psycopg://user:pass@localhost/db',
                'rate_limit_storage_uri': 'redis://localhost:6379/0',
                'secret_key': 'd1b3f29c80a4e75d947d670c5be839a23f91ca3e5b22a61f1cd8b9e05841ef72',
                'data_encryption_key': base64.b64encode(bytes(range(32))).decode()}
        for key in ('openai_api_base', 'sentiment_api_url', 'gemma_api_url'):
            with self.subTest(key=key), self.assertRaises(ValidationError):
                Settings(**(base | {key: 'http://api.example.net/infer'}))
            Settings(**(base | {key: 'https://api.example.net/infer'}))

    def test_loopback_http_requires_explicit_production_flag(self):
        base = {'_env_file': None, 'app_env': 'production',
                'database_url': 'postgresql+psycopg://user:pass@localhost/db',
                'rate_limit_storage_uri': 'redis://localhost:6379/0',
                'secret_key': 'd1b3f29c80a4e75d947d670c5be839a23f91ca3e5b22a61f1cd8b9e05841ef72',
                'data_encryption_key': base64.b64encode(bytes(range(32))).decode(),
                'sentiment_api_url': 'http://127.0.0.1:9000/infer'}
        with self.assertRaises(ValidationError):
            Settings(**base)
        Settings(**(base | {'allow_loopback_http_integrations': True}))
        for hostname in ('localhost', '127.0.0.1', '[::1]'):
            Settings(**(base | {'sentiment_api_url': f'http://{hostname}:9000/infer',
                               'allow_loopback_http_integrations': True}))
        development = Settings(_env_file=None, app_env='development', sentiment_api_url='http://external.test/api')
        self.assertEqual(development.sentiment_api_url, 'http://external.test/api')

    def test_postgres_and_redis_schemes_are_not_treated_as_http_urls(self):
        settings = self.production_settings()
        self.assertTrue(settings.database_url.startswith('postgresql+psycopg://'))
        self.assertTrue(settings.rate_limit_storage_uri.startswith('redis://'))

    def test_legacy_joblib_load_is_restricted_to_local_models_directory(self):
        settings = Settings(_env_file=None, model_path='/tmp/untrusted.joblib')
        predict_module._model = None
        with patch.object(predict_module.joblib, 'load') as load:
            with self.assertRaises(RuntimeError):
                predict_module.load_model(settings)
            load.assert_not_called()

        with tempfile.NamedTemporaryFile(suffix='.joblib') as outside_file:
            symlink_path = PROJECT_ROOT / 'models' / (Path(outside_file.name).name + '.link.joblib')
            symlink_path.symlink_to(outside_file.name)
            try:
                settings = Settings(_env_file=None, model_path=str(symlink_path))
                with patch.object(predict_module.joblib, 'load') as load:
                    with self.assertRaises(RuntimeError):
                        predict_module.load_model(settings)
                    load.assert_not_called()
            finally:
                symlink_path.unlink(missing_ok=True)

        with tempfile.NamedTemporaryFile(suffix='.joblib', dir=PROJECT_ROOT / 'models') as model_file:
            settings = Settings(_env_file=None, model_path=str(Path(model_file.name)))
            predict_module._model = None
            sentinel = object()
            with patch.object(predict_module.joblib, 'load', return_value=sentinel) as load:
                self.assertIs(predict_module.load_model(settings), sentinel)
            self.assertEqual(load.call_args.args[0], str(Path(model_file.name).resolve()))
        predict_module._model = None

    def test_loopback_http_uses_real_loopback_addresses_and_is_opt_in(self):
        base = {'_env_file': None, 'app_env': 'production',
                'database_url': 'postgresql+psycopg://user:pass@localhost/db',
                'rate_limit_storage_uri': 'redis://localhost:6379/0',
                'secret_key': 'd1b3f29c80a4e75d947d670c5be839a23f91ca3e5b22a61f1cd8b9e05841ef72',
                'data_encryption_key': base64.b64encode(bytes(range(32))).decode(),
                'sentiment_api_url': 'http://127.0.0.2:9000/infer'}
        self.assertFalse(Settings(**(base | {'sentiment_api_url': ''})).allow_loopback_http_integrations)
        with self.assertRaises(ValidationError):
            Settings(**base)
        Settings(**(base | {'allow_loopback_http_integrations': True}))
        for hostname in ('10.0.0.1', '127.0.0.1.example.net', '[::2]'):
            with self.subTest(hostname=hostname), self.assertRaises(ValidationError):
                Settings(**(base | {'sentiment_api_url': f'http://{hostname}:9000/infer',
                                    'allow_loopback_http_integrations': True}))
        Settings(**(base | {'sentiment_api_url': 'http://[::ffff:127.0.0.1]:9000/infer',
                            'allow_loopback_http_integrations': True}))

    def test_remote_http_calls_do_not_follow_redirects(self):
        from backend.app.core import llm, sentiment

        settings = self.production_settings()
        settings.sentiment_api_url = 'https://sentiment.example.org/infer'
        response = unittest.mock.MagicMock(status_code=200)
        response.json.return_value = {'label': 'positive', 'score': 0.9}
        with patch.object(sentiment, 'get_settings', return_value=settings), \
             patch.object(sentiment.httpx, 'post', return_value=response) as post:
            sentiment._remote_sentiment('texto de teste')
        self.assertIs(post.call_args.kwargs['follow_redirects'], False)

        settings.openai_api_key = 'test-key'
        client = unittest.mock.MagicMock()
        client.__enter__.return_value.post.return_value = unittest.mock.MagicMock(
            status_code=200,
            json=lambda: {'choices': [{'message': {'content': 'Resumo válido para o teste.'}}]},
        )
        with patch.object(llm, 'get_settings', return_value=settings), \
             patch.object(llm.httpx, 'Client', return_value=client) as client_factory, \
             patch.object(llm, '_post_process_summary', side_effect=lambda value: value):
            llm._run_openai('feedback de teste')
        self.assertIs(client_factory.call_args.kwargs['follow_redirects'], False)

    def test_effective_production_destinations_are_checked_before_sending(self):
        from backend.app.core import llm, sentiment

        settings = self.production_settings()
        settings.sentiment_api_url = 'http://remote.example.org/infer'
        with patch.object(sentiment, 'get_settings', return_value=settings), \
             patch.object(sentiment.httpx, 'post') as post, \
             patch.object(sentiment, 'get_sentiment_analyzer') as fallback:
            fallback.return_value.predict.return_value = ('neutro', 0.0)
            self.assertEqual(sentiment._remote_sentiment('teste'), ('neutro', 0.0))
            post.assert_not_called()

        settings.openai_api_key = 'test-key'
        settings.openai_api_base = 'http://remote.example.org/v1'
        with patch.object(llm, 'get_settings', return_value=settings), \
             patch.object(llm.httpx, 'Client') as client_factory:
            with self.assertRaises(ValueError):
                llm._run_openai('teste')
            client_factory.assert_not_called()


if __name__ == '__main__':
    unittest.main()
