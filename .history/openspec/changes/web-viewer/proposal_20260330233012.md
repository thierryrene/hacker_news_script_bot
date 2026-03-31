# Proposal: Web Viewer

## Intent
Transformar o sistema de apenas ser um canal "Push" de utilidade silenciada nas APIs para obter um leitor Web dinâmico e estático (disponível através do GitHub Pages). Os leitores poderão consultar os resultados diários do script sem precisar usar os canais sociais.

## Scope

### In Scope
- Criação de um pipeline de exportação `digest.json` salvando os dados dos posts lidos ao término do `hn_summary.js`.
- Modificação na "Landing Page" (`index.html` e `style.css`) para incluir marcações de grid DOM a fim de apresentar os tópicos do digest do JSON.
- Adaptação das rotinas assíncronas do `script.js` client-side para o consumo da Fetch API e renderização dos cards com animações do projeto (ex: `.feature-card`).
- Atualização do script de nuvem do GitHub Actions (`summary.yml`) para realizar um commit das mudanças persistentes no repositorio diariamente sem acionar um loop infinito de CI/CD.

### Out of Scope
- Adoção de frameworks de front-end nativos (React/Vue/Svelte) ou empacotadores profundos (Webpack/Vite). Vanilla JS será utilizado.
- Sistema de paginação histórico (Banco de Dados, logs contínuos e paginação do mês todo). Exportaremos apenas o último "resumo diário", mantendo ele focado.

## Approach
Abordagem "Static API". Após os loops de post com as variáveis extraídas, persistimos os dicionários JSON no file-system em uma stringfied payload (`data/latest.json`). O artefato web será atualizado pelos componentes no front por requisições locais base, injetadas com DOM Manipulation. Adotaremos as tags `[skip ci]` nos auto-commits.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `hn_summary.js` | Modified | Escrita do arquivo `.json` antes do processo `process.exit`. |
| `index.html` / `script.js` | Modified | Tag `<section>` base para alocar feeds das notícias |
| `.github/workflows/summary.yml` | Modified | Rotina Action de commit seguro na `origin/main` |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Actions recursivas por _bot pushes_ do JSON. | Med | Forçar que o bash script use flags limpas de auto-commit no push e adicionar `[skip ci]` na mensagem commital da Github Action limitando trigger no workflow. |
| CORS issue em requisições de testes. | Low | O client fará fetch via path web local `./data/latest.json` garantido de passar por servidores como os do Github Pages. |

## Rollback Plan
Fazer stash/revert do `.github/workflows/summary.yml` para a versão isolada de build sem auto-commits e desfazer HTML client-side para a tag antiga do branch.

## Dependencies
- Node.js Built-in `fs` API para escrever arquivos.
- Vanilla Fetch API (built-in do Browser). Nenhuma dependência externa será exigida em `package.json`. 

## Success Criteria
- [ ] Ao terminar o node local manual a pasta `/data/latest.json` recebe arquivos atualizados perfeitamente extraídos.
- [ ] O `index.html` mostra com DOM injection todas as ~15 notícias renderizadas bonitas mantendo os temas da landing original e usando o novo formato segmentado.
- [ ] Rodar o Github Actions resulta nos arquivos atualizados perfeitamente via `git push` no branch e a publicação live do Github Pages reflete.