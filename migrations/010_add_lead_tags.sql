-- 010: Add tags to leads for categorization (tags feature).
-- Stored as JSON text (array of lowercase strings) for SQLite/Postgres parity.
-- Backfills nothing — existing leads simply have NULL tags (treated as []).
ALTER TABLE leads ADD COLUMN IF NOT EXISTS tags TEXT;

-- Speed up tag filtering (LIKE '%"tag"%') with a trigram index.
CREATE INDEX IF NOT EXISTS ix_leads_tags_trgm ON leads USING gin (tags gin_trgm_ops);
