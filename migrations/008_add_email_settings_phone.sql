-- Migration 008: Add phone to email_settings (used for {{my_phone}} template variable)
ALTER TABLE email_settings ADD COLUMN IF NOT EXISTS phone VARCHAR;
