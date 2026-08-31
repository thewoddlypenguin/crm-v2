"""Backend tests for email variable rendering + the email-send route.

Run:  uv run pytest tests/ -v
Covers: variable rendering (all 8 tokens), signature rendering, manually
typed emails, saved templates, test mode, subject/body rendering, missing
values, unknown variables, DNC enforcement, auth, and preview endpoint.
"""

from __future__ import annotations

import os
import uuid

import pytest

# Must be set before importing app modules (auth.py raises without it)
os.environ.setdefault("JWT_SECRET", "test-secret-for-pytest-only")
os.environ.setdefault("EMAIL_SIGNATURE", "")  # deterministic signature behavior
os.environ.pop("EMAIL_SIGNATURE", None)  # ensure the env fallback is OFF by default

from types import SimpleNamespace

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

import db as db_module  # noqa: E402
from models import (  # noqa: E402
    Activity,
    Base,
    EmailSettings,
    EmailTemplate,
    Lead,
    Organization,
    OrganizationMember,
    User,
)

# ─── Fixture: isolated SQLite-backed app per test ────────────────────────────


@pytest.fixture()
def client(monkeypatch, tmp_path):
    """Fresh file-based SQLite app per test.

    The real routes/email_service/rendering run unmodified. Auth is resolved
    from the test DB via a dependency override (attached to the request
    session — no detached instances). The DB engine is patched BEFORE app
    import so nothing can touch a real database (DB9C5B34FB_DATABASE_URL IS
    set in some environments — file-based SQLite + tmp_path guarantees
    isolation and durable commits across the TestClient's sessions).
    """
    from fastapi import Depends

    db_file = tmp_path / "test_crm.db"
    engine = create_engine(
        f"sqlite:///{db_file}",
        connect_args={"check_same_thread": False, "timeout": 30},
    )
    TestSession = sessionmaker(bind=engine, autoflush=False)
    Base.metadata.create_all(bind=engine)

    # Patch db module BEFORE app import so create_app/init_db/gmail thread
    # bind to the in-memory test engine. Never touch a real DATABASE_URL.
    monkeypatch.setattr(db_module, "engine", engine, raising=True)
    monkeypatch.setattr(db_module, "SessionLocal", TestSession, raising=True)

    def override_get_db():
        s = TestSession()
        try:
            yield s
        finally:
            s.close()

    import app as app_module

    test_app = app_module.create_app("./dist-nonexistent")

    from auth import get_current_user
    from db import get_db as real_get_db
    from fastapi import HTTPException
    from routes import api as api_router  # noqa: F401 — ensures routes registered

    # ── Seed data ──
    s = TestSession()
    user = User(id="u-1", email="me@test.com", password_hash="x", full_name="Justin Mikkelsen")
    org = Organization(id="o-1", name="Test Org")
    member = OrganizationMember(id="m-1", organization_id="o-1", user_id="u-1", role="owner")
    settings = EmailSettings(
        owner_user_id="u-1",
        provider="resend",
        from_email="justin@mybiz.com",
        from_name="Justin M.",
        reply_to_email="replies@mybiz.com",
        phone="555-100-2000",
        signature="Thanks,\n{{my_name}}\n{{my_phone}}",
        test_mode_enabled=True,
    )
    lead = Lead(
        id="lead-1",
        owner_user_id="u-1",
        organization_id="o-1",
        first_name="Dana",
        last_name="Reeves",
        full_name="Dana Reeves",
        business_name="Reeves Fitness",
        email="dana@reevesfitness.com",
        phone="555-900-8000",
        do_not_contact=False,
    )
    lead_dnc = Lead(
        id="lead-dnc",
        owner_user_id="u-1",
        organization_id="o-1",
        first_name="No",
        last_name="Contact",
        full_name="No Contact",
        email="nc@x.com",
        do_not_contact=True,
    )
    lead_sparse = Lead(
        id="lead-sparse",
        owner_user_id="u-1",
        organization_id="o-1",
        full_name=None,
        first_name=None,
        last_name=None,
        business_name=None,
        email="sparse@x.com",
        phone=None,
    )
    tpl = EmailTemplate(
        id="tpl-1",
        owner_user_id="u-1",
        organization_id="o-1",
        name="Intro",
        subject="Hi {{lead_first_name}}",
        body="Hello {{lead_name}} at {{lead_business}},\n\n— {{my_name}}",
    )
    s.add_all([user, org, member, settings, lead, lead_dnc, lead_sparse, tpl])
    s.commit()
    s.close()

    def _fake_current_user(db: Session = Depends(override_get_db)):
        u = db.query(User).filter(User.id == "u-1").first()
        if u is None:
            raise HTTPException(status_code=401, detail="User not found")
        return u

    test_app.dependency_overrides[real_get_db] = override_get_db
    test_app.dependency_overrides[get_current_user] = _fake_current_user

    captured: dict = {}

    import email_service as email_service_module

    # Disable the background Gmail sync thread — its sessions race the
    # shared in-memory SQLite connection across tests.
    monkeypatch.setattr(app_module, "_start_gmail_sync_thread", lambda: None, raising=True)

    # Capture the FINAL prepared payload. send_email applies rendering
    # (safety-net) + signature internally; wrapping _simulate AND the Resend
    # provider lets us capture post-signature content on both paths.
    real_simulate = email_service_module._simulate

    def capturing_simulate(payload, cfg):
        captured["send_payload"] = {
            "to": [payload.to_address],
            "subject": payload.subject,
            "text": payload.body,
        }
        captured["config"] = cfg
        return real_simulate(payload, cfg)

    monkeypatch.setattr(email_service_module, "_simulate", capturing_simulate, raising=True)

    # Patch the OUTBOUND provider call (Resend SDK) so live-path sends don't hit network
    import resend as resend_module

    def fake_resend_send(send_payload):
        captured["provider_payload"] = send_payload
        return {"id": "msg-1"}

    monkeypatch.setattr(resend_module, "Emails", SimpleNamespace(send=fake_resend_send), raising=True)

    # Reset rate-limiter counters so tests sharing the global limiter never 429
    from limiter import limiter as shared_limiter

    try:
        shared_limiter._storage.reset()
    except Exception:
        pass

    c = TestClient(test_app)
    c.headers.update({"Authorization": "Bearer test-token"})

    # ── Warmup: some runs race the in-memory SQLite engine on the very first
    # request (401/403 'empty database'). Warm up + reseed if that happens so
    # the suite is deterministic.
    def _seed():
        s = TestSession()
        s.add_all([user, org, member, settings, lead, lead_dnc, lead_sparse, tpl])
        s.commit()
        s.close()

    for _attempt in range(3):
        _seed()
        warm = c.get("/api/auth/me")
        if warm.status_code == 200:
            break
    else:
        chk = TestSession()
        n_users = chk.query(User).count()
        chk.close()
        raise RuntimeError(
            f"Test DB warmup failed after retries: {warm.status_code} {warm.text[:200]} "
            f"(users in db={n_users})"
        )

    captured["send_payload"] = None  # ensure key exists; tests assert on it explicitly
    yield SimpleClient(c, captured, TestSession)
    test_app.dependency_overrides.clear()


