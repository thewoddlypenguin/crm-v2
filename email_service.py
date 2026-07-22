"""
Email service for Leverage CRM.

Dispatch logic:
  1. If test_mode_enabled → simulate (no external call), return simulated=True.
  2. If provider is not configured → fail with clear error.
  3. If provider is configured → call the appropriate send function.

To wire a real provider:
  - Set provider in Settings → Email (e.g. "smtp", "resend", "sendgrid", "postmark").
  - Add the required credentials as environment variables (never in DB):
      SMTP:      SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_USE_TLS
      Resend:    RESEND_API_KEY
      SendGrid:  SENDGRID_API_KEY
      Postmark:  POSTMARK_SERVER_TOKEN
  - Implement the corresponding _send_via_<provider>() function below.
  - Turn off test_mode_enabled in Settings → Email.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class EmailConfig:
    """Runtime email configuration loaded from the DB EmailSettings row."""
    provider: str | None = None          # "smtp" | "resend" | "sendgrid" | "postmark"
    from_email: str | None = None
    from_name: str | None = None
    reply_to_email: str | None = None
    test_mode_enabled: bool = True       # default SAFE: always simulate until explicitly disabled


@dataclass
class EmailPayload:
    to_address: str
    subject: str
    body: str


@dataclass
class EmailResult:
    success: bool
    simulated: bool = False              # True when test_mode intercepted the send
    message_id: str | None = None
    error: str | None = None


# ─── Public entry point ───────────────────────────────────────────────────────

def send_email(payload: EmailPayload, config: EmailConfig | None = None) -> EmailResult:
    """
    Send (or simulate) an email according to the current EmailConfig.

    Safe defaults: if config is None or test_mode_enabled, simulate.
    """
    cfg = config or EmailConfig()  # falls back to test_mode_enabled=True

    if cfg.test_mode_enabled:
        return _simulate(payload, cfg)

    if not cfg.provider:
        return EmailResult(
            success=False,
            error="No email provider configured. Set a provider in Settings → Email.",
        )

    if not cfg.from_email:
        return EmailResult(
            success=False,
            error="No sender address configured. Set 'From Email' in Settings → Email.",
        )

    provider = cfg.provider.lower().strip()

    if provider == "smtp":
        return _send_via_smtp(payload, cfg)
    elif provider == "resend":
        return _send_via_resend(payload, cfg)
    elif provider == "sendgrid":
        return _send_via_sendgrid(payload, cfg)
    elif provider == "postmark":
        return _send_via_postmark(payload, cfg)
    else:
        return EmailResult(
            success=False,
            error=f"Unknown provider '{cfg.provider}'. Supported: smtp, resend, sendgrid, postmark.",
        )


# ─── Test mode ────────────────────────────────────────────────────────────────

def _simulate(payload: EmailPayload, cfg: EmailConfig) -> EmailResult:
    """Return a successful simulated result without any external call."""
    return EmailResult(success=True, simulated=True, message_id="test-mode")


# ─── Provider stubs ───────────────────────────────────────────────────────────
# Each function should return EmailResult(success=True, message_id=...) on success
# or EmailResult(success=False, error=...) on failure.
# Credentials are read from environment variables — never stored in the DB.

def _send_via_smtp(payload: EmailPayload, cfg: EmailConfig) -> EmailResult:
    """
    Send via SMTP using Python stdlib smtplib.
    Required env vars: SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD
    Optional env vars: SMTP_USE_TLS (default "true")
    """
    raise NotImplementedError(
        "SMTP provider not yet implemented. "
        "Set SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD and implement _send_via_smtp()."
    )


def _send_via_resend(payload: EmailPayload, cfg: EmailConfig) -> EmailResult:
    """
    Send via Resend API (https://resend.com).
    Required env vars: RESEND_API_KEY
    Install: uv add resend
    """
    raise NotImplementedError(
        "Resend provider not yet implemented. "
        "Set RESEND_API_KEY, run `uv add resend`, and implement _send_via_resend()."
    )


def _send_via_sendgrid(payload: EmailPayload, cfg: EmailConfig) -> EmailResult:
    """
    Send via SendGrid API.
    Required env vars: SENDGRID_API_KEY
    Install: uv add sendgrid
    """
    raise NotImplementedError(
        "SendGrid provider not yet implemented. "
        "Set SENDGRID_API_KEY, run `uv add sendgrid`, and implement _send_via_sendgrid()."
    )


def _send_via_postmark(payload: EmailPayload, cfg: EmailConfig) -> EmailResult:
    """
    Send via Postmark API.
    Required env vars: POSTMARK_SERVER_TOKEN
    Install: uv add postmarker
    """
    raise NotImplementedError(
        "Postmark provider not yet implemented. "
        "Set POSTMARK_SERVER_TOKEN, run `uv add postmarker`, and implement _send_via_postmark()."
    )
