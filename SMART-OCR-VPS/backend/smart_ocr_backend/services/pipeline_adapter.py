"""
Pipeline adapter — bridge between OCREngine and the REST API.

Adds smart_ocr/ to sys.path and calls the real pipeline.
All imports from smart_ocr happen inside functions to avoid
import-time side effects.
"""

import os
import sys
from pathlib import Path
from typing import Callable, Optional

from smart_ocr_backend.settings import settings

# Ensure smart_ocr is importable
_smart_ocr_dir = str(settings.smart_ocr_dir.resolve())
if _smart_ocr_dir not in sys.path:
    sys.path.insert(0, _smart_ocr_dir)


def _get_compilatore(comp_str: str):
    from scorer.cbcl_scorer import Compilatore
    return Compilatore.PADRE if comp_str == "PD" else Compilatore.MADRE


def _serialize_report(report: dict, compilatore="MD", sex=None, age=None) -> dict:
    """Extract profile, build report_finale, return serializable dict."""
    from scorer.scale_colors import build_report_finale
    from core.scorer import build_score_report

    profile = report.pop("_profile", None)
    scoring = profile.to_dict() if profile else {}
    report_finale = build_report_finale(report)

    from pipeline.engine import OCREngine
    OCREngine.clear_cache()

    return {
        "items": report.get("items", {}),
        "scoring": scoring,
        "report_finale": report_finale,
        "subscale_scores": report.get("subscale_scores", {}),
        "total_score": report.get("total_score", 0),
        "statistics": report.get("statistics", {}),
        "compilatore": report.get("compilatore", compilatore),
        "method": report.get("_method"),
        "processing_time_ms": report.get("_processing_time_ms"),
    }


def run_pipeline(
    work_dir: Path,
    mode_str: str,
    progress_cb: Optional[Callable] = None,
    compilatore: str = "MD",
    sex: Optional[str] = None,
    age: Optional[int] = None,
) -> dict:
    """
    Run the full OCR pipeline on uploaded photos.
    """
    from config import ClassificationMode
    from pipeline.engine import OCREngine

    mode_map = {
        "svm": ClassificationMode.MODE_A_SVM,
        "yolo": ClassificationMode.MODE_B_YOLO,
        "ensemble": ClassificationMode.MODE_C_ENSEMBLE,
    }
    mode = mode_map.get(mode_str, ClassificationMode.MODE_C_ENSEMBLE)

    if progress_cb:
        progress_cb("Inizializzazione...", 0.05)

    engine = OCREngine(mode)

    # Find uploaded page files
    photo_paths = {}
    for page_num in (4, 5, 6):
        page_key = f"page_{page_num}"
        matches = list(work_dir.glob(f"{page_key}.*"))
        if not matches:
            raise FileNotFoundError(f"{page_key} not found in {work_dir}")
        photo_paths[page_key] = str(matches[0])

    if progress_cb:
        progress_cb("Elaborazione immagini...", 0.10)

    report = engine.process_photos(photo_paths=photo_paths)

    if progress_cb:
        progress_cb("Calcolo punteggi...", 0.95)

    return _serialize_report(report, compilatore, sex, age)


def run_pdf_pipeline(
    pdf_path: Path,
    mode_str: str,
    compilatore: str = "MD",
    sex: Optional[str] = None,
    age: Optional[int] = None,
    progress_cb: Optional[Callable] = None,
) -> dict:
    """
    Run OCR pipeline on a PDF file (3 pages = 1 CBCL questionnaire).
    """
    from config import ClassificationMode
    from pipeline.engine import OCREngine

    mode_map = {
        "svm": ClassificationMode.MODE_A_SVM,
        "yolo": ClassificationMode.MODE_B_YOLO,
        "ensemble": ClassificationMode.MODE_C_ENSEMBLE,
        "pdf": ClassificationMode.MODE_D_PDF,
    }
    mode = mode_map.get(mode_str, ClassificationMode.MODE_C_ENSEMBLE)

    if progress_cb:
        progress_cb("Apertura PDF...", 0.05)

    engine = OCREngine(mode)

    if progress_cb:
        progress_cb("Analisi pagine PDF...", 0.10)

    report = engine.process_pdf(str(pdf_path))

    if progress_cb:
        progress_cb("Calcolo punteggi...", 0.95)

    return _serialize_report(report, compilatore, sex, age)
