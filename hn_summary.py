"""Pipeline diário do Hacker News.

Busca os top stories, extrai conteúdo e comentários, resume com o Gemini
(saída JSON estruturada), cacheia em SQLite e distribui via Telegram e WhatsApp.
"""

import os
import re
import json
import time
from datetime import datetime, timezone
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

import cache
import telegram
import evolution

load_dotenv(override=True)

GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', '')

if not GEMINI_API_KEY:
    print('❌ Erro: GEMINI_API_KEY não encontrada no arquivo .env')
    raise SystemExit(1)

MODEL_NAME = os.environ.get('GEMINI_MODEL', 'gemini-2.5-flash')

_client = None

TONE_EMOJI = {
    'entusiasmado': '😊',
    'cético': '🤔',
    'polêmico': '⚔️',
    'neutro': '😐',
}

TAG_SECTION_ORDER = [
    'IA', 'Segurança', 'Programação', 'Startups', 'Ciência',
    'Hardware', 'Negócios', 'Show HN', 'Ask HN', 'Open Source', 'Outros',
]

TAG_EMOJI = {
    'ia': '🤖',
    'segurança': '🔒',
    'programação': '💻',
    'startups': '🚀',
    'ciência': '🔬',
    'hardware': '⚙️',
    'negócios': '💼',
    'show hn': '🛠️',
    'ask hn': '❓',
    'open source': '📦',
    'outros': '📌',
}

POST_SEPARATOR = '===POST_SEPARATOR==='


def _get_client():
    global _client
    if _client is None:
        from google import genai
        _client = genai.Client(api_key=GEMINI_API_KEY)
    return _client


USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'

POST_SCHEMA = {
    'type': 'ARRAY',
    'description': 'Lista de resumos estruturados para cada post, na mesma ordem enviada.',
    'items': {
        'type': 'OBJECT',
        'properties': {
            'emoji': {
                'type': 'STRING',
                'description': 'Um único emoji que represente a temática do post.',
            },
            'tldr': {
                'type': 'STRING',
                'description': '1 a 2 frases em português resumindo a ideia central.',
            },
            'tags': {
                'type': 'ARRAY',
                'description': '1 a 3 tags curtas em português (ex: IA, Segurança, Startups).',
                'items': {'type': 'STRING'},
            },
        },
        'required': ['emoji', 'tldr', 'tags'],
    },
}

COMMENT_SCHEMA = {
    'type': 'ARRAY',
    'description': 'Resumos da voz da comunidade para cada post, na mesma ordem.',
    'items': {
        'type': 'OBJECT',
        'properties': {
            'summary': {
                'type': 'STRING',
                'description': '1 a 2 frases em português sobre a opinião da comunidade. Sem HTML.',
            },
            'tone': {
                'type': 'STRING',
                'enum': ['entusiasmado', 'cético', 'polêmico', 'neutro'],
                'description': 'Tom predominante da discussão.',
            },
        },
        'required': ['summary', 'tone'],
    },
}

INTRO_SCHEMA = {
    'type': 'OBJECT',
    'properties': {
        'headline': {
            'type': 'STRING',
            'description': 'Resumo editorial de 1-2 frases sobre os destaques do dia no Hacker News, em português.',
        },
    },
    'required': ['headline'],
}


def _generate(prompt, schema):
    from google.genai import types
    response = _get_client().models.generate_content(
        model=MODEL_NAME,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type='application/json',
            response_schema=schema,
        ),
    )
    return (response.text or '').strip()


def call_gemini_json(prompt, schema, retries=3, base_delay_s=1.0, _generate_fn=None):
    generate = _generate_fn or _generate
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            text = generate(prompt, schema)
            try:
                return json.loads(text)
            except json.JSONDecodeError as parse_err:
                raise ValueError(f'Resposta não-JSON do Gemini: {parse_err}')
        except Exception as err:
            last_err = err
            print(f'⚠️ Gemini tentativa {attempt}/{retries} falhou: {err}')
            if attempt < retries:
                time.sleep(base_delay_s * 2 ** (attempt - 1))
    raise last_err


