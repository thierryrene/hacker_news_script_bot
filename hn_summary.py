"""Pipeline diário do Hacker News.

Busca os top stories, extrai conteúdo e comentários, resume com o Gemini
(saída JSON estruturada), cacheia em SQLite e distribui via Telegram e WhatsApp.
"""

import os
import re
import json
import time
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

# Cliente Gemini criado de forma preguiçosa: o SDK só é carregado quando uma
# chamada real acontece, mantendo o import do módulo leve e testável sem rede.
_client = None


def _get_client():
    global _client
    if _client is None:
        from google import genai
        _client = genai.Client(api_key=GEMINI_API_KEY)
    return _client

USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
POST_SEPARATOR = '===POST_SEPARATOR==='

# Schema JSON estruturado para os resumos dos posts.
POST_SCHEMA = {
    'type': 'ARRAY',
    'description': 'Lista de resumos e análises estruturadas para cada post enviado, mantendo a exata ordem dos posts.',
    'items': {
        'type': 'OBJECT',
        'properties': {
            'emoji': {
                'type': 'STRING',
                'description': 'Um único emoji que represente visualmente a temática do post.',
            },
            'tldr': {
                'type': 'STRING',
                'description': '1 a 2 frases em português resumindo a ideia central da notícia de forma rica e informativa.',
            },
        },
        'required': ['emoji', 'tldr'],
    },
}

# Schema JSON estruturado para os resumos dos comentários da comunidade.
COMMENT_SCHEMA = {
    'type': 'ARRAY',
    'description': 'Lista de resumos de opiniões da comunidade para cada post enviado, respeitando a ordem exata dos posts.',
    'items': {
        'type': 'STRING',
        'description': '1 a 2 frases em português resumindo a voz da comunidade do Hacker News sobre o post (divergências, elogios, discussões ou piadas). Sem formatação HTML.',
    },
}


def _generate(prompt, schema):
    """Faz uma única chamada ao Gemini esperando JSON e retorna o texto bruto."""
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
    """Chama o Gemini esperando JSON, com retry/backoff exponencial e parsing
    protegido. `_generate_fn` é injetável para permitir testes sem rede."""
    generate = _generate_fn or _generate
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            text = generate(prompt, schema)
            try:
                return json.loads(text)
            except json.JSONDecodeError as parse_err:
                raise ValueError(f'Resposta não-JSON do Gemini: {parse_err}')
        except Exception as err:  # retry em qualquer falha transitória (rede ou parse)
            last_err = err
            print(f'⚠️ Gemini tentativa {attempt}/{retries} falhou: {err}')
            if attempt < retries:
                time.sleep(base_delay_s * 2 ** (attempt - 1))
    raise last_err


def chunk_telegram_message(full_msg, separator=POST_SEPARATOR, max_len=3900):
    """Quebra a mensagem completa em chunks respeitando o limite do Telegram.
    Pura e testável."""
    chunks = []
    current = ''
    for block in full_msg.split(separator):
        clean = block.strip()
        if not clean:
            continue
        # 25 = margem de segurança para os separadores reinseridos entre blocos.
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
    """Tempo de leitura estimado em minutos (~200 palavras/min). 0 sem texto."""
    if not word_count:
        return 0
    return max(1, round(word_count / 200))


def fetch_link_content(url):
    """Retorna (excerpt, word_count).

    O excerpt é limitado a 1500 chars (recorte enviado ao Gemini). O word_count
    é contado no texto COMPLETO, para o tempo de leitura refletir o artigo inteiro
    e não apenas o trecho truncado. O formato do excerpt é preservado tal como
    antes para manter a compatibilidade do hash do cache."""
    if not url:
        return '', 0
    try:
        res = requests.get(url, timeout=5, headers={'User-Agent': USER_AGENT})
        res.raise_for_status()
        soup = BeautifulSoup(res.text, 'html.parser')
        for tag in soup(['script', 'style', 'iframe', 'nav', 'header', 'footer']):
            tag.decompose()
        text = ' '.join(p.get_text() for p in soup.find_all('p'))
        # Fallback para o <body> se não houver tag <p>.
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
        ids = res.json()[:60]  # Avalia os 60 primeiros

        # Busca os detalhes concorrentemente (muito mais rápido).
        with ThreadPoolExecutor(max_workers=10) as executor:
            raw_items = list(executor.map(_fetch_hn_item, ids))

        # Filtra itens válidos com pontuação superior a 50.
        items = [it for it in raw_items if it and it.get('score', 0) > 50 and it.get('title')]
        items.sort(key=lambda x: x['score'], reverse=True)
        return items[:15]  # Retorna apenas os 15 melhores
    except Exception as err:
        print(f'Erro ao carregar Hacker News: {err}')
        return []


