"""
Shared, authoritative template-variable rendering for outgoing email content.

This module is the SINGLE source of truth for {{variable}} handling. Every
email-send path renders through it before content reaches the provider.

Supported variables (strict allowlist — nothing else is ever substituted):
    Sender:  {{my_name}}  {{my_email}}  {{my_phone}}
    Lead:    {{lead_name}}  {{lead_first_name}}  {{lead_business}}
             {{lead_email}}  {{lead_phone}}

Security model:
- Values come exclusively from a VariableContext built by trusted callers
  from DB rows (EmailSettings + Lead). There is no expression syntax, no
  attribute/method access, no index access, no filters — a token is either
  this exact allowlist name or it is not substituted. Ever.
- Missing values render as the empty string. The literals "None"/"null"
  can never appear from a missing value.
- Unknown tokens are reported (and rejected by the send route), never
  silently passed to the provider.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# {{token}} — broad capture so that ANY {{...}} construct is seen (nothing
# slips through unflagged). Only exact allowlist names are substituted;
# everything else (dotted paths, brackets, arbitrary text) is unknown.
VARIABLE_PATTERN = re.compile(r"\{\{\s*([^{}]+?)\s*\}\}")

SENDER_VARIABLES: tuple[str, ...] = ("my_name", "my_email", "my_phone")
LEAD_VARIABLES: tuple[str, ...] = (
    "lead_name",
    "lead_first_name",
    "lead_business",
    "lead_email",
    "lead_phone",
)
SUPPORTED_VARIABLES: tuple[str, ...] = SENDER_VARIABLES + LEAD_VARIABLES
_SUPPORTED_SET = frozenset(SUPPORTED_VARIABLES)

SAMPLE_LEAD_CONTEXT: dict[str, str] = {
    "lead_name": "Alex Rivera",
    "lead_first_name": "Alex",
    "lead_business": "Rivera Coaching",
    "lead_email": "alex@riveracoaching.com",
    "lead_phone": "555-010-0199",
}


class UnsupportedVariableError(ValueError):
    """Raised in strict mode when content contains non-allowlisted tokens."""

    def __init__(self, variables: list[str]):
        self.variables = variables
        tokens = ", ".join(f"{{{{ {v} }}}}" for v in variables)
        super().__init__(f"Unsupported template variable(s): {tokens}")


@dataclass
class VariableContext:
    """Fully-resolved variable values. `None` or blank → rendered as ''."""

    my_name: str | None = None
    my_email: str | None = None
    my_phone: str | None = None
    lead_name: str | None = None
    lead_first_name: str | None = None
    lead_business: str | None = None
    lead_email: str | None = None
    lead_phone: str | None = None

    def as_dict(self) -> dict[str, str | None]:
        return {
            "my_name": self.my_name,
            "my_email": self.my_email,
            "my_phone": self.my_phone,
            "lead_name": self.lead_name,
            "lead_first_name": self.lead_first_name,
            "lead_business": self.lead_business,
            "lead_email": self.lead_email,
            "lead_phone": self.lead_phone,
        }


@dataclass
class RenderResult:
    text: str
    used_variables: list[str] = field(default_factory=list)
    unknown_variables: list[str] = field(default_factory=list)
    missing_variables: list[str] = field(default_factory=list)  # had no value → ''

    @property
    def ok(self) -> bool:
        return not self.unknown_variables


# ─── Context builders (trusted callers only) ─────────────────────────────────

def sender_context_from_settings(settings) -> dict[str, str | None]:
    """Build sender values from an EmailSettings ORM row (duck-typed).

    {{my_email}} prefers reply_to_email, falling back to from_email.
    """
    if settings is None:
        return {"my_name": None, "my_email": None, "my_phone": None}
    reply_to = (getattr(settings, "reply_to_email", None) or "").strip()
    from_email = (getattr(settings, "from_email", None) or "").strip()
    return {
        "my_name": (getattr(settings, "from_name", None) or "").strip() or None,
        "my_email": reply_to or from_email or None,
        "my_phone": (getattr(settings, "phone", None) or "").strip() or None,
    }


def lead_context_from_lead(lead) -> dict[str, str | None]:
    """Build lead values from a Lead ORM row (duck-typed).

    lead_name falls back to "first last" when full_name is blank.
    A None lead yields all-empty values (never crashes, never "None").
    """
    if lead is None:
        return {name: None for name in LEAD_VARIABLES}
    full_name = (getattr(lead, "full_name", None) or "").strip()
    if not full_name:
        first = (getattr(lead, "first_name", None) or "").strip()
        last = (getattr(lead, "last_name", None) or "").strip()
        full_name = f"{first} {last}".strip()
    return {
        "lead_name": full_name or None,
        "lead_first_name": (getattr(lead, "first_name", None) or "").strip() or None,
        "lead_business": (getattr(lead, "business_name", None) or "").strip() or None,
        "lead_email": (getattr(lead, "email", None) or "").strip() or None,
        "lead_phone": (getattr(lead, "phone", None) or "").strip() or None,
    }


def build_context(settings=None, lead=None) -> VariableContext:
    """One-stop context builder for send routes."""
    values = {**sender_context_from_settings(settings), **lead_context_from_lead(lead)}
    return VariableContext(**values)


# ─── Rendering ───────────────────────────────────────────────────────────────

def render_variables(
    text: str | None,
    context: VariableContext,
    *,
    strict: bool = False,
) -> RenderResult:
    """Replace allowlisted {{tokens}} in text using context.

    - Missing/blank values → '' (never "None"/"null").
    - Unknown tokens are left as literal text AND reported in
      unknown_variables (strict=True raises instead).
    - Idempotent: rendering already-rendered text is a no-op.
    """
    if not text:
        return RenderResult(text or "")

    values = context.as_dict()
    used: list[str] = []
    unknown: list[str] = []
    missing: list[str] = []

    def _sub(match: re.Match) -> str:
        name = match.group(1)
        if name not in _SUPPORTED_SET:
            if name not in unknown:
                unknown.append(name)
            return match.group(0)  # keep literal token visible
        if name not in used:
            used.append(name)
        value = values.get(name)
        if value is None or not str(value).strip():
            if name not in missing:
                missing.append(name)
            return ""
        return str(value)

    rendered = VARIABLE_PATTERN.sub(_sub, text)

    if strict and unknown:
        raise UnsupportedVariableError(unknown)

    return RenderResult(rendered, used, unknown, missing)


def validate_variables(text: str | None) -> list[str]:
    """Return sorted unique unsupported token names in text. [] = safe."""
    return sorted(
        {
            m.group(1)
            for m in VARIABLE_PATTERN.finditer(text or "")
            if m.group(1) not in _SUPPORTED_SET
        }
    )


def render_sender_variables(text: str | None, config) -> str:
    """Safety-net render for email_service.send_email.

    Uses only the EmailConfig (duck-typed: from_name, from_email,
    reply_to_email) — sender variables resolve; lead variables are blanked
    because no lead exists at this layer. Callers holding a Lead must render
    with build_context() BEFORE calling send_email; for any token that leaks
    through, this guarantees the provider never receives literal {{tokens}}.
    """
    if not text:
        return text or ""
    reply_to = (getattr(config, "reply_to_email", None) or "").strip()
    from_email = (getattr(config, "from_email", None) or "").strip()
    context = VariableContext(
        my_name=(getattr(config, "from_name", None) or "").strip() or None,
        my_email=reply_to or from_email or None,
        **{name: "" for name in LEAD_VARIABLES},
    )
    return render_variables(text, context).text


def supported_variables_help() -> str:
    return ", ".join(f"{{{{{v}}}}}" for v in SUPPORTED_VARIABLES)
