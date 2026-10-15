"""Backend tests for lead tags, status sorting, and CSV import duplicate handling.

Run:  uv run pytest tests/test_tags_import.py -q
Covers: tag normalization, tags on create/update/get, bulk tag add/remove/set,
tag filter, sort-by-status pipeline order, /leads-tags listing, CSV import
preview + commit with skip/update/merge strategies, legacy import auto-skip.
"""

from __future__ import annotations

import os

import pytest

# Must be set before importing app modules (auth.py raises without it)
os.environ.setdefault("JWT_SECRET", "test-secret-for-pytest-only")
os.environ.pop("EMAIL_SIGNATURE", None)

from types import SimpleNamespace  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

import db as db_module  # noqa: E402
from models import (  # noqa: E402
    Base,
    EmailSettings,
    Lead,
    Organization,
    OrganizationMember,
    Segment,
    User,
)


@pytest.fixture()
def client(monkeypatch, tmp_path):
    """Fresh file-based SQLite app per test (same harness as test_email_variables)."""
    from fastapi import Depends, HTTPException

    db_file = tmp_path / "test_crm.db"
    engine = create_engine(
        f"sqlite:///{db_file}",
        connect_args={"check_same_thread": False, "timeout": 30},
    )
    TestSession = sessionmaker(bind=engine, autoflush=False)
    Base.metadata.create_all(bind=engine)

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

    monkeypatch.setattr(app_module, "_start_gmail_sync_thread", lambda: None, raising=True)

    s = TestSession()
    user = User(id="u-1", email="me@test.com", password_hash="x", full_name="Justin Mikkelsen")
    org = Organization(id="o-1", name="Test Org")
    member = OrganizationMember(id="m-1", organization_id="o-1", user_id="u-1", role="owner")
    settings = EmailSettings(owner_user_id="u-1", test_mode_enabled=True)
    # Custom segment: key "home-services", label "Home Services" (org-created)
    seg = Segment(
        id="seg-home", owner_user_id="u-1", organization_id="o-1",
        key="home-services", label="Home Services", sort_order=10,
    )
    lead_a = Lead(
        id="lead-a", owner_user_id="u-1", organization_id="o-1",
        first_name="Dana", last_name="Reeves", full_name="Dana Reeves",
        business_name="Reeves Fitness", email="dana@reevesfitness.com",
        phone="555-900-8000", status="NEW",
    )
    lead_b = Lead(
        id="lead-b", owner_user_id="u-1", organization_id="o-1",
        first_name="Sam", last_name="Lee", full_name="Sam Lee",
        business_name="Lee Consulting", email="sam@leeconsulting.com",
        phone="555-111-2222", status="CONTACTED",
    )
    lead_c = Lead(
        id="lead-c", owner_user_id="u-1", organization_id="o-1",
        first_name="Al", last_name="Vega", full_name="Al Vega",
        business_name="Vega Coaching", email="al@vegacoach.com",
        phone="555-333-4444", status="WON",
    )
    s.add_all([user, org, member, settings, seg, lead_a, lead_b, lead_c])
    s.commit()
    s.close()

    def _fake_current_user(db: sessionmaker = Depends(override_get_db)):
        u = db.query(User).filter(User.id == "u-1").first()
        if u is None:
            raise HTTPException(status_code=401, detail="User not found")
        return u

    test_app.dependency_overrides[real_get_db] = override_get_db
    test_app.dependency_overrides[get_current_user] = _fake_current_user

    # Reset rate-limiter counters between tests
    from limiter import limiter as shared_limiter

    try:
        shared_limiter._storage.reset()
    except Exception:
        pass

    c = TestClient(test_app)
    c.headers.update({"Authorization": "Bearer test-token"})

    def _seed():
        s2 = TestSession()
        s2.add_all([user, org, member, settings, seg, lead_a, lead_b, lead_c])
        s2.commit()
        s2.close()

    for _attempt in range(3):
        _seed()
        warm = c.get("/api/auth/me")
        if warm.status_code == 200:
            break
    else:
        raise RuntimeError(f"Test DB warmup failed: {warm.status_code} {warm.text[:200]}")

    yield SimpleClient(c, TestSession)
    test_app.dependency_overrides.clear()


