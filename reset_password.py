import sys
from sqlalchemy.orm import Session
from db import SessionLocal
from models import User
from auth import get_password_hash  # uses your app's real hashing method

def main():
    if len(sys.argv) != 3:
        print("Usage: python reset_password.py <email> <new_password>")
        sys.exit(1)

    email = sys.argv[1].strip().lower()
    new_password = sys.argv[2]

    db: Session = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if not user:
            print(f"User not found: {email}")
            sys.exit(2)

        user.hashed_password = get_password_hash(new_password)
        db.add(user)
        db.commit()
        print(f"Password reset OK for: {email}")
    finally:
        db.close()

if __name__ == "__main__":
    main()