class SimpleClient:
    """TestClient wrapper + handle on captured provider payloads + db factory."""

    def __init__(self, client, captured, session_factory):
        self._client = client
        self.captured = captured
        self.session_factory = session_factory

    @property
    def payload(self):
        """The final payload passed to send_email (post-render, post-signature)."""
        from email_service import EmailPayload

        sp = self.captured["send_payload"]
        return EmailPayload(
            to_address=sp["to"][0],
            subject=sp["subject"],
            body=sp["text"],
        )

    def get(self, *a, **k):
        return self._client.get(*a, **k)

    def post(self, *a, **k):
        return self._client.post(*a, **k)

    def drop_auth_override(self):
        """Swap the auth override for one that raises — simulates unauthenticated."""
        from auth import get_current_user
        from fastapi import HTTPException

        def _unauthorized():
            raise HTTPException(status_code=401, detail="Not authenticated")

        self._client.app.dependency_overrides[get_current_user] = _unauthorized

    def restore_auth_override(self):
        from auth import get_current_user

        self._client.app.dependency_overrides.pop(get_current_user, None)


def send_email_to(client: SimpleClient, lead_id="lead-1", subject="", body="", to_address=None):
    payload: dict = {"subject": subject, "body": body}
    if to_address is not None:
        payload["to_address"] = to_address
    return client.post(f"/api/leads/{lead_id}/email", json=payload)


