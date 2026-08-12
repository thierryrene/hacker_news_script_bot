"""Configurações persistidas do digest (compartilhadas entre bot e pipeline)."""

import json
import os
from copy import deepcopy
from datetime import datetime, timezone

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
SETTINGS_PATH = os.path.join(DATA_DIR, 'settings.json')

DEFAULTS = {
    'llm_provider': 'gemini',
    'llm_model': 'gemini-2.5-flash',
}

PROVIDERS = {
    'gemini': {
        'label': 'Google Gemini',
        'emoji': '✨',
        'env_key': 'GEMINI_API_KEY',
        'models': [
            {'id': 'gemini-2.5-flash', 'label': '2.5 Flash'},
            {'id': 'gemini-2.5-pro', 'label': '2.5 Pro'},
            {'id': 'gemini-2.0-flash', 'label': '2.0 Flash'},
        ],
    },
    'openrouter': {
        'label': 'OpenRouter',
        'emoji': '🔀',
        'env_key': 'OPENROUTER_API_KEY',
        'models': [
            {'id': 'google/gemini-2.5-flash', 'label': 'Gemini 2.5 Flash'},
            {'id': 'anthropic/claude-sonnet-4', 'label': 'Claude Sonnet 4'},
            {'id': 'openai/gpt-4o', 'label': 'GPT-4o'},
            {'id': 'openai/o3-mini', 'label': 'o3-mini'},
        ],
    },
    'anthropic': {
        'label': 'Anthropic Claude',
        'emoji': '🎭',
        'env_key': 'ANTHROPIC_API_KEY',
        'models': [
            {'id': 'claude-sonnet-4-20250514', 'label': 'Sonnet 4'},
            {'id': 'claude-3-5-sonnet-20241022', 'label': '3.5 Sonnet'},
            {'id': 'claude-3-5-haiku-20241022', 'label': '3.5 Haiku'},
        ],
    },
    'openai': {
        'label': 'OpenAI / Codex',
        'emoji': '🧠',
        'env_key': 'OPENAI_API_KEY',
        'models': [
            {'id': 'gpt-4o', 'label': 'GPT-4o'},
            {'id': 'gpt-4o-mini', 'label': 'GPT-4o Mini'},
            {'id': 'o3-mini', 'label': 'o3-mini'},
        ],
    },
}


def _merge_defaults(raw):
    merged = deepcopy(DEFAULTS)
    if not isinstance(raw, dict):
        return merged
    provider = raw.get('llm_provider') or merged['llm_provider']
    if provider not in PROVIDERS:
        provider = merged['llm_provider']
    model = raw.get('llm_model') or merged['llm_model']
    valid_ids = {m['id'] for m in PROVIDERS[provider]['models']}
    if model not in valid_ids:
        model = PROVIDERS[provider]['models'][0]['id']
    merged['llm_provider'] = provider
    merged['llm_model'] = model
    if raw.get('updated_at'):
        merged['updated_at'] = raw['updated_at']
    if raw.get('updated_by') is not None:
        merged['updated_by'] = raw['updated_by']
    return merged


def load_settings():
    """Carrega settings.json; cria com defaults se ausente."""
    if os.path.isfile(SETTINGS_PATH):
        try:
            with open(SETTINGS_PATH, encoding='utf-8') as fh:
                return _merge_defaults(json.load(fh))
        except (OSError, json.JSONDecodeError):
            pass

    settings = _merge_defaults({})
    env_model = os.environ.get('GEMINI_MODEL')
    if env_model:
        settings['llm_model'] = env_model
    save_settings(settings)
    return settings


def save_settings(settings):
    os.makedirs(DATA_DIR, exist_ok=True)
    payload = _merge_defaults(settings)
    with open(SETTINGS_PATH, 'w', encoding='utf-8') as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
    return payload


def update_settings(**changes):
    current = load_settings()
    current.update(changes)
    current['updated_at'] = datetime.now(timezone.utc).isoformat()
    return save_settings(current)


def get_provider(provider_id=None):
    provider_id = provider_id or load_settings()['llm_provider']
    return PROVIDERS.get(provider_id)


def provider_label(provider_id=None):
    provider = get_provider(provider_id)
    if not provider:
        return provider_id or 'desconhecido'
    return f"{provider['emoji']} {provider['label']}"


def model_label(provider_id=None, model_id=None):
    settings = load_settings()
    provider_id = provider_id or settings['llm_provider']
    model_id = model_id or settings['llm_model']
    provider = get_provider(provider_id)
    if not provider:
        return model_id
    for model in provider['models']:
        if model['id'] == model_id:
            return model['label']
    return model_id


def current_llm_summary():
    settings = load_settings()
    return provider_label(settings['llm_provider']), model_label(
        settings['llm_provider'], settings['llm_model'],
    )


def validate_provider_api_key(provider_id=None):
    provider_id = provider_id or load_settings()['llm_provider']
    provider = get_provider(provider_id)
    if not provider:
        return False, f'Provedor desconhecido: {provider_id}'
    key = os.environ.get(provider['env_key'], '').strip()
    if not key:
        return False, f"Variável {provider['env_key']} não configurada."
    return True, ''


def set_llm(provider_id, model_id, updated_by=None):
    if provider_id not in PROVIDERS:
        raise ValueError(f'Provedor inválido: {provider_id}')
    valid_ids = {m['id'] for m in PROVIDERS[provider_id]['models']}
    if model_id not in valid_ids:
        raise ValueError(f'Modelo inválido para {provider_id}: {model_id}')
    changes = {'llm_provider': provider_id, 'llm_model': model_id}
    if updated_by is not None:
        changes['updated_by'] = updated_by
    return update_settings(**changes)
