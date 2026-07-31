"""
One-off migration: create the default organization and backfill organization_id
on all shared business rows (segments, email_templates, leads, activities, synced_emails).

Idempotent — safe to run multiple times:
  - Org creation is skipped if the org already exists (matched by name).
  - Owner membership insert uses an upsert-style check.
  - Rows already carrying organization_id are left untouched.

Which user owns the org is resolved by:
  1. CRM_OWNER_EMAIL env var (same as seed.py / public intake)
  2. fallback: the first user created (oldest created_at)

Usage (Docker):
    docker compose exec app python3 -m migrations.backfill_organizations

Env vars:
    CRM_OWNER_EMAIL   owner account email (recommended)
    CRM_ORG_NAME      org name, default "Justin's Business"
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session

from db import SessionLocal, init_db
from models import (
    Activity,
    EmailTemplate,
    Lead,
    Organization,
    OrganizationMember,
    Segment,
    SyncedEmail,
    User,
)

DEFAULT_ORG_NAME = os.environ.get("CRM_ORG_NAME", "Justin's Business")

BACKFILL_TABLES = [
    Segment,
    EmailTemplate,
    Lead,
    Activity,
    SyncedEmail,
]


def resolve_owner(db: Session) -> User:
    """Return the user who owns the CRM data (CRM_OWNER_EMAIL or first user)."""
    owner_email = os.environ.get("CRM_OWNER_EMAIL", "").strip().lower()
    if owner_email:
        owner = db.query(User).filter(User.email == owner_email).first()
        if owner:
            return owner
        print(f"  WARNING: CRM_OWNER_EMAIL {owner_email!r} not found — falling back to first user")
    return db.query(User).order_by(User.created_at.asc(), User.id.asc()).first()


def ensure_org(db: Session, name: str, owner: User) -> Organization:
    """Find or create the default org and add the owner as an 'owner' member."""
    org = db.query(Organization).filter(Organization.name == name).first()
    if not org:
        org = Organization(name=name)
        db.add(org)
        db.flush()
        print(f"  Created organization: {name!r} ({org.id})")

    existing = (
        db.query(OrganizationMember)
        .filter(
            OrganizationMember.organization_id == org.id,
            OrganizationMember.user_id == owner.id,
        )
        .first()
    )
    if not existing:
        db.add(OrganizationMember(
            organization_id=org.id,
            user_id=owner.id,
            role="owner",
        ))
        print(f"  Added owner membership: {owner.email} -> {name!r} (role=owner)")
    return org


def backfill(org: Organization, owner: User, db: Session) -> None:
    """Set organization_id on all owner-owned shared rows that don't have one yet."""
    for model in BACKFILL_TABLES:
        # Activity uses user_id (no owner_user_id column); everything else uses owner_user_id.
        user_col = model.user_id if hasattr(model, "user_id") else model.owner_user_id
        rows = (
            db.query(model)
            .filter(user_col == owner.id, model.organization_id.is_(None))
            .all()
        )
        for row in rows:
            row.organization_id = org.id
        if rows:
            print(f"  Backfilled {len(rows)} {model.__tablename__} rows")
        else:
            print(f"  No {model.__tablename__} rows to backfill")


def main() -> None:
    init_db()
    db = SessionLocal()
    try:
        owner = resolve_owner(db)
        if not owner:
            print("ERROR: no users found in the database — nothing to backfill.")
            sys.exit(2)

        print(f"Owner: {owner.email} ({owner.id})")
        org = ensure_org(db, DEFAULT_ORG_NAME, owner)
        backfill(org, owner, db)
        db.commit()
        print("Backfill complete. Run it again after deployment to catch any rows created in the gap.")
    except Exception as exc:
        db.rollback()
        print(f"Backfill error: {exc}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
