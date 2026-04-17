"""Pydantic schemas for jobs."""

from datetime import datetime
from typing import Optional, Any

from pydantic import BaseModel


class JobCreate(BaseModel):
    mode: str = "ensemble"


class JobStatus(BaseModel):
    job_id: str
    status: str
    progress: float = 0.0
    current_step: Optional[str] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    error_message: Optional[str] = None

    model_config = {"from_attributes": True}


class JobResult(BaseModel):
    job_id: str
    items: dict[str, Any]
    scoring: dict[str, Any]
    report_finale: dict[str, Any]
    subscale_scores: dict[str, Any]
    total_score: int
    statistics: dict[str, Any]
    method: Optional[str] = None
    processing_time_ms: Optional[int] = None