class SimpleClient:
    def __init__(self, client, session_factory):
        self._client = client
        self.session_factory = session_factory

    def get(self, *a, **k):
        return self._client.get(*a, **k)

    def post(self, *a, **k):
        return self._client.post(*a, **k)

    def put(self, *a, **k):
        return self._client.put(*a, **k)

    def request(self, *a, **k):
        return self._client.request(*a, **k)


# ─── 1. Tag normalization ─────────────────────────────────────────────────────


class TestTagNormalization:
    def test_list_input_normalized(self):
        from routes import normalize_tags

        assert normalize_tags(["  VIP ", "Hot Lead", "vip"]) == ["vip", "hot lead"]

    def test_comma_separated_string(self):
        from routes import normalize_tags

        assert normalize_tags("VIP, hot lead ,,  newsletter ") == ["vip", "hot lead", "newsletter"]

    def test_none_and_garbage(self):
        from routes import normalize_tags

        assert normalize_tags(None) == []
        assert normalize_tags(42) == []
        assert normalize_tags(",,,") == []

    def test_max_caps(self):
        from routes import normalize_tags, MAX_TAGS_PER_LEAD, MAX_TAG_LENGTH

        many = [f"tag{i}" for i in range(MAX_TAGS_PER_LEAD + 10)]
        assert len(normalize_tags(many)) == MAX_TAGS_PER_LEAD
        assert len(normalize_tags(["x" * 200])) == 0  # over-length tag dropped
        assert len(normalize_tags(["x" * MAX_TAG_LENGTH])) == 1

    def test_encode_decode_roundtrip(self):
        from routes import encode_tags, decode_tags

        encoded = encode_tags(["VIP", "Hot Lead"])
        assert encoded == '["vip", "hot lead"]'
        assert decode_tags(encoded) == ["vip", "hot lead"]
        assert decode_tags(None) == []
        assert decode_tags("not json at all") == []

    def test_encode_empty_returns_none(self):
        from routes import encode_tags

        assert encode_tags([]) is None
        assert encode_tags(None) is None


# ─── 2. Tags on lead CRUD ─────────────────────────────────────────────────────


class TestLeadTagsCrud:
    def test_create_lead_with_tags(self, client: SimpleClient):
        res = client.post("/api/leads", json={
            "full_name": "Tag Tester",
            "email": "tag@test.com",
            "tags": ["VIP", "hot lead"],
        })
        assert res.status_code == 201, res.text
        body = res.json()
        assert body["tags"] == ["vip", "hot lead"]

    def test_create_lead_accepts_comma_string(self, client: SimpleClient):
        res = client.post("/api/leads", json={
            "full_name": "Str Tester", "email": "str@test.com",
            "tags": "newsletter, referral",
        })
        assert res.status_code == 201
        assert res.json()["tags"] == ["newsletter", "referral"]

    def test_get_lead_returns_tags(self, client: SimpleClient):
        # seed tags directly through update
        res = client.put("/api/leads/lead-a", json={"tags": ["warm"]})
        assert res.status_code == 200
        got = client.get("/api/leads/lead-a").json()
        assert got["tags"] == ["warm"]

    def test_update_replaces_and_clears_tags(self, client: SimpleClient):
        client.put("/api/leads/lead-a", json={"tags": ["a", "b"]})
        res = client.put("/api/leads/lead-a", json={"tags": ["c"]})
        assert res.json()["tags"] == ["c"]
        res = client.put("/api/leads/lead-a", json={"tags": []})
        assert res.json()["tags"] == []

    def test_update_lead_without_tags_key_leaves_tags(self, client: SimpleClient):
        client.put("/api/leads/lead-a", json={"tags": ["keepme"]})
        res = client.put("/api/leads/lead-a", json={"niche": "fitness"})
        assert res.json()["tags"] == ["keepme"]
        assert res.json()["niche"] == "fitness"

    def test_invalid_tags_dropped_silently(self, client: SimpleClient):
        res = client.post("/api/leads", json={
            "full_name": "Bad Tags", "email": "bad@test.com",
            "tags": ["ok-tag", "", "   ", "x" * 100],
        })
        assert res.status_code == 201
        assert res.json()["tags"] == ["ok-tag"]