# ─── 1. Pure rendering: every variable resolves ──────────────────────────────


class TestVariableRendering:
    def test_all_supported_variables_render(self):
        from email_variables import VariableContext, render_variables

        ctx = VariableContext(
            my_name="Justin M.", my_email="j@b.com", my_phone="555-100-2000",
            lead_name="Dana Reeves", lead_first_name="Dana", lead_business="Reeves Fitness",
            lead_email="dana@r.com", lead_phone="555-900-8000",
        )
        text = (
            "Hi {{lead_first_name}} ({{lead_name}}) of {{lead_business}} — "
            "{{lead_email}} / {{lead_phone}}. From {{my_name}} <{{my_email}}> {{my_phone}}"
        )
        r = render_variables(text, ctx)
        assert r.text == (
            "Hi Dana (Dana Reeves) of Reeves Fitness — "
            "dana@r.com / 555-900-8000. From Justin M. <j@b.com> 555-100-2000"
        )
        assert r.used_variables == [
            "lead_first_name", "lead_name", "lead_business",
            "lead_email", "lead_phone", "my_name", "my_email", "my_phone",
        ]
        assert r.ok

    def test_missing_values_render_empty_never_none(self):
        from email_variables import VariableContext, render_variables

        ctx = VariableContext()  # everything None
        r = render_variables("Hi {{lead_first_name}} at {{lead_business}}, {{my_phone}}", ctx)
        assert r.text == "Hi  at , "
        assert "None" not in r.text and "null" not in r.text
        assert sorted(r.missing_variables) == ["lead_business", "lead_first_name", "my_phone"]

    def test_unknown_variables_flagged_not_substituted(self):
        from email_variables import VariableContext, render_variables

        ctx = VariableContext(my_name="X")
        r = render_variables("{{my_name}} {{password_hash}} {{user.password}}", ctx)
        assert r.text == "X {{password_hash}} {{user.password}}"
        assert r.unknown_variables == ["password_hash", "user.password"]

    def test_strict_mode_rejects_unknown(self):
        from email_variables import UnsupportedVariableError, VariableContext, render_variables

        with pytest.raises(UnsupportedVariableError) as e:
            render_variables("hi {{config.SECRET}}", VariableContext(), strict=True)
        assert "config.SECRET" in str(e.value)

    def test_whitespace_tolerant_tokens(self):
        from email_variables import VariableContext, render_variables

        r = render_variables("{{ my_name }} / {{lead_name}}", VariableContext(my_name="A", lead_name="B"))
        assert r.text == "A / B"

    def test_dotted_and_bracketed_tokens_rejected(self):
        from email_variables import VariableContext, validate_variables

        assert validate_variables("{{lead.__class__}} {{settings['JWT_SECRET']}}") == [
            "lead.__class__", "settings['JWT_SECRET']",
        ]

    def test_render_is_idempotent(self):
        from email_variables import VariableContext, render_variables

        ctx = VariableContext(my_name="A", lead_first_name="B")
        once = render_variables("Hi {{lead_first_name}} — {{my_name}}", ctx).text
        twice = render_variables(once, ctx).text
        assert once == twice == "Hi B — A"

    def test_sample_lead_context_has_all_lead_vars(self):
        from email_variables import LEAD_VARIABLES, SAMPLE_LEAD_CONTEXT

        assert set(SAMPLE_LEAD_CONTEXT.keys()) == set(LEAD_VARIABLES)

    def test_context_builders_from_orm_rows(self):
        from email_variables import build_context, render_variables

        class FakeSettings:
            from_name = " Justin "
            from_email = "from@b.com"
            reply_to_email = "reply@b.com"
            phone = None

        class FakeLead:
            full_name = None  # exercises first+last fallback
            first_name = "Dana"
            last_name = "Reeves"
            business_name = "Reeves"
            email = "d@r.com"
            phone = None

        ctx = build_context(settings=FakeSettings(), lead=FakeLead())
        r = render_variables("{{my_email}} {{my_name}} {{lead_name}} {{my_phone}}", ctx)
        assert r.text == "reply@b.com Justin Dana Reeves "
        # my_email prefers reply_to; blank phone → None → ''
        assert r.missing_variables == ["my_phone"]

    def test_none_lead_yields_empty_values(self):
        from email_variables import LEAD_VARIABLES, build_context, render_variables

        ctx = build_context(settings=None, lead=None)
        r = render_variables(" ".join("{{%s}}" % v for v in LEAD_VARIABLES), ctx)
        assert r.text == " " * (len(LEAD_VARIABLES) - 1)
        assert "None" not in r.text


