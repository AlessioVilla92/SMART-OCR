"""
scorer/cbcl_scorer.py

Wrapper: re-export dello scoring CBCL da core.scorer.
Condiviso tra Mode A e Mode B.
"""

from core.scorer import (
    build_score_report,
    report_to_csv,
    report_to_json,
    ALL_ITEMS,
    CBCL_SUBSCALES,
)

__all__ = [
    "build_score_report",
    "report_to_csv",
    "report_to_json",
    "ALL_ITEMS",
    "CBCL_SUBSCALES",
]
