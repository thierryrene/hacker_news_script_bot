# Proposal: Top Comments Summary

## Intent
Fetch the top comments for the best Hacker News daily posts, process them with Gemini to extract key dissenting opinions or rich discussions, and send them as a dedicated secondary update.

## Approach
1. During `hn_summary.js` execution, loop through the chosen top posts, grab the first few `kids` (comment IDs).
2. Fetch the text of those comments.
3. Pass a concatenated string of the comments to Gemini with a prompt focused on summary of discussion and dissenting opinions.
4. Save the results into `data/comments.json`.
5. Send a separate Telegram message containing just the community insights.

## Scope
- `hn_summary.js`: Add comment fetching, Gemini summarization for comments, and Telegram/file output.
- `summary.yml`: Make sure `data/comments.json` is also tracked by git in the GitHub Action.
- `script.js` & `index.html`: Update UI to show these comments, maybe as an expandable section or secondary feed (Out of scope for this task right now, or keep it simple).

