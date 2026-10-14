---
name: extract-entities
title: Extract Entities
description: Pull named entities (people, places, products) from text.
version: 0.3.1
category: nlp
updated_at: 2026-06-03T09:00:00+00:00
---

# Extract entities

1. Scan the provided text for: PERSON, ORGANIZATION, PRODUCT, LOCATION,
   DATE, MONEY, and SKU/ID codes.
2. Return a Markdown table with columns `Entity | Type | Context`, where
   Context is the shortest quote that shows how the entity is used.
3. Merge duplicates and normalize obvious variants ("iPhone15" → "iPhone 15").
4. If the user asks for JSON, return a JSON array of
   `{"text", "type", "context"}` objects instead — nothing else.
