-- Add phone number field to leads table.
-- Idempotent — safe to re-run (IF NOT EXISTS).

ALTER TABLE leads ADD COLUMN IF NOT EXISTS phone VARCHAR;
