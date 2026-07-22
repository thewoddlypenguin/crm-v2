"""API routes for Leverage CRM Lite."""

import csv
import io
import os
from models import Activity, Lead, User, Segment
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, and_
from sqlalchemy.orm import Session

from auth import (
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)
from business import apply_status_transition, compute_next_follow_up, recalculate_scores
from db import get_db
from models import Activity, Lead, User

api = APIRouter()


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
    password: str = Field(min_length=6)
    full_name: Optional[str] = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class AuthResponse(BaseModel):
    token: str
    user: dict


class LeadCreate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    full_name: Optional[str] = None
    business_name: Optional[str] = None
    segment: Optional[str] = None
    segment_id: Optional[str] = None
    niche: Optional[str] = None
    website_url: Optional[str] = None
    email: Optional[str] = None
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
    niche: Optional[str] = None
    website_url: Optional[str] = None
    email: Optional[str] = None
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


def lead_to_dict(lead: Lead) -> dict:
    return {
        "id": lead.id,
        "owner_user_id": lead.owner_user_id,
        "first_name": lead.first_name,
        "last_name": lead.last_name,
        "full_name": lead.full_name,
        "business_name": lead.business_name,
        "segment": lead.segment,
        "segment_id": lead.segment_id,
        "segment_label": lead.segment_rel.label if lead.segment_rel else None,
        "niche": lead.niche,
        "website_url": lead.website_url,
        "email": lead.email,
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
        "created_at": lead.created_at.isoformat() if lead.created_at else None,
        "updated_at": lead.updated_at.isoformat() if lead.updated_at else None,
    }
    
def segment_to_dict(segment: Segment) -> dict:
    return {
        "id": segment.id,
        "owner_user_id": segment.owner_user_id,
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
        "activity_type": a.activity_type,
        "body": a.body,
        "occurred_at": a.occurred_at.isoformat() if a.occurred_at else None,
        "created_at": a.created_at.isoformat() if a.created_at else None,
    }


# ─── Auth Routes ─────────────────────────────────────────────────────────────

@api.post("/auth/register", response_model=AuthResponse)
def register(req: RegisterRequest, db: Session = Depends(get_db)):
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
    token = create_access_token(user.id, user.email)
    return AuthResponse(
        token=token,
        user={"id": user.id, "email": user.email, "full_name": user.full_name},
    )


@api.post("/auth/login", response_model=AuthResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == req.email).first()
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token(user.id, user.email)
    return AuthResponse(
        token=token,
        user={"id": user.id, "email": user.email, "full_name": user.full_name},
    )


@api.get("/auth/me")
def get_me(current_user: User = Depends(get_current_user)):
    return {"id": current_user.id, "email": current_user.email, "full_name": current_user.full_name}


# ─── Segments ───────────────────────────────────────────────────────────────

