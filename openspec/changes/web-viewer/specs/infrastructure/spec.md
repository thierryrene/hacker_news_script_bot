# Infrastructure & Build Specification

## Purpose
Gerência de arquivos temporários, outputs baseados em file-system nativo (fs) e rotinas de pipeline CI/CD de commit back automatizadas (Github Actions).

## Requirements

### Requirement: Exportação JSON do Resumo Resultante
The Node.js summarizer system (`hn_summary.js`) MUST persist the array output of the processed posts mapped explicitly after receiving the AI prompt answers.

#### Scenario: Gravação Segura em File-System
- GIVEN that `hn_summary.js` successfully executed its summarization pipeline
- WHEN iterating over the posts array towards the end of execution
- THEN the script MUST parse strictly relevant fields (title, url, score, id, summarized_tldr, summarized_insight, tags) explicitly splitting the Gemini raw texts
- AND call synchronous or asynchronous `fs.writeFileSync(...)` to create or overwrite the file `./data/latest.json`.

### Requirement: Persistência Automática em Produção via CI/CD
The GitHub Actions configuration (`summary.yml`) MUST commit and push exactly and exclusively the newly overwritten data JSON file back to the repository to feed the Git Github Pages hook. 

#### Scenario: Bypass Recursivo de Github Action
- GIVEN that the `summary.yml` completed the `npm start` step which in turn altered `./data/latest.json`
- WHEN proceeding to the next automated hook steps
- THEN the runner MUST configure bot git credentials
- AND perform `git commit -am "chore(data): updated daily digest [skip ci]"` ensuring `[skip ci]` parameter avoids self-triggering recursive eternal loops
- AND push cleanly against the active `main` branch.