def chunk_telegram_message(full_msg, separator=POST_SEPARATOR, max_len=3900):
    chunks = []
    current = ''
    for block in full_msg.split(separator):
        clean = block.strip()
        if not clean:
            continue
        if len(current) + len(clean) + 25 > max_len:
            if current:
                chunks.append(current)
            current = clean
        else:
            current = (current + '\n\n' + clean) if current else clean
    if current:
        chunks.append(current)
    return chunks


def read_time_minutes(word_count):
    if not word_count:
        return 0
    return max(1, round(word_count / 200))


def extract_domain(url):
    if not url:
        return ''
    if 'news.ycombinator.com' in url:
        return 'discussão hn'
    try:
        host = urlparse(url).netloc
        if host.startswith('www.'):
            host = host[4:]
        return host or ''
    except Exception:
        return ''


def format_time_ago(unix_ts):
    if not unix_ts:
        return ''
    now = datetime.now(timezone.utc)
    posted = datetime.fromtimestamp(unix_ts, tz=timezone.utc)
    secs = max(0, int((now - posted).total_seconds()))
    if secs < 3600:
        return f'há {max(1, secs // 60)} min'
    if secs < 86400:
        return f'há {secs // 3600}h'
    return f'há {secs // 86400}d'


def normalize_tag(tag):
    return (tag or '').strip()


def primary_tag(tags):
    if not tags:
        return 'Outros'
    tag = normalize_tag(tags[0])
    return tag or 'Outros'


def tag_section_emoji(tag):
    lower = tag.lower()
    for key, emoji in TAG_EMOJI.items():
        if key in lower:
            return emoji
    return '📌'


def sort_tag_sections(groups):
    order_index = {name: idx for idx, name in enumerate(TAG_SECTION_ORDER)}

    def sort_key(item):
        tag, posts = item
        return (order_index.get(tag, len(TAG_SECTION_ORDER)), -len(posts), tag.lower())

    return sorted(groups.items(), key=sort_key)


def get_type_prefix(post):
    title_upper = post['title'].upper()
    url = post.get('url')
    if title_upper.startswith('SHOW HN:'):
        return '🛠️ [SHOW HN] '
    if title_upper.startswith('ASK HN:'):
        return '❓ [ASK HN] '
    if url and url.lower().endswith('.pdf'):
        return '📄 [PDF] '
    if (not url) or ('news.ycombinator.com/item' in url):
        return '💬 [DISCUSSÃO] '
    return ''


def get_score_badge(score):
    if score >= 300:
        return '👑'
    if score >= 120:
        return '🔥'
    if score >= 80:
        return '📈'
    return '📌'


def clean_title(title):
    return re.sub(r'^(SHOW HN:|ASK HN:)\s*', '', title, flags=re.IGNORECASE).strip()


def compute_novelty(post_ids, previous_ids):
    current = set(post_ids)
    previous = set(previous_ids)
    if not previous:
        return {'new': len(current), 'returning': 0}
    return {
        'new': len(current - previous),
        'returning': len(current & previous),
    }


def fetch_link_content(url):
    if not url:
        return '', 0
    try:
        res = requests.get(url, timeout=5, headers={'User-Agent': USER_AGENT})
        res.raise_for_status()
        soup = BeautifulSoup(res.text, 'html.parser')
        for tag in soup(['script', 'style', 'iframe', 'nav', 'header', 'footer']):
            tag.decompose()
        text = ' '.join(p.get_text() for p in soup.find_all('p'))
        if not text.strip():
            body = soup.find('body')
            source = body.get_text() if body else ''
        else:
            source = text
        word_count = len(re.sub(r'\s+', ' ', source).split())
        excerpt = re.sub(r'\s+', ' ', source[:1500])
        return excerpt, word_count
    except Exception:
        return '', 0


def _fetch_hn_item(item_id):
    try:
        r = requests.get(
            f'https://hacker-news.firebaseio.com/v0/item/{item_id}.json', timeout=10
        )
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


