"""Bot Telegram com polling — responde /menu e callbacks de configuração."""

import os
import time

from dotenv import load_dotenv

import telegram
import telegram_menu

load_dotenv(override=True)

TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')


def run_polling():
    if not TOKEN:
        raise SystemExit('❌ TELEGRAM_BOT_TOKEN não configurado no .env')

    print('🤖 Bot Telegram iniciado. Aguardando /menu …')
    offset = None

    while True:
        try:
            resp = telegram.get_updates(TOKEN, offset=offset, timeout=30)
            for update in resp.get('result', []):
                offset = update['update_id'] + 1
                if 'callback_query' in update:
                    telegram_menu.handle_callback(TOKEN, update['callback_query'])
                elif 'message' in update:
                    telegram_menu.handle_message(TOKEN, update['message'])
        except KeyboardInterrupt:
            print('\n👋 Bot encerrado.')
            break
        except Exception as err:
            print(f'⚠️ Erro no polling: {err}')
            time.sleep(3)


if __name__ == '__main__':
    run_polling()