# ─── 2. Signatures ───────────────────────────────────────────────────────────


class TestSignatures:
    def test_signature_variables_render_per_lead(self, client):
        # Signature contains {{my_name}} and {{my_phone}}; subject/body may too.
        r = send_email_to(client, subject="s", body="b")
        assert r.status_code == 201, f"{r.status_code}: {r.text[:300]}"
        body = client.payload.body
        assert "Thanks,\nJustin M.\n555-100-2000" in body  # separator + rendered sig
        assert "{{" not in body

    def test_signature_with_lead_variable_renders_lead_context(self, client, monkeypatch):
        # Rewrite the seeded signature to include a lead variable
        s = client.session_factory()
        s.query(EmailSettings).filter(EmailSettings.owner_user_id == "u-1").update(
            {"signature": "Best, {{my_name}} — talk soon, {{lead_first_name}}!"}
        )
        s.commit()
        s.close()
        r = send_email_to(client, subject="s", body="b")
        assert r.status_code == 201
        assert "talk soon, Dana!" in client.payload.body

    def test_signature_blank_variables_render_empty(self, client):
        s = client.session_factory()
        s.query(EmailSettings).filter(EmailSettings.owner_user_id == "u-1").update(
            {"signature": "{{my_phone}}", "phone": None}
        )
        s.commit()
        s.close()
        r = send_email_to(client, subject="s", body="b")
        assert r.status_code == 201
        # "{{my_phone}}" must NOT leak — it renders empty, and an empty
        # signature is skipped entirely by _apply_signature (no separator).
        assert client.payload.body == "b"
        assert "{{" not in client.payload.body


# ─── 3. Send route: manual, template, subject/body, test mode ────────────────


