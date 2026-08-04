-- Migration 006: Add signature column to email_settings
ALTER TABLE email_settings ADD COLUMN IF NOT EXISTS signature TEXT;
