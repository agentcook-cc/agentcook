---
name: generate-followups
title: Generate Follow-ups
description: Suggest 3 follow-up questions for the current conversation.
version: 0.1.0
category: chat
updated_at: 2026-06-03T09:00:00+00:00
---

# Generate follow-up questions

1. Look at the last answer and the user's underlying goal.
2. Propose exactly three follow-up questions the user is likely to ask
   next: one that goes deeper, one that broadens scope, one that moves
   toward action.
3. Each question ≤ 15 words, phrased from the user's point of view,
   in the user's language. Output as a numbered list, nothing else.
