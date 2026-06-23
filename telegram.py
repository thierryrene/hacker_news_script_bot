"""Wrapper da API do Telegram (sendMessage)."""

import requests


def send_message(token, chat_id, text, parse_mode='HTML', disable_web_page_preview=True):
    url = f'https://api.telegram.org/bot{token}/sendMessage'
    try:
        resp = requests.post(
            url,
            json={
                'chat_id': chat_id,
                'text': text,
                'parse_mode': parse_mode,
                'disable_web_page_preview': disable_web_page_preview,
            },
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as error:
        body = getattr(error.response, 'text', None) if error.response is not None else None
        print(f'❌ Erro Telegram API: {body or error}')
        raise