@api.get("/segments")
def list_segments(
    include_inactive: bool = False,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(Segment).filter(Segment.owner_user_id == current_user.id)
    if not include_inactive:
        from sqlalchemy import true
        q = q.filter(Segment.is_active == true())
    segments = q.order_by(Segment.sort_order.asc(), Segment.label.asc()).all()
    return [segment_to_dict(s) for s in segments]


@api.post("/segments", status_code=201)
def create_segment(
    req: SegmentCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    key = req.key.strip().lower()
    label = req.label.strip()

    if not key:
        raise HTTPException(status_code=400, detail="Segment key is required")
    if not label:
        raise HTTPException(status_code=400, detail="Segment label is required")

    existing = db.query(Segment).filter(
        Segment.owner_user_id == current_user.id,
        Segment.key == key,
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Segment key already exists")

    segment = Segment(
        owner_user_id=current_user.id,
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
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    segment = db.query(Segment).filter(
        Segment.id == segment_id,
        Segment.owner_user_id == current_user.id,
    ).first()
    if not segment:
        raise HTTPException(status_code=404, detail="Segment not found")

    updates = req.model_dump(exclude_unset=True)

    if "key" in updates and updates["key"] is not None:
        updates["key"] = updates["key"].strip().lower()
        if not updates["key"]:
            raise HTTPException(status_code=400, detail="Segment key cannot be empty")

        existing = db.query(Segment).filter(
            Segment.owner_user_id == current_user.id,
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
    sort_by: Optional[str] = "total_score",
    sort_dir: Optional[str] = "desc",
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(Lead).filter(Lead.owner_user_id == current_user.id)

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
def create_lead(req: LeadCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    payload = req.model_dump()
    payload.pop("segment", None)
    segment_id = payload.pop("segment_id", None)

    lead = Lead(
        owner_user_id=current_user.id,
        **{k: v for k, v in payload.items() if v is not None},
    )

    if segment_id:
        segment = db.query(Segment).filter(
            Segment.id == segment_id,
            Segment.owner_user_id == current_user.id,
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
def get_lead(lead_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    lead = db.query(Lead).filter(Lead.id == lead_id, Lead.owner_user_id == current_user.id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return lead_to_dict(lead)


@api.put("/leads/{lead_id}")
def update_lead(lead_id: str, req: LeadUpdate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    lead = db.query(Lead).filter(Lead.id == lead_id, Lead.owner_user_id == current_user.id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    updates.pop("segment", None)
    segment_id = updates.pop("segment_id", None)

    for k, v in updates.items():
        setattr(lead, k, v)

    if segment_id:
        segment = db.query(Segment).filter(
            Segment.id == segment_id,
            Segment.owner_user_id == current_user.id,
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
def delete_lead(lead_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    lead = db.query(Lead).filter(Lead.id == lead_id, Lead.owner_user_id == current_user.id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    db.query(Activity).filter(Activity.lead_id == lead_id).delete()
    db.delete(lead)
    db.commit()
    return {"status": "deleted"}


# ─── Status Transition ───────────────────────────────────────────────────────

VALID_STATUSES = {"NEW", "SCORED", "READY_TO_CONTACT", "CONTACTED", "FOLLOW_UP_1", "FOLLOW_UP_2", "REPLIED", "CALL_BOOKED", "WON", "CLIENT", "LOST", "NURTURE"}


@api.post("/leads/{lead_id}/status")
def change_status(lead_id: str, req: StatusChangeRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if req.status not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid status: {req.status}")

    lead = db.query(Lead).filter(Lead.id == lead_id, Lead.owner_user_id == current_user.id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    old_status = lead.status
    activity_body = apply_status_transition(lead, req.status)

    # Write activity
    activity = Activity(
        lead_id=lead.id,
        user_id=current_user.id,
        activity_type="STATUS_CHANGE",
        body=activity_body,
    )
    db.add(activity)
    db.commit()
    db.refresh(lead)
    return lead_to_dict(lead)


@api.post("/leads/bulk-status")
def bulk_status_change(req: BulkStatusChange, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if req.status not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid status: {req.status}")

    leads = db.query(Lead).filter(
        Lead.id.in_(req.lead_ids),
        Lead.owner_user_id == current_user.id,
    ).all()

    now = datetime.utcnow()
    for lead in leads:
        activity_body = apply_status_transition(lead, req.status, now=now)
        db.add(Activity(
            lead_id=lead.id,
            user_id=current_user.id,
            activity_type="STATUS_CHANGE",
            body=activity_body,
            occurred_at=now,
        ))

    db.commit()
    return {"updated": len(leads)}

@api.post("/leads/bulk-segment")
def bulk_segment_change(req: BulkSegmentChange, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    segment = db.query(Segment).filter(
        Segment.id == req.segment_id,
        Segment.owner_user_id == current_user.id,
    ).first()
    if not segment:
        raise HTTPException(status_code=400, detail="Invalid segment_id")

    leads = db.query(Lead).filter(
        Lead.id.in_(req.lead_ids),
        Lead.owner_user_id == current_user.id,
    ).all()

    for lead in leads:
        lead.segment_id = segment.id
        lead.segment = legacy_segment_or_none(segment.key)

    db.commit()
    return {"updated": len(leads)}


# ─── Activities ──────────────────────────────────────────────────────────────

VALID_ACTIVITY_TYPES = {"NOTE", "STATUS_CHANGE", "OUTREACH_SENT", "FOLLOW_UP_SENT", "REPLY_RECEIVED", "CALL_BOOKED", "OTHER"}


@api.get("/leads/{lead_id}/activities")
def list_activities(lead_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    lead = db.query(Lead).filter(Lead.id == lead_id, Lead.owner_user_id == current_user.id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    activities = db.query(Activity).filter(Activity.lead_id == lead_id).order_by(Activity.occurred_at.desc()).all()
    return [activity_to_dict(a) for a in activities]


@api.post("/leads/{lead_id}/activities", status_code=201)
def create_activity(lead_id: str, req: ActivityCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if req.activity_type not in VALID_ACTIVITY_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid activity type: {req.activity_type}")

    lead = db.query(Lead).filter(Lead.id == lead_id, Lead.owner_user_id == current_user.id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    activity = Activity(
        lead_id=lead.id,
        user_id=current_user.id,
        activity_type=req.activity_type,
        body=req.body,
        occurred_at=req.occurred_at or datetime.utcnow(),
    )
    db.add(activity)
    db.commit()
    db.refresh(activity)
    return activity_to_dict(activity)


@api.put("/leads/{lead_id}/activities/{activity_id}")
def update_activity(lead_id: str, activity_id: str, req: ActivityUpdate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    lead = db.query(Lead).filter(Lead.id == lead_id, Lead.owner_user_id == current_user.id).first()
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
def delete_activity(lead_id: str, activity_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    lead = db.query(Lead).filter(Lead.id == lead_id, Lead.owner_user_id == current_user.id).first()
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


# ─── Email ───────────────────────────────────────────────────────────────────

@api.post("/leads/{lead_id}/email", status_code=201)
def send_lead_email(
    lead_id: str,
    req: EmailSendRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Compose and send an email to a lead, then log it as an OUTREACH_SENT activity.

    STUB: send_email() raises NotImplementedError until a provider is configured.
    The activity log is only written on successful send.
    """
    lead = db.query(Lead).filter(Lead.id == lead_id, Lead.owner_user_id == current_user.id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    recipient = req.to_address or lead.email
    if not recipient:
        raise HTTPException(status_code=400, detail="No recipient address — set to_address or add an email to the lead")

    from email_service import EmailPayload, send_email  # deferred — keeps app bootable if module is missing

    try:
        result = send_email(EmailPayload(
            to_address=recipient,
            subject=req.subject,
            body=req.body,
        ))
    except NotImplementedError as exc:
        raise HTTPException(status_code=501, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Email provider error: {exc}")

    if not result.success:
        raise HTTPException(status_code=502, detail=result.error or "Email send failed")

    # Log the send as an activity
    activity = Activity(
        lead_id=lead.id,
        user_id=current_user.id,
        activity_type="OUTREACH_SENT",
        body=f"Subject: {req.subject}\n\n{req.body}",
        occurred_at=datetime.utcnow(),
    )
    db.add(activity)
    db.commit()
    db.refresh(activity)
    return activity_to_dict(activity)


# ─── Dashboard Metrics ───────────────────────────────────────────────────────

@api.get("/dashboard")
def dashboard(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    now = datetime.utcnow()
    week_ago = now - timedelta(days=7)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    base = db.query(Lead).filter(Lead.owner_user_id == current_user.id)

    leads_contacted_week = base.filter(
        Lead.last_contacted_at >= week_ago,
        Lead.status.in_(["CONTACTED", "FOLLOW_UP_1", "FOLLOW_UP_2", "REPLIED", "CALL_BOOKED", "WON"]),
    ).count()

    replies_week = db.query(Activity).filter(
        Activity.user_id == current_user.id,
        Activity.activity_type == "REPLY_RECEIVED",
        Activity.occurred_at >= week_ago,
    ).count()

    calls_booked_week = db.query(Activity).filter(
        Activity.user_id == current_user.id,
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
    current_user: User = Depends(get_current_user),
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

    for i, row in enumerate(reader, start=2):
        try:
            lead_data = {}
            for csv_col, model_field in header_map.items():
                val = row.get(csv_col, "").strip()
                if val:
                    if model_field == "team_size_estimate":
                        raw_team_size = str(val).strip().lower()

                        if raw_team_size in {"", "unknown", "n/a", "na", "none", "null", "unsure", "not sure", "-"}:
                            pass
                        else:
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
                        if model_field in ENUM_FIELDS:
                            val = normalize_enum_value(model_field, val)
                        lead_data[model_field] = val


            if not lead_data.get("full_name") and (lead_data.get("first_name") or lead_data.get("last_name")):
                lead_data["full_name"] = f"{lead_data.get('first_name', '')} {lead_data.get('last_name', '')}".strip()

            lead = Lead(owner_user_id=current_user.id, **lead_data)
            recalculate_scores(lead)
            db.add(lead)
            accepted += 1
        except Exception as e:
            rejected += 1
            errors.append({"row": i, "error": str(e)})

    db.commit()
    return {"accepted": accepted, "rejected": rejected, "errors": errors[:20]}


# ─── CSV Export ──────────────────────────────────────────────────────────────

@api.get("/export/csv")
def export_csv(
    search: Optional[str] = None,
    status: Optional[str] = None,
    priority: Optional[str] = None,
    segment: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(Lead).filter(Lead.owner_user_id == current_user.id)

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
        "status", "total_score", "priority_tier",
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
            l.status, l.total_score, l.priority_tier,
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
def get_pipeline(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    leads = db.query(Lead).filter(Lead.owner_user_id == current_user.id).all()
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

    # Build lead from allowed fields only
    lead_data = {k: v for k, v in req.model_dump().items() if v is not None}
    lead = Lead(owner_user_id=owner.id, **lead_data)

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
        activity_type="NOTE",
        body="Lead created via public intake form",
    ))

    db.commit()
    db.refresh(lead)
    return lead_to_dict(lead)
