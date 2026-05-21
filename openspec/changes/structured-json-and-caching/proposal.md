# Proposal: Structured JSON and Caching

## Intent
Enhance the reliability, performance, and depth of the news summaries by transitioning to Gemini's structured JSON output and implementing a local SQLite cache.

## Approach
1. **Gemini JSON Schema**: Utilize `responseMimeType: "application/json"` and explicit `responseSchema` to ensure predictable outputs for both post summaries and community discussions.
2. **Local Caching**: Implement an SQLite database (managed via a Python helper script for simplicity and performance) to store generated summaries, avoiding redundant API calls for the same content.
3. **Data Model Expansion**: Include new fields like "Por Que Importa" (Why it Matters), Emojis, and "Community Discussion" in the exported JSON and message templates.
4. **Asynchronous Processing**: Optimize link scraping and comment fetching by using `Promise.all` for concurrent execution.
5. **Web Viewer Update**: Update the frontend to render the new structured data fields.

## Affected Modules
- `hn_summary.js`: Main logic refactored for JSON schema and caching.
- `cache.js` & `cache_helper.py`: New caching layer.
- `script.js`: Updated to handle new JSON fields.
- `data/latest.json`: Schema updated with enriched data.
