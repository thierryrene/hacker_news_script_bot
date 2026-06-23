"""Envio para WhatsApp via Evolution API, com conversão HTML->Markdown."""

import os
import re

import requests


def html_to_whatsapp(text):
    """Converte o HTML básico usado no Telegram para Markdown do WhatsApp,
    encurtando os links via is.gd. Sem flag DOTALL para espelhar o regex do JS."""
    if not text:
        return ''

    formatted = str(text)
    formatted = re.sub(r'<b>(.*?)</b>', r'*\1*', formatted)
    formatted = re.sub(r'<strong>(.*?)</strong>', r'*\1*', formatted)
    formatted = re.sub(r'<i>(.*?)</i>', r'_\1_', formatted)
    formatted = re.sub(r'<em>(.*?)</em>', r'_\1_', formatted)
    formatted = re.sub(r'<code>(.*?)</code>', r'```\1```', formatted)

    link_re = re.compile(r'<a\s+href="([^"]+)">(.*?)</a>')
    links = [
        {'full': m.group(0), 'url': m.group(1), 'label': m.group(2)}
        for m in link_re.finditer(formatted)
    ]

    for link in links:
        try:
            resp = requests.get(
                'https://is.gd/create.php',
                params={'format': 'simple', 'url': link['url']},
                timeout=10,
            )
            resp.raise_for_status()
            formatted = formatted.replace(link['full'], f"{link['label']}: {resp.text.strip()}")
        except requests.RequestException:
            formatted = formatted.replace(link['full'], f"{link['label']}: {link['url']}")

    return re.sub(r'<[^>]*>', '', formatted)


def send_message(text):
    url_base = os.environ.get('EVOLUTION_API_URL')
    api_key = os.environ.get('EVOLUTION_API_KEY')
    instance = os.environ.get('EVOLUTION_API_INSTANCE')
    number = os.environ.get('WHATSAPP_NUMBER')  # Pode ser número ou JID de grupo

    if not (url_base and api_key and instance and number):
        print('⚠️ Evolution API não configurada corretamente no .env. Ignorando envio WhatsApp.')
        return None

    url = f'{url_base}/message/sendText/{instance}'
    formatted_text = html_to_whatsapp(text)

    try:
        print(f'📤 Enviando mensagem via Evolution API para {number}...')
        resp = requests.post(
            url,
            json={
                'number': number,
                'text': formatted_text,
                'delay': 1200,  # Delay de segurança
                'linkPreview': False,
            },
            headers={'apikey': api_key, 'Content-Type': 'application/json'},
            timeout=30,
        )
        resp.raise_for_status()
        print('✅ Mensagem WhatsApp enviada com sucesso!')
        return resp.json()
    except requests.RequestException as error:
        body = getattr(error.response, 'text', None) if error.response is not None else None
        print(f'❌ Erro ao enviar mensagem Evolution API: {body or error}')
        # Não lança erro para não quebrar o fluxo principal se o WhatsApp falhar
        return None
