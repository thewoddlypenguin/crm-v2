-- Multi-user organization access.
-- Adds organizations + organization_members tables, and organization_id columns
-- to shared business tables (segments, email_templates, leads, activities, synced_emails).
-- Idempotent — safe to re-run (IF NOT EXISTS everywhere).

-- ─── Organizations ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS organizations (
    id VARCHAR NOT NULL PRIMARY KEY,
    name VARCHAR NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- ─── Organization members (join table: user <-> organization) ────────────────
CREATE TABLE IF NOT EXISTS organization_members (
    id VARCHAR NOT NULL PRIMARY KEY,
    organization_id VARCHAR NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    user_id VARCHAR NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role VARCHAR NOT NULL DEFAULT 'member',
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_organization_members_organization_id ON organization_members(organization_id);
CREATE INDEX IF NOT EXISTS ix_organization_members_user_id ON organization_members(user_id);
CREATE UNIQUE INDEX IF NOT EXISTS ix_organization_members_org_user ON organization_members(organization_id, user_id);

-- ─── Shared business tables: add organization_id ─────────────────────────────
ALTER TABLE segments ADD COLUMN IF NOT EXISTS organization_id VARCHAR;
ALTER TABLE email_templates ADD COLUMN IF NOT EXISTS organization_id VARCHAR;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS organization_id VARCHAR;
ALTER TABLE activities ADD COLUMN IF NOT EXISTS organization_id VARCHAR;
ALTER TABLE synced_emails ADD COLUMN IF NOT EXISTS organization_id VARCHAR;

CREATE INDEX IF NOT EXISTS ix_segments_organization_id ON segments(organization_id);
CREATE INDEX IF NOT EXISTS ix_email_templates_organization_id ON email_templates(organization_id);
CREATE INDEX IF NOT EXISTS ix_leads_organization_id ON leads(organization_id);
CREATE INDEX IF NOT EXISTS ix_activities_organization_id ON activities(organization_id);
CREATE INDEX IF NOT EXISTS ix_synced_emails_organization_id ON synced_emails(organization_id);

-- Per-org segment key uniqueness (coexists with the existing per-user index)
CREATE UNIQUE INDEX IF NOT EXISTS ix_segments_org_key_unique ON segments(organization_id, key);
