# Proposal: Telegram Template Optimization

## Intent
Maximização da absorção de conhecimento dos resumos do Hacker News via Telegram. O formato atual (um único bloco de texto) é denso. Dividiremos o resumo em seções claras e adicionaremos o link da discussão original da comunidade.

## Scope

### In Scope
- Atualizar o prompt do Gemini em `hn_summary.js` para forçar um formato estruturado (TL;DR + Insight/Ação + Tags).
- Modificar o template da string final (Telegram/WhatsApp) para injetar o link dos comentários do Hacker News (`news.ycombinator.com/item?id=X`).
- Proteger a lógica de _chunking_ (`\n\n`) do Telegram para evitar quebra de blocos no meio de uma notícia.

### Out of Scope
- Fetch direto via API de comentários do Hacker News (muita requisição, deixado para futura versão se necessário).
- Mudanças profundas no `evolution.js` (apenas garantir que o novo HTML converte bem para Markdown do WhatsApp).

## Approach
Refatorar apenas o construtor do bot (`hn_summary.js`), com as seguintes escolhas técnicas:

**Approach Selecionada:**
- **Approach 1 ("TL;DR + Insight + Tags e Discussão"):** Mudar o prompt do modelo no `summarizeAllWithGemini` para incluir as seções pedidas e injetar no iterador de mensagens o link de discussões da comunidade (News YCombinator). O menor risco e custo/benefício mais alto.

**Alternative Approaches Considered (Rejeitadas por hora):**
- **Approach 2 (Inclusão de Comentários Nativos no Fetch):** Alterar requisições em lote para extrair os *top 2* comentários do HTML da news.ycombinator.com para servir de contexto adicional para o Gemini. *Rejeitada porque aumenta drasticamente o tempo, falhas de conectividade e consumo de tokens LLM.*
- **Approach 3 (Parsing Restrito via Regex):** Forçar o Gemini a entregar um output chave-valor estrito e parsear isso via Regex em Node antes da conversão para HTML. *Rejeitada pois o esforço extra é alto e a fragilidade do modelo falhar no regex criaria exceções duras de envio.*

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `hn_summary.js` | Modified | Prompt do LLM e iterador da montagem da variável `fullMsg`. |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Quebra do Parser HTML do Telegram (formatação desbalanceada do LLM). | Medium | Validar/limpar resposta do LLM ou usar regex restritivo no Node antes do envio. |
| Chunking irregular (`\n\n` dividindo um mesmo post). | Low | Ajustar o _split_ para usar um delimitador fixo de post, e não apensas _newline_. |

## Rollback Plan
Fazer stash das mudanças locais em `hn_summary.js` e/ou reverter o commit de refatoração pelo `git checkout`. Custo de falha mínimo.

## Dependencies
- Nenhuma dependência externa nova (utiliza as mesmas chaves de API da OpenAI/Google e Telegram atuais).

## Success Criteria
- [ ] O script envia mensagens no formato "TL;DR + Insight".
- [ ] O link para a página dos comentários originais no Hacker News é visível.
- [ ] Nenhuma mensagem falha via HTTP 400 (Bad Request) do Telegram.
- [ ] O script para o WhatsApp (evolution.js) continua enviando mensagens com sucesso.
