"""Geração JSON estruturada via múltiplos provedores de LLM."""

import json
import os
import re
import time

import requests

import settings as app_settings


def _schema_prompt_suffix(schema):
    return (
        '\n\nResponda APENAS com JSON válido, sem markdown, sem texto extra. '
        f'Siga estritamente este schema:\n{json.dumps(schema, ensure_ascii=False)}'
    )


def _strip_json_fences(text):
    cleaned = (text or '').strip()
    if cleaned.startswith('```'):
        cleaned = re.sub(r'^```(?:json)?\s*', '', cleaned)
        cleaned = re.sub(r'\s*```$', '', cleaned)
    return cleaned.strip()


def _generate_gemini(prompt, schema, model):
    from google.genai import types

    api_key = os.environ.get('GEMINI_API_KEY', '').strip()
    if not api_key:
        raise RuntimeError('GEMINI_API_KEY não configurada.')

    from google import genai
    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type='application/json',
            response_schema=schema,
        ),
    )
    return (response.text or '').strip()


def _generate_openai_compatible(prompt, schema, model, api_key, base_url, extra_headers=None):
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json',
    }
    if extra_headers:
        headers.update(extra_headers)

    payload = {
        'model': model,
        'messages': [
            {
                'role': 'system',
                'content': 'Você responde somente em JSON válido conforme o schema pedido.',
            },
            {'role': 'user', 'content': prompt + _schema_prompt_suffix(schema)},
        ],
        'response_format': {'type': 'json_object'},
        'temperature': 0.2,
    }
    resp = requests.post(
        f'{base_url.rstrip("/")}/chat/completions',
        headers=headers,
        json=payload,
        timeout=120,
    )
    resp.raise_for_status()
    data = resp.json()
    return data['choices'][0]['message']['content']


def _generate_openrouter(prompt, schema, model):
    api_key = os.environ.get('OPENROUTER_API_KEY', '').strip()
    if not api_key:
        raise RuntimeError('OPENROUTER_API_KEY não configurada.')
    return _generate_openai_compatible(
        prompt,
        schema,
        model,
        api_key,
        'https://openrouter.ai/api/v1',
        extra_headers={
            'HTTP-Referer': 'https://github.com/thierryrene/hacker_news_script_bot',
            'X-Title': 'HN FastDigest',
        },
    )


def _generate_openai(prompt, schema, model):
    api_key = os.environ.get('OPENAI_API_KEY', '').strip()
    if not api_key:
        raise RuntimeError('OPENAI_API_KEY não configurada.')
    return _generate_openai_compatible(
        prompt, schema, model, api_key, 'https://api.openai.com/v1',
    )


def _generate_anthropic(prompt, schema, model):
    api_key = os.environ.get('ANTHROPIC_API_KEY', '').strip()
    if not api_key:
        raise RuntimeError('ANTHROPIC_API_KEY não configurada.')

    resp = requests.post(
        'https://api.anthropic.com/v1/messages',
        headers={
            'x-api-key': api_key,
            'anthropic-version': '2023-06-01',
            'content-type': 'application/json',
        },
        json={
            'model': model,
            'max_tokens': 8192,
            'system': 'Responda somente com JSON válido conforme o schema pedido.',
            'messages': [
                {'role': 'user', 'content': prompt + _schema_prompt_suffix(schema)},
            ],
            'temperature': 0.2,
        },
        timeout=120,
    )
    resp.raise_for_status()
    data = resp.json()
    parts = data.get('content') or []
    texts = [part.get('text', '') for part in parts if part.get('type') == 'text']
    return ''.join(texts)


_GENERATORS = {
    'gemini': _generate_gemini,
    'openrouter': _generate_openrouter,
    'openai': _generate_openai,
    'anthropic': _generate_anthropic,
}


def generate_raw(prompt, schema, provider=None, model=None):
    cfg = app_settings.load_settings()
    provider = provider or cfg['llm_provider']
    model = model or cfg['llm_model']
    generator = _GENERATORS.get(provider)
    if not generator:
        raise ValueError(f'Provedor não suportado: {provider}')
    ok, err = app_settings.validate_provider_api_key(provider)
    if not ok:
        raise RuntimeError(err)
    return generator(prompt, schema, model)


def call_llm_json(prompt, schema, retries=3, base_delay_s=1.0, _generate_fn=None, provider=None, model=None):
    generate = _generate_fn or (lambda p, s: generate_raw(p, s, provider=provider, model=model))
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            text = _strip_json_fences(generate(prompt, schema))
            try:
                return json.loads(text)
            except json.JSONDecodeError as parse_err:
                raise ValueError(f'Resposta não-JSON do LLM: {parse_err}')
        except Exception as err:
            last_err = err
            print(f'⚠️ LLM tentativa {attempt}/{retries} falhou: {err}')
            if attempt < retries:
                time.sleep(base_delay_s * 2 ** (attempt - 1))
    raise last_err
