"""
Email service for Leverage CRM.

Dispatch logic:
  1. If test_mode_enabled → simulate (no external call), return simulated=True.
  2. If provider is not configured → fail with clear error.
  3. If provider is configured → call the appropriate send function.
"""

from __future__ import annotations

import logging
import os
import traceback
from dataclasses import dataclass


logger = logging.getLogger("uvicorn.error")


@dataclass
class EmailConfig:
    """Runtime email configuration loaded from the DB EmailSettings row."""
    provider: str | None = None
    from_email: str | None = None
    from_name: str | None = None
    reply_to_email: str | None = None
    test_mode_enabled: bool = True


@dataclass
class EmailPayload:
    to_address: str
    subject: str
    body: str


@dataclass
class EmailResult:
    success: bool
    simulated: bool = False
    message_id: str | None = None
    error: str | None = None


def send_email(payload: EmailPayload, config: EmailConfig | None = None) -> EmailResult:
    """
    Send (or simulate) an email according to the current EmailConfig.

    Safe defaults: if config is None or test_mode_enabled, simulate.
    """
    cfg = config or EmailConfig()
    provider_name = (cfg.provider or "").strip().lower() or "unconfigured"

    prepared_payload = EmailPayload(
        to_address=payload.to_address.strip(),
        subject=payload.subject.strip(),
        body=_apply_signature(payload.body),
    )

    logger.info(
        "Email send requested | provider=%s to=%s subject=%s test_mode=%s",
        provider_name,
        prepared_payload.to_address,
        prepared_payload.subject,
        cfg.test_mode_enabled,
    )

    if cfg.test_mode_enabled:
        result = _simulate(prepared_payload, cfg)
        logger.info(
            "Email simulated | provider=%s to=%s subject=%s message_id=%s",
            provider_name,
            prepared_payload.to_address,
            prepared_payload.subject,
            result.message_id,
        )
        return result

    if not cfg.provider:
        error = "No email provider configured. Set a provider in Settings → Email."
        logger.warning(
            "Email send blocked | provider=%s to=%s subject=%s error=%s",
            provider_name,
            prepared_payload.to_address,
            prepared_payload.subject,
            error,
        )
        return EmailResult(success=False, error=error)

    if not cfg.from_email:
        error = "No sender address configured. Set 'From Email' in Settings → Email."
        logger.warning(
            "Email send blocked | provider=%s to=%s subject=%s error=%s",
            provider_name,
            prepared_payload.to_address,
            prepared_payload.subject,
            error,
        )
        return EmailResult(success=False, error=error)

    provider = cfg.provider.lower().strip()

    try:
        if provider == "smtp":
            result = _send_via_smtp(prepared_payload, cfg)
        elif provider == "resend":
            result = _send_via_resend(prepared_payload, cfg)
        elif provider == "sendgrid":
            result = _send_via_sendgrid(prepared_payload, cfg)
        elif provider == "postmark":
            result = _send_via_postmark(prepared_payload, cfg)
        else:
            result = EmailResult(
                success=False,
                error=f"Unknown provider '{cfg.provider}'. Supported: smtp, resend, sendgrid, postmark.",
            )
    except Exception as e:
        logger.exception(
            "Unhandled email send exception | provider=%s to=%s subject=%s",
            provider,
            prepared_payload.to_address,
            prepared_payload.subject,
        )
        return EmailResult(success=False, error=f"Unhandled email send failure: {str(e)}")

    if result.success:
        logger.info(
            "Email send succeeded | provider=%s to=%s subject=%s message_id=%s simulated=%s",
            provider,
            prepared_payload.to_address,
            prepared_payload.subject,
            result.message_id,
            result.simulated,
        )
    else:
        logger.warning(
            "Email send failed | provider=%s to=%s subject=%s error=%s",
            provider,
            prepared_payload.to_address,
            prepared_payload.subject,
            result.error,
        )

    return result


def _apply_signature(body: str) -> str:
    """
    Append a simple signature from EMAIL_SIGNATURE if configured.
    For now, keep it lightweight and text-oriented.
    """
    signature = os.environ.get("EMAIL_SIGNATURE", "").replace("\\n", "\n").strip()
    if not signature:
        return body

    body = (body or "").rstrip()
    if not body:
        return signature

    html_break = "<br><br>" if "<" in body and ">" in body else "\n\n"
    return f"{body}{html_break}--{html_break}{signature}"


def _simulate(payload: EmailPayload, cfg: EmailConfig) -> EmailResult:
    """Return a successful simulated result without any external call."""
    return EmailResult(success=True, simulated=True, message_id="test-mode")


def _send_via_smtp(payload: EmailPayload, cfg: EmailConfig) -> EmailResult:
    raise NotImplementedError(
        "SMTP provider not yet implemented. "
        "Set SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD and implement _send_via_smtp()."
    )


def _send_via_resend(payload: EmailPayload, cfg: EmailConfig) -> EmailResult:
    """
    Send via Resend API.
    Required env vars: RESEND_API_KEY
    """
    api_key = os.environ.get("RESEND_API_KEY")
    if not api_key:
        return EmailResult(
            success=False,
            error="Missing RESEND_API_KEY environment variable."
        )

    try:
        import resend
    except ImportError:
        return EmailResult(
            success=False,
            error="Resend SDK not installed. Rebuild the app with the dependency included."
        )

    try:
        resend.api_key = api_key

        from_value = cfg.from_email
        if cfg.from_name and cfg.from_name.strip():
            from_value = f"{cfg.from_name.strip()} <{cfg.from_email}>"

        send_payload = {
            "from": from_value,
            "to": [payload.to_address],
            "subject": payload.subject,
            "html": payload.body,
            "text": _strip_html(payload.body),
        }

        if cfg.reply_to_email and cfg.reply_to_email.strip():
            send_payload["reply_to"] = cfg.reply_to_email.strip()

        response = resend.Emails.send(send_payload)

        message_id = None
        if isinstance(response, dict):
            message_id = response.get("id")
        else:
            message_id = getattr(response, "id", None)

        return EmailResult(
            success=True,
            simulated=False,
            message_id=str(message_id) if message_id else None,
        )

    except Exception as e:
        logger.error(
            "Resend send exception | to=%s subject=%s error=%s\n%s",
            payload.to_address,
            payload.subject,
            str(e),
            traceback.format_exc(),
        )
        return EmailResult(
            success=False,
            error=f"Resend send failed: {str(e)}"
        )


def _strip_html(value: str) -> str:
    """
    Very lightweight fallback plain-text generator.
    Good enough for tomorrow; can be improved later.
    """
    return (
        value.replace("<br>", "\n")
        .replace("<br/>", "\n")
        .replace("<br />", "\n")
        .replace("</p>", "\n\n")
        .replace("<p>", "")
        .replace("&nbsp;", " ")
    )


def _send_via_sendgrid(payload: EmailPayload, cfg: EmailConfig) -> EmailResult:
    raise NotImplementedError(
        "SendGrid provider not yet implemented. "
        "Set SENDGRID_API_KEY, run `uv add sendgrid`, and implement _send_via_sendgrid()."
    )


def _send_via_postmark(payload: EmailPayload, cfg: EmailConfig) -> EmailResult:
    raise NotImplementedError(
        "Postmark provider not yet implemented. "
        "Set POSTMARK_SERVER_TOKEN, run `uv add postmarker`, and implement _send_via_postmark()."
    )
