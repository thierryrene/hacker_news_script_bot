"""Testes do cache — foco no gate de comentários por `descendants`.

Cada teste usa um cache.db temporário para não tocar no banco versionado.
Rodar: python -m unittest
"""

import os
import sqlite3
import tempfile
import unittest

import cache


class CommentCacheGateTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._orig_path = cache.DB_PATH
        self._orig_last_run = cache.LAST_RUN_PATH
        cache.DB_PATH = os.path.join(self._tmp.name, 'cache.db')
        cache.LAST_RUN_PATH = os.path.join(self._tmp.name, 'last_run.json')
        for var in ('CACHE_TTL_DAYS', 'COMMENT_REFRESH_GROWTH'):
            os.environ.pop(var, None)
        cache.init_db()

    def tearDown(self):
        cache.DB_PATH = self._orig_path
        cache.LAST_RUN_PATH = self._orig_last_run
        self._tmp.cleanup()

    def test_reuses_when_discussion_stable(self):
        cache.save_comment_summary(1, 'resumo', 10, 'neutro')
        self.assertEqual(cache.get_comment_summary(1, 10), {'summary': 'resumo', 'tone': 'neutro'})

    def test_reuses_on_small_growth(self):
        cache.save_comment_summary(1, 'resumo', 10)
        self.assertEqual(cache.get_comment_summary(1, 11), {'summary': 'resumo', 'tone': 'neutro'})

    def test_invalidates_on_material_growth(self):
        cache.save_comment_summary(1, 'resumo', 10)
        self.assertIsNone(cache.get_comment_summary(1, 13))

    def test_reuses_when_discussion_shrinks(self):
        cache.save_comment_summary(1, 'resumo', 10)
        self.assertEqual(cache.get_comment_summary(1, 8), {'summary': 'resumo', 'tone': 'neutro'})

    def test_miss_when_absent(self):
        self.assertIsNone(cache.get_comment_summary(99, 5))

    def test_zero_baseline_forces_resummary(self):
        cache.save_comment_summary(1, 'resumo', 0)
        self.assertIsNone(cache.get_comment_summary(1, 5))
        self.assertEqual(cache.get_comment_summary(1, 0), {'summary': 'resumo', 'tone': 'neutro'})

    def test_custom_threshold_via_env(self):
        os.environ['COMMENT_REFRESH_GROWTH'] = '0.5'
        try:
            cache.save_comment_summary(1, 'resumo', 10)
            self.assertEqual(cache.get_comment_summary(1, 14), {'summary': 'resumo', 'tone': 'neutro'})
            self.assertIsNone(cache.get_comment_summary(1, 16))
        finally:
            os.environ.pop('COMMENT_REFRESH_GROWTH', None)

    def test_null_baseline_forces_resummary(self):
        conn = sqlite3.connect(cache.DB_PATH)
        conn.execute(
            "INSERT OR REPLACE INTO comment_summaries "
            "(post_id, raw_comments_hash, summary, descendants, created_at) "
            "VALUES (5, 'h', 'old', NULL, datetime('now'))"
        )
        conn.commit()
        conn.close()
        self.assertIsNone(cache.get_comment_summary(5, 100))

    def test_migration_adds_descendants_column(self):
        old_path = os.path.join(self._tmp.name, 'old.db')
        conn = sqlite3.connect(old_path)
        conn.execute(
            'CREATE TABLE comment_summaries '
            '(post_id INTEGER PRIMARY KEY, raw_comments_hash TEXT, summary TEXT, created_at TEXT)'
        )
        conn.commit()
        conn.close()

        cache.DB_PATH = old_path
        cache.init_db()

        conn = sqlite3.connect(old_path)
        cols = [r[1] for r in conn.execute('PRAGMA table_info(comment_summaries)').fetchall()]
        conn.close()
        self.assertIn('descendants', cols)
        self.assertIn('tone', cols)


class LastRunTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._orig_last_run = cache.LAST_RUN_PATH
        cache.LAST_RUN_PATH = os.path.join(self._tmp.name, 'last_run.json')

    def tearDown(self):
        cache.LAST_RUN_PATH = self._orig_last_run
        self._tmp.cleanup()

    def test_load_empty_when_missing(self):
        self.assertEqual(cache.load_last_run_post_ids(), set())

    def test_save_and_load_roundtrip(self):
        cache.save_last_run([1, 2, 3])
        self.assertEqual(cache.load_last_run_post_ids(), {1, 2, 3})


if __name__ == '__main__':
    unittest.main()