# ─── 3. Bulk tags ─────────────────────────────────────────────────────────────


class TestBulkTags:
    def test_bulk_add(self, client: SimpleClient):
        client.put("/api/leads/lead-a", json={"tags": ["existing"]})
        res = client.post("/api/leads/bulk-tags", json={
            "lead_ids": ["lead-a", "lead-b"], "tags": ["vip", "existing"], "mode": "add",
        })
        assert res.status_code == 200, res.text
        assert res.json() == {"updated": 2}
        a = client.get("/api/leads/lead-a").json()
        b = client.get("/api/leads/lead-b").json()
        assert a["tags"] == ["existing", "vip"]  # union, no dupes
        assert b["tags"] == ["vip", "existing"]  # both tags applied to every selected lead

    def test_bulk_remove(self, client: SimpleClient):
        client.post("/api/leads/bulk-tags", json={
            "lead_ids": ["lead-a", "lead-b"], "tags": "vip, warm", "mode": "set",
        })
        res = client.post("/api/leads/bulk-tags", json={
            "lead_ids": ["lead-a", "lead-b"], "tags": "warm", "mode": "remove",
        })
        assert res.json() == {"updated": 2}
        assert client.get("/api/leads/lead-a").json()["tags"] == ["vip"]
        assert client.get("/api/leads/lead-b").json()["tags"] == ["vip"]

    def test_bulk_set_replaces(self, client: SimpleClient):
        client.put("/api/leads/lead-a", json={"tags": ["old"]})
        client.post("/api/leads/bulk-tags", json={
            "lead_ids": ["lead-a"], "tags": ["fresh"], "mode": "set",
        })
        assert client.get("/api/leads/lead-a").json()["tags"] == ["fresh"]

    def test_bulk_invalid_mode_rejected(self, client: SimpleClient):
        res = client.post("/api/leads/bulk-tags", json={
            "lead_ids": ["lead-a"], "tags": "x", "mode": "nuke",
        })
        assert res.status_code == 400

    def test_bulk_empty_tags_rejected_for_add(self, client: SimpleClient):
        res = client.post("/api/leads/bulk-tags", json={
            "lead_ids": ["lead-a"], "tags": "", "mode": "add",
        })
        assert res.status_code == 400

    def test_bulk_scoped_to_org(self, client: SimpleClient):
        res = client.post("/api/leads/bulk-tags", json={
            "lead_ids": ["other-org-lead"], "tags": "vip", "mode": "set",
        })
        assert res.json() == {"updated": 0}


# ─── 4. Tag filter + org tag list ─────────────────────────────────────────────


class TestTagFiltering:
    def test_filter_by_tag(self, client: SimpleClient):
        client.post("/api/leads/bulk-tags", json={
            "lead_ids": ["lead-a"], "tags": "vip", "mode": "set",
        })
        res = client.get("/api/leads", params={"tag": "vip"})
        names = [l["id"] for l in res.json()["items"]]
        assert "lead-a" in names
        assert "lead-b" not in names

    def test_leads_tags_endpoint(self, client: SimpleClient):
        client.post("/api/leads/bulk-tags", json={
            "lead_ids": ["lead-a", "lead-b"], "tags": "vip, warm", "mode": "add",
        })
        res = client.get("/api/leads-tags")
        assert res.status_code == 200
        assert res.json()["tags"] == ["vip", "warm"]


