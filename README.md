# Resumo Hacker News 📰🤖

Este projeto é um script automatizado que coleta os posts mais populares do **Hacker News**, gera resumos inteligentes em português utilizando a IA do **Google Gemini**, e envia um digest diário para canais do **Telegram** e **WhatsApp**.

## 🚀 Funcionalidades

- **Coleta Inteligente**: Filtra os top stories do Hacker News com pontuação superior a 50 pontos.
- **Extração de Conteúdo**: Lê o conteúdo das páginas dos links para fornecer mais contexto à IA.
- **Resumos com IA**: Utiliza o Google Gemini para gerar resumos ricos de 2 a 4 frases por notícia.
- **Multi-plataforma**: Envia as notificações formatadas para:
  - **Telegram**: Mensagens em HTML.
  - **WhatsApp**: Via Evolution API (com conversão automática para markdown e encurtador de links).

---

## 🛠️ Instalação

### Pré-requisitos
- [Node.js](https://nodejs.org/) (versão 18 ou superior recomendada)
- Chave de API do Google Gemini
- Bot do Telegram (ou canal) configurado
- Instância da Evolution API para WhatsApp (opcional)

### Passo a Passo

1. **Instale as dependências**:
   ```bash
   npm install
   ```

2. **Configure as variáveis de ambiente**:
   Copie o arquivo de exemplo:
   ```bash
   cp .env.example .env
   ```
   Abra o arquivo `.env` e preencha com suas credenciais do Telegram, Gemini e Evolution API.

---

## 🏃‍♂️ Como Executar

Para rodar o script manualmente:

```bash
npm start
```

### 📅 Automatização (Cron / GitHub Actions)

Você pode agendar a execução deste script para receber os resumos diariamente. 

Exemplo de **Cron** para rodar todos os dias às 08:00:
```bash
0 8 * * * cd /caminho/para/resumo_hacker_news && npm start >> logs.txt 2>&1
```

---

## 📦 Dependências Principais

- `axios`: Para requisições HTTP.
- `@google/generative-ai`: Integração com o Google Gemini.
- `cheerio`: Para raspagem e extração de texto dos links.
- `dotenv`: Gerenciamento de variáveis de ambiente.

---
*Desenvolvido para facilitar sua leitura diária de notícias tech!*
