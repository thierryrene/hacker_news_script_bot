import unittest
from unittest.mock import Mock, patch
import requests
import telegram
import evolution


class TelegramDeliveryTests(unittest.TestCase):
    @patch('telegram.time.sleep')
    @patch('telegram.requests.post')
    def test_retries_bad_gateway_then_succeeds(self, post, sleep):
        bad = Mock(status_code=502)
        good = Mock(status_code=200)
        good.json.return_value = {'ok': True, 'result': {'message_id': 1}}
        post.side_effect = [bad, good]
        self.assertTrue(telegram.send_message('token', 'chat', 'message')['ok'])
        self.assertEqual(post.call_count, 2)
        sleep.assert_called_once_with(2)

    @patch('telegram.time.sleep')
    @patch('telegram.requests.post')
    def test_exhausted_retries_raise(self, post, sleep):
        response = Mock(status_code=502)
        response.raise_for_status.side_effect = requests.HTTPError(response=response)
        post.return_value = response
        with self.assertRaises(requests.HTTPError):
            telegram._api('token', 'sendMessage')
        self.assertEqual(post.call_count, 4)

    @patch('telegram.requests.post')
    def test_permanent_error_does_not_retry(self, post):
        response = Mock(status_code=401)
        response.raise_for_status.side_effect = requests.HTTPError(response=response)
        post.return_value = response
        with self.assertRaises(requests.HTTPError):
            telegram._api('token', 'sendMessage')
        post.assert_called_once()


class WhatsAppDeliveryTests(unittest.TestCase):
    @patch.dict('os.environ', {'EVOLUTION_API_URL': 'https://example.test', 'EVOLUTION_API_KEY': 'key', 'EVOLUTION_API_INSTANCE': 'instance', 'WHATSAPP_NUMBER': '123'})
    @patch('evolution.requests.get')
    @patch('evolution.requests.post')
    def test_disconnected_instance_fails_before_sending(self, post, get):
        get.return_value.ok = True
        get.return_value.json.return_value = {'instance': {'state': 'close'}}
        with self.assertRaisesRegex(RuntimeError, 'WhatsApp desconectado'):
            evolution.send_message('plain text')
        post.assert_not_called()

    @patch.dict('os.environ', {'EVOLUTION_API_URL': 'https://example.test', 'EVOLUTION_API_KEY': 'key', 'EVOLUTION_API_INSTANCE': 'instance', 'WHATSAPP_NUMBER': '123'})
    @patch('evolution.requests.get')
    @patch('evolution.requests.post')
    def test_unauthorized_raises_instead_of_returning_success(self, post, get):
        get.return_value.ok = True
        get.return_value.json.return_value = {'instance': {'state': 'open'}}
        response = Mock(status_code=401, text='Unauthorized')
        response.raise_for_status.side_effect = requests.HTTPError(response=response)
        post.return_value = response
        with self.assertRaisesRegex(RuntimeError, 'HTTP 401'):
            evolution.send_message('plain text')


class PipelineDeliveryTests(unittest.TestCase):
    def test_partial_delivery_updates_history_and_reports_failure(self):
        from contextlib import ExitStack
        import hn_summary
        post = {'id': 1, 'title': 'Test', 'score': 100, 'url': '', 'kids': [], 'descendants': 0}
        with ExitStack() as stack:
            stack.enter_context(patch.object(hn_summary.app_settings, 'validate_provider_api_key', return_value=(True, '')))
            stack.enter_context(patch.object(hn_summary, 'get_hacker_news_top', return_value=[post]))
            stack.enter_context(patch.object(hn_summary, 'fetch_top_comments', return_value=''))
            stack.enter_context(patch.object(hn_summary, 'summarize_daily_intro', return_value='Intro'))
            stack.enter_context(patch.object(hn_summary, 'TELEGRAM_BOT_TOKEN', 'test'))
            stack.enter_context(patch.object(hn_summary, 'TELEGRAM_CHAT_ID', 'test'))
            stack.enter_context(patch.object(hn_summary.time, 'sleep'))
            stack.enter_context(patch.object(hn_summary.cache, 'init_db'))
            stack.enter_context(patch.object(hn_summary.cache, 'load_last_run_post_ids', return_value=set()))
            stack.enter_context(patch.object(hn_summary.cache, 'get_comment_summary', return_value={'summary': '', 'tone': 'neutro'}))
            stack.enter_context(patch.object(hn_summary.cache, 'get_post_summary', return_value={'emoji': 'X', 'tldr': 'Summary', 'tags': []}))
            saved = stack.enter_context(patch.object(hn_summary.cache, 'save_last_run'))
            stack.enter_context(patch.object(hn_summary.telegram, 'send_message', return_value={'ok': True}))
            stack.enter_context(patch.object(hn_summary.evolution, 'send_message', side_effect=RuntimeError('disconnected')))
            with self.assertRaisesRegex(RuntimeError, 'Falha na entrega: WhatsApp'):
                hn_summary.main()
            saved.assert_called_once_with([1])
