"""API routes for Leverage CRM Lite."""

import csv
import io
import json
import logging
import os
import re
import uuid
from datetime import datetime, timedelta
from typing import Optional
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query, Request, UploadFile, File, status
from fastapi.responses import RedirectResponse, StreamingResponse
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, and_, case
from sqlalchemy.orm import Session

from auth import (
    create_access_token,
    get_current_org,
    get_current_user,
    hash_password,
    verify_password,
    OrgContext,
)
from limiter import limiter
from business import apply_status_transition, compute_next_follow_up, recalculate_scores
from db import get_db
from models import Activity, EmailSettings, EmailTemplate, GmailConnection, Notification, OAuthState, PasswordResetToken, SyncedEmail, Lead, User, Segment, Organization, OrganizationMember

api = APIRouter()
logger = logging.getLogger(__name__)


# ----Helper to allow for custom segments
LEGACY_SEGMENTS = {"COACH", "CONSULTANT", "SOLOPRENEUR", "OTHER"}

def legacy_segment_or_none(key: str | None) -> str | None:
    if not key:
        return None
    normalized = key.strip().upper()
    return normalized if normalized in LEGACY_SEGMENTS else None
#-- end helper--

# ─── Pydantic Schemas ────────────────────────────────────────────────────────
class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=10)
    full_name: Optional[str] = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class AuthResponse(BaseModel):
    token: str
    user: dict


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=10)


class LeadCreate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    full_name: Optional[str] = None
    business_name: Optional[str] = None
    segment: Optional[str] = None
    segment_id: Optional[str] = None
    tags: Optional[object] = None  # list[str] or comma-separated str — normalized server-side
    niche: Optional[str] = None
    website_url: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    contact_path: Optional[str] = None
    linkedin_url: Optional[str] = None
    location_text: Optional[str] = None
    team_size_estimate: Optional[int] = None
    source_url: Optional[str] = None
    personalization_note: Optional[str] = None
    outreach_angle: Optional[str] = None
    offer_clarity_score: Optional[int] = Field(None, ge=0, le=2)
    bottleneck_evidence_score: Optional[int] = Field(None, ge=0, le=2)
    buying_signal_score: Optional[int] = Field(None, ge=0, le=2)
    decision_maker_access_score: Optional[int] = Field(None, ge=0, le=2)
    contactability_score: Optional[int] = Field(None, ge=0, le=2)
    strategic_fit_score: Optional[int] = Field(None, ge=0, le=2)

class LeadUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    full_name: Optional[str] = None
    business_name: Optional[str] = None
    segment: Optional[str] = None
    segment_id: Optional[str] = None
    tags: Optional[object] = None  # replaces the full tag set (send [] to clear)
    niche: Optional[str] = None
    website_url: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    contact_path: Optional[str] = None
    linkedin_url: Optional[str] = None
    location_text: Optional[str] = None
    team_size_estimate: Optional[int] = None
    source_url: Optional[str] = None
    personalization_note: Optional[str] = None
    outreach_angle: Optional[str] = None
    offer_clarity_score: Optional[int] = Field(None, ge=0, le=2)
    bottleneck_evidence_score: Optional[int] = Field(None, ge=0, le=2)
    buying_signal_score: Optional[int] = Field(None, ge=0, le=2)
    decision_maker_access_score: Optional[int] = Field(None, ge=0, le=2)
    contactability_score: Optional[int] = Field(None, ge=0, le=2)
    strategic_fit_score: Optional[int] = Field(None, ge=0, le=2)
    outcome_note: Optional[str] = None
    do_not_contact: Optional[bool] = None

class StatusChangeRequest(BaseModel):
    status: str


class EmailSendRequest(BaseModel):
    subject: str
    body: str
    to_address: Optional[str] = None  # falls back to lead.email


class ActivityCreate(BaseModel):
    activity_type: str
    body: Optional[str] = None
    occurred_at: Optional[datetime] = None


class ActivityUpdate(BaseModel):
    body: str


class BulkStatusChange(BaseModel):
    lead_ids: list[str]
    status: str

class BulkSegmentChange(BaseModel):
    lead_ids: list[str]
    segment_id: str

class BulkTagChange(BaseModel):
    lead_ids: list[str]
    tags: object  # list[str] or comma-separated str
    mode: str = "add"  # "add" (union) | "remove" (subtract) | "set" (replace)

class SegmentCreate(BaseModel):
    key: str
    label: str
    sort_order: Optional[int] = 0
    is_active: Optional[bool] = True


class SegmentUpdate(BaseModel):
    key: Optional[str] = None
    label: Optional[str] = None
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None


