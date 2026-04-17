"""
ORM models — User and Job tables.

Zero clinical data stored. Only auth metadata and job lifecycle.
"""

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column, Integer, String, Boolean, Float, Text,
    DateTime, ForeignKey, Enum as SAEnum,
)
from sqlalchemy.orm import relationship

from smart_ocr_backend.db.session import Base


class UserRole(str, enum.Enum):
    admin = "admin"
    clinician = "clinician"


class JobStatus(str, enum.Enum):
    queued = "queued"
    processing = "processing"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


def _utcnow():
    return datetime.now(timezone.utc)


def _new_uuid():
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(64), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(SAEnum(UserRole), default=UserRole.clinician, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    last_login = Column(DateTime(timezone=True), nullable=True)

    jobs = relationship("Job", back_populates="user")


class Job(Base):
    __tablename__ = "jobs"

    id = Column(String(36), primary_key=True, default=_new_uuid)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    status = Column(SAEnum(JobStatus), default=JobStatus.queued, nullable=False)
    mode = Column(String(16), nullable=False, default="ensemble")
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    duration_seconds = Column(Float, nullable=True)
    error_message = Column(Text, nullable=True)
    current_step = Column(String(64), nullable=True)
    progress = Column(Float, default=0.0)

    user = relationship("User", back_populates="jobs")
