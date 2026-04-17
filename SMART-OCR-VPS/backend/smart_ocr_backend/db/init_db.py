"""
Initialize the database — create all tables.
"""

from smart_ocr_backend.db.session import engine, Base
from smart_ocr_backend.db import models  # noqa: F401 — registers models


def init_db(bind=None):
    """Create all tables if they don't exist."""
    Base.metadata.create_all(bind=bind or engine)


if __name__ == "__main__":
    init_db()
    print("Database initialized.")
