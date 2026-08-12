"""Testes de settings e presets de provedores."""

import json
import os
import tempfile
import unittest

import settings


class SettingsTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._orig_path = settings.SETTINGS_PATH
        settings.SETTINGS_PATH = os.path.join(self._tmp.name, 'settings.json')
        self._orig_gemini_model = os.environ.pop('GEMINI_MODEL', None)

    def tearDown(self):
        settings.SETTINGS_PATH = self._orig_path
        if self._orig_gemini_model is not None:
            os.environ['GEMINI_MODEL'] = self._orig_gemini_model
        self._tmp.cleanup()

    def test_defaults_when_missing(self):
        cfg = settings.load_settings()
        self.assertEqual(cfg['llm_provider'], 'gemini')
        self.assertEqual(cfg['llm_model'], 'gemini-2.5-flash')

    def test_set_llm_persists(self):
        saved = settings.set_llm('openrouter', 'openai/gpt-4o', updated_by=123)
        self.assertEqual(saved['llm_provider'], 'openrouter')
        self.assertEqual(saved['llm_model'], 'openai/gpt-4o')
        self.assertEqual(settings.load_settings()['llm_model'], 'openai/gpt-4o')

    def test_invalid_provider_raises(self):
        with self.assertRaises(ValueError):
            settings.set_llm('invalid', 'x')

    def test_invalid_model_falls_back_on_load(self):
        with open(settings.SETTINGS_PATH, 'w', encoding='utf-8') as fh:
            json.dump({'llm_provider': 'gemini', 'llm_model': 'modelo-inexistente'}, fh)
        cfg = settings.load_settings()
        self.assertEqual(cfg['llm_model'], 'gemini-2.5-flash')

    def test_validate_api_key_missing(self):
        old = os.environ.pop('GEMINI_API_KEY', None)
        try:
            ok, err = settings.validate_provider_api_key('gemini')
            self.assertFalse(ok)
            self.assertIn('GEMINI_API_KEY', err)
        finally:
            if old is not None:
                os.environ['GEMINI_API_KEY'] = old


if __name__ == '__main__':
    unittest.main()
