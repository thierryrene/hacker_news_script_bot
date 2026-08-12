"""Cache SQLite local — acesso direto, sem subprocesso.

Substitui o antigo par cache.js + cache_helper.py, que falava com o SQLite
spawnando um processo Python a cada operação. Agora é uma única linguagem
acessando o banco diretamente.

Os hashes continuam sendo MD5 utf-8 do conteúdo — idênticos aos gerados pela
versão Node — então o data/cache.db existente permanece válido após a migração.
"""

import os
import json
import sqlite3
import hashlib

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'cache.db')
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
LAST_RUN_PATH = os.path.join(DATA_DIR, 'last_run.json')


def _ttl_days():
    """TTL do cache em dias. 0 desativa a expiração. Default: 7 dias."""
    try:
        return max(0, int(os.environ.get('CACHE_TTL_DAYS', '7')))
    except ValueError:
        return 7


def _comment_growth_threshold():
    """Fração de crescimento de comentários (descendants) que invalida o cache de
    comentários. Default 0.25 (25%). Configurável via COMMENT_REFRESH_GROWTH."""
    try:
        return max(0.0, float(os.environ.get('COMMENT_REFRESH_GROWTH', '0.25')))
    except ValueError:
        return 0.25


def _connect():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    return sqlite3.connect(DB_PATH)


def init_db():
    conn = _connect()
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS post_summaries (
          post_id INTEGER PRIMARY KEY,
          title TEXT,
          url TEXT,
          fetched_text_hash TEXT,
          emoji TEXT,
          tldr TEXT,
          por_que_importa TEXT,
          tags TEXT,
          created_at TEXT
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS comment_summaries (
          post_id INTEGER PRIMARY KEY,
          raw_comments_hash TEXT,
          summary TEXT,
          tone TEXT,
          descendants INTEGER,
          created_at TEXT
        )
    ''')
    existing_cols = [r[1] for r in cur.execute('PRAGMA table_info(comment_summaries)').fetchall()]
    if 'descendants' not in existing_cols:
        cur.execute('ALTER TABLE comment_summaries ADD COLUMN descendants INTEGER')
    if 'tone' not in existing_cols:
        cur.execute('ALTER TABLE comment_summaries ADD COLUMN tone TEXT')
    conn.commit()
    conn.close()


def get_hash(text):
    return hashlib.md5((text or '').encode('utf-8')).hexdigest()


def get_post_summary(post_id, text_hash):
    conn = _connect()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    ttl = _ttl_days()
    if ttl > 0:
        cur.execute(
            "SELECT emoji, tldr, por_que_importa, tags FROM post_summaries "
            "WHERE post_id = ? AND fetched_text_hash = ? AND created_at > datetime('now', ?)",
            (post_id, text_hash, f'-{ttl} days'),
        )
    else:
        cur.execute(
            'SELECT emoji, tldr, por_que_importa, tags FROM post_summaries '
            'WHERE post_id = ? AND fetched_text_hash = ?',
            (post_id, text_hash),
        )
    row = cur.fetchone()
    conn.close()
    if row:
        return {
            'emoji': row['emoji'],
            'tldr': row['tldr'],
            'porQueImporta': row['por_que_importa'],
            'tags': json.loads(row['tags'] or '[]'),
        }
    return None


def save_post_summary(post_id, title, url, text_hash, summary_obj):
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        '''INSERT OR REPLACE INTO post_summaries
           (post_id, title, url, fetched_text_hash, emoji, tldr, por_que_importa, tags, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))''',
        (
            post_id,
            title or '',
            url or '',
            text_hash,
            summary_obj.get('emoji') or '📰',
            summary_obj.get('tldr') or '',
            summary_obj.get('porQueImporta') or '',
            json.dumps(summary_obj.get('tags') or []),
        ),
    )
    conn.commit()
    conn.close()


def get_comment_summary(post_id, current_descendants):
    """Reusa o resumo de comentários cacheado, a menos que a discussão tenha
    crescido materialmente (medido por `descendants`) ou o TTL tenha expirado."""
    conn = _connect()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    ttl = _ttl_days()
    if ttl > 0:
        cur.execute(
            "SELECT summary, tone, descendants FROM comment_summaries "
            "WHERE post_id = ? AND created_at > datetime('now', ?)",
            (post_id, f'-{ttl} days'),
        )
    else:
        cur.execute(
            'SELECT summary, tone, descendants FROM comment_summaries WHERE post_id = ?',
            (post_id,),
        )
    row = cur.fetchone()
    conn.close()
    if not row:
        return None

    cached_descendants = row['descendants']
    if cached_descendants is None:
        return None

    current = current_descendants or 0
    growth = (current - cached_descendants) / max(cached_descendants, 1)
    if growth >= _comment_growth_threshold():
        return None
    return {
        'summary': row['summary'] or '',
        'tone': row['tone'] or 'neutro',
    }


def save_comment_summary(post_id, summary, descendants, tone='neutro'):
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        '''INSERT OR REPLACE INTO comment_summaries
           (post_id, raw_comments_hash, summary, tone, descendants, created_at)
           VALUES (?, NULL, ?, ?, ?, datetime('now'))''',
        (post_id, summary or '', tone or 'neutro', descendants),
    )
    conn.commit()
    conn.close()


def load_last_run_post_ids():
    """Retorna o conjunto de post_ids da execução anterior, ou vazio."""
    if not os.path.isfile(LAST_RUN_PATH):
        return set()
    try:
        with open(LAST_RUN_PATH, encoding='utf-8') as fh:
            data = json.load(fh)
        return set(data.get('post_ids') or [])
    except (OSError, json.JSONDecodeError):
        return set()


def save_last_run(post_ids):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(LAST_RUN_PATH, 'w', encoding='utf-8') as fh:
        json.dump({'post_ids': list(post_ids)}, fh, ensure_ascii=False)
