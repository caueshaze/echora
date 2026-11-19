"""OpenAI completion handling; no network or paid requests."""
import copy
import logging
import unittest
from unittest.mock import MagicMock, patch
import httpx
from fastapi.testclient import TestClient
from backend.app.core import llm
from backend.app.core.config import Settings
from backend.app.main import create_app


def completion(content, reason='stop', usage=None):
    return httpx.Response(200, json={'choices': [{'finish_reason': reason, 'message': {'content': content}}],
                                     'usage': usage or {'prompt_tokens': 30, 'completion_tokens': 24,
                                                        'completion_tokens_details': {'reasoning_tokens': 4}}})


class OpenAISummaryTests(unittest.TestCase):
    def setUp(self):
        self.settings = Settings(_env_file=None, app_env='test', openai_api_key='test-secret-key', summary_model='gpt-5-nano')
        self.settings_patch = patch.object(llm, 'get_settings', return_value=self.settings)
        self.settings_patch.start()
        self.addCleanup(self.settings_patch.stop)

    def call(self, responses):
        captured = []
        mock_client = MagicMock()
        def post(url, *, headers, json):
            captured.append(copy.deepcopy(json))
            item = responses[len(captured)-1]
            if isinstance(item, Exception):
                raise item
            return item
        mock_client.__enter__.return_value.post.side_effect = post
        with patch.object(llm.httpx, 'Client', return_value=mock_client) as factory:
            value = llm._run_openai('relato privado de teste')
        self.assertFalse(factory.call_args.kwargs['follow_redirects'])
        return value, captured

    def test_success_records_safe_metrics_and_minimal_reasoning(self):
        with self.assertLogs(llm.LOGGER, level=logging.INFO) as logs:
            value, calls = self.call([completion('assistant: Uma mensagem acolhedora.')])
        self.assertEqual(value, 'Uma mensagem acolhedora.')
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]['max_completion_tokens'], 512)
        self.assertEqual(calls[0]['reasoning_effort'], 'minimal')
        self.assertNotIn('temperature', calls[0])
        self.assertFalse(calls[0]['store'])
        output = '\n'.join(logs.output)
        for phrase in ('input_tokens=30', 'output_tokens=24', 'reasoning_tokens=4', 'finish_reason=stop', 'attempt=1'):
            self.assertIn(phrase, output)
        self.assertNotIn('relato privado', output)
        self.assertNotIn('test-secret-key', output)

    def test_empty_and_truncated_responses_retry_once_with_bounded_budget(self):
        for first in (completion(''), completion(None), completion('parcial', 'length'), completion('Maya')):
            with self.subTest(first=first):
                value, calls = self.call([first, completion('Resumo recuperado.')])
                self.assertEqual(value, 'Resumo recuperado.')
                self.assertEqual([item['max_completion_tokens'] for item in calls], [512, 1024])

    def test_empty_or_truncated_twice_fails(self):
        for first in (completion(''), completion(None), completion('parcial', 'length')):
            with self.subTest(first=first), self.assertRaisesRegex(RuntimeError, 'completo'):
                self.call([first, completion('', 'length')])

    def test_http_errors_and_transport_failures_never_retry(self):
        for response in (httpx.Response(400), httpx.Response(401), httpx.Response(402), httpx.Response(403),
                         httpx.Response(429), httpx.Response(500), httpx.Response(302),
                         httpx.TimeoutException('private prompt'), httpx.ConnectError('private token')):
            client = MagicMock()
            client.__enter__.return_value.post.side_effect = [response] if isinstance(response, Exception) else None
            if not isinstance(response, Exception):
                client.__enter__.return_value.post.return_value = response
            with self.subTest(response=response), patch.object(llm.httpx, 'Client', return_value=client), \
                 self.assertLogs(llm.LOGGER, level=logging.WARNING) as logs, self.assertRaises(RuntimeError):
                llm._run_openai('private prompt')
            self.assertEqual(client.__enter__.return_value.post.call_count, 1)
            self.assertNotIn('private', '\n'.join(logs.output))

    def test_malformed_json_unexpected_shapes_and_filtered_are_not_retried(self):
        for response in (httpx.Response(200, content=b'not json'), httpx.Response(200, json=[]),
                         httpx.Response(200, json={'choices': []}),
                         httpx.Response(200, json={'choices': [{'finish_reason': 'stop', 'message': {'content': []}}]}),
                         completion(None, 'content_filter'),
                         httpx.Response(200, json={'choices': [{'finish_reason': 'stop', 'message': {'content': None, 'refusal': 'recusado'}}]})):
            client = MagicMock()
            client.__enter__.return_value.post.return_value = response
            with self.subTest(response=response), patch.object(llm.httpx, 'Client', return_value=client), self.assertRaises(RuntimeError):
                llm._run_openai('relato')
            self.assertEqual(client.__enter__.return_value.post.call_count, 1)

    def test_other_models_and_compatible_endpoints_do_not_receive_reasoning_parameter(self):
        for model, base in [('gpt-4o', 'https://api.openai.com/v1'), ('gpt-5-nano', 'https://compatible.example/v1')]:
            self.settings.summary_model, self.settings.openai_api_base = model, base
            _, calls = self.call([completion('Resumo')])
            self.assertNotIn('reasoning_effort', calls[0])

    def test_openai_budget_is_independent_of_gemma_argument(self):
        with patch.object(llm, '_run_openai', return_value='ok') as run:
            self.assertEqual(llm._run_llm('teste', max_new_tokens=64), 'ok')
        run.assert_called_once_with('teste')

    def test_gemma_keeps_its_own_max_new_tokens(self):
        self.settings.summary_provider = 'gemma'
        prompt_ids = MagicMock()
        prompt_ids.size.return_value = 5
        generated = MagicMock()
        generated.size.return_value = 8
        model = MagicMock()
        model.generate.return_value = generated
        tokenizer = MagicMock()
        tokenizer.return_value = {'input_ids': prompt_ids}
        tokenizer.eos_token_id = 0
        tokenizer.decode.return_value = ' '.join(['palavra'] * 16)
        fake_torch = MagicMock()
        fake_torch.cuda.is_available.return_value = False
        with patch.object(llm, '_ensure_gemma'), patch.object(llm, '_LLM_MODEL', model), \
             patch.object(llm, '_LLM_TOKENIZER', tokenizer), patch.object(llm, 'torch', fake_torch), \
             patch.object(llm, '_run_openai', side_effect=AssertionError('unexpected OpenAI call')):
            self.assertTrue(llm._run_llm('teste', max_new_tokens=77))
        self.assertEqual(model.generate.call_args.kwargs['max_new_tokens'], 77)

    def test_startup_openai_does_not_load_or_call_any_model(self):
        settings = Settings(_env_file=None, summary_provider='openai', llm_provider='openai', gemma_enabled=False)
        with patch('backend.app.main.get_settings', return_value=settings), \
             patch('backend.app.main.setup_logging'), \
             patch.object(llm, '_ensure_gemma', side_effect=AssertionError('unexpected call')), \
             patch.object(llm, '_run_openai', side_effect=AssertionError('paid call')), \
             self.assertLogs('echora.app', level='INFO') as logs:
            with TestClient(create_app()):
                pass
        self.assertNotIn('Nenhum LLM habilitado', '\n'.join(logs.output))
