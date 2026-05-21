# Specification: Cache and JSON Refactor

## Requirement: SQLite Caching System
The system MUST cache Gemini-generated summaries to avoid redundant API usage and improve performance.

### Scenario: Cache Hit
- GIVEN a post with a specific ID and content hash
- AND a summary for this post and hash already exists in the database
- WHEN the system requests a summary for this post
- THEN the system MUST retrieve the summary from the database
- AND MUST NOT call the Gemini API.

### Scenario: Cache Miss
- GIVEN a post with a specific ID and content hash
- AND no summary for this post and hash exists in the database
- WHEN the system requests a summary for this post
- THEN the system MUST call the Gemini API
- AND MUST save the resulting summary in the database for future use.

## Requirement: Structured JSON Responses
The system MUST use Gemini's JSON schema feature to ensure the output is always in a parseable format.

### Scenario: Validating Schema
- GIVEN a list of posts
- WHEN the system calls `summarizeAllWithGemini`
- THEN the response MUST be a valid JSON array of objects
- AND each object MUST contain `emoji`, `tldr`, `porQueImporta`, and `tags`.
