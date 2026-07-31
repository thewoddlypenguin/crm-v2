"""
Provision an organization member account (admin script).

Creates the user if they don't exist, then joins them to an organization.
Does NOT touch the public registration endpoint — REGISTRATION_ENABLED can
stay "false" in production.

Usage:
    python provision_org_member.py --email wife@example.com --full-name "Jane Doe"
    python provision_org_member.py --email wife@example.com --password "s3cret!" --role owner

Docker:
    docker compose exec app python3 provision_org_member.py --email wife@example.com --full-name "Jane Doe"

Behavior:
  - Org is matched by name (default "Justin's Business"); created if missing.
  - If the user already exists in the org, prints a message and exits 0 (idempotent).
  - If --password is omitted, a random temporary password is generated and printed ONCE.
"""

import argparse
import os
import secrets
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy.orm import Session

from db import SessionLocal, init_db
from models import Organization, OrganizationMember, User
from auth import hash_password

DEFAULT_ORG_NAME = os.environ.get("CRM_ORG_NAME", "Justin's Business")


def main() -> None:
    parser = argparse.ArgumentParser(description="Provision an organization member account")
    parser.add_argument("--email", required=True, help="Member email address")
    parser.add_argument("--full-name", default=None, help="Member display name")
    parser.add_argument("--org", default=DEFAULT_ORG_NAME, help="Organization name (created if missing)")
    parser.add_argument("--role", default="member", choices=["owner", "member"], help="Membership role")
    parser.add_argument("--password", default=None, help="Optional explicit password (min 10 chars)")
    args = parser.parse_args()

    email = args.email.strip().lower()
    if not email:
        print("ERROR: --email is required")
        sys.exit(2)

    init_db()
    db: Session = SessionLocal()
    try:
        org = db.query(Organization).filter(Organization.name == args.org).first()
        if not org:
            org = Organization(name=args.org)
            db.add(org)
            db.flush()
            print(f"Created organization: {args.org!r} ({org.id})")

        user = db.query(User).filter(User.email == email).first()
        if user:
            existing = (
                db.query(OrganizationMember)
                .filter(
                    OrganizationMember.organization_id == org.id,
                    OrganizationMember.user_id == user.id,
                )
                .first()
            )
            if existing:
                print(f"{email} is already a {existing.role} of {args.org!r} — nothing to do.")
                return
        else:
            password = args.password or secrets.token_urlsafe(12)
            if args.password and len(args.password) < 10:
                print("ERROR: password must be at least 10 characters")
                sys.exit(2)
            user = User(
                email=email,
                password_hash=hash_password(password),
                full_name=args.full_name,
            )
            db.add(user)
            db.flush()
            if not args.password:
                print(f"TEMPORARY PASSWORD (shown once): {password}")
                print("  Ask the member to log in and change it, or re-run with --password to set one.")

        db.add(OrganizationMember(
            organization_id=org.id,
            user_id=user.id,
            role=args.role,
        ))
        db.commit()
        print(f"Provisioned {email} as {args.role} of {args.org!r} (user_id={user.id})")
    except Exception as exc:
        db.rollback()
        print(f"Provision error: {exc}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
