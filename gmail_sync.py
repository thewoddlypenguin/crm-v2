"""
Gmail mailbox sync — background job.

Runs periodically, iterates connected Gmail accounts, refreshes tokens,
fetches recent messages, matches to leads by email address, and logs
matched messages as CRM activity records.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from models import Activity, Lead, SyncedEmail  # deferred-free; app imports gmail_sync only at runtime

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Number of minutes between sync cycles
SYNC_INTERVAL_MINUTES = int(os.environ.get("GMAIL_SYNC_INTERVAL_MINUTES", "5"))

# How far back to look on first sync for a connection
INITIAL_SYNC_LOOKBACK_HOURS = int(os.environ.get("GMAIL_SYNC_LOOKBACK_HOURS", "24"))


def refresh_access_token(conn) -> str | None:
    """Refresh the Gmail access token using the stored refresh token.

    Returns the new access token string, or None on failure.
    Mutates ``conn`` in place (updates access_token, token_expiry, last_error).
    The caller is responsible for committing the session.
    """
    from crypto_utils import decrypt_token, encrypt_token

    # Decrypt the stored refresh token
    plain_refresh = decrypt_token(conn.refresh_token or "")
    if not plain_refresh:
        conn.last_error = "No refresh token available — reconnect Gmail"
        return None

    try:
        import httpx

        resp = httpx.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": os.environ.get("GOOGLE_OAUTH_CLIENT_ID") or os.environ.get("GOOGLE_CLIENT_ID", ""),
                "client_secret": os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET") or os.environ.get("GOOGLE_CLIENT_SECRET", ""),
                "refresh_token": plain_refresh,
                "grant_type": "refresh_token",
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        new_access = data.get("access_token")
        expires_in = data.get("expires_in", 3600)
        if new_access:
            conn.access_token = encrypt_token(new_access)
            conn.token_expiry = datetime.utcnow() + timedelta(seconds=expires_in)
            conn.last_error = None
            return new_access
        else:
            conn.last_error = "Token refresh returned no access_token"
            return None
    except Exception as exc:
        conn.last_error = f"Token refresh failed: {exc}"
        logger.warning("Token refresh failed for user %s: %s", conn.owner_user_id, exc)
        return None


def _get_valid_token(conn) -> str | None:
    """Return a valid access token, refreshing if expired or missing.

    Does NOT commit — the caller owns the session commit.
    """
    from crypto_utils import decrypt_token

    plain_access = decrypt_token(conn.access_token) if conn.access_token else None
    if plain_access and conn.token_expiry and conn.token_expiry > datetime.utcnow() + timedelta(minutes=1):
        return plain_access
    return refresh_access_token(conn)


def _list_messages(access_token: str, query: str, max_results: int = 50) -> list[dict]:
    """Fetch recent Gmail messages matching the given query."""
    import httpx

    resp = httpx.get(
        "https://gmail.googleapis.com/gmail/v1/users/me/messages",
        headers={"Authorization": f"Bearer {access_token}"},
        params={"q": query, "maxResults": max_results},
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    return data.get("messages", [])


def _get_message_details(access_token: str, message_id: str) -> dict | None:
    """Fetch full metadata for a single message (headers, snippet, etc.)."""
    import httpx

    resp = httpx.get(
        f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{message_id}",
        headers={"Authorization": f"Bearer {access_token}"},
        params={"format": "metadata", "metadataHeaders": "From,To,Cc,Subject,Date"},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def _parse_headers(headers: list[dict]) -> dict:
    """Extract common headers from the Gmail API payload headers list."""
    result = {"subject": "", "from": "", "to": "", "cc": "", "date": ""}
    for h in headers:
        name = h.get("name", "").lower()
        if name == "subject":
            result["subject"] = h.get("value", "")
        elif name == "from":
            result["from"] = h.get("value", "")
        elif name == "to":
            result["to"] = h.get("value", "")
        elif name == "cc":
            result["cc"] = h.get("value", "")
        elif name == "date":
            result["date"] = h.get("value", "")
    return result


def _extract_email_addresses(raw: str) -> list[str]:
    """Parse email addresses from a header value like 'Name <a@b.com>, c@d.com'."""
    import re
    return re.findall(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", raw)


def _determine_direction(from_emails: list[str], user_google_email: str) -> str:
    """Return 'outbound' if the user is in the from list, 'inbound' otherwise."""
    for addr in from_emails:
        if addr.lower() == user_google_email.lower():
            return "outbound"
    return "inbound"


def _parse_gmail_date(date_str: str) -> datetime | None:
    """Parse a Gmail Date header into a datetime."""
    from email.utils import parsedate_to_datetime
    try:
        dt = parsedate_to_datetime(date_str)
        return dt.replace(tzinfo=None)  # naive UTC
    except Exception:
        return None


def sync_connection(conn, db: "Session") -> None:
    """Run one sync cycle for a single GmailConnection.

    Fetches recent messages, matches to leads, logs as activities,
    and updates the connection's last_sync_at / last_error.
    """
    user_id = conn.owner_user_id
    google_email = conn.google_email

    # Resolve the connection owner's organization once per sync.
    # Gmail connections are user-owned, but the leads/activities they produce
    # are organization-shared — so matching is scoped by organization.
    from models import OrganizationMember
    membership = (
        db.query(OrganizationMember)
        .filter(OrganizationMember.user_id == user_id)
        .first()
    )
    org_id = membership.organization_id if membership else None

    # 1. Get a valid token
    token = _get_valid_token(conn)
    if not token:
        db.commit()  # persist updated last_error
        return

    # 2. Determine lookback window
    if conn.last_sync_at:
        # Sync from 1 minute before last sync to avoid gaps
        lookback = conn.last_sync_at - timedelta(minutes=1)
    else:
        lookback = datetime.utcnow() - timedelta(hours=INITIAL_SYNC_LOOKBACK_HOURS)

    # Gmail search query: messages after the lookback time
    # Gmail's search uses YYYY/MM/DD format; we use "after:" which is more granular
    # Using "newer_than:" is simpler — but we'll use "after:" with a timestamp
    # Actually Gmail search doesn't support minute-level granularity easily.
    # We'll use "after:" with the date and rely on dedup.
    # Also search for messages involving the user's own email (sent/received)
    after_str = lookback.strftime("%Y/%m/%d")
    query = f"after:{after_str}"

    try:
        # 3. Fetch message list
        messages = _list_messages(token, query, max_results=50)
    except Exception as exc:
        conn.last_error = f"Failed to list messages: {exc}"
        db.commit()
        return

    if not messages:
        conn.last_sync_at = datetime.utcnow()
        conn.last_error = None
        db.commit()
        return

    # 4. Process each message
    for msg in messages:
        msg_id = msg.get("id")
        if not msg_id:
            continue

        # Dedup check — skip if already synced for this user
        existing = db.query(SyncedEmail).filter(
            SyncedEmail.user_id == user_id,
            SyncedEmail.external_message_id == msg_id,
        ).first()
        if existing:
            continue

        # Fetch details
        try:
            details = _get_message_details(token, msg_id)
        except Exception:
            continue

        if not details:
            continue

        payload = details.get("payload", {})
        headers = _parse_headers(payload.get("headers", []))
        snippet = details.get("snippet", "")

        from_emails = _extract_email_addresses(headers["from"])
        to_emails = _extract_email_addresses(headers["to"])
        cc_emails = _extract_email_addresses(headers["cc"])
        all_addresses = set(from_emails + to_emails + cc_emails)

        # Remove the user's own email from matching
        all_addresses.discard(google_email.lower())

        # Find matching leads by exact email match, scoped to the connection
        # owner's organization (falls back to owner_user_id if no org yet).
        matching_leads = []
        for addr in all_addresses:
            q = db.query(Lead).filter(Lead.email.ilike(addr))
            if org_id:
                q = q.filter(Lead.organization_id == org_id)
            else:
                q = q.filter(Lead.owner_user_id == user_id)
            matching_leads.extend(q.all())

        # Deduplicate by lead id
        seen_ids = set()
        unique_leads = []
        for l in matching_leads:
            if l.id not in seen_ids:
                seen_ids.add(l.id)
                unique_leads.append(l)

        # If multiple leads match the same email address, skip
        if len(unique_leads) > 1:
            logger.warning(
                "GMAIL_SYNC_AMBIGUITY user=%s message=%s matched %d leads — skipping",
                user_id, msg_id, len(unique_leads),
            )
            conn.last_error = f"Skipped message {msg_id}: matched {len(unique_leads)} leads"
            db.commit()
            continue

        if not unique_leads:
            continue  # No matching lead — skip silently

        lead = unique_leads[0]

        sent_at = _parse_gmail_date(headers["date"]) or datetime.utcnow()
        direction = _determine_direction(from_emails, google_email)

        # Create SyncedEmail record
        synced = SyncedEmail(
            user_id=user_id,
            organization_id=org_id,
            lead_id=lead.id,
            provider="gmail",
            external_message_id=msg_id,
            thread_id=details.get("threadId"),
            direction=direction,
            subject=headers["subject"][:500] if headers["subject"] else None,
            from_email=from_emails[0] if from_emails else google_email,
            to_emails=", ".join(to_emails) if to_emails else None,
            cc_emails=", ".join(cc_emails) if cc_emails else None,
            sent_at=sent_at,
            snippet=snippet[:1000] if snippet else None,
        )
        db.add(synced)

        # Create Activity record
        direction_label = "Received" if direction == "inbound" else "Sent"
        activity_body = (
            f"[Gmail] {direction_label} — {headers['subject'] or '(no subject)'}\n"
            f"From: {headers['from']}\n"
            f"To: {headers['to']}\n"
            f"{'Cc: ' + headers['cc'] if headers['cc'] else ''}"
            f"\n{snippet[:500] if snippet else ''}"
        ).strip()

        # Determine activity type
        act_type = "REPLY_RECEIVED" if direction == "inbound" else "OUTREACH_SENT"

        act = Activity(
            lead_id=lead.id,
            user_id=user_id,
            organization_id=org_id,
            activity_type=act_type,
            body=activity_body,
            occurred_at=sent_at,
        )
        db.add(act)

        # Create Notification record for inbound emails — one row per org member
        # (each member keeps independent is_read state).
        if direction == "inbound":
            from models import Notification, OrganizationMember, User
            lead_name = " ".join(filter(None, [lead.first_name, lead.last_name])) or lead.email or "Unknown"

            # Fan out to every member of the organization (fallback: just the
            # connection owner when no org is attached yet).
            member_user_ids = []
            if org_id:
                member_user_ids = [
                    m.user_id
                    for m in db.query(OrganizationMember)
                    .filter(OrganizationMember.organization_id == org_id)
                    .all()
                ]
            if not member_user_ids:
                member_user_ids = [user_id]

            for member_id in member_user_ids:
                notification = Notification(
                    owner_user_id=member_id,
                    lead_id=lead.id,
                    title=f"New email from {lead_name}",
                    body=f"Inbound email logged as note for {lead_name}: {headers['subject'] or '(no subject)'}",
                    notification_type="email_received",
                )
                db.add(notification)

    # Update connection status
    conn.last_sync_at = datetime.utcnow()
    conn.last_error = None
    db.commit()