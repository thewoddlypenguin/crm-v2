"""Seed script: create a demo user and 20 sample leads."""

import sys
import os

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime, timedelta
import uuid

from db import SessionLocal, init_db
from models import User, Lead, Activity
from auth import hash_password
from business import recalculate_scores, apply_status_transition

SEGMENTS = ["COACH", "CONSULTANT", "SOLOPRENEUR", "OTHER"]
STATUSES = ["NEW", "SCORED", "READY_TO_CONTACT", "CONTACTED", "FOLLOW_UP_1", "FOLLOW_UP_2", "REPLIED", "CALL_BOOKED", "WON", "LOST", "NURTURE"]
CONTACT_PATHS = ["EMAIL", "FORM", "DM", "OTHER"]

FIRST_NAMES = ["Alex", "Jordan", "Taylor", "Morgan", "Casey", "Riley", "Quinn", "Avery", "Blake", "Cameron",
               "Dakota", "Emerson", "Finley", "Harper", "Kennedy", "Logan", "Parker", "Reese", "Sage", "Rowan"]
LAST_NAMES = ["Chen", "Patel", "Rodriguez", "Kim", "Johnson", "Williams", "Garcia", "Martinez", "Anderson", "Lee",
              "Thompson", "White", "Harris", "Clark", "Lewis", "Walker", "Hall", "Young", "King", "Wright"]
BUSINESSES = [
    "Mindset Coaching", "Growth Consulting", "Freelance Design", "SaaS Advisory",
    "Fitness Coaching", "Marketing Consulting", "Content Creation", "Tech Strategy",
    "Life Coaching", "Business Advisory", "Copywriting Studio", "Product Consulting",
    "Executive Coaching", "Brand Strategy", "AI Consulting", "Health Coaching",
    "Sales Training", "UX Consulting", "Financial Advisory", "Leadership Coaching",
]
NICHES = [
    "Health & Wellness", "B2B SaaS", "E-commerce", "Real Estate",
    "Online Education", "Digital Marketing", "FinTech", "Personal Development",
]


def seed():
    init_db()
    db = SessionLocal()

    try:
        # Check if demo user exists
        demo_email = "demo@leveragecrm.com"
        user = db.query(User).filter(User.email == demo_email).first()
        if user:
            print(f"Demo user already exists ({user.id}). Deleting and re-seeding...")
            # Delete existing data
            db.query(Activity).filter(Activity.user_id == user.id).delete()
            db.query(Lead).filter(Lead.owner_user_id == user.id).delete()
            db.query(User).filter(User.id == user.id).delete()
            db.flush()

        # Create demo user
        user = User(
            id=str(uuid.uuid4()),
            email=demo_email,
            password_hash=hash_password("demo123"),
            full_name="Demo User",
        )
        db.add(user)
        db.flush()

        now = datetime.utcnow()

        # Create 20 leads across various statuses
        for i in range(20):
            status_idx = i % len(STATUSES)
            lead_status = STATUSES[status_idx]

            first = FIRST_NAMES[i]
            last = LAST_NAMES[i]
            full = f"{first} {last}"
            business = BUSINESSES[i]

            # Vary scores
            offer = min(i % 3, 2)
            bottleneck = min((i + 1) % 3, 2)
            buying = min((i + 2) % 3, 2)
            decision = min((i + 3) % 3, 2)
            contact = min((i + 4) % 3, 2)
            strategic = min((i + 5) % 3, 2)

            next_fu = None
            last_contacted = None
            follow_up_count = 0

            if lead_status in ("CONTACTED", "FOLLOW_UP_1", "FOLLOW_UP_2"):
                last_contacted = now - timedelta(days=5 - status_idx)
                follow_up_count = status_idx - 3 if status_idx > 3 else 0
                next_fu = now + timedelta(days=status_idx - 3)

            if lead_status in ("REPLIED", "CALL_BOOKED", "WON", "LOST"):
                last_contacted = now - timedelta(days=3)

            # Make some follow-ups overdue
            if i == 7:
                next_fu = now - timedelta(days=2)  # overdue
            if i == 12:
                next_fu = now - timedelta(hours=6)  # overdue today

            lead = Lead(
                id=str(uuid.uuid4()),
                owner_user_id=user.id,
                first_name=first,
                last_name=last,
                full_name=full,
                business_name=business,
                segment=SEGMENTS[i % 4],
                niche=NICHES[i % len(NICHES)],
                email=f"{first.lower()}.{last.lower()}@example.com",
                contact_path=CONTACT_PATHS[i % 4],
                website_url=f"https://{business.lower().replace(' ', '')}.com",
                location_text=["NYC", "SF", "Austin", "Chicago", "Miami"][i % 5],
                offer_clarity_score=offer,
                bottleneck_evidence_score=bottleneck,
                buying_signal_score=buying,
                decision_maker_access_score=decision,
                contactability_score=contact,
                strategic_fit_score=strategic,
                status=lead_status,
                last_contacted_at=last_contacted,
                follow_up_count=follow_up_count,
                next_follow_up_at=next_fu,
            )
            recalculate_scores(lead)
            db.add(lead)

            # Add an activity for each lead
            db.add(Activity(
                id=str(uuid.uuid4()),
                lead_id=lead.id,
                user_id=user.id,
                activity_type="NOTE",
                body=f"Initial research on {business}",
                occurred_at=now - timedelta(days=7),
            ))

            if lead_status != "NEW":
                db.add(Activity(
                    id=str(uuid.uuid4()),
                    lead_id=lead.id,
                    user_id=user.id,
                    activity_type="STATUS_CHANGE",
                    body=f"Status changed from NEW to {lead_status}",
                    occurred_at=now - timedelta(days=5),
                ))

        db.commit()
        print(f"Seeded demo user ({demo_email}) with 20 leads.")
        print("Login: demo@leveragecrm.com / demo123")

    except Exception as e:
        db.rollback()
        print(f"Seed error: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
