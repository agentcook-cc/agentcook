---
name: classify-intent
title: Classify Intent
description: Map a user utterance to one of a registered intent set.
version: 1.2.0
category: nlp
updated_at: 2026-06-03T09:00:00+00:00
---

# Classify intent

Default intent set (use the user's own set if they provide one):
`pre_sale_question`, `order_status`, `return_or_refund`, `complaint`,
`product_feedback`, `other`.

1. Read the utterance; pick exactly one primary intent.
2. Give a confidence between 0 and 1 and a one-line rationale.
3. If confidence < 0.6, also list the runner-up intent.
4. Output format:
   `intent: <name> (confidence 0.00) — <rationale>`
