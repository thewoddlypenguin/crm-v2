"""Business logic: scoring, tier calculation, status transitions."""

from datetime import datetime, timedelta
from typing import Optional


STATUS_ORDER = [
    "NEW", "SCORED", "READY_TO_CONTACT", "CONTACTED",
    "FOLLOW_UP_1", "FOLLOW_UP_2", "REPLIED", "CALL_BOOKED",
    "WON", "CLIENT", "LOST", "NURTURE",
]

CLEAR_FOLLOW_UP_STATUSES = {"REPLIED", "CALL_BOOKED", "WON", "CLIENT", "LOST"}


def compute_total_score(lead) -> int:
    """Sum the six score fields (0-12)."""
    return (
        (lead.offer_clarity_score or 0)
        + (lead.bottleneck_evidence_score or 0)
        + (lead.buying_signal_score or 0)
        + (lead.decision_maker_access_score or 0)
        + (lead.contactability_score or 0)
        + (lead.strategic_fit_score or 0)
    )


def compute_priority_tier(total_score: int) -> str:
    """A >= 10, B 7-9, C <= 6."""
    if total_score >= 10:
        return "A"
    elif total_score >= 7:
        return "B"
    return "C"


def compute_next_follow_up(status: str, now: Optional[datetime] = None) -> Optional[datetime]:
    """Compute next follow-up date based on status transition."""
    if now is None:
        now = datetime.utcnow()

    if status == "CONTACTED":
        return now + timedelta(days=3)
    elif status == "FOLLOW_UP_1":
        return now + timedelta(days=4)
    elif status == "FOLLOW_UP_2":
        return now + timedelta(days=5)
    elif status in CLEAR_FOLLOW_UP_STATUSES:
        return None
    return None


def apply_status_transition(lead, new_status: str, now: Optional[datetime] = None) -> str:
    """
    Apply a status transition to a lead. Returns the activity body text.
    Mutates lead in place.
    """
    if now is None:
        now = datetime.utcnow()

    old_status = lead.status
    lead.status = new_status

    # Update last_contacted_at for outreach statuses
    if new_status in ("CONTACTED", "FOLLOW_UP_1", "FOLLOW_UP_2"):
        lead.last_contacted_at = now
        lead.follow_up_count = lead.follow_up_count or 0
        if new_status == "FOLLOW_UP_1":
            lead.follow_up_count = max(lead.follow_up_count, 1)
        elif new_status == "FOLLOW_UP_2":
            lead.follow_up_count = max(lead.follow_up_count, 2)

    # Compute next follow-up
    next_fu = compute_next_follow_up(new_status, now)
    if next_fu is not None:
        lead.next_follow_up_at = next_fu
    elif new_status in CLEAR_FOLLOW_UP_STATUSES:
        lead.next_follow_up_at = None

    # If moving to CONTACTED and no next_follow_up_at set, set it
    if new_status == "CONTACTED" and lead.next_follow_up_at is None:
        lead.next_follow_up_at = now + timedelta(days=3)

    return f"Status changed from {old_status} to {new_status}"


def recalculate_scores(lead):
    """Recalculate total_score and priority_tier from individual scores."""
    lead.total_score = compute_total_score(lead)
    lead.priority_tier = compute_priority_tier(lead.total_score)