class OrgMemberAdd(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None
    role: str = "member"  # "owner" | "member"
    password: Optional[str] = Field(None, min_length=10)


class OrgMemberRoleUpdate(BaseModel):
    role: str  # "owner" | "member"


class MarkNotificationRead(BaseModel):
    notification_id: str


class EmailTemplateCreate(BaseModel):
    name: str
    subject: str
    body: str


class EmailTemplateUpdate(BaseModel):
    name: Optional[str] = None
    subject: Optional[str] = None
    body: Optional[str] = None


class EmailSettingsUpdate(BaseModel):
    provider: Optional[str] = None          # "smtp" | "resend" | "sendgrid" | "postmark" | None
    from_email: Optional[str] = None
    from_name: Optional[str] = None
    reply_to_email: Optional[str] = None
    phone: Optional[str] = None
    signature: Optional[str] = None
    test_mode_enabled: Optional[bool] = None


# ─── Tags helpers ────────────────────────────────────────────────────────────

MAX_TAGS_PER_LEAD = 20
MAX_TAG_LENGTH = 40
VALID_TAG_RE = re.compile(r"^[\w][\w\s/&+.-]{0,%d}$" % (MAX_TAG_LENGTH - 1), re.UNICODE)


def normalize_tags(raw: object) -> list[str]:
    """Normalize arbitrary input into a clean, deduped tag list.

    Accepts: list of strings, comma-separated string, or None.
    Rules: lowercase, trimmed, deduped (order-preserving), capped at
    MAX_TAGS_PER_LEAD entries of MAX_TAG_LENGTH chars. Empty/invalid
    entries are dropped silently (tags are advisory metadata).
    """
    if raw is None:
        return []
    if isinstance(raw, str):
        parts = [p for p in raw.split(",")]
    elif isinstance(raw, (list, tuple)):
        parts = [str(p) for p in raw]
    else:
        return []
    out: list[str] = []
    for p in parts:
        tag = re.sub(r"\s+", " ", p.strip().lower())
        if not tag or tag in out:
            continue
        if not VALID_TAG_RE.match(tag):
            continue
        out.append(tag)
        if len(out) >= MAX_TAGS_PER_LEAD:
            break
    return out


def encode_tags(tags: object) -> str | None:
    normalized = normalize_tags(tags)
    return json.dumps(normalized) if normalized else None


def decode_tags(value: str | None) -> list[str]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
    except (ValueError, TypeError):
        return []
    return normalize_tags(parsed)


def lead_to_dict(lead: Lead) -> dict:
    return {
        "id": lead.id,
        "owner_user_id": lead.owner_user_id,
        "organization_id": lead.organization_id,
        "first_name": lead.first_name,
        "last_name": lead.last_name,
        "full_name": lead.full_name,
        "business_name": lead.business_name,
        "segment": lead.segment,
        "segment_id": lead.segment_id,
        "segment_label": lead.segment_rel.label if lead.segment_rel else None,
        "tags": decode_tags(lead.tags),
        "niche": lead.niche,
        "website_url": lead.website_url,
        "email": lead.email,
        "phone": lead.phone,
        "contact_path": lead.contact_path,
        "linkedin_url": lead.linkedin_url,
        "location_text": lead.location_text,
        "team_size_estimate": lead.team_size_estimate,
        "source_url": lead.source_url,
        "personalization_note": lead.personalization_note,
        "outreach_angle": lead.outreach_angle,
        "offer_clarity_score": lead.offer_clarity_score,
        "bottleneck_evidence_score": lead.bottleneck_evidence_score,
        "buying_signal_score": lead.buying_signal_score,
        "decision_maker_access_score": lead.decision_maker_access_score,
        "contactability_score": lead.contactability_score,
        "strategic_fit_score": lead.strategic_fit_score,
        "total_score": lead.total_score,
        "priority_tier": lead.priority_tier,
        "status": lead.status,
        "last_contacted_at": lead.last_contacted_at.isoformat() if lead.last_contacted_at else None,
        "follow_up_count": lead.follow_up_count,
        "next_follow_up_at": lead.next_follow_up_at.isoformat() if lead.next_follow_up_at else None,
        "outcome_note": lead.outcome_note,
        "do_not_contact": lead.do_not_contact,
        "created_at": lead.created_at.isoformat() if lead.created_at else None,
        "updated_at": lead.updated_at.isoformat() if lead.updated_at else None,
    }
    
def segment_to_dict(segment: Segment) -> dict:
    return {
        "id": segment.id,
        "owner_user_id": segment.owner_user_id,
        "organization_id": segment.organization_id,
        "key": segment.key,
        "label": segment.label,
        "sort_order": segment.sort_order,
        "is_active": segment.is_active,
        "created_at": segment.created_at.isoformat() if segment.created_at else None,
        "updated_at": segment.updated_at.isoformat() if segment.updated_at else None,
    }

def activity_to_dict(a: Activity) -> dict:
    return {
        "id": a.id,
        "lead_id": a.lead_id,
        "user_id": a.user_id,
        "organization_id": a.organization_id,
        "activity_type": a.activity_type,
        "body": a.body,
        "occurred_at": a.occurred_at.isoformat() if a.occurred_at else None,
        "created_at": a.created_at.isoformat() if a.created_at else None,
    }

def template_to_dict(t: EmailTemplate) -> dict:
    return {
        "id": t.id,
        "owner_user_id": t.owner_user_id,
        "organization_id": t.organization_id,
        "name": t.name,
        "subject": t.subject,
        "body": t.body,
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "updated_at": t.updated_at.isoformat() if t.updated_at else None,
    }

def email_settings_to_dict(s: EmailSettings) -> dict:
    return {
        "id": s.id,
        "provider": s.provider,
        "from_email": s.from_email,
        "from_name": s.from_name,
        "reply_to_email": s.reply_to_email,
        "phone": s.phone,
        "signature": s.signature,
        "test_mode_enabled": s.test_mode_enabled,
        "updated_at": s.updated_at.isoformat() if s.updated_at else None,
    }


def notification_to_dict(n) -> dict:
    return {
        "id": n.id,
        "owner_user_id": n.owner_user_id,
        "lead_id": n.lead_id,
        "title": n.title,
        "body": n.body,
        "notification_type": n.notification_type,
        "is_read": n.is_read,
        "created_at": n.created_at.isoformat() if n.created_at else None,
    }


# ─── Auth Routes ─────────────────────────────────────────────────────────────

# Dummy hash used to keep login response time constant even when a user isn't found.
# This prevents email enumeration via timing side-channel.
_DUMMY_HASH = hash_password("__timing_guard__")


@api.post("/auth/register", response_model=AuthResponse)
@limiter.limit("5/minute")
def register(request: Request, req: RegisterRequest, db: Session = Depends(get_db)):
    # REGISTRATION_ENABLED defaults to "true". Set to "false" in production
    # once your account is created to lock the endpoint.
    if os.environ.get("REGISTRATION_ENABLED", "true").lower() != "true":
        raise HTTPException(status_code=403, detail="Registration is closed")

    existing = db.query(User).filter(User.email == req.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    user = User(
        email=req.email,
        password_hash=hash_password(req.password),
        full_name=req.full_name,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_access_token(user.id)
    return AuthResponse(
        token=token,
        user={"id": user.id, "email": user.email, "full_name": user.full_name},
    )


@api.post("/auth/login", response_model=AuthResponse)
@limiter.limit("10/minute")
def login(request: Request, req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == req.email).first()
    # Always run bcrypt — prevents email enumeration via response-time difference
    candidate_hash = user.password_hash if user else _DUMMY_HASH
    password_ok = verify_password(req.password, candidate_hash)
    if not user or not password_ok:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token(user.id)
    return AuthResponse(
        token=token,
        user={"id": user.id, "email": user.email, "full_name": user.full_name},
    )


@api.get("/auth/me")
def get_me(current_user: User = Depends(get_current_user)):
    return {"id": current_user.id, "email": current_user.email, "full_name": current_user.full_name}


@api.post("/auth/forgot-password", status_code=200)
@limiter.limit("5/minute")
def forgot_password(request: Request, req: ForgotPasswordRequest, db: Session = Depends(get_db)):
    """
    Generate a password reset token and email a reset link.
    Always returns 200 — never reveals whether the email exists (prevents enumeration).
    """
    import secrets
    from email_service import EmailConfig, EmailPayload, send_email

    user = db.query(User).filter(User.email == req.email).first()
    if user:
        # Invalidate any existing unused tokens for this user
        db.query(PasswordResetToken).filter(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.used == False,
        ).update({"used": True})

        token = secrets.token_urlsafe(32)
        expires_at = datetime.utcnow() + timedelta(hours=1)
        reset_token = PasswordResetToken(
            user_id=user.id,
            token=token,
            expires_at=expires_at,
        )
        db.add(reset_token)
        db.commit()

        frontend_url = os.environ.get("FRONTEND_URL", "https://crm.justinmikkelsen.com").rstrip("/")
        reset_link = f"{frontend_url}/reset-password?token={token}"

        body = (
            f"Hi{' ' + user.full_name if user.full_name else ''},\n\n"
            f"We received a request to reset your Leverage CRM password.\n\n"
            f"Click the link below to set a new password. This link expires in 1 hour.\n\n"
            f"{reset_link}\n\n"
            f"If you didn't request this, you can ignore this email — your password won't change."
        )

        # System email — always send live via Resend regardless of user's test mode setting.
        # Use the requesting user's email settings if available; fall back to the org
        # owner's settings (the member who has Resend configured).
        cfg_row = db.query(EmailSettings).filter(EmailSettings.owner_user_id == user.id).first()
        if not cfg_row or not cfg_row.from_email:
            owner_member = db.query(OrganizationMember).filter(
                OrganizationMember.role == "owner"
            ).first()
            if owner_member:
                cfg_row = db.query(EmailSettings).filter(
                    EmailSettings.owner_user_id == owner_member.user_id
                ).first()

        from_email = (
            os.environ.get("RESET_FROM_EMAIL")
            or (cfg_row.from_email if cfg_row else None)
            or os.environ.get("DEFAULT_FROM_EMAIL")
        )
        from_name = (cfg_row.from_name if cfg_row else None) or "Leverage CRM"

        email_cfg = EmailConfig(
            provider="resend",
            from_email=from_email,
            from_name=from_name,
            reply_to_email=None,
            signature=None,
            test_mode_enabled=False,  # always deliver system emails
        )

        send_email(
            EmailPayload(
                to_address=user.email,
                subject="Reset your Leverage CRM password",
                body=body,
            ),
            config=email_cfg,
        )

        logger.info("Password reset email sent | user_id=%s", user.id)

    return {"message": "If that email is registered, a reset link has been sent."}


@api.post("/auth/reset-password", status_code=200)
@limiter.limit("10/minute")
def reset_password(request: Request, req: ResetPasswordRequest, db: Session = Depends(get_db)):
    """Validate a reset token and update the user's password."""
    reset_token = db.query(PasswordResetToken).filter(
        PasswordResetToken.token == req.token,
        PasswordResetToken.used == False,
    ).first()

    if not reset_token or reset_token.expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Reset link is invalid or has expired.")

    user = db.query(User).filter(User.id == reset_token.user_id).first()
    if not user:
        raise HTTPException(status_code=400, detail="Reset link is invalid or has expired.")

    user.password_hash = hash_password(req.new_password)
    reset_token.used = True
    db.commit()

    logger.info("Password reset completed | user_id=%s", user.id)
    return {"message": "Password updated. You can now sign in."}


# ─── Segments ───────────────────────────────────────────────────────────────

@api.get("/segments")
def list_segments(
    include_inactive: bool = False,
    org: OrgContext = Depends(get_current_org),
    db: Session = Depends(get_db),
):
    q = db.query(Segment).filter(Segment.organization_id == org.id)
    if not include_inactive:
        from sqlalchemy import true
        q = q.filter(Segment.is_active == true())
    segments = q.order_by(Segment.sort_order.asc(), Segment.label.asc()).all()
    return [segment_to_dict(s) for s in segments]


@api.post("/segments", status_code=201)
def create_segment(
    req: SegmentCreate,
    org: OrgContext = Depends(get_current_org),
    db: Session = Depends(get_db),
):
    key = req.key.strip().lower()
    label = req.label.strip()

    if not key:
        raise HTTPException(status_code=400, detail="Segment key is required")
    if not label:
        raise HTTPException(status_code=400, detail="Segment label is required")

    existing = db.query(Segment).filter(
        Segment.organization_id == org.id,
        Segment.key == key,
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Segment key already exists")

    segment = Segment(
        owner_user_id=org.user_id,
        organization_id=org.id,
        key=key,
        label=label,
        sort_order=req.sort_order or 0,
        is_active=True if req.is_active is None else req.is_active,
    )
    db.add(segment)
    db.commit()
    db.refresh(segment)
    return segment_to_dict(segment)


@api.put("/segments/{segment_id}")
def update_segment(
    segment_id: str,
    req: SegmentUpdate,
    org: OrgContext = Depends(get_current_org),
    db: Session = Depends(get_db),
):
    segment = db.query(Segment).filter(
        Segment.id == segment_id,
        Segment.organization_id == org.id,
    ).first()
    if not segment:
        raise HTTPException(status_code=404, detail="Segment not found")

    updates = req.model_dump(exclude_unset=True)

    if "key" in updates and updates["key"] is not None:
        updates["key"] = updates["key"].strip().lower()
        if not updates["key"]:
            raise HTTPException(status_code=400, detail="Segment key cannot be empty")

        existing = db.query(Segment).filter(
            Segment.organization_id == org.id,
            Segment.key == updates["key"],
            Segment.id != segment.id,
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail="Segment key already exists")

    if "label" in updates and updates["label"] is not None:
        updates["label"] = updates["label"].strip()
        if not updates["label"]:
            raise HTTPException(status_code=400, detail="Segment label cannot be empty")

    for k, v in updates.items():
        setattr(segment, k, v)

    db.commit()
    db.refresh(segment)
    return segment_to_dict(segment)

# ─── Lead CRUD ───────────────────────────────────────────────────────────────

@api.get("/leads")
def list_leads(
    search: Optional[str] = None,
    status: Optional[str] = None,
    priority: Optional[str] = None,
    segment_id: Optional[str] = None,
    tag: Optional[str] = None,
    sort_by: Optional[str] = "total_score",
    sort_dir: Optional[str] = "desc",
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    org: OrgContext = Depends(get_current_org),
    db: Session = Depends(get_db),
):
    q = db.query(Lead).filter(Lead.organization_id == org.id)

    if search:
        search_lower = f"%{search.lower()}%"
        q = q.filter(
            (func.lower(Lead.full_name).like(search_lower))
            | (func.lower(Lead.business_name).like(search_lower))
            | (func.lower(Lead.email).like(search_lower))
        )
    if status:
        q = q.filter(Lead.status == status)
    if priority:
        q = q.filter(Lead.priority_tier == priority)
    if segment_id:
        q = q.filter(Lead.segment_id == segment_id)
    if tag:
        # JSON-encoded array stored as text — match with a JSON-safe substring
        q = q.filter(Lead.tags.like(f'%"{tag.strip().lower()}"%'))

    # Sorting
    sort_col = None
    if sort_by == "total_score":
        sort_col = Lead.total_score
    elif sort_by == "next_follow_up_at":
        sort_col = Lead.next_follow_up_at
    elif sort_by == "created_at":
        sort_col = Lead.created_at
    elif sort_by == "last_contacted_at":
        sort_col = Lead.last_contacted_at
    elif sort_by == "status":
        # Pipeline order — NEW first, LOST/NURTURE last (SQLite + Postgres safe)
        status_order = case(
            {s: i for i, s in enumerate(PIPELINE_ORDER)},
            value=Lead.status,
            else_=len(PIPELINE_ORDER),
        )
        q = q.order_by(status_order.asc()) if sort_dir == "asc" else q.order_by(status_order.desc())
        total = q.count()
        leads = q.offset((page - 1) * page_size).limit(page_size).all()
        return {"total": total, "page": page, "page_size": page_size, "items": [lead_to_dict(l) for l in leads]}
    elif sort_by == "niche":
        sort_col = Lead.niche
    elif sort_by == "full_name":
        sort_col = Lead.full_name
    else:
        sort_col = Lead.total_score

    if sort_dir == "asc":
        q = q.order_by(sort_col.asc().nulls_last())
    else:
        q = q.order_by(sort_col.desc().nulls_last())

    total = q.count()
    leads = q.offset((page - 1) * page_size).limit(page_size).all()
    return {"total": total, "page": page, "page_size": page_size, "items": [lead_to_dict(l) for l in leads]}


@api.post("/leads", status_code=201)
def create_lead(req: LeadCreate, org: OrgContext = Depends(get_current_org), db: Session = Depends(get_db)):
    payload = req.model_dump()
    payload.pop("segment", None)
    segment_id = payload.pop("segment_id", None)
    lead_tags = encode_tags(payload.pop("tags", None))

    lead = Lead(
        owner_user_id=org.user_id,
        organization_id=org.id,
        **{k: v for k, v in payload.items() if v is not None},
    )
    if lead_tags:
        lead.tags = lead_tags

    if segment_id:
        segment = db.query(Segment).filter(
            Segment.id == segment_id,
            Segment.organization_id == org.id,
        ).first()
        if not segment:
            raise HTTPException(status_code=400, detail="Invalid segment_id")
        lead.segment_id = segment.id
        lead.segment = legacy_segment_or_none(segment.key)

    if not lead.full_name and (lead.first_name or lead.last_name):
        lead.full_name = f"{lead.first_name or ''} {lead.last_name or ''}".strip()

    recalculate_scores(lead)
    db.add(lead)
    db.commit()
    db.refresh(lead)
    return lead_to_dict(lead)


@api.get("/leads/{lead_id}")
def get_lead(lead_id: str, org: OrgContext = Depends(get_current_org), db: Session = Depends(get_db)):
    lead = db.query(Lead).filter(Lead.id == lead_id, Lead.organization_id == org.id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return lead_to_dict(lead)


@api.put("/leads/{lead_id}")
def update_lead(lead_id: str, req: LeadUpdate, org: OrgContext = Depends(get_current_org), db: Session = Depends(get_db)):
    lead = db.query(Lead).filter(Lead.id == lead_id, Lead.organization_id == org.id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    updates.pop("segment", None)
    segment_id = updates.pop("segment_id", None)

    # tags: list/str input → normalized JSON; empty list clears the set
    if "tags" in updates:
        updates["tags"] = encode_tags(updates.pop("tags"))

    # do_not_contact is a boolean — must be handled separately since False is falsy
    if req.do_not_contact is not None:
        lead.do_not_contact = req.do_not_contact
    updates.pop("do_not_contact", None)

    for k, v in updates.items():
        setattr(lead, k, v)

    if segment_id:
        segment = db.query(Segment).filter(
            Segment.id == segment_id,
            Segment.organization_id == org.id,
        ).first()
        if not segment:
            raise HTTPException(status_code=400, detail="Invalid segment_id")
        lead.segment_id = segment.id
        lead.segment = legacy_segment_or_none(segment.key)

    if lead.first_name or lead.last_name:
        lead.full_name = f"{lead.first_name or ''} {lead.last_name or ''}".strip()

    score_fields = {
        "offer_clarity_score", "bottleneck_evidence_score", "buying_signal_score",
        "decision_maker_access_score", "contactability_score", "strategic_fit_score",
    }
    if score_fields & updates.keys():
        recalculate_scores(lead)

    db.commit()
    db.refresh(lead)
    return lead_to_dict(lead)


@api.delete("/leads/{lead_id}")
def delete_lead(lead_id: str, org: OrgContext = Depends(get_current_org), db: Session = Depends(get_db)):
    lead = db.query(Lead).filter(Lead.id == lead_id, Lead.organization_id == org.id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    db.query(Activity).filter(Activity.lead_id == lead_id).delete()
    db.delete(lead)
    db.commit()
    return {"status": "deleted"}


# ─── Status Transition ───────────────────────────────────────────────────────

VALID_STATUSES = {"NEW", "SCORED", "READY_TO_CONTACT", "CONTACTED", "FOLLOW_UP_1", "FOLLOW_UP_2", "REPLIED", "CALL_BOOKED", "WON", "CLIENT", "LOST", "NURTURE"}


@api.post("/leads/{lead_id}/status")
def change_status(lead_id: str, req: StatusChangeRequest, org: OrgContext = Depends(get_current_org), db: Session = Depends(get_db)):
    if req.status not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid status: {req.status}")

    lead = db.query(Lead).filter(Lead.id == lead_id, Lead.organization_id == org.id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    old_status = lead.status
    activity_body = apply_status_transition(lead, req.status)

    # Write activity
    activity = Activity(
        lead_id=lead.id,
        user_id=org.user_id,
        organization_id=org.id,
        activity_type="STATUS_CHANGE",
        body=activity_body,
    )
    db.add(activity)
    db.commit()
    db.refresh(lead)
    return lead_to_dict(lead)


@api.post("/leads/bulk-status")
def bulk_status_change(req: BulkStatusChange, org: OrgContext = Depends(get_current_org), db: Session = Depends(get_db)):
    if req.status not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid status: {req.status}")

    leads = db.query(Lead).filter(
        Lead.id.in_(req.lead_ids),
        Lead.organization_id == org.id,
    ).all()

    now = datetime.utcnow()
    for lead in leads:
        activity_body = apply_status_transition(lead, req.status, now=now)
        db.add(Activity(
            lead_id=lead.id,
            user_id=org.user_id,
            organization_id=org.id,
            activity_type="STATUS_CHANGE",
            body=activity_body,
            occurred_at=now,
        ))

    db.commit()
    return {"updated": len(leads)}

@api.post("/leads/bulk-segment")
def bulk_segment_change(req: BulkSegmentChange, org: OrgContext = Depends(get_current_org), db: Session = Depends(get_db)):
    segment = db.query(Segment).filter(
        Segment.id == req.segment_id,
        Segment.organization_id == org.id,
    ).first()
    if not segment:
        raise HTTPException(status_code=400, detail="Invalid segment_id")

    leads = db.query(Lead).filter(
        Lead.id.in_(req.lead_ids),
        Lead.organization_id == org.id,
    ).all()

    for lead in leads:
        lead.segment_id = segment.id
        lead.segment = legacy_segment_or_none(segment.key)

    db.commit()
    return {"updated": len(leads)}


@api.post("/leads/bulk-tags")
def bulk_tag_change(req: BulkTagChange, org: OrgContext = Depends(get_current_org), db: Session = Depends(get_db)):
    if req.mode not in {"add", "remove", "set"}:
        raise HTTPException(status_code=400, detail=f"Invalid mode: {req.mode}")

    tags = normalize_tags(req.tags)
    if req.mode in {"add", "set"} and not tags:
        raise HTTPException(status_code=400, detail="No valid tags provided")

    leads = db.query(Lead).filter(
        Lead.id.in_(req.lead_ids),
        Lead.organization_id == org.id,
    ).all()

    for lead in leads:
        current = decode_tags(lead.tags)
        if req.mode == "add":
            merged = current + [t for t in tags if t not in current]
        elif req.mode == "remove":
            merged = [t for t in current if t not in tags]
        else:  # set
            merged = tags
        lead.tags = json.dumps(merged) if merged else None

    db.commit()
    return {"updated": len(leads)}


@api.get("/leads-tags")
def list_lead_tags(org: OrgContext = Depends(get_current_org), db: Session = Depends(get_db)):
    """All distinct tags in use across the org — powers filter dropdowns and autocomplete."""
    rows = db.query(Lead.tags).filter(
        Lead.organization_id == org.id,
        Lead.tags.isnot(None),
    ).all()
    out: list[str] = []
    for (raw,) in rows:
        for tag in decode_tags(raw):
            if tag not in out:
                out.append(tag)
    return {"tags": sorted(out)}


# ─── Activities ──────────────────────────────────────────────────────────────

VALID_ACTIVITY_TYPES = {"NOTE", "STATUS_CHANGE", "OUTREACH_SENT", "TEST_EMAIL_SENT", "FOLLOW_UP_SENT", "REPLY_RECEIVED", "CALL_BOOKED", "OTHER"}


@api.get("/leads/{lead_id}/activities")
def list_activities(lead_id: str, org: OrgContext = Depends(get_current_org), db: Session = Depends(get_db)):
    lead = db.query(Lead).filter(Lead.id == lead_id, Lead.organization_id == org.id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    activities = db.query(Activity).filter(Activity.lead_id == lead_id).order_by(Activity.occurred_at.desc()).all()
    return [activity_to_dict(a) for a in activities]


@api.post("/leads/{lead_id}/activities", status_code=201)
def create_activity(lead_id: str, req: ActivityCreate, org: OrgContext = Depends(get_current_org), db: Session = Depends(get_db)):
    if req.activity_type not in VALID_ACTIVITY_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid activity type: {req.activity_type}")

    lead = db.query(Lead).filter(Lead.id == lead_id, Lead.organization_id == org.id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    activity = Activity(
        lead_id=lead.id,
        user_id=org.user_id,
        organization_id=org.id,
        activity_type=req.activity_type,
        body=req.body,
        occurred_at=req.occurred_at or datetime.utcnow(),
    )
    db.add(activity)
    db.commit()
    db.refresh(activity)
    return activity_to_dict(activity)


@api.put("/leads/{lead_id}/activities/{activity_id}")
def update_activity(lead_id: str, activity_id: str, req: ActivityUpdate, org: OrgContext = Depends(get_current_org), db: Session = Depends(get_db)):
    lead = db.query(Lead).filter(Lead.id == lead_id, Lead.organization_id == org.id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    activity = db.query(Activity).filter(Activity.id == activity_id, Activity.lead_id == lead_id).first()
    if not activity:
        raise HTTPException(status_code=404, detail="Note not found")
    if activity.activity_type != "NOTE":
        raise HTTPException(status_code=400, detail="Only NOTE activities can be edited")
    activity.body = req.body
    db.commit()
    db.refresh(activity)
    return activity_to_dict(activity)


@api.delete("/leads/{lead_id}/activities/{activity_id}")
def delete_activity(lead_id: str, activity_id: str, org: OrgContext = Depends(get_current_org), db: Session = Depends(get_db)):
    lead = db.query(Lead).filter(Lead.id == lead_id, Lead.organization_id == org.id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    activity = db.query(Activity).filter(Activity.id == activity_id, Activity.lead_id == lead_id).first()
    if not activity:
        raise HTTPException(status_code=404, detail="Note not found")
    if activity.activity_type != "NOTE":
        raise HTTPException(status_code=400, detail="Only NOTE activities can be deleted")
    db.delete(activity)
    db.commit()
    return {"status": "deleted"}


# ─── Email Settings ──────────────────────────────────────────────────────────

@api.get("/email-settings")
def get_email_settings(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Return the current user's email config. Returns defaults if not yet saved."""
    s = db.query(EmailSettings).filter(EmailSettings.owner_user_id == current_user.id).first()
    if not s:
        return {"id": None, "provider": None, "from_email": None, "from_name": None,
                "reply_to_email": None, "phone": None, "signature": None, "test_mode_enabled": True, "updated_at": None}
    return email_settings_to_dict(s)


@api.put("/email-settings")
def upsert_email_settings(req: EmailSettingsUpdate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Create or update the current user's email config (upsert)."""
    s = db.query(EmailSettings).filter(EmailSettings.owner_user_id == current_user.id).first()
    if not s:
        s = EmailSettings(owner_user_id=current_user.id)
        db.add(s)
    if req.provider is not None:
        s.provider = req.provider or None
    if req.from_email is not None:
        s.from_email = req.from_email or None
    if req.from_name is not None:
        s.from_name = req.from_name or None
    if req.reply_to_email is not None:
        s.reply_to_email = req.reply_to_email or None
    if req.phone is not None:
        s.phone = req.phone or None
    if req.signature is not None:
        s.signature = req.signature or None
    if req.test_mode_enabled is not None:
        s.test_mode_enabled = req.test_mode_enabled
    db.commit()
    db.refresh(s)
    return email_settings_to_dict(s)


# ─── Variable Rendering Preview ──────────────────────────────────────────────

class EmailRenderPreviewRequest(BaseModel):
    subject: Optional[str] = None
    body: Optional[str] = None
    signature: Optional[str] = None
    lead_id: Optional[str] = None            # render against a real lead's context
    use_sample_lead: bool = True             # when no lead_id: fill lead vars with sample data


@api.post("/email/render-preview")
def render_email_preview(
    req: EmailRenderPreviewRequest,
    org: OrgContext = Depends(get_current_org),
    db: Session = Depends(get_db),
):
    """
    Render template variables in subject/body/signature exactly as the send
    route will, and report which variables are unsupported or resolved empty.

    Used by the composer/template editor for live previews and by the variable
    picker to validate content before sending. Never sends anything.
    """
    from email_variables import (  # deferred import
        SAMPLE_LEAD_CONTEXT,
        VariableContext,
        build_context,
        render_variables,
        sender_context_from_settings,
        supported_variables_help,
    )

    cfg = db.query(EmailSettings).filter(EmailSettings.owner_user_id == org.user_id).first()

    lead = None
    if req.lead_id:
        lead = db.query(Lead).filter(
            Lead.id == req.lead_id, Lead.organization_id == org.id
        ).first()
        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found")

    if lead is not None:
        ctx = build_context(settings=cfg, lead=lead)
    elif req.use_sample_lead:
        sender = sender_context_from_settings(cfg)
        ctx = VariableContext(**{**sender, **SAMPLE_LEAD_CONTEXT})
    else:
        ctx = build_context(settings=cfg, lead=None)

    result: dict = {"subject": "", "body": "", "signature": None,
                    "used_variables": [], "missing_variables": [], "unknown_variables": []}
    used: set[str] = set()
    missing: set[str] = set()
    unknown: set[str] = set()

    for field_name in ("subject", "body", "signature"):
        text = getattr(req, field_name)
        if text is None:
            continue
        r = render_variables(text, ctx)
        result[field_name] = r.text
        used.update(r.used_variables)
        missing.update(r.missing_variables)
        unknown.update(r.unknown_variables)

    result["used_variables"] = sorted(used)
    result["missing_variables"] = sorted(missing)
    result["unknown_variables"] = sorted(unknown)
    return result


# ─── Email Templates ─────────────────────────────────────────────────────────

@api.get("/email-templates")
def list_email_templates(org: OrgContext = Depends(get_current_org), db: Session = Depends(get_db)):
    templates = db.query(EmailTemplate).filter(
        EmailTemplate.organization_id == org.id
    ).order_by(EmailTemplate.created_at.asc()).all()
    return [template_to_dict(t) for t in templates]


@api.post("/email-templates", status_code=201)
def create_email_template(req: EmailTemplateCreate, org: OrgContext = Depends(get_current_org), db: Session = Depends(get_db)):
    t = EmailTemplate(
        owner_user_id=org.user_id,
        organization_id=org.id,
        name=req.name,
        subject=req.subject,
        body=req.body,
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return template_to_dict(t)


@api.put("/email-templates/{template_id}")
def update_email_template(template_id: str, req: EmailTemplateUpdate, org: OrgContext = Depends(get_current_org), db: Session = Depends(get_db)):
    t = db.query(EmailTemplate).filter(
        EmailTemplate.id == template_id,
        EmailTemplate.organization_id == org.id,
    ).first()
    if not t:
        raise HTTPException(status_code=404, detail="Template not found")
    if req.name is not None:
        t.name = req.name
    if req.subject is not None:
        t.subject = req.subject
    if req.body is not None:
        t.body = req.body
    db.commit()
    db.refresh(t)
    return template_to_dict(t)


@api.delete("/email-templates/{template_id}")
def delete_email_template(template_id: str, org: OrgContext = Depends(get_current_org), db: Session = Depends(get_db)):
    t = db.query(EmailTemplate).filter(
        EmailTemplate.id == template_id,
        EmailTemplate.organization_id == org.id,
    ).first()
    if not t:
        raise HTTPException(status_code=404, detail="Template not found")
    db.delete(t)
    db.commit()
    return {"status": "deleted"}


# ─── Email ───────────────────────────────────────────────────────────────────

@api.post("/leads/{lead_id}/email", status_code=201)
@limiter.limit("20/minute")
def send_lead_email(
    request: Request,
    lead_id: str,
    req: EmailSendRequest,
    org: OrgContext = Depends(get_current_org),
    db: Session = Depends(get_db),
):
    """
    Compose and send an email to a lead, then log it as an OUTREACH_SENT activity.

    STUB: send_email() raises NotImplementedError until a provider is configured.
    The activity log is only written on successful send.
    """
    lead = db.query(Lead).filter(Lead.id == lead_id, Lead.organization_id == org.id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    # Do Not Contact guard — must be checked before any send attempt
    if lead.do_not_contact:
        logger.warning(
            "DNC_BLOCKED lead_id=%s user_id=%s recipient=%s",
            lead.id,
            org.user_id,
            req.to_address or lead.email or "<no address>",
        )
        raise HTTPException(
            status_code=451,  # 451 Unavailable For Legal Reasons — semantically correct for DNC
            detail="This lead is marked Do Not Contact. Email send blocked.",
        )


    from email_variables import supported_variables_help  # deferred import

    recipient = req.to_address or lead.email
    if not recipient:
        raise HTTPException(status_code=400, detail="No recipient address — set to_address or add an email to the lead")

    # Load caller's email config (user-owned — each member sends as themselves)
    cfg = db.query(EmailSettings).filter(EmailSettings.owner_user_id == org.user_id).first()

    from email_service import EmailConfig, EmailPayload, send_email  # deferred import
    from email_variables import build_context, render_variables, supported_variables_help

    # ── Authoritative variable rendering (backend is the single source of truth) ──
    # Applied to subject AND body regardless of how content was composed
    # (manually typed, from a saved template, or with the variable picker).
    ctx = build_context(settings=cfg, lead=lead)
    rendered_subject = render_variables(req.subject, ctx)
    rendered_body = render_variables(req.body, ctx)

    # Reject unsupported variables — they would ship literal {{tokens}} to the
    # provider. Strict allowlist; nothing dynamic is ever evaluated.
    unknown_all = rendered_subject.unknown_variables + rendered_body.unknown_variables
    if unknown_all:
        logger.warning(
            "Email send rejected: unsupported variables | lead_id=%s user_id=%s unknown=%s",
            lead.id, org.user_id, unknown_all,
        )
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported template variable(s): "
                f"{', '.join('{{ ' + v + ' }}' for v in sorted(set(unknown_all)))}. "
                f"Supported: {supported_variables_help()}. "
                "Use the 'Insert variable' picker to add valid ones."
            ),
        )

    # Warn (don't block) when a supported variable resolved to empty — e.g.
    # {{lead_phone}} used but the lead has no phone on file.
    empty_warnings = sorted(set(rendered_subject.missing_variables) | set(rendered_body.missing_variables))

    email_cfg = EmailConfig(
        provider=cfg.provider if cfg else None,
        from_email=cfg.from_email if cfg else None,
        from_name=cfg.from_name if cfg else None,
        reply_to_email=cfg.reply_to_email if cfg else None,
        # Render the signature with the same full context (sender + lead) so
        # variables in signatures resolve per-lead; send_email only appends it.
        signature=render_variables(cfg.signature, ctx).text if (cfg and cfg.signature) else None,
        test_mode_enabled=cfg.test_mode_enabled if cfg else True,
    )

    try:
        result = send_email(EmailPayload(
            to_address=recipient,
            subject=rendered_subject.text,
            body=rendered_body.text,
        ), config=email_cfg)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Email error: {exc}")

    if not result.success:
        raise HTTPException(status_code=502, detail=result.error or "Email send failed")

    # Log the send as an activity — ONLY after the provider confirmed success.
    # The log stores the RENDERED content (exactly what the provider received),
    # the recipient address, the sending user, and the server-side timestamp.
    # Test-mode (simulated) sends get their own activity type so they are never
    # mistaken for real outreach; the body keeps an explicit banner as well.
    rendered_body_text = rendered_body.text
    if result.simulated:
        activity_body = (
            f"[TEST MODE — not delivered]\n"
            f"To: {recipient}\n"
            f"Subject: {rendered_subject.text}\n\n"
            f"{rendered_body_text}"
        )
        activity_type = "TEST_EMAIL_SENT"
    else:
        activity_body = (
            f"To: {recipient}\n"
            f"Subject: {rendered_subject.text}\n\n"
            f"{rendered_body_text}"
        )
        activity_type = "OUTREACH_SENT"
    activity = Activity(
        lead_id=lead.id,
        user_id=org.user_id,
        organization_id=org.id,
        activity_type=activity_type,
        body=activity_body,
        occurred_at=datetime.utcnow(),
    )
    db.add(activity)
    db.commit()
    db.refresh(activity)
    resp = activity_to_dict(activity)
    resp["simulated"] = result.simulated  # surface to frontend
    if empty_warnings:
        resp["missing_variables"] = empty_warnings  # e.g. ["lead_phone"] → blank in message
    return resp


# ─── Org Member Management ───────────────────────────────────────────────────

@api.get("/org/members")
def list_org_members(
    org: OrgContext = Depends(get_current_org),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(OrganizationMember, User)
        .join(User, User.id == OrganizationMember.user_id)
        .filter(OrganizationMember.organization_id == org.id)
        .order_by(OrganizationMember.created_at.asc())
        .all()
    )
    return [
        {
            "user_id": m.user_id,
            "email": u.email,
            "full_name": u.full_name,
            "role": m.role,
            "created_at": m.created_at.isoformat() if m.created_at else None,
            "is_self": m.user_id == org.user_id,
        }
        for m, u in rows
    ]


@api.post("/org/members", status_code=201)
def add_org_member(
    req: OrgMemberAdd,
    org: OrgContext = Depends(get_current_org),
    db: Session = Depends(get_db),
):
    if org.role != "owner":
        raise HTTPException(status_code=403, detail="Only owners can manage members")
    if req.role not in ("owner", "member"):
        raise HTTPException(status_code=400, detail="role must be 'owner' or 'member'")

    email = req.email.strip().lower()
    user = db.query(User).filter(User.email == email).first()
    temp_password = None
    if not user:
        import secrets as _secrets
        raw = req.password or _secrets.token_urlsafe(12)
        temp_password = None if req.password else raw
        user = User(
            email=email,
            password_hash=hash_password(raw),
            full_name=req.full_name,
        )
        db.add(user)
        db.flush()

    existing = db.query(OrganizationMember).filter(
        OrganizationMember.organization_id == org.id,
        OrganizationMember.user_id == user.id,
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"{email} is already a member")

    db.add(OrganizationMember(
        organization_id=org.id,
        user_id=user.id,
        role=req.role,
    ))
    db.commit()
    return {
        "user_id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "role": req.role,
        "temp_password": temp_password,
        "is_self": False,
    }


@api.patch("/org/members/{user_id}")
def update_org_member_role(
    user_id: str,
    req: OrgMemberRoleUpdate,
    org: OrgContext = Depends(get_current_org),
    db: Session = Depends(get_db),
):
    if org.role != "owner":
        raise HTTPException(status_code=403, detail="Only owners can manage members")
    if req.role not in ("owner", "member"):
        raise HTTPException(status_code=400, detail="role must be 'owner' or 'member'")
    if user_id == org.user_id:
        raise HTTPException(status_code=400, detail="Cannot change your own role")
    membership = db.query(OrganizationMember).filter(
        OrganizationMember.organization_id == org.id,
        OrganizationMember.user_id == user_id,
    ).first()
    if not membership:
        raise HTTPException(status_code=404, detail="Member not found")
    membership.role = req.role
    db.commit()
    return {"user_id": user_id, "role": req.role}


@api.delete("/org/members/{user_id}")
def remove_org_member(
    user_id: str,
    org: OrgContext = Depends(get_current_org),
    db: Session = Depends(get_db),
):
    if org.role != "owner":
        raise HTTPException(status_code=403, detail="Only owners can manage members")
    if user_id == org.user_id:
        raise HTTPException(status_code=400, detail="Cannot remove yourself")
    membership = db.query(OrganizationMember).filter(
        OrganizationMember.organization_id == org.id,
        OrganizationMember.user_id == user_id,
    ).first()
    if not membership:
        raise HTTPException(status_code=404, detail="Member not found")
    db.delete(membership)
    db.commit()
    return {"status": "removed"}


# ─── Dashboard Metrics ───────────────────────────────────────────────────────

@api.get("/dashboard")
def dashboard(org: OrgContext = Depends(get_current_org), db: Session = Depends(get_db)):
    now = datetime.utcnow()
    week_ago = now - timedelta(days=7)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    base = db.query(Lead).filter(Lead.organization_id == org.id)

    leads_contacted_week = base.filter(
        Lead.last_contacted_at >= week_ago,
        Lead.status.in_(["CONTACTED", "FOLLOW_UP_1", "FOLLOW_UP_2", "REPLIED", "CALL_BOOKED", "WON"]),
    ).count()

    # Shared metrics — count across the whole organization, not just this member
    replies_week = db.query(Activity).filter(
        Activity.organization_id == org.id,
        Activity.activity_type == "REPLY_RECEIVED",
        Activity.occurred_at >= week_ago,
    ).count()

    calls_booked_week = db.query(Activity).filter(
        Activity.organization_id == org.id,
        Activity.activity_type == "CALL_BOOKED",
        Activity.occurred_at >= week_ago,
    ).count()

    wins_month = base.filter(
        Lead.status.in_(["WON", "CLIENT"]),
        Lead.updated_at >= month_start,
    ).count()

    follow_ups_due = base.filter(
        Lead.next_follow_up_at >= today_start,
        Lead.next_follow_up_at < now,
    ).all()

    overdue = base.filter(
        Lead.next_follow_up_at < today_start,
    ).all()

    return {
        "leads_contacted_week": leads_contacted_week,
        "replies_week": replies_week,
        "calls_booked_week": calls_booked_week,
        "wins_month": wins_month,
        "follow_ups_due_today": [lead_to_dict(l) for l in follow_ups_due],
        "overdue_follow_ups": [lead_to_dict(l) for l in overdue],
    }


# ─── CSV Import ──────────────────────────────────────────────────────────────

CSV_FIELD_MAP = {
    "first_name": "first_name",
    "last_name": "last_name",
    "full_name": "full_name",
    "business_name": "business_name",
    "company": "business_name",
    "segment": "segment",
    "niche": "niche",
    "website_url": "website_url",
    "website": "website_url",
    "email": "email",
    "phone": "phone",
    "contact_path": "contact_path",
    "linkedin_url": "linkedin_url",
    "linkedin": "linkedin_url",
    "location_text": "location_text",
    "location": "location_text",
    "team_size_estimate": "team_size_estimate",
    "team_size": "team_size_estimate",
    "source_url": "source_url",
    "personalization_note": "personalization_note",
    "outreach_angle": "outreach_angle",
    "tags": "_tags",
}

# Enum field mappings
ENUM_FIELDS = {
    "segment": ["COACH", "CONSULTANT", "SOLOPRENEUR", "OTHER"],
    "contact_path": ["EMAIL", "FORM", "DM", "OTHER"],
    "status": [
        "NEW",
        "SCORED",
        "READY_TO_CONTACT",
        "CONTACTED",
        "FOLLOW_UP_1",
        "FOLLOW_UP_2",
        "REPLIED",
        "CALL_BOOKED",
        "WON",
        "CLIENT",
        "LOST",
        "NURTURE",
    ],
    "priority_tier": ["A", "B", "C"],
}


def normalize_enum_value(field_name: str, value: str) -> str:
    """Normalize enum values to match database requirements."""
    if not value or field_name not in ENUM_FIELDS:
        return value

    raw = str(value).strip()
    if raw == "":
        return value

    valid_values = ENUM_FIELDS[field_name]

    # Phrase-aware mapping for human CSV contact-path values.
    # DB contact_path enum values are: EMAIL, FORM, DM, OTHER.
    if field_name == "contact_path":
        lowered = raw.lower()

        if any(token in lowered for token in [
            "contact form",
            "form",
            "website",
            "web site",
            "site form",
        ]):
            return "FORM"

        if any(token in lowered for token in [
            "email",
            "e-mail",
            "mail",
            "phone listed",
            "phone",
            "contact page",
        ]):
            return "EMAIL"

        if any(token in lowered for token in [
            "dm",
            "direct message",
            "instagram",
            "linkedin",
            "twitter",
            "x.com",
            "facebook",
            "social",
        ]):
            return "DM"

        return "OTHER"

    # Phrase-aware mapping for segment values.
    # DB lead_segment enum values are: COACH, CONSULTANT, SOLOPRENEUR, OTHER.
    if field_name == "segment":
        lowered = raw.lower()

        if "coach" in lowered:
            return "COACH"

        if "consult" in lowered:
            return "CONSULTANT"

        if any(token in lowered for token in [
            "solo",
            "solopreneur",
            "one person",
            "independent",
        ]):
            return "SOLOPRENEUR"

        return "OTHER"

    normalized = raw.upper().replace(" ", "_").replace("-", "_").replace("/", "_")

    if normalized in valid_values:
        return normalized

    clean = normalized.replace("_", "")
    for valid_value in valid_values:
        if clean == valid_value.replace("_", ""):
            return valid_value

    raise ValueError(
        f"Invalid {field_name} value: {value!r}. "
        f"Expected one of: {', '.join(valid_values)}"
    )


@api.post("/import/csv")
async def import_csv(
    file: UploadFile = File(...),
    org: OrgContext = Depends(get_current_org),
    db: Session = Depends(get_db),
):
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files accepted")

    content = await file.read()
    text = content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))

    if not reader.fieldnames:
        raise HTTPException(status_code=400, detail="CSV has no headers")

    # Map CSV headers to lead fields
    header_map = {}
    for header in reader.fieldnames:
        clean = header.strip().lower().replace(" ", "_")
        if clean in CSV_FIELD_MAP:
            header_map[header] = CSV_FIELD_MAP[clean]

    accepted = 0
    rejected = 0
    errors = []
    duplicates = 0  # legacy endpoint: duplicates auto-skip (never silent double-insert)

    for i, row in enumerate(reader, start=2):
        try:
            lead_data = parse_csv_row(row, header_map)
            if find_existing_lead(db, org.id, lead_data, exclude_row_keys=set()):
                duplicates += 1
                continue

            lead = Lead(owner_user_id=org.user_id, organization_id=org.id, **lead_data)
            recalculate_scores(lead)
            db.add(lead)
            accepted += 1
        except Exception as e:
            rejected += 1
            errors.append({"row": i, "error": str(e)})

    db.commit()
    return {"accepted": accepted, "rejected": rejected, "duplicates_skipped": duplicates, "errors": errors[:20]}


# ─── CSV Import: preview + commit (duplicate handling) ──────────────────────

class ImportCommitRequest(BaseModel):
    batch: str  # batch token from /import/csv/preview
    actions: dict  # row_number -> "update" | "skip" | "merge" (missing rows default to "skip")


_IMPORT_BATCHES: dict = {}  # in-memory batch store (single-process deployment)


def parse_csv_row(row: dict, header_map: dict) -> dict:
    """Map one CSV row to lead model fields (shared by import paths)."""
    lead_data = {}
    for csv_col, model_field in header_map.items():
        val = (row.get(csv_col) or "").strip()
        if not val:
            continue
        if model_field == "team_size_estimate":
            raw_team_size = val.lower()
            if raw_team_size in {"", "unknown", "n/a", "na", "none", "null", "unsure", "not sure", "-"}:
                continue
            raw_team_size = raw_team_size.replace(" to ", "-")
            first_part = raw_team_size.split("-", 1)[0].strip()
            digits = ""
            for ch in first_part:
                if ch.isdigit():
                    digits += ch
                elif digits:
                    break
            if digits:
                lead_data[model_field] = int(digits)
        else:
            if model_field == "_tags":  # CSV tags column — handled separately
                lead_data["tags"] = val
                continue
            if model_field in ENUM_FIELDS:
                val = normalize_enum_value(model_field, val)
            lead_data[model_field] = val
    if not lead_data.get("full_name") and (lead_data.get("first_name") or lead_data.get("last_name")):
        lead_data["full_name"] = f"{lead_data.get('first_name', '')} {lead_data.get('last_name', '')}".strip()
    return lead_data


def _dup_key(lead_data: dict) -> tuple | None:
    """Primary unique-identifier key for duplicate detection."""
    email = (lead_data.get("email") or "").strip().lower() or None
    phone = re.sub(r"\D", "", lead_data.get("phone") or "") or None
    if email:
        return ("email", email)
    if phone:
        return ("phone", phone)
    return None


def _dup_keys(lead_data: dict) -> list[tuple]:
    """All identifier keys for a row — email first, then phone."""
    keys = []
    email = (lead_data.get("email") or "").strip().lower()
    phone = re.sub(r"\D", "", lead_data.get("phone") or "")
    if email:
        keys.append(("email", email))
    if phone:
        keys.append(("phone", phone))
    return keys


def find_existing_lead(db: Session, org_id: str, lead_data: dict, exclude_row_keys: set) -> Lead | None:
    """Find an org lead matching the row's email, else its (normalized) phone.
    Skips matching on keys already claimed by earlier rows in this import."""
    for kind, value in _dup_keys(lead_data):
        if (kind, value) in exclude_row_keys:
            continue
        q = db.query(Lead).filter(Lead.organization_id == org_id)
        if kind == "email":
            hit = q.filter(func.lower(Lead.email) == value).first()
        else:
            digits_expr = func.replace(
                func.replace(func.replace(func.replace(Lead.phone, " ", ""), "-", ""), "(", ""), ")", ""
            )
            hit = q.filter(digits_expr == value).first()
        if hit:
            return hit
    return None


def _merge_into(existing: Lead, incoming: dict) -> None:
    """Merge incoming CSV values into an existing lead (fill-blank wins).
    Blank/non-provided incoming values never overwrite existing data."""
    for field, value in incoming.items():
        if field in {"segment", "segment_id"}:
            continue
        current = getattr(existing, field, None)
        if current is None or (isinstance(current, str) and not current.strip()):
            setattr(existing, field, value)
    # Merge tags (union)
    merged = decode_tags(existing.tags)
    for tag in normalize_tags(incoming.get("tags")):
        if tag not in merged:
            merged.append(tag)
    existing.tags = json.dumps(merged) if merged else None


@api.post("/import/csv/preview")
async def import_csv_preview(
    file: UploadFile = File(...),
    org: OrgContext = Depends(get_current_org),
    db: Session = Depends(get_db),
):
    """Phase 1: parse the CSV, detect duplicates, return a reviewable batch.

    The batch (parsed rows + duplicate matches) is held in memory under a
    token; the client then POSTs per-row actions to /import/csv/commit.
    Rows without email AND phone are never treated as duplicates.
    """
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files accepted")

    content = await file.read()
    text = content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise HTTPException(status_code=400, detail="CSV has no headers")

    header_map = {}
    for header in reader.fieldnames:
        clean = header.strip().lower().replace(" ", "_")
        if clean in CSV_FIELD_MAP:
            header_map[header] = CSV_FIELD_MAP[clean]

    rows = []          # valid parsed rows
    errors = []        # unparseable rows
    claimed_keys = set()  # dup keys claimed by earlier rows in this same file
    seen_keys = set()     # dup keys appearing multiple times in the file itself

    for i, row in enumerate(reader, start=2):
        try:
            lead_data = parse_csv_row(row, header_map)
            row_tags = normalize_tags(lead_data.pop("tags", ""))
            key = _dup_key(lead_data)
            matched = find_existing_lead(db, org.id, lead_data, exclude_row_keys=claimed_keys)
            if key:
                claimed_keys.add(key)
                if matched is None and key in seen_keys:
                    # duplicate *within* the file — first occurrence stays new,
                    # later ones are flagged against the first row
                    first_row = next((r for r in rows if r.get("dup_key") == key), None)
                    matched = {"in_file": True, "first_row": first_row["row_number"]} if first_row else None
                seen_keys.add(key)
            rows.append({
                "row_number": i,
                "data": lead_data,
                "tags": row_tags,
                "dup_key": key,
                "duplicate_of": (
                    {"lead_id": matched.id, "full_name": matched.full_name, "email": matched.email, "phone": matched.phone}
                    if isinstance(matched, Lead)
                    else matched  # {"in_file": True, ...} or None
                ),
            })
        except Exception as e:
            errors.append({"row": i, "error": str(e)})

    token = uuid.uuid4().hex
    _IMPORT_BATCHES[token] = {"org_id": org.id, "rows": rows, "created": datetime.utcnow()}
    # Opportunistic cleanup: drop batches older than 1 hour
    cutoff = datetime.utcnow() - timedelta(hours=1)
    for t in [t for t, b in _IMPORT_BATCHES.items() if b["created"] < cutoff]:
        _IMPORT_BATCHES.pop(t, None)

    duplicates = [r for r in rows if r["duplicate_of"]]
    return {
        "batch": token,
        "new_count": len([r for r in rows if not r["duplicate_of"]]),
        "duplicate_count": len(duplicates),
        "duplicates": [
            {
                "row_number": r["row_number"],
                "incoming": {k: r["data"].get(k) for k in ("full_name", "business_name", "email", "phone")},
                "existing": r["duplicate_of"],
                "incoming_tags": r["tags"],
            }
            for r in duplicates
        ],
        "errors": errors[:20],
        "header_map": {k: v for k, v in header_map.items()},
    }


@api.post("/import/csv/commit")
def import_csv_commit(
    req: ImportCommitRequest,
    org: OrgContext = Depends(get_current_org),
    db: Session = Depends(get_db),
):
    """Phase 2: apply the previewed batch with a per-duplicate-row action.

    New (non-duplicate) rows are always inserted. Duplicate rows get the
    client's chosen strategy: update (incoming fills blanks on the existing
    lead), merge (same as update + union tags), or skip (leave untouched).
    """
    batch = _IMPORT_BATCHES.pop(req.batch, None)
    if batch is None or batch["org_id"] != org.id:
        raise HTTPException(status_code=404, detail="Import batch not found or expired — re-upload the CSV")

    inserted = 0
    updated = 0
    merged = 0
    skipped = 0

    for row in batch["rows"]:
        action = req.actions.get(str(row["row_number"]), "skip")
        if row["duplicate_of"] and isinstance(row["duplicate_of"], dict) and row["duplicate_of"].get("in_file"):
            skipped += 1  # in-file duplicates beyond the first occurrence
            continue
        if row["duplicate_of"] and action in {"update", "merge", "skip"}:
            existing = db.query(Lead).filter(
                Lead.id == row["duplicate_of"]["lead_id"],
                Lead.organization_id == org.id,
            ).first()
            if existing is None:
                skipped += 1
                continue
            if action == "skip":
                skipped += 1
            else:
                incoming = dict(row["data"])
                incoming["tags"] = row["tags"] if action == "merge" else normalize_tags(row["tags"])
                if action == "update":
                    incoming.pop("tags", None)  # plain update: fill blanks only
                _merge_into(existing, incoming)
                recalculate_scores(existing)
                if action == "update":
                    updated += 1
                else:
                    merged += 1
            continue

        # New lead
        lead = Lead(owner_user_id=org.user_id, organization_id=org.id, **{
            k: v for k, v in row["data"].items() if k not in {"tags"}
        })
        if row["tags"]:
            lead.tags = json.dumps(row["tags"])
        recalculate_scores(lead)
        db.add(lead)
        inserted += 1

    db.commit()
    return {"inserted": inserted, "updated": updated, "merged": merged, "skipped": skipped}


# ─── CSV Export ──────────────────────────────────────────────────────────────

@api.get("/export/csv")
def export_csv(
    search: Optional[str] = None,
    status: Optional[str] = None,
    priority: Optional[str] = None,
    segment: Optional[str] = None,
    org: OrgContext = Depends(get_current_org),
    db: Session = Depends(get_db),
):
    q = db.query(Lead).filter(Lead.organization_id == org.id)

    if search:
        search_lower = f"%{search.lower()}%"
        q = q.filter(
            (func.lower(Lead.full_name).like(search_lower))
            | (func.lower(Lead.business_name).like(search_lower))
            | (func.lower(Lead.email).like(search_lower))
        )
    if status:
        q = q.filter(Lead.status == status)
    if priority:
        q = q.filter(Lead.priority_tier == priority)
    if segment:
        q = q.filter(Lead.segment_id == segment)

    leads = q.order_by(Lead.total_score.desc()).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "full_name", "business_name", "email", "segment", "niche",
        "status", "total_score", "priority_tier", "tags",
        "offer_clarity_score", "bottleneck_evidence_score", "buying_signal_score",
        "decision_maker_access_score", "contactability_score", "strategic_fit_score",
        "website_url", "linkedin_url", "contact_path", "location_text",
        "team_size_estimate", "source_url", "personalization_note", "outreach_angle",
        "outcome_note", "last_contacted_at", "next_follow_up_at", "follow_up_count",
        "created_at",
    ])
    for l in leads:
        writer.writerow([
            l.full_name, l.business_name, l.email, l.segment, l.niche,
            l.status, l.total_score, l.priority_tier, ", ".join(decode_tags(l.tags)),
            l.offer_clarity_score, l.bottleneck_evidence_score, l.buying_signal_score,
            l.decision_maker_access_score, l.contactability_score, l.strategic_fit_score,
            l.website_url, l.linkedin_url, l.contact_path, l.location_text,
            l.team_size_estimate, l.source_url, l.personalization_note, l.outreach_angle,
            l.outcome_note,
            l.last_contacted_at.isoformat() if l.last_contacted_at else "",
            l.next_follow_up_at.isoformat() if l.next_follow_up_at else "",
            l.follow_up_count,
            l.created_at.isoformat() if l.created_at else "",
        ])

    output.seek(0)
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode("utf-8")),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=leads_export.csv"},
    )


# ─── Pipeline (grouped leads by status) ──────────────────────────────────────

PIPELINE_ORDER = ["NEW", "SCORED", "READY_TO_CONTACT", "CONTACTED", "FOLLOW_UP_1", "FOLLOW_UP_2", "REPLIED", "CALL_BOOKED", "WON", "CLIENT", "LOST", "NURTURE"]


@api.get("/pipeline")
def get_pipeline(org: OrgContext = Depends(get_current_org), db: Session = Depends(get_db)):
    leads = db.query(Lead).filter(Lead.organization_id == org.id).all()
    grouped = {s: [] for s in PIPELINE_ORDER}
    for l in leads:
        status = l.status or "NEW"
        if status in grouped:
            grouped[status].append(lead_to_dict(l))
    return grouped


# ─── Public Lead Intake ────────────────────────────────────────────────────

class PublicLeadCreate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    full_name: Optional[str] = None
    business_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    segment: Optional[str] = None
    niche: Optional[str] = None
    website_url: Optional[str] = None
    linkedin_url: Optional[str] = None
    location_text: Optional[str] = None
    source_url: Optional[str] = None
    personalization_note: Optional[str] = None
    outreach_angle: Optional[str] = None


@api.post("/public/leads", status_code=201)
def public_create_lead(
    req: PublicLeadCreate,
    api_key: str = Query(..., description="API key for public access"),
    db: Session = Depends(get_db),
):
    """
    Public endpoint for lead intake (no JWT required).
    Requires an API key passed as ?api_key=xxx query parameter.
    Auto-assigns lead to the configured CRM owner.
    """
    # Validate API key
    expected_key = os.environ.get("CRM_PUBLIC_API_KEY", "")
    if not expected_key or api_key != expected_key:
        raise HTTPException(status_code=401, detail="Invalid API key")

    # Find the owner — use CRM_OWNER_EMAIL env var or fall back to first user
    owner_email = os.environ.get("CRM_OWNER_EMAIL", "")
    if owner_email:
        owner = db.query(User).filter(User.email == owner_email).first()
    else:
        owner = db.query(User).first()

    if not owner:
        raise HTTPException(status_code=500, detail="No CRM owner configured")

    # Resolve the owner's organization so the lead lands in shared org data
    from models import OrganizationMember
    membership = (
        db.query(OrganizationMember)
        .filter(OrganizationMember.user_id == owner.id)
        .order_by(OrganizationMember.created_at.asc())
        .first()
    )
    organization_id = membership.organization_id if membership else None

    # Build lead from allowed fields only
    lead_data = {k: v for k, v in req.model_dump().items() if v is not None}
    lead = Lead(owner_user_id=owner.id, organization_id=organization_id, **lead_data)

    # Auto-generate full_name
    if not lead.full_name and (lead.first_name or lead.last_name):
        lead.full_name = f"{lead.first_name or ''} {lead.last_name or ''}".strip()

    # Auto-tag source
    if not lead.source_url:
        lead.source_url = "public_intake_form"

    recalculate_scores(lead)
    db.add(lead)
    db.flush()  # Flush to get the lead.id before creating activity

    # Log activity
    db.add(Activity(
        lead_id=lead.id,
        user_id=owner.id,
        organization_id=organization_id,
        activity_type="NOTE",
        body="Lead created via public intake form",
    ))

    db.commit()
# ─── Gmail OAuth ─────────────────────────────────────────────────────────────

class GmailStatusResponse(BaseModel):
    connected: bool
    google_email: str | None = None
    sync_enabled: bool | None = None
    last_sync_at: str | None = None
    last_error: str | None = None


@api.get("/gmail/auth-url")
def gmail_auth_url(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generate an OAuth authorization URL and store state for CSRF validation."""
    state = str(uuid.uuid4())
    # Prune stale states for this user
    db.query(OAuthState).filter(
        OAuthState.user_id == current_user.id,
        OAuthState.created_at < datetime.utcnow() - timedelta(minutes=10),
    ).delete()
    db.add(OAuthState(user_id=current_user.id, state=state))
    db.commit()

    redirect_uri = os.environ.get(
        "GOOGLE_OAUTH_REDIRECT_URI",
        "http://localhost:5173/api/gmail/callback",
    )
    client_id = os.environ.get("GOOGLE_OAUTH_CLIENT_ID") or os.environ.get("GOOGLE_CLIENT_ID", "")
    if not client_id:
        raise HTTPException(status_code=500, detail="GOOGLE_OAUTH_CLIENT_ID not configured")

    params = urlencode({
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "https://www.googleapis.com/auth/gmail.readonly https://www.googleapis.com/auth/userinfo.email",
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    })
    return {"auth_url": f"https://accounts.google.com/o/oauth2/v2/auth?{params}"}


@api.get("/gmail/callback")
def gmail_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: Session = Depends(get_db),
):
    """Handle the OAuth callback from Google. Validates state, exchanges code for tokens."""
    # Validate state
    stored = db.query(OAuthState).filter(OAuthState.state == state).first()
    if not stored:
        raise HTTPException(status_code=400, detail="Invalid or expired state parameter")
    user_id = stored.user_id
    db.delete(stored)
    db.commit()

    # Exchange code for tokens
    client_id = os.environ.get("GOOGLE_OAUTH_CLIENT_ID") or os.environ.get("GOOGLE_CLIENT_ID", "")
    client_secret = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET") or os.environ.get("GOOGLE_CLIENT_SECRET", "")
    redirect_uri = os.environ.get("GOOGLE_OAUTH_REDIRECT_URI", "")
    if not client_id or not client_secret:
        raise HTTPException(status_code=500, detail="Google OAuth not configured")

    # Fire the token exchange with httpx (deferred import to avoid boot failure)
    try:
        import httpx
        resp = httpx.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
            timeout=30,
        )
        resp.raise_for_status()
        token_data = resp.json()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Token exchange failed: {exc}")

    access_token = token_data.get("access_token")
    refresh_token = token_data.get("refresh_token")
    expires_in = token_data.get("expires_in", 3600)
    token_expiry = datetime.utcnow() + timedelta(seconds=expires_in)

    if not access_token:
        raise HTTPException(status_code=502, detail="No access_token in OAuth response")

    # Fetch the user's Google email
    try:
        import httpx
        info_resp = httpx.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10,
        )
        info_resp.raise_for_status()
        google_email = info_resp.json().get("email", "unknown@google.com")
    except Exception as exc:
        google_email = "unknown@google.com"

    # Encrypt tokens before storing
    from crypto_utils import encrypt_token
    encrypted_access = encrypt_token(access_token)
    encrypted_refresh = encrypt_token(refresh_token or "")

    # Upsert GmailConnection
    conn = db.query(GmailConnection).filter(GmailConnection.owner_user_id == user_id).first()
    if not conn:
        conn = GmailConnection(owner_user_id=user_id)
        db.add(conn)

    conn.provider = "gmail"
    conn.google_email = google_email
    conn.access_token = encrypted_access
    conn.refresh_token = encrypted_refresh or conn.refresh_token  # preserve existing if not returned
    conn.token_expiry = token_expiry
    conn.sync_enabled = True
    conn.last_error = None
    db.commit()

    # Redirect to the frontend settings page
    frontend_url = os.environ.get("FRONTEND_URL", "http://localhost:5173")
    return RedirectResponse(url=f"{frontend_url}/settings?tab=gmail", status_code=302)


@api.get("/gmail/status")
def gmail_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return the current Gmail connection status for the authenticated user."""
    conn = db.query(GmailConnection).filter(GmailConnection.owner_user_id == current_user.id).first()
    if not conn:
        return GmailStatusResponse(connected=False)
    return GmailStatusResponse(
        connected=True,
        google_email=conn.google_email,
        sync_enabled=conn.sync_enabled,
        last_sync_at=conn.last_sync_at.isoformat() if conn.last_sync_at else None,
        last_error=conn.last_error,
    )


@api.post("/gmail/disconnect")
def gmail_disconnect(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Disconnect Gmail and revoke the token."""
    conn = db.query(GmailConnection).filter(GmailConnection.owner_user_id == current_user.id).first()
    if not conn:
        raise HTTPException(status_code=404, detail="No Gmail connection found")

    # Attempt to revoke the token remotely
    if conn.access_token:
        try:
            import httpx
            httpx.post(
                "https://oauth2.googleapis.com/revoke",
                params={"token": conn.access_token},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=10,
            )
        except Exception:
            logger.warning("Token revocation failed for user %s", current_user.id)

    db.delete(conn)
    db.commit()
    return {"status": "disconnected"}


@api.post("/gmail/sync-toggle")
def gmail_sync_toggle(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Toggle sync_enabled on/off for the current user's Gmail connection."""
    conn = db.query(GmailConnection).filter(GmailConnection.owner_user_id == current_user.id).first()
    if not conn:
        raise HTTPException(status_code=404, detail="No Gmail connection found")
    conn.sync_enabled = not conn.sync_enabled
    db.commit()
    return {"sync_enabled": conn.sync_enabled}


# ─── Notifications ──────────────────────────────────────────────────────────


@api.get("/notifications")
def list_notifications(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    unread_only: bool = False,
):
    """List notifications for the current user, newest first."""
    q = db.query(Notification).filter(Notification.owner_user_id == current_user.id)
    if unread_only:
        q = q.filter(Notification.is_read == False)
    q = q.order_by(Notification.created_at.desc()).limit(50)
    return [notification_to_dict(n) for n in q.all()]


@api.get("/notifications/unread-count")
def unread_notification_count(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return the count of unread notifications."""
    count = (
        db.query(Notification)
        .filter(Notification.owner_user_id == current_user.id, Notification.is_read == False)
        .count()
    )
    return {"count": count}


@api.post("/notifications/mark-read")
def mark_notification_read(
    body: MarkNotificationRead,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mark a single notification as read."""
    n = db.query(Notification).filter(
        Notification.id == body.notification_id,
        Notification.owner_user_id == current_user.id,
    ).first()
    if not n:
        raise HTTPException(status_code=404, detail="Notification not found")
    n.is_read = True
    db.commit()
    return notification_to_dict(n)


@api.post("/notifications/mark-all-read")
def mark_all_notifications_read(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mark all notifications as read for the current user."""
    rows = (
        db.query(Notification)
        .filter(Notification.owner_user_id == current_user.id, Notification.is_read == False)
        .update({"is_read": True})
    )
    db.commit()
    return {"updated": rows}
