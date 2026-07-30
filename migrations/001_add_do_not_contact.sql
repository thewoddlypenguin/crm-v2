-- Migration: add do_not_contact to leads
-- Run once against the live database before restarting the app.
--
--   docker compose exec db psql -U leverage -d leveragecrm -f /dev/stdin < migrations/001_add_do_not_contact.sql
--
-- Safe to run multiple times (IF NOT EXISTS guard).

ALTER TABLE leads
    ADD COLUMN IF NOT EXISTS do_not_contact BOOLEAN NOT NULL DEFAULT FALSE;
