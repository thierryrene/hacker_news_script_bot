"""Construção e handlers do menu /menu do bot Telegram."""

import os
import threading

import settings as app_settings
import telegram


def _btn(text, callback_data):
    return {'text': text, 'callback_data': callback_data}


def _keyboard(rows):
    return {'inline_keyboard': rows}


def main_menu_markup():
    return _keyboard([
        [_btn('🤖 Modelo de resumo', 'n:model')],
        [_btn('📋 Ver configuração', 'n:status')],
        [_btn('🚀 Enviar digest agora', 'a:run')],
    ])


def providers_markup():
    rows = []
    for provider_id, provider in app_settings.PROVIDERS.items():
        rows.append([_btn(
            f"{provider['emoji']} {provider['label']}",
            f'n:p:{provider_id}',
        )])
    rows.append([_btn('« Voltar', 'n:main')])
    return _keyboard(rows)


def models_markup(provider_id):
    provider = app_settings.get_provider(provider_id)
    if not provider:
        return main_menu_markup()

    rows = []
    current = app_settings.load_settings()
    for model in provider['models']:
        prefix = '✅ ' if (
            current['llm_provider'] == provider_id and current['llm_model'] == model['id']
        ) else ''
        rows.append([_btn(
            f'{prefix}{model["label"]}',
            f's:{provider_id}:{model["id"]}',
        )])
    rows.append([_btn('« Provedores', 'n:model'), _btn('« Menu', 'n:main')])
    return _keyboard(rows)


def main_menu_text():
    provider_label, model_label = app_settings.current_llm_summary()
    return (
        '<b>⚙️ Configurações — HN FastDigest</b>\n\n'
        f'Modelo atual: <b>{provider_label}</b>\n'
        f'↳ <code>{model_label}</code>\n\n'
        'Escolha uma opção abaixo:'
    )


def providers_text():
    return (
        '<b>🤖 Modelo de resumo</b>\n\n'
        'Selecione o provedor de IA.\n'
        'A chave de API correspondente precisa estar no <code>.env</code>.'
    )


def models_text(provider_id):
    provider = app_settings.get_provider(provider_id)
    if not provider:
        return main_menu_text()
    return (
        f"<b>{provider['emoji']} {provider['label']}</b>\n\n"
        'Escolha o modelo para os resumos:'
    )


def status_text():
    cfg = app_settings.load_settings()
    provider_label, model_label = app_settings.current_llm_summary()
    ok, err = app_settings.validate_provider_api_key(cfg['llm_provider'])
    key_status = '✅ configurada' if ok else f'❌ {err}'

    lines = [
        '<b>📋 Configuração atual</b>\n',
        f'Provedor: <b>{provider_label}</b>',
        f'Modelo: <code>{cfg["llm_model"]}</code> ({model_label})',
        f'API key: {key_status}',
    ]
    if cfg.get('updated_at'):
        lines.append(f"Atualizado em: <code>{cfg['updated_at']}</code>")
    lines.append('\nUse /menu para alterar.')
    return '\n'.join(lines)


def is_authorized(chat_id, user_id):
    allowed_chat = os.environ.get('TELEGRAM_CHAT_ID', '').strip()
    admin_ids = {
        item.strip()
        for item in os.environ.get('TELEGRAM_ADMIN_IDS', '').split(',')
        if item.strip()
    }
    if allowed_chat and str(chat_id) == allowed_chat:
        return True
    if admin_ids and str(user_id) in admin_ids:
        return True
    return False


def send_menu(token, chat_id):
    return telegram.send_message(
        token,
        chat_id,
        main_menu_text(),
        reply_markup=main_menu_markup(),
    )


def handle_callback(token, callback_query):
    data = callback_query.get('data') or ''
    message = callback_query.get('message') or {}
    chat_id = message.get('chat', {}).get('id')
    message_id = message.get('message_id')
    user_id = callback_query.get('from', {}).get('id')
    callback_id = callback_query.get('id')

    if not is_authorized(chat_id, user_id):
        telegram.answer_callback(token, callback_id, 'Sem permissão.', show_alert=True)
        return

    if data == 'n:main':
        telegram.edit_message(token, chat_id, message_id, main_menu_text(), reply_markup=main_menu_markup())
        telegram.answer_callback(token, callback_id)
        return

    if data == 'n:model':
        telegram.edit_message(token, chat_id, message_id, providers_text(), reply_markup=providers_markup())
        telegram.answer_callback(token, callback_id)
        return

    if data == 'n:status':
        telegram.edit_message(
            token, chat_id, message_id, status_text(),
            reply_markup=_keyboard([[ _btn('« Menu', 'n:main') ]]),
        )
        telegram.answer_callback(token, callback_id)
        return

    if data.startswith('n:p:'):
        provider_id = data.split(':', 2)[2]
        telegram.edit_message(
            token, chat_id, message_id, models_text(provider_id),
            reply_markup=models_markup(provider_id),
        )
        telegram.answer_callback(token, callback_id)
        return

    if data.startswith('s:'):
        _, provider_id, model_id = data.split(':', 2)
        try:
            app_settings.set_llm(provider_id, model_id, updated_by=user_id)
        except ValueError as err:
            telegram.answer_callback(token, callback_id, str(err), show_alert=True)
            return
        provider_label, model_label = app_settings.current_llm_summary()
        telegram.edit_message(
            token, chat_id, message_id,
            (
                '<b>✅ Modelo atualizado</b>\n\n'
                f'Provedor: <b>{provider_label}</b>\n'
                f'Modelo: <code>{model_label}</code>\n\n'
                'Próximo digest usará esta configuração.'
            ),
            reply_markup=_keyboard([
                [_btn('« Menu', 'n:main')],
                [_btn('🚀 Enviar digest agora', 'a:run')],
            ]),
        )
        telegram.answer_callback(token, callback_id, 'Modelo salvo!')
        return

    if data == 'a:run':
        telegram.answer_callback(token, callback_id, 'Gerando digest…')
        threading.Thread(target=_run_digest_async, args=(token, chat_id), daemon=True).start()
        return

    telegram.answer_callback(token, callback_id)


def handle_message(token, message):
    text = (message.get('text') or '').strip()
    chat_id = message.get('chat', {}).get('id')
    user_id = message.get('from', {}).get('id')

    if text.split('@')[0].lower() not in ('/menu', '/start', '/config'):
        return

    if not is_authorized(chat_id, user_id):
        telegram.send_message(token, chat_id, '⛔ Você não tem permissão para usar este bot.')
        return

    if text.split('@')[0].lower() == '/start':
        telegram.send_message(
            token,
            chat_id,
            '👋 <b>HN FastDigest</b>\n\nUse /menu para ajustar modelo e configurações.',
        )
        return

    send_menu(token, chat_id)


def _run_digest_async(token, chat_id):
    try:
        import hn_summary
        hn_summary.main()
        telegram.send_message(token, chat_id, '✅ Digest enviado com sucesso!')
    except Exception as err:
        telegram.send_message(token, chat_id, f'❌ Erro ao gerar digest: {err}')