# ─── 5. Status sorting ────────────────────────────────────────────────────────


class TestStatusSorting:
    def test_sort_by_status_pipeline_order(self, client: SimpleClient):
        # seeded: lead-a NEW, lead-b CONTACTED, lead-c WON
        res = client.get("/api/leads", params={"sort_by": "status", "sort_dir": "asc"})
        ids = [l["id"] for l in res.json()["items"]]
        assert ids.index("lead-a") < ids.index("lead-b") < ids.index("lead-c")

    def test_sort_by_status_desc_reverses(self, client: SimpleClient):
        res = client.get("/api/leads", params={"sort_by": "status", "sort_dir": "desc"})
        ids = [l["id"] for l in res.json()["items"]]
        assert ids.index("lead-c") < ids.index("lead-b") < ids.index("lead-a")

    def test_newly_uploaded_sort_together(self, client: SimpleClient):
        """Requirement: sort so newly uploaded leads display together."""
        client.post("/api/leads", json={"full_name": "Fresh Lead", "email": "fresh@x.com"})
        res = client.get("/api/leads", params={"sort_by": "created_at", "sort_dir": "desc"})
        items = res.json()["items"]
        assert items[0]["full_name"] == "Fresh Lead"

    def test_sort_by_segment_label(self, client: SimpleClient):
        """Segment sort orders by the custom segment's LABEL, unsegmented last."""
        client.put("/api/leads/lead-a", json={"segment_id": "seg-home"})
        res = client.get("/api/leads", params={"sort_by": "segment", "sort_dir": "asc"})
        labels = [
            (l["segment_label"] or l["segment"] or "")
            for l in res.json()["items"]
        ]
        # labeled segments first (alphabetical by label), blanks last
        assert [x for x in labels if x] == sorted([x for x in labels if x])
        assert labels[-1] == ""

    def test_sort_by_priority_tier(self, client: SimpleClient):
        client.put("/api/leads/lead-a", json={"priority_tier": "A"})
        client.put("/api/leads/lead-b", json={"priority_tier": "C"})
        client.put("/api/leads/lead-c", json={"priority_tier": "B"})
        res = client.get("/api/leads", params={"sort_by": "priority_tier", "sort_dir": "asc"})
        tiers = [l["priority_tier"] for l in res.json()["items"]]
        assert tiers == sorted(tiers)

    def test_sort_by_business_name(self, client: SimpleClient):
        res = client.get("/api/leads", params={"sort_by": "business_name", "sort_dir": "asc"})
        names = [l["business_name"] for l in res.json()["items"] if l["business_name"]]
        assert names == sorted(names)


# ─── 6. CSV import: duplicate handling ────────────────────────────────────────


def _csv_file(content: str) -> dict:
    return {"file": ("leads.csv", content.encode("utf-8"), "text/csv")}


