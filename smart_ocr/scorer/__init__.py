"""
Modulo scoring CBCL 6-18 per Smart OCR.

Uso:
    from scorer.cbcl_scorer import CBCLScorer, Compilatore
"""

from .cbcl_scorer import (
    CBCLScorer,
    CBCLProfile,
    Compilatore,
    ScaleResult,
    ALL_ITEMS,
    SYNDROME_SCALES,
    DSM_SCALES,
    BROADBAND_COMPONENTS,
    OTHER_PROBLEMS,
    T_THRESHOLDS,
    all_cbcl_items,
    item_to_excel_row,
)
from .scale_colors import (
    SCALE_COLORS, ITEM_TO_SCALE, SYNDROME_ORDER,
    load_italian_questions, build_report_finale,
)
