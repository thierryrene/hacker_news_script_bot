# Proposal: Integrate Comments Message

## Intent
Move the community discussion context directly under each individual post's main Telegram block (alongside TL;DR and Insights) to maintain contextual coherence and remove hashtags from the summary output.

## Approach
1. Refactor the Gemini prompt in `hn_summary.js` to instruct it not to produce hashtags.
2. Remove any regex logic parsing tags.
3. During the `fullMsg` builder loop, append `🗣️ Comunidade: [comments summary]` directly after the `📝 [summary]` block.
4. Remove the dedicated isolated message `commentsMsg` and its chunk sending execution.
5. This reduces visual clutter and keeps everything unified.

