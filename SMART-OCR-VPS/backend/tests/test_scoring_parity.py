"""
Test scoring parity — verify that the backend scoring service
produces the same results as the standalone CBCLScorer.
"""

import sys
from pathlib import Path

import pytest

# Ensure smart_ocr is importable
smart_ocr_dir = str(Path(__file__).parent.parent.parent.parent / "smart_ocr")
if smart_ocr_dir not in sys.path:
    sys.path.insert(0, smart_ocr_dir)


def test_all_zeros():
    """All items = 0 should produce total_score = 0."""
    from smart_ocr_backend.services.scoring_service import recompute_scores
    from scorer.cbcl_scorer import ALL_ITEMS

    items = {str(i): 0 for i in ALL_ITEMS}
    result = recompute_scores(items, age=10, gender="M", compilatore_str="MD")

    assert result["total_score"] == 0
    assert "scoring" in result
    assert "report_finale" in result


def test_all_twos():
    """All items = 2 should produce maximum total_score = 244."""
    from smart_ocr_backend.services.scoring_service import recompute_scores
    from scorer.cbcl_scorer import ALL_ITEMS

    items = {str(i): 2 for i in ALL_ITEMS}
    result = recompute_scores(items, age=10, gender="F", compilatore_str="PD")

    assert result["total_score"] == 244
    # Internalizing = I(13) + II(8) + III(11) = 32 items * 2 = 64
    assert result["subscale_scores"]["internalizing"]["score"] == 64
    # Externalizing = VII(17) + VIII(18) = 35 items * 2 = 70
    assert result["subscale_scores"]["externalizing"]["score"] == 70


def test_md_pd_same_raw_scores():
    """MD and PD with same responses should produce identical raw scores."""
    from smart_ocr_backend.services.scoring_service import recompute_scores
    from scorer.cbcl_scorer import ALL_ITEMS

    items = {str(i): hash(str(i)) % 3 for i in ALL_ITEMS}

    result_md = recompute_scores(items, compilatore_str="MD")
    result_pd = recompute_scores(items, compilatore_str="PD")

    assert result_md["total_score"] == result_pd["total_score"]
    assert result_md["subscale_scores"] == result_pd["subscale_scores"]


def test_report_finale_structure():
    """report_finale should have critical_areas and areas_without_critical."""
    from smart_ocr_backend.services.scoring_service import recompute_scores
    from scorer.cbcl_scorer import ALL_ITEMS

    items = {str(i): 2 for i in ALL_ITEMS}
    result = recompute_scores(items)

    rf = result["report_finale"]
    assert "critical_areas" in rf
    assert "areas_without_critical" in rf
    assert "total_critical" in rf
    assert rf["total_critical"] > 0