def fetch_top_comments(kids):
    if not kids or not isinstance(kids, list):
        return ''
    first_kids = kids[:5]
    try:
        with ThreadPoolExecutor(max_workers=5) as executor:
            comments = list(executor.map(_fetch_hn_item, first_kids))
        parts = []
        for c in comments:
            if c and c.get('text') and not c.get('deleted') and not c.get('dead'):
                parts.append(re.sub(r'<[^>]*>?', ' ', c['text'])[:400])
        return ' | '.join(parts)
    except Exception:
        return ''


def get_hacker_news_top():
    try:
        res = requests.get('https://hacker-news.firebaseio.com/v0/topstories.json', timeout=10)
        res.raise_for_status()
        ids = res.json()[:60]

        with ThreadPoolExecutor(max_workers=10) as executor:
            raw_items = list(executor.map(_fetch_hn_item, ids))

        items = [it for it in raw_items if it and it.get('score', 0) > 50 and it.get('title')]
        items.sort(key=lambda x: x['score'], reverse=True)
        return items[:15]
    except Exception as err:
        print(f'Erro ao carregar Hacker News: {err}')
        return []


def summarize_comments_with_gemini(posts_with_comments):
    try:
        prompt = (
            'Você é um analista de comunidade discutindo links de tecnologia.\n'
            'Para cada post, resuma a voz da comunidade do Hacker News em 1-2 frases '
            'e classifique o tom predominante (entusiasmado, cético, polêmico ou neutro).\n\n'
            'Posts:\n'
        )
        for index, post in enumerate(posts_with_comments):
            prompt += (
                f"\n[Post {index + 1}]\n"
                f"Título: {post['title']}\n"
                f"Comentários Brutos: {post.get('rawComments') or 'Sem comentários.'}\n"
            )
        return call_gemini_json(prompt, COMMENT_SCHEMA)
    except Exception as err:
        print(f'❌ Erro no resumo de comentários: {err}')
        return []


def summarize_all_with_gemini(posts):
    try:
        prompt = (
            'Você é um sumarizador especialista de notícias tech. Recebi posts do Hacker News.\n'
            'Para cada um, gere emoji, TL;DR em português e 1-3 tags curtas de tema.\n\n'
            'Posts:\n'
        )
        for index, post in enumerate(posts):
            prompt += (
                f"\n[Post {index + 1}]\n"
                f"Título: {post['title']}\n"
                f"URL: {post.get('url') or 'N/A'}\n"
                f"Conteúdo extraído: {post.get('fetchedText') or post.get('text') or 'Apenas o título está disponível.'}\n"
            )
        return call_gemini_json(prompt, POST_SCHEMA)
    except Exception as err:
        print(f'❌ Erro no Gemini ao resumir os posts: {err}')
        return []


def summarize_daily_intro(posts, summaries):
    try:
        prompt = (
            'Você escreve a abertura de um digest diário do Hacker News em português.\n'
            'Com base nos posts abaixo, escreva 1-2 frases sobre os temas dominantes e destaques do dia.\n'
            'Seja direto, informativo e sem hashtags.\n\n'
        )
        for index, post in enumerate(posts):
            summary = summaries[index] or {}
            tags = ', '.join(summary.get('tags') or []) or 'sem tag'
            prompt += f"- {post['title']} ({post['score']} pts, tags: {tags})\n"
        result = call_gemini_json(prompt, INTRO_SCHEMA)
        return (result or {}).get('headline', '').strip()
    except Exception as err:
        print(f'⚠️ Erro no intro editorial: {err}')
        return ''


