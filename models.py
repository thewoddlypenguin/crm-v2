import uuid
from datetime import datetime

from sqlalchemy import (
    Column, String, Text, Integer, DateTime, ForeignKey, Enum as SAEnum, Index
)
from sqlalchemy.orm import relationship

from db import Base


def uuid_pk():
    return Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))


def now():
    return Column(DateTime, default=datetime.utcnow)


# --- Enums ---

SEGMENT_ENUM = SAEnum(
    "COACH", "CONSULTANT", "SOLOPRENEUR", "OTHER",
    name="lead_segment", create_constraint=True
)

CONTACT_PATH_ENUM = SAEnum(
    "EMAIL", "FORM", "DM", "OTHER",
    name="contact_path", create_constraint=True
)

PRIORITY_TIER_ENUM = SAEnum(
    "A", "B", "C",
    name="priority_tier", create_constraint=True
)

STATUS_ENUM = SAEnum(
    "NEW", "SCORED", "READY_TO_CONTACT", "CONTACTED",
    "FOLLOW_UP_1", "FOLLOW_UP_2", "REPLIED", "CALL_BOOKED",
    "WON", "CLIENT", "LOST", "NURTURE",
    name="lead_status", create_constraint=True
)

ACTIVITY_TYPE_ENUM = SAEnum(
    "NOTE", "STATUS_CHANGE", "OUTREACH_SENT", "FOLLOW_UP_SENT",
    "REPLY_RECEIVED", "CALL_BOOKED", "OTHER",
    name="activity_type", create_constraint=True
)


# --- Models ---

class User(Base):
    __tablename__ = "users"

    id = uuid_pk()
    email = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    full_name = Column(String, nullable=True)
    created_at = now()
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    leads = relationship("Lead", back_populates="owner")


class Lead(Base):
    __tablename__ = "leads"

    id = uuid_pk()
    owner_user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)

    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    full_name = Column(String, nullable=True, index=True)
    business_name = Column(String, nullable=True, index=True)
    segment = Column(SEGMENT_ENUM, nullable=True)
    niche = Column(String, nullable=True)
    website_url = Column(String, nullable=True)
    email = Column(String, nullable=True)
    contact_path = Column(CONTACT_PATH_ENUM, nullable=True)
    linkedin_url = Column(String, nullable=True)
    location_text = Column(String, nullable=True)
    team_size_estimate = Column(Integer, nullable=True)
    source_url = Column(String, nullable=True)
    personalization_note = Column(Text, nullable=True)
    outreach_angle = Column(Text, nullable=True)

    # Scoring
    offer_clarity_score = Column(Integer, default=0)
    bottleneck_evidence_score = Column(Integer, default=0)
    buying_signal_score = Column(Integer, default=0)
    decision_maker_access_score = Column(Integer, default=0)
    contactability_score = Column(Integer, default=0)
    strategic_fit_score = Column(Integer, default=0)
    total_score = Column(Integer, default=0, index=True)
    priority_tier = Column(PRIORITY_TIER_ENUM, default="C", index=True)

    # Pipeline
    status = Column(STATUS_ENUM, default="NEW", index=True)
    last_contacted_at = Column(DateTime, nullable=True)
    follow_up_count = Column(Integer, default=0)
    next_follow_up_at = Column(DateTime, nullable=True, index=True)
    outcome_note = Column(Text, nullable=True)

    # Audit
    created_at = now()
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    owner = relationship("User", back_populates="leads")
    activities = relationship("Activity", back_populates="lead", order_by="Activity.occurred_at.desc()")

    __table_args__ = (
        Index("ix_leads_full_name_trgm", "full_name"),
        Index("ix_leads_business_name_trgm", "business_name"),
    )


class Activity(Base):
    __tablename__ = "activities"

    id = uuid_pk()
    lead_id = Column(String, ForeignKey("leads.id"), nullable=False, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    activity_type = Column(ACTIVITY_TYPE_ENUM, nullable=False)
    body = Column(Text, nullable=True)
    occurred_at = Column(DateTime, default=datetime.utcnow, index=True)
    created_at = now()

    lead = relationship("Lead", back_populates="activities")
