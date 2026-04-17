#!/usr/bin/env python3
"""
CLI script to create a user in the database.

Usage:
    python scripts/create_user.py <username> <password> [--admin]
"""

import argparse
import sys
from pathlib import Path

# Ensure backend package is importable
sys.path.insert(0, str(Path(__file__).parent.parent))

from smart_ocr_backend.db.init_db import init_db
from smart_ocr_backend.db.session import SessionLocal
from smart_ocr_backend.db.models import User, UserRole
from smart_ocr_backend.security import hash_password


def main():
    parser = argparse.ArgumentParser(description="Create a Smart OCR user")
    parser.add_argument("username", help="Username")
    parser.add_argument("password", help="Password")
    parser.add_argument("--admin", action="store_true", help="Grant admin role")
    args = parser.parse_args()

    init_db()

    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.username == args.username).first()
        if existing:
            print(f"User '{args.username}' already exists (id={existing.id})")
            sys.exit(1)

        user = User(
            username=args.username,
            password_hash=hash_password(args.password),
            role=UserRole.admin if args.admin else UserRole.clinician,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        print(f"User created: {user.username} (id={user.id}, role={user.role.value})")
    finally:
        db.close()


if __name__ == "__main__":
    main()