class TestSendRoute:
    def test_manually_typed_email_with_variables_renders(self, client):
        r = send_email_to(
            client,
            subject="Quick question, {{lead_first_name}}",
            body="Hi {{lead_first_name}} at {{lead_business}},\n\nFrom {{my_name}} ({{my_email}})",
        )
        assert r.status_code == 201
        p = client.payload
        assert p.subject == "Quick question, Dana"
        assert p.body.startswith("Hi Dana at Reeves Fitness,\n\nFrom Justin M. (replies@mybiz.com)")

    def test_template_stored_raw_sent_rendered(self, client):
        # Apply the template client-side like the UI does: copy raw tokens into fields
        s = client.session_factory()
        tpl = s.query(EmailTemplate).filter(EmailTemplate.id == "tpl-1").first()
        subject, body = tpl.subject, tpl.body
        s.close()
        r = send_email_to(client, subject=subject, body=body)
        assert r.status_code == 201
        p = client.payload
        assert p.subject == "Hi Dana"
        # Route pre-renders the signature with lead context, so the send
        # payload = rendered template body + separator + rendered signature.
        assert p.body.startswith("Hello Dana Reeves at Reeves Fitness,\n\n— Justin M.")
        assert p.body.endswith("\n\n--\nThanks,\nJustin M.\n555-100-2000")
        assert "{{" not in p.body

    def test_subject_and_body_rendered_independently(self, client):
        r = send_email_to(client, subject="{{lead_name}}", body="{{my_name}}")
        p = client.payload
        assert p.subject == "Dana Reeves"
        assert p.body.startswith("Justin M.")

    def test_test_mode_simulates_and_logs_rendered(self, client):
        r = send_email_to(client, subject="Hi {{lead_first_name}}", body="b {{my_name}}")
        assert r.status_code == 201
        assert r.json()["simulated"] is True
        s = client.session_factory()
        # Test-mode sends are logged with their OWN activity type so they are
        # never mistaken for real outreach.
        act = s.query(Activity).filter(Activity.activity_type == "TEST_EMAIL_SENT").first()
        s.close()
        assert act is not None
        assert "[TEST MODE — not delivered]" in act.body
        assert "To: dana@reevesfitness.com" in act.body
        assert "Hi Dana" in act.body and "Justin M." in act.body
        assert "{{" not in act.body  # log stores exactly what the provider got

    def test_no_literal_tokens_ever_reach_provider(self, client):
        r = send_email_to(client, subject="{{lead_name}}", body="{{lead_email}} {{my_phone}}")
        p = client.payload
        assert p.body.startswith("dana@reevesfitness.com 555-100-2000")
        assert "{{" not in p.body  # including the appended signature

    def test_missing_variables_returned_as_warning(self, client):
        # Blank both phones so {{lead_phone}}/{{my_phone}} resolve to empty
        s = client.session_factory()
        s.query(Lead).filter(Lead.id == "lead-1").update({"phone": None})
        s.query(EmailSettings).filter(EmailSettings.owner_user_id == "u-1").update({"phone": None})
        s.commit()
        s.close()
        r = send_email_to(client, subject="s", body="Call me at {{lead_phone}} or {{my_phone}}")
        assert r.status_code == 201
        assert sorted(r.json()["missing_variables"]) == ["lead_phone", "my_phone"]
        # never "None"/"null" — blank vars render as empty; signature follows
        # after rstrip by _apply_signature, so only assert the prefix
        assert client.payload.body.startswith("Call me at  or")
        assert "None" not in client.payload.body and "null" not in client.payload.body


# ─── 4. Unknown variables rejected at the API boundary ───────────────────────


class TestUnknownVariableRejection:
    @pytest.mark.parametrize("content", [
        {"subject": "{{unknown_var}}", "body": "b"},
        {"subject": "s", "body": "{{user.password_hash}}"},
        {"subject": "s", "body": "{{lead.__class__.__mro__}}"},
    ])
    def test_unknown_token_returns_400_and_never_sends(self, client, content):
        before = len(client.captured)
        r = send_email_to(client, **content)
        assert r.status_code == 400
        assert "Unsupported template variable" in r.json()["detail"]
        assert len(client.captured) == before  # nothing sent

    def test_error_lists_supported_variables(self, client):
        r = send_email_to(client, subject="{{nope}}", body="b")
        detail = r.json()["detail"]
        assert "{{ nope }}" in detail
        for v in ("my_name", "lead_phone", "lead_business"):
            assert f"{{{{{v}}}}}" in detail  # "{{my_name}}" etc. listed as supported


# ─── 5. Missing-lead / no-lead safety ────────────────────────────────────────


class TestNoLeadSafety:
    def test_lead_variables_with_sparse_lead_render_empty(self, client):
        # lead-sparse has only an email — all other lead vars render blank, send still works
        r = send_email_to(client, lead_id="lead-sparse", subject="Hi {{lead_first_name}}", body="b")
        assert r.status_code == 201
        # send_email strips the trailing space from the subject — verify the
        # token rendered empty (never "None"/"null") rather than exact spacing
        assert client.payload.subject == "Hi"
        assert "{{" not in client.payload.subject
        assert r.json()["missing_variables"] == ["lead_first_name"]

    def test_lead_name_falls_back_to_first_last(self, client):
        s = client.session_factory()
        s.query(Lead).filter(Lead.id == "lead-sparse").update({"first_name": "Sol", "last_name": "Owner"})
        s.commit()
        s.close()
        r = send_email_to(client, lead_id="lead-sparse", subject="{{lead_name}}", body="b")
        assert client.payload.subject == "Sol Owner"


# ─── 6. render-preview endpoint ──────────────────────────────────────────────


