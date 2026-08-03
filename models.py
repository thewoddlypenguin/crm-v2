import uuid
from datetime import datetime

from sqlalchemy import (
    Column, String, Text, Integer, DateTime, ForeignKey, Enum as SAEnum, Index, Boolean
)
from sqlalchemy.orm import relationship, backref

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

class Organization(Base):
    """A shared workspace. Multiple users (OrganizationMember) share its data."""
    __tablename__ = "organizations"

    id = uuid_pk()
    name = Column(String, nullable=False)
    created_at = now()

    members = relationship("OrganizationMember", back_populates="organization")


class OrganizationMember(Base):
    """Join table: user membership in an organization with a role."""
    __tablename__ = "organization_members"

    id = uuid_pk()
    organization_id = Column(String, ForeignKey("organizations.id"), nullable=False, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    role = Column(String, default="member", nullable=False)  # "owner" | "member"
    created_at = now()

    organization = relationship("Organization", back_populates="members")
    user = relationship("User", back_populates="memberships")

    __table_args__ = (
        Index("ix_organization_members_org_user", "organization_id", "user_id", unique=True),
    )


class User(Base):
    __tablename__ = "users"

    id = uuid_pk()
    email = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    full_name = Column(String, nullable=True)
    created_at = now()
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    segments = relationship("Segment", back_populates="owner")
    email_templates = relationship("EmailTemplate", back_populates="owner")
    email_settings = relationship("EmailSettings", back_populates="owner", uselist=False)

    leads = relationship("Lead", back_populates="owner")
    memberships = relationship("OrganizationMember", back_populates="user")

class Segment(Base):
    __tablename__ = "segments"

    id = uuid_pk()
    owner_user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    organization_id = Column(String, ForeignKey("organizations.id"), nullable=True, index=True)

    key = Column(String, nullable=False)
    label = Column(String, nullable=False)
    sort_order = Column(Integer, default=0, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    created_at = now()
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    owner = relationship("User", back_populates="segments")
    leads = relationship("Lead", back_populates="segment_rel")

    __table_args__ = (
        Index("ix_segments_owner_key_unique", "owner_user_id", "key", unique=True),
        Index("ix_segments_org_key_unique", "organization_id", "key", unique=True),
    )

class EmailSettings(Base):
    """Per-user email provider configuration. One row per user (upsert pattern)."""
    __tablename__ = "email_settings"

    id = uuid_pk()
    owner_user_id = Column(String, ForeignKey("users.id"), nullable=False, unique=True, index=True)

    # Provider identity — no secrets stored here; credentials stay in env vars
    provider = Column(String, nullable=True)          # "smtp" | "resend" | "sendgrid" | "postmark"
    from_email = Column(String, nullable=True)
    from_name = Column(String, nullable=True)
    reply_to_email = Column(String, nullable=True)

    # Gate: must be explicitly disabled before any live send is attempted
    test_mode_enabled = Column(Boolean, default=True, nullable=False)

    created_at = now()
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    owner = relationship("User", back_populates="email_settings")


class EmailTemplate(Base):
    __tablename__ = "email_templates"

    id = uuid_pk()
    owner_user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    organization_id = Column(String, ForeignKey("organizations.id"), nullable=True, index=True)
    name = Column(String, nullable=False)
    subject = Column(String, nullable=False)
    body = Column(Text, nullable=False)
    created_at = now()
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    owner = relationship("User", back_populates="email_templates")


class Lead(Base):
    __tablename__ = "leads"

    id = uuid_pk()
    owner_user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    organization_id = Column(String, ForeignKey("organizations.id"), nullable=True, index=True)

    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    full_name = Column(String, nullable=True, index=True)
    business_name = Column(String, nullable=True, index=True)
    segment = Column(SEGMENT_ENUM, nullable=True)
    segment_id = Column(String, ForeignKey("segments.id"), nullable=True, index=True)
    segment_rel = relationship("Segment", back_populates="leads")
    niche = Column(String, nullable=True)
    website_url = Column(String, nullable=True)
    email = Column(String, nullable=True)
    phone = Column(String, nullable=True)
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

    # Compliance
    do_not_contact = Column(Boolean, default=False, nullable=False)

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
    organization_id = Column(String, ForeignKey("organizations.id"), nullable=True, index=True)
    activity_type = Column(ACTIVITY_TYPE_ENUM, nullable=False)
    body = Column(Text, nullable=True)
    occurred_at = Column(DateTime, default=datetime.utcnow, index=True)
    created_at = now()

    lead = relationship("Lead", back_populates="activities")


class GmailConnection(Base):
    """Per-user Gmail OAuth connection. One row per user (upsert pattern)."""
    __tablename__ = "gmail_connections"

    id = uuid_pk()
    owner_user_id = Column(String, ForeignKey("users.id"), nullable=False, unique=True, index=True)

    provider = Column(String, default="gmail", nullable=False)
    google_email = Column(String, nullable=False)

    # OAuth tokens — stored as-is; encryption is a follow-up
    access_token = Column(Text, nullable=False)
    refresh_token = Column(Text, nullable=False)
    token_expiry = Column(DateTime, nullable=True)

    # Sync configuration
    sync_enabled = Column(Boolean, default=True, nullable=False)
    last_sync_at = Column(DateTime, nullable=True)
    last_error = Column(Text, nullable=True)

    created_at = now()
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    owner = relationship("User", backref=backref("gmail_connection", uselist=False))


class SyncedEmail(Base):
    """Deduplicated Gmail messages synced for a lead."""
    __tablename__ = "synced_emails"

    id = uuid_pk()
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    organization_id = Column(String, ForeignKey("organizations.id"), nullable=True, index=True)
    lead_id = Column(String, ForeignKey("leads.id"), nullable=False, index=True)

    provider = Column(String, default="gmail", nullable=False)
    external_message_id = Column(String, nullable=False)
    thread_id = Column(String, nullable=True)
    direction = Column(String, nullable=False)  # "inbound" or "outbound"

    subject = Column(Text, nullable=True)
    from_email = Column(String, nullable=False)
    to_emails = Column(Text, nullable=True)
    cc_emails = Column(Text, nullable=True)
    sent_at = Column(DateTime, nullable=False, index=True)
    snippet = Column(Text, nullable=True)

    synced_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    lead = relationship("Lead", backref=backref("synced_emails", lazy="dynamic"))

    __table_args__ = (
        Index("ix_synced_emails_user_message", "user_id", "external_message_id", unique=True),
    )


class OAuthState(Base):
    """Temporary OAuth state tokens for CSRF protection during OAuth flows."""
    __tablename__ = "oauth_states"

    id = uuid_pk()
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    state = Column(String, nullable=False, unique=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class Notification(Base):
    """In-app notification for a user, generated by inbound email sync events."""
    __tablename__ = "notifications"

    id = uuid_pk()
    owner_user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    lead_id = Column(String, ForeignKey("leads.id"), nullable=True, index=True)

    title = Column(String, nullable=False)
    body = Column(Text, nullable=True)
    notification_type = Column(String, nullable=False, default="email_received")

    is_read = Column(Boolean, default=False, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    owner = relationship("User", backref=backref("notifications", lazy="dynamic", order_by="Notification.created_at.desc()"))
    lead = relationship("Lead", backref=backref("notifications", lazy="dynamic"))
