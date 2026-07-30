"""
One-off migration: encrypt existing plaintext Gmail OAuth tokens at rest.

Safe to run multiple times — decrypt_token() returns plaintext as-is,
so already-encrypted tokens are written back as the same encrypted value.

Usage (Docker):
    docker compose exec app python3 -m migrations.migrate_tokens

Usage (bare-metal):
    cd /var/www/leverage-crm
    .venv/bin/python3 -m migrations.migrate_tokens

Requires:
    - TOKEN_ENCRYPTION_KEY set in the environment
    - Database reachable via DATABASE_URL
"""

import os
import sys

# Ensure the project root is on sys.path so we can import project modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db import SessionLocal
from models import GmailConnection
from crypto_utils import encrypt_token, decrypt_token


def migrate():
    key = os.environ.get("TOKEN_ENCRYPTION_KEY", "")
    if not key:
        print("FATAL: TOKEN_ENCRYPTION_KEY is not set.")
        print("Generate one:  python3 -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\"")
        sys.exit(1)

    db = SessionLocal()
    try:
        rows = db.query(GmailConnection).all()
        total = len(rows)
        encrypted_access = 0
        encrypted_refresh = 0
        skipped_access = 0
        skipped_refresh = 0
        errors = 0

        for row in rows:
            try:
                # --- access_token ---
                raw_access = row.access_token or ""
                if raw_access.startswith("gAAAAA"):
                    skipped_access += 1
                else:
                    # confirm it's actually decryptable (valid plaintext or legacy token)
                    plain = decrypt_token(raw_access)
                    row.access_token = encrypt_token(plain)
                    encrypted_access += 1

                # --- refresh_token ---
                raw_refresh = row.refresh_token or ""
                if raw_refresh.startswith("gAAAAA"):
                    skipped_refresh += 1
                else:
                    plain = decrypt_token(raw_refresh)
                    row.refresh_token = encrypt_token(plain)
                    encrypted_refresh += 1

            except Exception as exc:
                print(f"  ERROR row {row.id} (user={row.owner_user_id}): {exc}")
                errors += 1

        db.commit()

        print(f"\nMigration complete.")
        print(f"  Total rows examined:     {total}")
        print(f"  Access tokens encrypted:  {encrypted_access}")
        print(f"  Refresh tokens encrypted: {encrypted_refresh}")
        print(f"  Already encrypted (skip): access={skipped_access}, refresh={skipped_refresh}")
        print(f"  Errors:                  {errors}")

        # Verification
        print("\n── Verification ──")
        verify_count = 0
        for row in db.query(GmailConnection).all():
            at = row.access_token or ""
            rt = row.refresh_token or ""
            if at.startswith("gAAAAA") and (rt == "" or rt.startswith("gAAAAA")):
                verify_count += 1
                # Decrypt round-trip check on a sample
                if verify_count <= 3:
                    try:
                        _ = decrypt_token(at)
                        _ = decrypt_token(rt)
                    except Exception as exc:
                        print(f"  WARNING round-trip failed for {row.id}: {exc}")

        print(f"  Rows with valid encrypted tokens: {verify_count} / {total}")
        if verify_count == total:
            print("  ✅ All tokens are properly encrypted.")
        else:
            print(f"  ⚠️  {total - verify_count} rows may still have plaintext tokens.")
            print("  Re-run the migration to catch any remaining rows.")

    finally:
        db.close()


if __name__ == "__main__":
    migrate()