def summarize_comments_with_gemini(posts_with_comments):
    try:
        prompt = (
            'Você é um analista de comunidade discutindo links de tecnologia.\n'
            'Abaixo estão os títulos dos posts e as opiniões mais relevantes da comunidade do Hacker News sobre eles.\n'
            'Para cada post, gere um resumo conciso (1 a 2 frases) da voz da comunidade.\n\n'
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
            'Você é um sumarizador especialista de notícias tech. Recebi posts do Hacker News com o título e um trecho do seu conteúdo original.\n'
            'Faça um resumo rico, denso e estruturado em português para cada um deles.\n\n'
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


def main():
    cache.init_db()
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
            comment_summaries[i] = None
            uncached_comment_posts.append(post)
            comment_cached_indexes.append(i)

    if uncached_comment_posts:
        print(f'- Chamando Gemini para resumir comentários de {len(uncached_comment_posts)} posts...')
        new_comment_summaries = summarize_comments_with_gemini(uncached_comment_posts)
        has_valid = bool(new_comment_summaries)

        for j, post in enumerate(uncached_comment_posts):
            original_index = comment_cached_indexes[j]
            if has_valid and j < len(new_comment_summaries) and new_comment_summaries[j]:
                summary_text = new_comment_summaries[j]
            else:
                summary_text = ''
            comment_summaries[original_index] = summary_text

            # Apenas salva no cache se tivemos uma resposta válida da API.
            if has_valid and summary_text:
                cache.save_comment_summary(post['id'], summary_text, post.get('descendants'))

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
            summaries[i] = None
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
                summaries[original_index] = summary_obj

                # Apenas salva no cache se não for o fallback de erro.
                if summary_obj.get('tldr') and summary_obj.get('tldr') != 'Não foi possível gerar um resumo detalhado.':
                    text_hash = cache.get_hash(post.get('fetchedText') or post['title'])
                    cache.save_post_summary(post['id'], post['title'], post.get('url') or '', text_hash, summary_obj)
            else:
                # Fallback temporário (não cacheado).
                summaries[original_index] = {
                    'emoji': '📰',
                    'tldr': 'Não foi possível gerar um resumo detalhado.',
                }

    full_msg = '<b>📰 HACKER NEWS - TOP STORIES 🚀</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━\n\n'

    for i, post in enumerate(posts):
        summary = summaries[i] or {
            'emoji': '📰',
            'tldr': 'Não foi possível gerar um resumo detalhado.',
        }

        emoji_str = summary.get('emoji') or '📰'
        tldr_str = summary.get('tldr') or ''

        clean_comm = (comment_summaries[i] or '').strip()

        # Tempo de leitura estimado a partir do texto completo do artigo.
        read_time = read_time_minutes(post.get('fetchedWords', 0))

        # Identificação do tipo de post.
        type_prefix = ''
        title_upper = post['title'].upper()
        url = post.get('url')
        if title_upper.startswith('SHOW HN:'):
            type_prefix = '🛠️ [SHOW HN] '
        elif title_upper.startswith('ASK HN:'):
            type_prefix = '❓ [ASK HN] '
        elif url and url.lower().endswith('.pdf'):
            type_prefix = '📄 [PDF] '
        elif (not url) or ('news.ycombinator.com/item' in url):
            type_prefix = '💬 [DISCUSSÃO] '

        clean_title = re.sub(r'^(SHOW HN:|ASK HN:)\s*', '', post['title'], flags=re.IGNORECASE).strip()

        # Feedback visual baseado no score.
        badge = '📌'
        if post['score'] >= 300:
            badge = '👑'
        elif post['score'] >= 120:
            badge = '🔥'
        elif post['score'] >= 80:
            badge = '📈'

        formatted_title = f'{type_prefix}{clean_title.upper()}' if type_prefix else clean_title.upper()

        full_msg += f'{badge} <b>{formatted_title}</b> ({post["score"]} pts)\n'
        access_url = url or f"https://news.ycombinator.com/item?id={post['id']}"
        meta_line = (
            f'  🔗 <a href="{access_url}">Notícia</a> | '
            f'💬 <a href="https://news.ycombinator.com/item?id={post["id"]}">Discussão</a>'
        )
        if read_time > 0:
            meta_line += f' | ⏱️ {read_time} min'
        full_msg += meta_line + '\n'
        full_msg += f'  {emoji_str} <b>TL;DR:</b> {tldr_str.strip()}\n'
        if clean_comm:
            full_msg += f'  🗣️ <b>Comunidade:</b> {clean_comm}\n'
        full_msg += f'\n{POST_SEPARATOR}\n\n'

    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        # Limite do Telegram é 4096. Usamos 3900 como margem segura incluindo o divisor.
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
            time.sleep(0.5)  # Flood limit delay
        print('✅ Resumo enviado para o Telegram!')

    # Montagem da mensagem limpa para WhatsApp (sem o separador interno).
    whatsapp_msg = full_msg.replace(POST_SEPARATOR, '').strip()
    evolution.send_message(whatsapp_msg)
    print('✅ Resumo enviado para o WhatsApp!')


if __name__ == '__main__':
    main()
