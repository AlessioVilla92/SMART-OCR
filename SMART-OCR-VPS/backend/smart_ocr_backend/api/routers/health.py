"""
Health check router — unauthenticated liveness probe.
"""

import sys
from pathlib import Path

from fastapi import APIRouter

from smart_ocr_backend.settings import settings

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check():
    """Returns API status, available models, and template status."""
    smart_ocr_dir = settings.smart_ocr_dir

    models_dir = smart_ocr_dir / "models"
    templates_dir = smart_ocr_dir / "templates"

    svm_available = (
        (models_dir / "svm_classifier.pkl").exists()
        or (models_dir / "model.pkl").exists()
    )
    yolo_available = (models_dir / "yolo_cbcl.onnx").exists()

    templates_ok = all(
        (templates_dir / f"cbcl_page_{p}_ref.png").exists()
        for p in (4, 5, 6)
    )
    grid_ok = (templates_dir / "cbcl_grid.json").exists()

    return {
        "status": "ok",
        "version": "6.0.0",
        "models": {
            "svm": svm_available,
            "yolo_onnx": yolo_available,
        },
        "templates": {
            "references": templates_ok,
            "grid": grid_ok,
        },
        "smart_ocr_dir": str(smart_ocr_dir),
    }


@router.get("/questions")
def get_questions():
    """Return Italian CBCL question texts for all 122 items."""
    import json
    questions_path = settings.smart_ocr_dir / "resources" / "cbcl_questions_it.json"
    if not questions_path.exists():
        return {"questions": {}}
    data = json.loads(questions_path.read_text(encoding="utf-8"))
    # Flatten pages into single dict
    flat = {}
    for page_data in data.values():
        if isinstance(page_data, dict):
            flat.update(page_data)
    return {"questions": flat}
