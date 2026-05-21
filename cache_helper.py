import sys
import sqlite3
import json
import os

# Caminho para a pasta data relativa a este script
db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'cache.db')

def init_db():
    # Cria a pasta data se não existir
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('''
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
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS comment_summaries (
          post_id INTEGER PRIMARY KEY,
          raw_comments_hash TEXT,
          summary TEXT,
          created_at TEXT
        )
    ''')
    conn.commit()
    conn.close()

def get_post_summary(post_id, text_hash):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(
        'SELECT emoji, tldr, por_que_importa, tags FROM post_summaries WHERE post_id = ? AND fetched_text_hash = ?',
        (post_id, text_hash)
    )
    row = cursor.fetchone()
    conn.close()
    if row:
        return {
            'emoji': row['emoji'],
            'tldr': row['tldr'],
            'porQueImporta': row['por_que_importa'],
            'tags': json.loads(row['tags'] or '[]')
        }
    return None

def save_post_summary(post_id, title, url, text_hash, emoji, tldr, por_que_importa, tags_str):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        '''INSERT OR REPLACE INTO post_summaries 
           (post_id, title, url, fetched_text_hash, emoji, tldr, por_que_importa, tags, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))''',
        (post_id, title, url, text_hash, emoji, tldr, por_que_importa, tags_str)
    )
    conn.commit()
    conn.close()

def get_comment_summary(post_id, comments_hash):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        'SELECT summary FROM comment_summaries WHERE post_id = ? AND raw_comments_hash = ?',
        (post_id, comments_hash)
    )
    row = cursor.fetchone()
    conn.close()
    if row:
        return row[0]
    return None

def save_comment_summary(post_id, comments_hash, summary):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        '''INSERT OR REPLACE INTO comment_summaries 
           (post_id, raw_comments_hash, summary, created_at)
           VALUES (?, ?, ?, datetime('now'))''',
        (post_id, comments_hash, summary)
    )
    conn.commit()
    conn.close()

def main():
    if len(sys.argv) < 2:
        print(json.dumps({'error': 'Missing command'}))
        return
        
    cmd = sys.argv[1]
    
    if cmd == 'init':
        init_db()
        print(json.dumps({'status': 'ok'}))
    elif cmd == 'get_post':
        post_id = int(sys.argv[2])
        text_hash = sys.argv[3]
        res = get_post_summary(post_id, text_hash)
        print(json.dumps({'result': res}))
    elif cmd == 'save_post':
        post_id = int(sys.argv[2])
        title = sys.argv[3]
        url = sys.argv[4]
        text_hash = sys.argv[5]
        emoji = sys.argv[6]
        tldr = sys.argv[7]
        por_que_importa = sys.argv[8]
        tags_str = sys.argv[9]
        save_post_summary(post_id, title, url, text_hash, emoji, tldr, por_que_importa, tags_str)
        print(json.dumps({'status': 'ok'}))
    elif cmd == 'get_comment':
        post_id = int(sys.argv[2])
        comments_hash = sys.argv[3]
        res = get_comment_summary(post_id, comments_hash)
        print(json.dumps({'result': res}))
    elif cmd == 'save_comment':
        post_id = int(sys.argv[2])
        comments_hash = sys.argv[3]
        summary = sys.argv[4]
        save_comment_summary(post_id, comments_hash, summary)
        print(json.dumps({'status': 'ok'}))

if __name__ == '__main__':
    main()
