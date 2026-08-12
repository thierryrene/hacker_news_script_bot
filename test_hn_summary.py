"""Testes do pipeline — stdlib unittest, sem dependências de teste extras.

Rodar: python -m unittest
"""

import os
import unittest

os.environ.setdefault('GEMINI_API_KEY', 'test-key')

from datetime import datetime, timezone

import hn_summary


def _generator(steps):
    state = {'i': 0}

    def generate(_prompt, _schema):
        step = steps[state['i']]
        state['i'] += 1
        if isinstance(step, Exception):
            raise step
        return step

    return generate, state


class CallLlmJsonTests(unittest.TestCase):
    def test_parses_valid_json_first_try(self):
        gen, state = _generator(['[{"emoji": "🚀"}]'])
        out = hn_summary.call_llm_json('p', {}, base_delay_s=0, _generate_fn=gen)
        self.assertEqual(out, [{'emoji': '🚀'}])
        self.assertEqual(state['i'], 1)

    def test_retries_on_transient_error(self):
        gen, state = _generator([RuntimeError('503 indisponível'), '{"ok": true}'])
        out = hn_summary.call_llm_json('p', {}, retries=3, base_delay_s=0, _generate_fn=gen)
        self.assertEqual(out, {'ok': True})
        self.assertEqual(state['i'], 2)

    def test_retries_on_non_json(self):
        gen, state = _generator(['isto não é json', '[]'])
        out = hn_summary.call_llm_json('p', {}, retries=2, base_delay_s=0, _generate_fn=gen)
        self.assertEqual(out, [])
        self.assertEqual(state['i'], 2)

    def test_raises_after_exhausting_retries(self):
        gen, state = _generator([RuntimeError('fail 1'), RuntimeError('fail 2')])
        with self.assertRaises(RuntimeError):
            hn_summary.call_llm_json('p', {}, retries=2, base_delay_s=0, _generate_fn=gen)
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
        self.assertEqual(hn_summary.read_time_minutes(50), 1)

    def test_scales_with_article_length(self):
        self.assertEqual(hn_summary.read_time_minutes(420), 2)
        self.assertEqual(hn_summary.read_time_minutes(1000), 5)


class MetadataHelpersTests(unittest.TestCase):
    def test_extract_domain(self):
        self.assertEqual(hn_summary.extract_domain('https://github.com/foo'), 'github.com')
        self.assertEqual(hn_summary.extract_domain('https://news.ycombinator.com/item?id=1'), 'discussão hn')
        self.assertEqual(hn_summary.extract_domain(''), '')

    def test_format_time_ago(self):
        now = int(datetime.now(timezone.utc).timestamp())
        self.assertEqual(hn_summary.format_time_ago(now - 120), 'há 2 min')
        self.assertEqual(hn_summary.format_time_ago(now - 7200), 'há 2h')

    def test_compute_novelty(self):
        self.assertEqual(
            hn_summary.compute_novelty([1, 2, 3], [2, 3, 4]),
            {'new': 1, 'returning': 2},
        )
        self.assertEqual(hn_summary.compute_novelty([1, 2], []), {'new': 2, 'returning': 0})

    def test_primary_tag(self):
        self.assertEqual(hn_summary.primary_tag(['IA', 'Startups']), 'IA')
        self.assertEqual(hn_summary.primary_tag([]), 'Outros')

    def test_clean_title(self):
        self.assertEqual(hn_summary.clean_title('Show HN: My App'), 'My App')

    def test_build_grouped_message_contains_sections(self):
        posts = [{
            'id': 1,
            'title': 'AI breakthrough',
            'score': 200,
            'url': 'https://example.com',
            'time': int(datetime.now(timezone.utc).timestamp()) - 3600,
            'descendants': 50,
            'fetchedWords': 400,
        }]
        digest_items = [{
            'post': posts[0],
            'rank': 1,
            'summary': {'emoji': '🤖', 'tldr': 'Resumo teste.', 'tags': ['IA']},
            'comment': {'summary': 'Comentários positivos.', 'tone': 'entusiasmado'},
            'is_new': True,
        }]
        msg = hn_summary.build_grouped_message('Destaques do dia.', {'new': 1, 'returning': 0}, digest_items)
        self.assertIn('Destaques do dia.', msg)
        self.assertIn('🤖 IA', msg)
        self.assertIn('🆕', msg)
        self.assertIn('entusiasmado', msg)


if __name__ == '__main__':
    unittest.main()
