"""Testes do pipeline — stdlib unittest, sem dependências de teste extras.

Rodar: python -m unittest
"""

import os
import unittest

# call_gemini_json injeta `_generate_fn`, então os testes rodam sem rede.
# A GEMINI_API_KEY é exigida no import do módulo; injeta um valor fake.
os.environ.setdefault('GEMINI_API_KEY', 'test-key')

import hn_summary


def _generator(steps):
    """Retorna uma função geradora fake que percorre `steps` em ordem.
    Um item Exception é levantado; uma string é retornada como texto bruto."""
    state = {'i': 0}

    def generate(_prompt, _schema):
        step = steps[state['i']]
        state['i'] += 1
        if isinstance(step, Exception):
            raise step
        return step

    return generate, state


class CallGeminiJsonTests(unittest.TestCase):
    def test_parses_valid_json_first_try(self):
        gen, state = _generator(['[{"emoji": "🚀"}]'])
        out = hn_summary.call_gemini_json('p', {}, base_delay_s=0, _generate_fn=gen)
        self.assertEqual(out, [{'emoji': '🚀'}])
        self.assertEqual(state['i'], 1)

    def test_retries_on_transient_error(self):
        gen, state = _generator([RuntimeError('503 indisponível'), '{"ok": true}'])
        out = hn_summary.call_gemini_json('p', {}, retries=3, base_delay_s=0, _generate_fn=gen)
        self.assertEqual(out, {'ok': True})
        self.assertEqual(state['i'], 2)

    def test_retries_on_non_json(self):
        gen, state = _generator(['isto não é json', '[]'])
        out = hn_summary.call_gemini_json('p', {}, retries=2, base_delay_s=0, _generate_fn=gen)
        self.assertEqual(out, [])
        self.assertEqual(state['i'], 2)

    def test_raises_after_exhausting_retries(self):
        gen, state = _generator([RuntimeError('fail 1'), RuntimeError('fail 2')])
        with self.assertRaises(RuntimeError):
            hn_summary.call_gemini_json('p', {}, retries=2, base_delay_s=0, _generate_fn=gen)
        self.assertEqual(state['i'], 2)


class ChunkTelegramMessageTests(unittest.TestCase):
    def test_keeps_small_blocks_together(self):
        chunks = hn_summary.chunk_telegram_message('A===SEP===B===SEP===C', '===SEP===', 3900)
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0], 'A\n\nB\n\nC')

    def test_splits_when_exceeding_limit(self):
        big = 'x' * 2000
        chunks = hn_summary.chunk_telegram_message(f'{big}===SEP==={big}', '===SEP===', 3900)
        self.assertEqual(len(chunks), 2)

    def test_ignores_empty_blocks(self):
        chunks = hn_summary.chunk_telegram_message('A===SEP===   ===SEP===B', '===SEP===', 3900)
        self.assertEqual(chunks[0], 'A\n\nB')


class ReadTimeTests(unittest.TestCase):
    def test_zero_when_no_words(self):
        self.assertEqual(hn_summary.read_time_minutes(0), 0)

    def test_minimum_one_minute(self):
        # round(50/200) = 0, mas o mínimo é 1 quando há texto.
        self.assertEqual(hn_summary.read_time_minutes(50), 1)

    def test_scales_with_article_length(self):
        self.assertEqual(hn_summary.read_time_minutes(420), 2)
        self.assertEqual(hn_summary.read_time_minutes(1000), 5)


if __name__ == '__main__':
    unittest.main()
