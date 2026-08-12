"""Testes do menu Telegram (autorização e callbacks)."""

import os
import tempfile
import unittest
from unittest.mock import patch

import settings
import telegram_menu


class TelegramMenuTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._orig_path = settings.SETTINGS_PATH
        settings.SETTINGS_PATH = os.path.join(self._tmp.name, 'settings.json')
        os.environ['TELEGRAM_CHAT_ID'] = '100'
        os.environ['TELEGRAM_ADMIN_IDS'] = '200,300'

    def tearDown(self):
        settings.SETTINGS_PATH = self._orig_path
        self._tmp.cleanup()

    def test_authorized_by_chat(self):
        self.assertTrue(telegram_menu.is_authorized('100', '999'))

    def test_authorized_by_admin(self):
        self.assertTrue(telegram_menu.is_authorized('999', '200'))

    def test_unauthorized(self):
        self.assertFalse(telegram_menu.is_authorized('999', '888'))

    @patch('telegram_menu.telegram.edit_message')
    @patch('telegram_menu.telegram.answer_callback')
    def test_set_model_callback(self, mock_answer, mock_edit):
        callback = {
            'id': 'cb1',
            'data': 's:anthropic:claude-3-5-haiku-20241022',
            'from': {'id': 200},
            'message': {'chat': {'id': 100}, 'message_id': 1},
        }
        telegram_menu.handle_callback('token', callback)
        mock_edit.assert_called_once()
        mock_answer.assert_called_once()
        cfg = settings.load_settings()
        self.assertEqual(cfg['llm_provider'], 'anthropic')
        self.assertEqual(cfg['llm_model'], 'claude-3-5-haiku-20241022')


if __name__ == '__main__':
    unittest.main()
