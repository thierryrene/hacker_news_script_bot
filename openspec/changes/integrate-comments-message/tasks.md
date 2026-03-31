# Tasks: Integrate Comments Message

- [x] 1. Update the `summarizeAllWithGemini` prompt in `hn_summary.js` to explicitly avoid outputting tags/hashtags.
- [x] 2. Remove the tags extraction regex logic and variable assignment in `hn_summary.js`.
- [x] 3. Move the community text insertion (`cleanComm`) directly into `fullMsg` formulation inside the main loop for each post (appended below `📝 summary`).
- [x] 4. Delete the logic that created and sent the separate `commentsMsg` chunk at the bottom of the script.
- [x] 5. Execute code, verify outputs locally, and commit changes.
