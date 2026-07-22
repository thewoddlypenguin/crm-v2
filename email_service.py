"""
Email service abstraction for Leverage CRM.

STUB — does not send live email.

To wire a real provider later:
1. Store provider credentials via the /api/settings/email route (not yet built)
   or as environment variables (EMAIL_PROVIDER, SMTP_HOST, SMTP_PORT,
   SMTP_USER, SMTP_PASSWORD, FROM_ADDRESS).
2. Replace the body of `send_email()` with your provider SDK call
   (e.g. smtplib, sendgrid, resend, postmark).
3. Remove the NotImplementedError and return a real message_id.

The rest of the call chain (route → activity log) requires no changes.
"""

from dataclasses import dataclass


@dataclass
class EmailPayload:
    to_address: str
    subject: str
    body: str
    from_address: str | None = None  # falls back to configured default


@dataclass
class EmailResult:
    success: bool
    message_id: str | None = None
    error: str | None = None


def send_email(payload: EmailPayload) -> EmailResult:
    """
    Send a transactional email.

    STUB: raises NotImplementedError until a provider is configured.
    Replace this implementation when credentials are available.
    """
    raise NotImplementedError(
        "Email sending is not configured. "
        "Set provider credentials and implement send_email() in email_service.py."
    )
