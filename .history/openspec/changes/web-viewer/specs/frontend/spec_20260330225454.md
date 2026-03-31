# Frontend & Rendering Specification

## Purpose
Gerenciamento da estrutura de exibição visual dos resultados sumarizados através do site estático hospedado publicamente.

## Requirements

### Requirement: Exibição Assíncrona do Feed Diário
The system MUST dynamically fetch the latest exported `digest.json` and inject the records efficiently into a designated DOM container upon page load.

#### Scenario: Sucesso na recuperação do feed
- GIVEN that `data/latest.json` is legitimately populated by an earlier script execution
- WHEN the user accesses `index.html` through a web server (like Github Pages)
- THEN the vanilla javascript MUST execute a GET fetch for the json contents
- AND iterate through the array rendering HTML components containing Title, Points, Original URL, Discussion URL, TL;DR, Insight and extracted tags.

#### Scenario: Fallback para estados vazios ou arquivos perdidos
- GIVEN that `data/latest.json` is either missing (404) or malformed
- WHEN the user accesses `index.html`
- THEN the script MUST cleanly catch the error without crashing the rest of the application
- AND inject a user-friendly error message indicating that "Os resumos de hoje ainda não foram gerados".

### Requirement: Layout Responsivo e Fluido
The rendered feed MUST reuse existing design tokens and CSS patterns (such as `.feature-card` or custom grid properties) to maintain UI consistency and readability out of the box in Mobile devices.

#### Scenario: Enquadramento Grid Mobile
- GIVEN the successfully parsed nodes
- WHEN the browser renders the cards array
- THEN it MUST follow flexbox or grid properties guaranteeing a single-column layout on viewports under 768px.