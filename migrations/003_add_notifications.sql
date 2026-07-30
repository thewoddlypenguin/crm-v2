-- Create notifications table for in-app notifications (email sync events, etc.)
CREATE TABLE IF NOT EXISTS notifications (
    id VARCHAR NOT NULL PRIMARY KEY,
    owner_user_id VARCHAR NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    lead_id VARCHAR REFERENCES leads(id) ON DELETE SET NULL,
    title VARCHAR NOT NULL,
    body TEXT,
    notification_type VARCHAR NOT NULL DEFAULT 'email_received',
    is_read BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_notifications_owner_user_id ON notifications(owner_user_id);
CREATE INDEX IF NOT EXISTS ix_notifications_lead_id ON notifications(lead_id);
CREATE INDEX IF NOT EXISTS ix_notifications_is_read ON notifications(is_read);
CREATE INDEX IF NOT EXISTS ix_notifications_created_at ON notifications(created_at);