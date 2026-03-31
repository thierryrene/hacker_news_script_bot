# Notifications Specification

## Purpose
Gerenciamento da formatação e envio de resumos diários do Hacker News para canais de notificação (Telegram e WhatsApp), otimizando a legibilidade e garantindo a aquisição de conhecimento.

## Requirements

### Requirement: Formatação Estruturada do Resumo Modular via LLM
The system MUST request the LLM to format the response into specific semantic sections for each post to facilitate reading.

#### Scenario: Geração Condicionada na API do Gemini
- GIVEN a list of fetched top Hacker News posts
- WHEN the system builds the prompt string for the LLM
- THEN the prompt MUST explicitly instruct the model to return the summary using "TL;DR", "Insight/Ação" e "Tags"
- AND it MUST contain strictly valid HTML or string characters that will not trigger Telegram parse mode failure.

### Requirement: Inclusão do Link de Comentários Hacker News
The system MUST inject the original discussion URL of the Hacker News item in the generated layout.

#### Scenario: Compilação das URLs do Post
- GIVEN a valid fetched post with an ID attribute
- WHEN the script iterates over the summarized items to build the `fullMsg`
- THEN the system MUST concatenate an explicit link to `https://news.ycombinator.com/item?id={id}`
- AND the link SHOULD be labeled as "Discussão (HN)".

### Requirement: Lógica Segura de Chunking para Mensagens de Envio
The system MUST divide the generated final message into chunks smaller than the character limit of the Telegram API (~4000 characters) WITHOUT breaking the layout of an individual post.

#### Scenario: Particionamento da Mensagem Extensa
- GIVEN a compiled `fullMsg` string that exceeds the max character limit
- WHEN the system attempts to split the message to bypass limits
- THEN it MUST split gracefully at a hard delimiter (e.g., standard post separator string like `\n\n---`) rather than arbitrary `\n\n`
- AND the Telegram API bot MUST accept all chunked arrays with a 200 HTTP response.