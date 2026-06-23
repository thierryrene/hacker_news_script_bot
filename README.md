# Resumo Hacker News 📰🤖

Este projeto é um pipeline automatizado em **Python** que coleta os posts mais populares do **Hacker News**, gera resumos inteligentes em português utilizando a IA do **Google Gemini** (saída JSON estruturada), cacheia os resultados em SQLite e envia um digest diário para canais do **Telegram** e **WhatsApp**.

## 🚀 Funcionalidades

- **Coleta Inteligente**: Filtra os top stories do Hacker News com pontuação superior a 50 pontos.
- **Extração de Conteúdo**: Lê o conteúdo das páginas dos links e os comentários da comunidade para dar mais contexto à IA.
- **Resumos com IA**: Usa o Google Gemini com schema JSON estruturado (emoji + TL;DR por post, e um resumo da voz da comunidade).
- **Cache SQLite**: Evita reprocessar conteúdo idêntico; com TTL configurável.
- **Multi-plataforma**:
  - **Telegram**: Mensagens em HTML.
  - **WhatsApp**: Via Evolution API (conversão automática para markdown e encurtador de links).

---

## 🧱 Stack

Projeto **single-language (Python 3)**:

| Camada          | Ferramenta                               |
| --------------- | ---------------------------------------- |
| HTTP / scraping | `requests` + `beautifulsoup4`            |
| Resumo (LLM)    | `google-genai` (Gemini, structured JSON) |
| Cache           | `sqlite3` da stdlib (acesso direto)      |
| Config          | `python-dotenv`                          |
| Testes          | `unittest` da stdlib                     |

---

## 🧭 Por que Python puro (a verdade do projeto)

A primeira versão era um orquestrador **Node.js** que, só para o cache SQLite, chamava um script Python (`cache_helper.py`) via `execFileSync` — **um processo Python novo a cada leitura/escrita de cache**. Em uma execução isso eram dezenas de spawns de `python3`, exigia Node **e** Python no ambiente e serializava JSON na fronteira entre as duas linguagens.

A justificativa original ("simplicidade e performance") não se sustentava: duas linguagens não são simples, e spawnar um processo por query é o jeito mais lento de falar com SQLite. A migração para Python puro elimina o subprocesso por operação, remove Node/pnpm do CI e deixa **uma linguagem só** para manter.

> Os hashes do cache continuam sendo MD5 utf-8 do conteúdo — idênticos aos da versão Node — então o `data/cache.db` já existente **permanece válido** após a migração.

---

## 🛠️ Instalação

### Pré-requisitos
- [Python 3](https://www.python.org/) (3.10+ recomendado)
- Chave de API do Google Gemini
- Bot do Telegram (ou canal) configurado
- Instância da Evolution API para WhatsApp (opcional)

### Passo a Passo

1. **Instale as dependências**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure as variáveis de ambiente**:
   ```bash
   cp .env.example .env
   ```
   Abra o `.env` e preencha com suas credenciais do Telegram, Gemini e Evolution API.

---

## 🏃 Como Executar

```bash
python hn_summary.py
```

### ✅ Testes

```bash
python -m unittest
```

### 📅 Automatização (GitHub Actions)

O workflow `.github/workflows/summary.yml` roda diariamente às 11:00 UTC (08:00 BRT) e também sob demanda (`workflow_dispatch`). Ele instala as deps Python, executa `python hn_summary.py` e commita `data/cache.db` (o cache é versionado de propósito para persistir entre execuções).

---

## ⚙️ Variáveis de Ambiente

| Variável                 | Obrigatória | Descrição                                    |
| ------------------------ | ----------- | -------------------------------------------- |
| `GEMINI_API_KEY`         | sim         | Chave da API do Google Gemini                |
| `TELEGRAM_BOT_TOKEN`     | p/ Telegram | Token do bot                                 |
| `TELEGRAM_CHAT_ID`       | p/ Telegram | ID do chat de destino                        |
| `GEMINI_MODEL`           | não         | Default: `gemini-2.5-flash`                  |
| `CACHE_TTL_DAYS`         | não         | TTL do cache em dias (default 7; `0` desliga)|
| `COMMENT_REFRESH_GROWTH` | não         | Crescimento de comentários que re-resume (default `0.25` = 25%) |
| `EVOLUTION_API_URL`      | p/ WhatsApp | Base URL da Evolution API                    |
| `EVOLUTION_API_KEY`      | p/ WhatsApp | Chave de autenticação                        |
| `EVOLUTION_API_INSTANCE` | p/ WhatsApp | Instância do WhatsApp                        |
| `WHATSAPP_NUMBER`        | p/ WhatsApp | Número ou JID de grupo                       |

---
*Desenvolvido para facilitar sua leitura diária de notícias tech!*
