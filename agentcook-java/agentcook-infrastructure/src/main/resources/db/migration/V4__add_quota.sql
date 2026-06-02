-- ADR-018 chat quota tiered models (v1 = 2 free questions / account, no reset)
-- New columns on `users`:
--   free_questions_used   — running counter of consumed free-tier questions.
--                           Domain layer increments via User.consumeFreeQuestion().
--   free_questions_quota  — the per-account ceiling; v1 default 2 per ADR-018 §1.
--                           Stored per-row (not from env) so individual upgrades
--                           — e.g. a paid user lift to 50 — are a single UPDATE.
--   quota_reset_at        — reserved for v2 (daily / monthly reset). NULL means
--                           "no reset scheduled"; the column ships now so v2
--                           doesn't require another ALTER on a populated table.
ALTER TABLE users ADD COLUMN free_questions_used  INTEGER     DEFAULT 0    NOT NULL;
ALTER TABLE users ADD COLUMN free_questions_quota INTEGER     DEFAULT 2    NOT NULL;
ALTER TABLE users ADD COLUMN quota_reset_at       TIMESTAMPTZ DEFAULT NULL;