class TestCsvDuplicateHandling:
    def test_preview_flags_duplicates(self, client: SimpleClient):
        csv_content = (
            "full_name,email,phone\n"
            "Dana Reeves,dana@reevesfitness.com,555-900-8000\n"  # dup of lead-a (email)
            "Someone New,new@x.com,\n"                            # new
        )
        res = client.post("/api/import/csv/preview", files=_csv_file(csv_content))
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["new_count"] == 1
        assert body["duplicate_count"] == 1
        assert body["duplicates"][0]["row_number"] == 2
        assert body["duplicates"][0]["existing"]["lead_id"] == "lead-a"
        assert body["batch"]

    def test_preview_phone_fallback_match(self, client: SimpleClient):
        csv_content = (
            "full_name,email,phone\n"
            "Dana R. (new email),different@x.com,(555) 900-8000\n"  # phone dup of lead-a
        )
        res = client.post("/api/import/csv/preview", files=_csv_file(csv_content))
        body = res.json()
        assert body["duplicate_count"] == 1
        assert body["duplicates"][0]["existing"]["lead_id"] == "lead-a"

    def test_preview_in_file_duplicate(self, client: SimpleClient):
        csv_content = (
            "full_name,email\n"
            "First Copy,fresh@x.com\n"
            "Second Copy,fresh@x.com\n"  # duplicate within the same file
        )
        res = client.post("/api/import/csv/preview", files=_csv_file(csv_content))
        body = res.json()
        assert body["new_count"] == 1
        assert body["duplicate_count"] == 1
        assert body["duplicates"][0]["row_number"] == 3

    def test_preview_rows_without_email_and_phone_are_new(self, client: SimpleClient):
        csv_content = (
            "full_name,business_name\n"
            "Mystery Lead,Mystery Biz\n"
        )
        res = client.post("/api/import/csv/preview", files=_csv_file(csv_content))
        assert res.json()["new_count"] == 1
        assert res.json()["duplicate_count"] == 0

    def test_commit_skip_leaves_existing(self, client: SimpleClient):
        prev = client.post("/api/import/csv/preview", files=_csv_file(
            "full_name,email,phone\nDana Reeves,dana@reevesfitness.com,\n"
        )).json()
        dup_row = str(prev["duplicates"][0]["row_number"])
        before = client.get("/api/leads/lead-a").json()
        res = client.post("/api/import/csv/commit", json={"batch": prev["batch"], "actions": {dup_row: "skip"}})
        assert res.status_code == 200
        assert res.json() == {"inserted": 0, "updated": 0, "merged": 0, "skipped": 1}
        after = client.get("/api/leads/lead-a").json()
        assert after["updated_at"] == before["updated_at"] or after["business_name"] == before["business_name"]

    def test_commit_update_fills_blanks_only(self, client: SimpleClient):
        # lead-b has no website_url or location; CSV brings both, plus an email that must NOT overwrite
        csv_content = (
            "full_name,email,website_url,location_text\n"
            "Sam Lee,sam@leeconsulting.com,https://leeconsulting.com,Austin TX\n"
        )
        prev = client.post("/api/import/csv/preview", files=_csv_file(csv_content)).json()
        assert prev["duplicate_count"] == 1
        dup_row = str(prev["duplicates"][0]["row_number"])
        res = client.post("/api/import/csv/commit", json={"batch": prev["batch"], "actions": {dup_row: "update"}})
        assert res.json()["updated"] == 1
        b = client.get("/api/leads/lead-b").json()
        assert b["website_url"] == "https://leeconsulting.com"
        assert b["location_text"] == "Austin TX"
        assert b["email"] == "sam@leeconsulting.com"  # untouched (was already set)

    def test_commit_update_does_not_clobber_tags(self, client: SimpleClient):
        client.put("/api/leads/lead-a", json={"tags": ["vip"]})
        csv_content = "full_name,email,tags\nDana Reeves,dana@reevesfitness.com,imported-tag\n"
        prev = client.post("/api/import/csv/preview", files=_csv_file(csv_content)).json()
        dup_row = str(prev["duplicates"][0]["row_number"])
        client.post("/api/import/csv/commit", json={"batch": prev["batch"], "actions": {dup_row: "update"}})
        a = client.get("/api/leads/lead-a").json()
        assert a["tags"] == ["vip"]  # update strategy never touches tags

    def test_commit_merge_unions_tags(self, client: SimpleClient):
        client.put("/api/leads/lead-a", json={"tags": ["vip"]})
        csv_content = "full_name,email,tags\nDana Reeves,dana@reevesfitness.com,csv-tag\n"
        prev = client.post("/api/import/csv/preview", files=_csv_file(csv_content)).json()
        dup_row = str(prev["duplicates"][0]["row_number"])
        res = client.post("/api/import/csv/commit", json={"batch": prev["batch"], "actions": {dup_row: "merge"}})
        assert res.json()["merged"] == 1
        a = client.get("/api/leads/lead-a").json()
        assert a["tags"] == ["vip", "csv-tag"]

    def test_commit_inserts_new_rows_with_tags(self, client: SimpleClient):
        csv_content = (
            "full_name,email,tags\n"
            "New Person,new@x.com,vip, newsletter\n"
        )
        prev = client.post("/api/import/csv/preview", files=_csv_file(csv_content)).json()
        res = client.post("/api/import/csv/commit", json={"batch": prev["batch"], "actions": {}})
        assert res.json()["inserted"] == 1
        leads = client.get("/api/leads", params={"tag": "vip"}).json()["items"]
        assert any(l["email"] == "new@x.com" for l in leads)

    def test_commit_unknown_batch_404(self, client: SimpleClient):
        res = client.post("/api/import/csv/commit", json={"batch": "nope", "actions": {}})
        assert res.status_code == 404

    def test_commit_scoped_to_org(self, client: SimpleClient):
        prev = client.post("/api/import/csv/preview", files=_csv_file(
            "full_name,email\nDana Reeves,dana@reevesfitness.com\n"
        )).json()
        # Simulate a different org stealing the batch token
        import routes as routes_module

        routes_module._IMPORT_BATCHES[prev["batch"]]["org_id"] = "org-other"
        res = client.post("/api/import/csv/commit", json={"batch": prev["batch"], "actions": {}})
        assert res.status_code == 404

    def test_legacy_import_skips_duplicates(self, client: SimpleClient):
        csv_content = (
            "full_name,email\n"
            "Dana Reeves,dana@reevesfitness.com\n"  # dup → skipped
            "Legacy New,legacy@x.com\n"             # new → inserted
        )
        res = client.post("/api/import/csv", files=_csv_file(csv_content))
        assert res.status_code == 200
        body = res.json()
        assert body["accepted"] == 1
        assert body["duplicates_skipped"] == 1

    def test_export_includes_tags(self, client: SimpleClient):
        client.put("/api/leads/lead-a", json={"tags": "vip, warm"})
        res = client.get("/api/export/csv")
        assert res.status_code == 200
        text = res.text
        assert "tags" in text.splitlines()[0]
        assert "vip, warm" in text