def format_post_block(post, rank, summary, comment_obj, is_new):
    emoji_str = (summary or {}).get('emoji') or '📰'
    tldr_str = (summary or {}).get('tldr') or 'Não foi possível gerar um resumo detalhado.'
    tags = (summary or {}).get('tags') or []
    comment_summary = (comment_obj or {}).get('summary', '').strip()
    comment_tone = (comment_obj or {}).get('tone', 'neutro')
    tone_emoji = TONE_EMOJI.get(comment_tone, '😐')

    read_time = read_time_minutes(post.get('fetchedWords', 0))
    type_prefix = get_type_prefix(post)
    badge = get_score_badge(post['score'])
    title = clean_title(post['title'])
    display_title = f'{type_prefix}{title}' if type_prefix else title

    domain = extract_domain(post.get('url'))
    age = format_time_ago(post.get('time'))
    comment_count = post.get('descendants') or 0
    new_marker = '🆕 ' if is_new else ''

    meta_bits = [f'#{rank}', domain]
    if comment_count:
        meta_bits.append(f'{comment_count} 💬')
    if age:
        meta_bits.append(age)
    if read_time > 0:
        meta_bits.append(f'⏱️ {read_time} min')
    meta_header = ' · '.join(bit for bit in meta_bits if bit)

    access_url = post.get('url') or f"https://news.ycombinator.com/item?id={post['id']}"
    tag_line = ''
    if tags:
        tag_line = '  🏷️ ' + ' · '.join(normalize_tag(t) for t in tags[:3]) + '\n'

    block = (
        f'{new_marker}{badge} <b>{display_title}</b> ({post["score"]} pts)\n'
        f'  <i>{meta_header}</i>\n'
        f'  🔗 <a href="{access_url}">Notícia</a> | '
        f'💬 <a href="https://news.ycombinator.com/item?id={post["id"]}">Discussão</a>\n'
        f'{tag_line}'
        f'  {emoji_str} <b>TL;DR:</b> {tldr_str.strip()}\n'
    )
    if comment_summary:
        block += f'  {tone_emoji} <b>Comunidade ({comment_tone}):</b> {comment_summary}\n'
    return block


def build_grouped_message(intro, novelty, digest_items):
    header = '<b>📰 HACKER NEWS - TOP STORIES 🚀</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━\n\n'
    if intro:
        header += f'<i>{intro}</i>\n\n'
    if novelty and (novelty['new'] or novelty['returning']):
        header += f"🆕 {novelty['new']} novos · 🔄 {novelty['returning']} ainda no top\n\n"

    groups = {}
    for item in digest_items:
        tag = primary_tag((item['summary'] or {}).get('tags'))
        groups.setdefault(tag, []).append(item)

    parts = [header]
    for tag, items in sort_tag_sections(groups):
        section_emoji = tag_section_emoji(tag)
        parts.append(f'<b>{section_emoji} {tag}</b>\n')
        for item in sorted(items, key=lambda x: x['post']['score'], reverse=True):
            parts.append(format_post_block(
                item['post'],
                item['rank'],
                item['summary'],
                item['comment'],
                item['is_new'],
            ))
            parts.append(f'\n{POST_SEPARATOR}\n\n')

    return ''.join(parts)


