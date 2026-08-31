-- Migration 009: Add TEST_EMAIL_SENT to the activity_type enum
--
-- Distinguishes test-mode (simulated) lead email sends from real outreach in the
-- activity history. SQLAlchemy's create_all() cannot extend an existing enum on
-- Postgres, so the new value must be added with ALTER TYPE.
--
-- Safe to re-run: IF NOT EXISTS is supported on PostgreSQL 10+.
ALTER TYPE activity_type ADD VALUE IF NOT EXISTS 'TEST_EMAIL_SENT';
