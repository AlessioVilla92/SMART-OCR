"""Pydantic schemas for scoring recompute."""

from typing import Optional, Any

from pydantic import BaseModel


class RecomputeRequest(BaseModel):
    items: dict[str, int]  # {item_id: 0|1|2}
    age: Optional[int] = None
    gender: Optional[str] = None  # "M" or "F"
    compilatore: str = "MD"  # "MD" or "PD"


class RecomputeResponse(BaseModel):
    scoring: dict[str, Any]
    report_finale: dict[str, Any]
    subscale_scores: dict[str, Any]
    total_score: int
    statistics: dict[str, Any]