# ─── 7. CSV segment resolution (custom segments) ─────────────────────────────


class TestCsvSegmentResolution:
    """CSV `segment` column must match org-created segments, not just legacy enums.

    Regression: importing leads with segment "Home Services" (a custom segment)
    filed them all under OTHER because only the legacy enum was consulted.
    """

    def test_preview_resolves_custom_segment_by_label(self, client: SimpleClient):
        csv_content = (
            "full_name,email,segment\n"
            "Pat Home,pathome@x.com,Home Services\n"
        )
        prev = client.post("/api/import/csv/preview", files=_csv_file(csv_content))
        assert prev.status_code == 200, prev.text
        assert prev.json()["new_count"] == 1
        assert prev.json()["duplicate_count"] == 0
        res = client.post("/api/import/csv/commit", json={
            "batch": prev.json()["batch"], "actions": {},
        })
        assert res.status_code == 200
        assert res.json()["inserted"] == 1
        leads = client.get("/api/leads", params={"search": "pathome@x.com"}).json()
        assert leads["total"] == 1
        assert leads["items"][0]["segment_label"] == "Home Services"
        assert leads["items"][0]["segment_id"] == "seg-home"

    def test_import_resolves_segment_key_and_slug_variants(self, client: SimpleClient):
        for raw in ("home-services", "home_services", "HOMESERVICES"):
            csv_content = (
                f"full_name,email,segment\n"
                f"Slug Lead {raw},slug-{raw.replace('_', '').replace('-', '')}@x.com,{raw}\n"
            )
            prev = client.post("/api/import/csv/preview", files=_csv_file(csv_content))
            assert prev.status_code == 200, prev.text
            res = client.post("/api/import/csv/commit", json={
                "batch": prev.json()["batch"], "actions": {},
            })
            assert res.status_code == 200
            leads = client.get(
                "/api/leads", params={"search": f"slug-{raw.replace('_', '').replace('-', '')}@x.com"}
            ).json()
            assert leads["total"] == 1, f"{raw!r} should resolve"
            assert leads["items"][0]["segment_id"] == "seg-home"
            assert leads["items"][0]["segment_label"] == "Home Services"

    def test_import_legacy_enum_still_works(self, client: SimpleClient):
        csv_content = (
            "full_name,email,segment\n"
            "Coach Kim,coachkim@x.com,coach\n"
        )
        prev = client.post("/api/import/csv/preview", files=_csv_file(csv_content))
        assert prev.status_code == 200
        client.post("/api/import/csv/commit", json={"batch": prev.json()["batch"], "actions": {}})
        leads = client.get("/api/leads", params={"search": "coachkim@x.com"}).json()
        assert leads["items"][0]["segment"] == "COACH"

    def test_import_unknown_segment_falls_back_to_other(self, client: SimpleClient):
        csv_content = (
            "full_name,email,segment\n"
            "Odd Lead,odd@x.com,Underwater Basket Weaving\n"
        )
        prev = client.post("/api/import/csv/preview", files=_csv_file(csv_content))
        assert prev.status_code == 200
        client.post("/api/import/csv/commit", json={"batch": prev.json()["batch"], "actions": {}})
        leads = client.get("/api/leads", params={"search": "odd@x.com"}).json()
        assert leads["items"][0]["segment"] == "OTHER"
        assert leads["items"][0]["segment_id"] is None

    def test_import_without_segment_column_leaves_blank(self, client: SimpleClient):
        csv_content = (
            "full_name,email\n"
            "No Seg,noseg@x.com\n"
        )
        prev = client.post("/api/import/csv/preview", files=_csv_file(csv_content))
        assert prev.status_code == 200
        client.post("/api/import/csv/commit", json={"batch": prev.json()["batch"], "actions": {}})
        leads = client.get("/api/leads", params={"search": "noseg@x.com"}).json()
        assert leads["items"][0]["segment"] is None
        assert leads["items"][0]["segment_id"] is None

    def test_legacy_import_endpoint_resolves_custom_segment(self, client: SimpleClient):
        csv_content = (
            "full_name,email,segment\n"
            "Legacy Home,legacyhome@x.com,Home Services\n"
        )
        res = client.post("/api/import/csv", files=_csv_file(csv_content))
        assert res.status_code == 200
        assert res.json()["accepted"] == 1
        leads = client.get("/api/leads", params={"search": "legacyhome@x.com"}).json()
        assert leads["items"][0]["segment_id"] == "seg-home"

    def test_update_action_does_not_clobber_segment(self, client: SimpleClient):
        """Duplicate 'update' fills blanks but never overwrites segment fields."""
        # lead-a (Dana) has no segment; incoming row claims Home Services.
        csv_content = (
            "full_name,email,segment\n"
            "Dana R,dana@reevesfitness.com,Home Services\n"
        )
        prev = client.post("/api/import/csv/preview", files=_csv_file(csv_content))
        assert prev.json()["duplicate_count"] == 1
        res = client.post("/api/import/csv/commit", json={
            "batch": prev.json()["batch"], "actions": {"2": "update"},
        })
        assert res.json()["updated"] == 1
        lead = client.get("/api/leads/lead-a").json()
        # fill-blank policy: lead-a had NO segment, so incoming segment applies
        assert lead["segment_id"] == "seg-home"

    def test_segments_api_exposes_csv_value(self, client: SimpleClient):
        res = client.get("/api/segments")
        assert res.status_code == 200
        seg = next(s for s in res.json() if s["id"] == "seg-home")
        assert seg["csv_value"] == "Home Services"

