"""
Scoring service — recompute CBCL scores from edited item values.

No ML involved, just arithmetic. Should complete in <500ms.
"""

import sys
from pathlib import Path

from smart_ocr_backend.settings import settings

# Ensure smart_ocr is importable
_smart_ocr_dir = str(settings.smart_ocr_dir.resolve())
if _smart_ocr_dir not in sys.path:
    sys.path.insert(0, _smart_ocr_dir)


def recompute_scores(
    items: dict,
    age: int = None,
    gender: str = None,
    compilatore_str: str = "MD",
) -> dict:
    """
    Recompute CBCL scores from a dict of item values.

    Args:
        items: {item_id_str: 0|1|2}
        age: child age (6-18)
        gender: "M" or "F"
        compilatore_str: "MD" (madre) or "PD" (padre)

    Returns:
        Dict with scoring, report_finale, subscale_scores, total_score, statistics.
    """
    from scorer.cbcl_scorer import CBCLScorer, Compilatore
    from core.scorer import build_score_report
    from scorer.scale_colors import build_report_finale

    compilatore = Compilatore.MADRE if compilatore_str == "MD" else Compilatore.PADRE

    # Build classification_results format expected by build_score_report
    classification_results = {}
    for item_key, value in items.items():
        classification_results[str(item_key)] = {
            "value": int(value),
            "confidence": 1.0,
            "flag": None,
        }

    # Use the same scoring path as the pipeline
    report = build_score_report(
        classification_results,
        compilatore=compilatore,
        sex=gender,
        age=age,
    )

    profile = report.pop("_profile", None)
    scoring = profile.to_dict() if profile else {}
    report_finale = build_report_finale(report)

    return {
        "scoring": scoring,
        "report_finale": report_finale,
        "subscale_scores": report.get("subscale_scores", {}),
        "total_score": report.get("total_score", 0),
        "statistics": report.get("statistics", {}),
    }
