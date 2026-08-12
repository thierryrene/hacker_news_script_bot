"""Wrapper da API do Telegram (Bot API)."""

import requests


def _api(token, method, payload=None):
    url = f'https://api.telegram.org/bot{token}/{method}'
    resp = requests.post(url, json=payload or {}, timeout=30)
    resp.raise_for_status()
    return resp.json()


def send_message(token, chat_id, text, parse_mode='HTML', disable_web_page_preview=True, reply_markup=None):
    payload = {
        'chat_id': chat_id,
        'text': text,
        'parse_mode': parse_mode,
        'disable_web_page_preview': disable_web_page_preview,
    }
    if reply_markup is not None:
        payload['reply_markup'] = reply_markup
    try:
        return _api(token, 'sendMessage', payload)
    except requests.RequestException as error:
        body = getattr(error.response, 'text', None) if error.response is not None else None
        print(f'❌ Erro Telegram API: {body or error}')
        raise


def edit_message(token, chat_id, message_id, text, parse_mode='HTML', reply_markup=None):
    payload = {
        'chat_id': chat_id,
        'message_id': message_id,
        'text': text,
        'parse_mode': parse_mode,
    }
    if reply_markup is not None:
        payload['reply_markup'] = reply_markup
    return _api(token, 'editMessageText', payload)


def answer_callback(token, callback_query_id, text=None, show_alert=False):
    payload = {'callback_query_id': callback_query_id, 'show_alert': show_alert}
    if text:
        payload['text'] = text
    return _api(token, 'answerCallbackQuery', payload)


def get_updates(token, offset=None, timeout=30):
    payload = {'timeout': timeout, 'allowed_updates': ['message', 'callback_query']}
    if offset is not None:
        payload['offset'] = offset
    return _api(token, 'getUpdates', payload)