class TestRenderPreview:
    def test_preview_with_sample_lead(self, client):
        r = client.post("/api/email/render-preview", json={
            "subject": "Hi {{lead_first_name}}",
            "body": "{{lead_business}} — {{my_name}}",
        })
        assert r.status_code == 200
        data = r.json()
        assert data["subject"] == "Hi Alex"
        assert data["body"] == "Rivera Coaching — Justin M."
        assert sorted(data["used_variables"]) == ["lead_business", "lead_first_name", "my_name"]
        assert data["unknown_variables"] == []

    def test_preview_flags_unknown(self, client):
        r = client.post("/api/email/render-preview", json={"body": "{{totally_bogus}}"})
        assert r.status_code == 200
        assert r.json()["unknown_variables"] == ["totally_bogus"]

    def test_preview_with_real_lead_missing_values(self, client):
        r = client.post("/api/email/render-preview", json={
            "body": "{{lead_phone}} {{lead_first_name}}", "lead_id": "lead-sparse",
        })
        assert r.status_code == 200
        data = r.json()
        assert data["body"] == " "
        assert sorted(data["missing_variables"]) == ["lead_first_name", "lead_phone"]

    def test_preview_renders_signature(self, client):
        r = client.post("/api/email/render-preview", json={"signature": "— {{my_name}} ({{my_phone}})"})
        assert r.status_code == 200
        assert r.json()["signature"] == "— Justin M. (555-100-2000)"

    def test_preview_requires_auth(self, client):
        from auth import get_current_user

        client._client.app.dependency_overrides.pop(get_current_user, None)
        try:
            r = client.post("/api/email/render-preview", json={"body": "x"})
            assert r.status_code in (401, 403)
        finally:
            client.restore_auth_override()

    def test_preview_404s_for_other_org_lead(self, client):
        s = client.session_factory()
        s.add(Lead(id="lead-other", owner_user_id="u-1", organization_id="o-OTHER",
                   full_name="Other Org Lead", email="o@x.com"))
        s.commit()
        s.close()
        r = client.post("/api/email/render-preview", json={"body": "b", "lead_id": "lead-other"})
        assert r.status_code == 404


# ─── 7. Preserved protections: DNC, auth, rate limit, no-provider ────────────


class TestPreservedProtections:
    def test_dnc_still_blocks(self, client):
        r = send_email_to(client, lead_id="lead-dnc", subject="s", body="b")
        assert r.status_code == 451
        assert "Do Not Contact" in r.json()["detail"]
        assert client.captured.get("send_payload") is None  # nothing sent
        assert "provider_payload" not in client.captured

    def test_auth_required_on_send(self, client):
        from auth import get_current_user

        client._client.app.dependency_overrides.pop(get_current_user, None)
        try:
            r = send_email_to(client, subject="s", body="b")
            assert r.status_code in (401, 403)
        finally:
            client.restore_auth_override()

    def test_send_404_for_other_org_lead(self, client):
        s = client.session_factory()
        s.add(Lead(id="lead-other2", owner_user_id="u-1", organization_id="o-OTHER", email="o@x.com"))
        s.commit()
        s.close()
        r = send_email_to(client, lead_id="lead-other2", subject="s", body="b")
        assert r.status_code == 404

    def test_unsupported_variable_in_signature_config_renders_empty_safety_net(self, client, monkeypatch):
        # Signature with an unsupported token: route renders it (unknown stays literal),
        # then send_email's safety-net resolves senders and blanks the rest.
        from email_service import EmailConfig
        from email_variables import render_sender_variables

        cfg = EmailConfig(provider="resend", from_email="f@b.com", from_name="FN", test_mode_enabled=True)
        out = render_sender_variables("{{my_name}} {{lead_name}} {{evil}}", cfg)
        assert out == "FN  {{evil}}"  # sender resolved, lead blanked, unknown untouched

    def test_lead_email_validation_edge_empty_body(self, client):
        # Empty string body is accepted by pydantic (no min_length constraint);
        # route must not crash — renders and sends an empty body harmlessly.
        r = send_email_to(client, subject="s", body="")
        assert r.status_code in (201, 400)  # 400 if the route requires non-empty


# ─── 8. Activity logging of sent lead emails ─────────────────────────────────


