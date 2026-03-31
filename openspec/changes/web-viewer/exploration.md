## Exploration: Web Viewer para Informações Resumidas

### Current State
Atualmente o sistema é um script Node.js assíncrono (`hn_summary.js`) projetado especificamente para envio _push_. Ele gera dados temporários em memória (objetos JSON mapeados e manipulados do HN + respostas do Gemini), compila tudo numa longa string HTML ou Markdown (`fullMsg`), e dispara sequencialmente requisições via axios para as APIs do Telegram e EvolutionAPI (WhatsApp). A interface existente (`index.html` e `style.css`) é uma "Landing Page" estática pura que não apresenta o conteúdo dinâmico ou último resumo gerado. Não há persistência permanente das métricas das notícias geradas entre execuções.

### Affected Areas
- `hn_summary.js` — Necessário modificar para exportar o dado processado para algum artefato durável.
- `index.html` — Adaptações na landing page atual (`HN FastDigest`) para incluir um link/botão "Ver Edição de Hoje", ou até reestruturá-la para carregar o feed na mesma página se o estado for dinâmico.
- `script.js` — Lógica do client-side para renderizar esses dados.
- `.github/workflows/summary.yml` — Necessário atualizar para realizar deploy do artefato atualizado para o GitHub Pages.

### Approaches

1. **Geração Estática de Componentes HTML (SSG Hardcoded)** — O próprio `hn_summary.js` após construir a `fullMsg`, lê um `template_feed.html`, substitui delimitadores por tags pre-formatadas das notícias renderizadas em HTML, e salva num `.html` estático injetado no diretório. O repositório realiza commit do resultado (ou build via Github Pages).
   - Pros: Suporte impecável de SEO, muito fácil não exige uso de Fetch APi no front, o HTML entrega direto.
   - Cons: Mexer com HTML dinâmico acoplado dentro do `.js` final enche o arquivo utilitário de boilerplates. Menos elegante.
   - Effort: Low

2. **JSON Dump com Fetch no Front-End (Static API Architecture)** — O script `hn_summary.js` consolida o array de objetos e salva-os em um aquivo `latest.json` que é salvo (via build/commit da action) no diretório raiz do GitHub Pages. A `index.html` (com `script.js`) usa um simples `fetch('./latest.json')` e renderiza os cards das notícias de forma nativa e viva na DOM.
   - Pros: Arquitetura mais separada, front focado em UI e JS atuando de "Static API". Permite criar filtros e animações no front end se quiser evoluir depois.
   - Cons: Necessário o Commit Back por parte do runner Github Actions no repositório com o arquivo `latest.json` na master para a hospedagem refleti-lo diariamente (isso pode sujar histórico).
   - Effort: Medium

3. **Banco de Dados Leve (Supabase / Firebase / Supabase)** — Modificar o backend Node.JS para invés de atuar estaticamente, inserir o digest de hoje numa DB serverless. O frontend usa essa DB ou uma Edge Function para requisitar o feed.
   - Pros: Escala massiva. Mantém histórico infinito. Evita sujar o git de commits com dados e JSON.
   - Cons: Desvia o foco leve do projeto. Exige gerenciar mais senhas, migrations e provedores.
   - Effort: High

### Recommendation
A **Approach 2 (JSON Dump c/ Front-End Fetch)** aliada as vantagens do **GitHub Pages** é a mais sólida e elegante. 
A Action do GitHub de cron vai rodar `hn_summary.js`, os resumos criados vão gerar um pacote com informações (Título, Link, Score, TL;DR e Insight). Esse pacote vai ser salvo no raiz como `digest.json`. Depois, a própria action faz um deploy disso pro GitHub Pages. No Front-End o client-side usa Javascript Vanilla (`script.js`) pare recuperar esse `digest.json` e construir os cards bonitos e laranjas da nossa página! 

### Risks
- Precisamos garantir que o arquivo `digest.json` esteja exposto ao servidor estático.
- Necessário certificar que os Commits do bot na cron do painel de Github Actions não gerem loops infinitos se ele disparar push em master. Ideal é ter uma rotina da Actions que comita as mudanças.

### Ready for Proposal
Yes — As opções estão maduras e alinhadas ao ecossistema atual. Podemos iniciar a Proposta via `sdd-propose` e estabelecer exatamente onde ficará o visualizador dentro da pasta.