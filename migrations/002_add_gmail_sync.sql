-- Migration: add Gmail OAuth connection and synced email tables
-- Run once against the live database before restarting the app.
--
-- Safe to run multiple times (IF NOT EXISTS guard).

CREATE TABLE IF NOT EXISTS gmail_connections (
    id VARCHAR PRIMARY KEY,
    owner_user_id VARCHAR NOT NULL REFERENCES users(id),
    provider VARCHAR NOT NULL DEFAULT 'gmail',
    google_email VARCHAR NOT NULL,
    access_token TEXT NOT NULL,
    refresh_token TEXT NOT NULL,
    token_expiry TIMESTAMP,
    sync_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    last_sync_at TIMESTAMP,
    last_error TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE UNIQUE INDEX IF NOT EXISTS ix_gmail_connections_owner ON gmail_connections(owner_user_id);

CREATE TABLE IF NOT EXISTS synced_emails (
    id VARCHAR PRIMARY KEY,
    user_id VARCHAR NOT NULL REFERENCES users(id),
    lead_id VARCHAR NOT NULL REFERENCES leads(id),
    provider VARCHAR NOT NULL DEFAULT 'gmail',
    external_message_id VARCHAR NOT NULL,
    thread_id VARCHAR,
    direction VARCHAR NOT NULL,
    subject TEXT,
    from_email VARCHAR NOT NULL,
    to_emails TEXT,
    cc_emails TEXT,
    sent_at TIMESTAMP NOT NULL,
    snippet TEXT,
    synced_at TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE UNIQUE INDEX IF NOT EXISTS ix_synced_emails_user_message ON synced_emails(user_id, external_message_id);
CREATE INDEX IF NOT EXISTS ix_synced_emails_lead ON synced_emails(lead_id);
CREATE INDEX IF NOT EXISTS ix_synced_emails_user ON synced_emails(user_id);

CREATE TABLE IF NOT EXISTS oauth_states (
    id VARCHAR PRIMARY KEY,
    user_id VARCHAR NOT NULL REFERENCES users(id),
    state VARCHAR NOT NULL UNIQUE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_oauth_states_user ON oauth_states(user_id);
CREATE INDEX IF NOT EXISTS ix_oauth_states_state ON oauth_states(state);