class TestActivityLogging:
    """Successful lead emails create a complete activity record; failures do not."""

    def _get_activity(self, client, activity_type):
        s = client.session_factory()
        act = s.query(Activity).filter(Activity.activity_type == activity_type).order_by(Activity.occurred_at.desc()).first()
        s.close()
        return act

    def test_successful_send_creates_activity_with_full_record(self, client, monkeypatch):
        # Simulate a REAL (non-test-mode) delivery through Resend so the activity
        # is logged with the OUTREACH_SENT type.
        import resend as resend_module

        monkeypatch.setenv("RESEND_API_KEY", "test-key-not-real")

        def fake_resend_send(send_payload):
            return {"id": "msg-real-1"}

        monkeypatch.setattr(resend_module, "Emails", SimpleNamespace(send=fake_resend_send), raising=True)

        s0 = client.session_factory()
        s0.query(EmailSettings).filter(EmailSettings.owner_user_id == "u-1").update({"test_mode_enabled": False})
        s0.commit()
        s0.close()

        from datetime import datetime

        before = datetime.utcnow()
        r = send_email_to(
            client,
            subject="Quick question, {{lead_first_name}}",
            body="Hi {{lead_first_name}} at {{lead_business}},\n\n— {{my_name}}",
        )
        assert r.status_code == 201, r.text[:300]
        act = self._get_activity(client, "OUTREACH_SENT")
        assert act is not None
        # Correct lead + sending user + org
        assert act.lead_id == "lead-1"
        assert act.user_id == "u-1"
        assert act.organization_id == "o-1"
        # Server-generated timestamp at send time
        assert act.occurred_at is not None
        assert before <= act.occurred_at <= datetime.utcnow()
        # Recipient stored in the structured header block
        assert act.body.startswith("To: dana@reevesfitness.com\n")
        # RENDERED content stored — never the raw tokens
        assert "Subject: Quick question, Dana\n" in act.body
        assert "Hi Dana at Reeves Fitness," in act.body
        assert "— Justin M." in act.body
        assert "{{" not in act.body

    def test_send_response_echoes_activity_fields(self, client):
        r = send_email_to(client, subject="s", body="b")
        assert r.status_code == 201
        data = r.json()
        # fixture settings run with test_mode_enabled=True
        assert data["activity_type"] == "TEST_EMAIL_SENT"
        assert data["lead_id"] == "lead-1"
        assert data["user_id"] == "u-1"
        assert data["occurred_at"] is not None
        assert data["simulated"] is True

    def test_failed_send_not_marked_successful(self, client, monkeypatch):
        # Provider failure -> 502 and NO OUTREACH_SENT/TEST_EMAIL_SENT activity
        import email_service as email_service_module

        def failing_send_email(payload, config=None):
            from email_service import EmailResult

            return EmailResult(success=False, error="Resend API rejected the send")

        monkeypatch.setattr(email_service_module, "send_email", failing_send_email, raising=True)
        r = send_email_to(client, subject="s", body="b")
        assert r.status_code == 502
        assert "failed" in r.json()["detail"].lower() or "rejected" in r.json()["detail"].lower()
        s = client.session_factory()
        n = s.query(Activity).filter(
            Activity.activity_type.in_(["OUTREACH_SENT", "TEST_EMAIL_SENT"])
        ).count()
        s.close()
        assert n == 0  # nothing recorded as sent

    def test_send_exception_not_marked_successful(self, client, monkeypatch):
        # Provider raising unexpectedly -> 502 and still no activity
        import email_service as email_service_module

        def exploding_send_email(payload, config=None):
            raise RuntimeError("connection reset")

        monkeypatch.setattr(email_service_module, "send_email", exploding_send_email, raising=True)
        r = send_email_to(client, subject="s", body="b")
        assert r.status_code == 502
        s = client.session_factory()
        n = s.query(Activity).filter(
            Activity.activity_type.in_(["OUTREACH_SENT", "TEST_EMAIL_SENT"])
        ).count()
        s.close()
        assert n == 0

    def test_live_send_logs_real_outreach_type(self, client, monkeypatch):
        # Simulate a REAL (non-test-mode) successful delivery through Resend
        import resend as resend_module

        monkeypatch.setenv("RESEND_API_KEY", "test-key-not-real")

        def fake_resend_send(send_payload):
            return {"id": "msg-real-1"}

        monkeypatch.setattr(resend_module, "Emails", SimpleNamespace(send=fake_resend_send), raising=True)

        s = client.session_factory()
        s.query(EmailSettings).filter(EmailSettings.owner_user_id == "u-1").update({"test_mode_enabled": False})
        s.commit()
        s.close()

        r = send_email_to(client, subject="Live {{lead_first_name}}", body="Real body")
        assert r.status_code == 201, r.text[:300]
        assert r.json()["simulated"] is False
        act = self._get_activity(client, "OUTREACH_SENT")
        assert act is not None
        assert act.body.startswith("To: dana@reevesfitness.com\n")
        assert "Subject: Live Dana\n" in act.body
        assert "[TEST MODE" not in act.body
        # only ONE activity row for the send
        s = client.session_factory()
        total = s.query(Activity).filter(
            Activity.activity_type.in_(["OUTREACH_SENT", "TEST_EMAIL_SENT"])
        ).count()
        s.close()
        assert total == 1

    def test_test_mode_send_logged_as_test_type_not_outreach(self, client):
        r = send_email_to(client, subject="s", body="b")
        assert r.status_code == 201
        # TEST_EMAIL_SENT exists, OUTREACH_SENT does NOT
        s = client.session_factory()
        outreach = s.query(Activity).filter(Activity.activity_type == "OUTREACH_SENT").count()
        test = s.query(Activity).filter(Activity.activity_type == "TEST_EMAIL_SENT").count()
        s.close()
        assert test == 1
        assert outreach == 0
        act = self._get_activity(client, "TEST_EMAIL_SENT")
        assert act.user_id == "u-1"  # correct user even for test sends
        assert act.body.startswith("[TEST MODE — not delivered]\nTo: dana@reevesfitness.com\n")

    def test_dnc_send_creates_no_activity(self, client):
        r = send_email_to(client, lead_id="lead-dnc", subject="s", body="b")
        assert r.status_code == 451
        s = client.session_factory()
        n = s.query(Activity).filter(
            Activity.activity_type.in_(["OUTREACH_SENT", "TEST_EMAIL_SENT"])
        ).count()
        s.close()
        assert n == 0

    def test_activities_endpoint_returns_sent_email(self, client):
        send_email_to(client, subject="Hello there", body="Body content")
        r = client.get("/api/leads/lead-1/activities")
        assert r.status_code == 200
        items = r.json()
        assert any(
            a["activity_type"] == "TEST_EMAIL_SENT" and "To: dana@reevesfitness.com" in (a["body"] or "")
            for a in items
        )
        assert all("{{" not in (a["body"] or "") for a in items)