def main():
    cache.init_db()
    previous_ids = cache.load_last_run_post_ids()

    print('📊 Buscando melhores posts do Hacker News...')
    posts = get_hacker_news_top()

    if not posts:
        print('Nenhum post recente com score > 50 encontrado.')
        return

    print(f'📝 Extraindo conteúdo de {len(posts)} links concorrentemente...')

    def scrape(post):
        url = post.get('url')
        if url and 'news.ycombinator.com/item' not in url:
            print(f"- Lendo: {post['title']}")
            post['fetchedText'], post['fetchedWords'] = fetch_link_content(url)

    with ThreadPoolExecutor(max_workers=10) as executor:
        list(executor.map(scrape, posts))

    print('🗣️ Extraindo comentários top concorrentemente...')

    def load_comments(post):
        post['rawComments'] = fetch_top_comments(post.get('kids'))

    with ThreadPoolExecutor(max_workers=10) as executor:
        list(executor.map(load_comments, posts))

    print('💭 Resumindo opiniões da comunidade com Gemini (JSON)...')
    comment_summaries = [None] * len(posts)
    uncached_comment_posts = []
    comment_cached_indexes = []

    for i, post in enumerate(posts):
        cached = cache.get_comment_summary(post['id'], post.get('descendants'))
        if cached:
            print(f"- [Cache Hit] Comentários do Post {post['id']} carregados do SQLite")
            comment_summaries[i] = cached
        else:
            uncached_comment_posts.append(post)
            comment_cached_indexes.append(i)

    if uncached_comment_posts:
        print(f'- Chamando Gemini para resumir comentários de {len(uncached_comment_posts)} posts...')
        new_comment_summaries = summarize_comments_with_gemini(uncached_comment_posts)
        has_valid = bool(new_comment_summaries)

        for j, post in enumerate(uncached_comment_posts):
            original_index = comment_cached_indexes[j]
            if has_valid and j < len(new_comment_summaries) and new_comment_summaries[j]:
                entry = new_comment_summaries[j]
                summary_text = (entry.get('summary') or '').strip()
                tone = entry.get('tone') or 'neutro'
            else:
                summary_text = ''
                tone = 'neutro'
            comment_summaries[original_index] = {'summary': summary_text, 'tone': tone}

            if has_valid and summary_text:
                cache.save_comment_summary(
                    post['id'], summary_text, post.get('descendants'), tone,
                )

    print('📝 Enviando para resumo estruturado em lote no Gemini (JSON)...')
    summaries = [None] * len(posts)
    uncached_posts = []
    post_cached_indexes = []

    for i, post in enumerate(posts):
        text_hash = cache.get_hash(post.get('fetchedText') or post['title'])
        cached = cache.get_post_summary(post['id'], text_hash)
        if cached:
            print(f"- [Cache Hit] Resumo do Post {post['id']} carregados do SQLite")
            summaries[i] = cached
        else:
            uncached_posts.append(post)
            post_cached_indexes.append(i)

    if uncached_posts:
        print(f'- Chamando Gemini para resumir {len(uncached_posts)} posts...')
        new_summaries = summarize_all_with_gemini(uncached_posts)
        has_valid = bool(new_summaries)

        for j, post in enumerate(uncached_posts):
            original_index = post_cached_indexes[j]
            if has_valid and j < len(new_summaries) and new_summaries[j]:
                summary_obj = new_summaries[j]
                if not summary_obj.get('tags'):
                    summary_obj['tags'] = []
                summaries[original_index] = summary_obj

                if summary_obj.get('tldr') and summary_obj.get('tldr') != 'Não foi possível gerar um resumo detalhado.':
                    text_hash = cache.get_hash(post.get('fetchedText') or post['title'])
                    cache.save_post_summary(post['id'], post['title'], post.get('url') or '', text_hash, summary_obj)
            else:
                summaries[original_index] = {
                    'emoji': '📰',
                    'tldr': 'Não foi possível gerar um resumo detalhado.',
                    'tags': [],
                }

    print('✍️ Gerando intro editorial do dia...')
    intro = summarize_daily_intro(posts, summaries)

    post_ids = [post['id'] for post in posts]
    novelty = compute_novelty(post_ids, previous_ids)

    digest_items = []
    for rank, post in enumerate(posts, start=1):
        digest_items.append({
            'post': post,
            'rank': rank,
            'summary': summaries[rank - 1],
            'comment': comment_summaries[rank - 1] or {'summary': '', 'tone': 'neutro'},
            'is_new': post['id'] not in previous_ids,
        })

    full_msg = build_grouped_message(intro, novelty, digest_items)
    cache.save_last_run(post_ids)

    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        chunks = chunk_telegram_message(full_msg)
        print(f'[DEBUG] Quantidade de chunks a enviar: {len(chunks)}')

        for chunk in chunks:
            print(f'[DEBUG] Tamanho do chunk atual: {len(chunk)} caracteres')
            try:
                resp = telegram.send_message(
                    TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, chunk,
                    parse_mode='HTML', disable_web_page_preview=True,
                )
                msg_id = (resp.get('result') or {}).get('message_id')
                print(f"[DEBUG] Resposta API Telegram: ok={resp.get('ok')}, msg_id={msg_id}")
            except Exception as err:
                print(f'❌ Erro envio Telegram: {err}')
            time.sleep(0.5)
        print('✅ Resumo enviado para o Telegram!')

    whatsapp_msg = full_msg.replace(POST_SEPARATOR, '').strip()
    evolution.send_message(whatsapp_msg)
    print('✅ Resumo enviado para o WhatsApp!')


if __name__ == '__main__':
    main()
