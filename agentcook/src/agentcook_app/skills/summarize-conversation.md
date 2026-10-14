---
name: summarize-conversation
title: Summarize Conversation
description: Condense a long chat into key bullet points.
version: 1.0.0
category: memory
updated_at: 2026-06-03T09:00:00+00:00
---

# Summarize a conversation

Use when the user asks for a recap, summary, TL;DR or "where are we".

1. Re-read the conversation and identify: the user's goal, decisions made,
   open questions, and action items (with owners if mentioned).
2. Output, in the user's language:
   - **Goal** — one sentence.
   - **Decisions** — bullets, most important first.
   - **Open questions** — bullets (omit the section if none).
   - **Next steps** — numbered list.
3. Keep it under 150 words unless the user asks for more detail.
4. Do not introduce facts that were not in the conversation.