# ─── 9. email_service safety-net integration ─────────────────────────────────


class TestSendEmailSafetyNet:
    def test_send_email_blanks_unrendered_lead_tokens(self, monkeypatch):
        # A rogue path calling send_email directly with raw tokens still
        # cannot leak them: the safety-net renders senders, blanks leads.
        monkeypatch.setenv("RESEND_API_KEY", "test-key-not-real")

        from email_service import EmailConfig, EmailPayload, send_email

        captured: dict = {}

        import resend as resend_module

        def fake_resend_send(send_payload):
            captured["sp"] = send_payload
            return {"id": "msg-1"}

        monkeypatch.setattr(resend_module, "Emails", SimpleNamespace(send=fake_resend_send), raising=True)

        cfg = EmailConfig(provider="resend", from_email="f@b.com", from_name="FN", test_mode_enabled=False)
        result = send_email(
            EmailPayload(
                to_address="x@y.com",
                subject="Hi {{lead_first_name}}",
                body="From {{my_name}} {{lead_email}}",
            ),
            config=cfg,
        )

        assert result.success
        sp = captured["sp"]
        assert sp["subject"] == "Hi "
        assert sp["text"].startswith("From FN ")
        assert "{{" not in sp["text"] and "{{" not in sp["subject"]
        # HTML part also clean
        assert "{{" not in sp["html"]
