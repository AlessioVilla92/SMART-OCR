"""
Script per processare TEST4 con tutti i modelli (A, B, C) ed esportare
i risultati in formato Markdown domanda-risposta.

Replica la pipeline di app.py:
1. Boundary detection
2. Perspective correction A4
3. Preprocessing (shadow removal + denoise + CLAHE)
4. SIFT+ECC alignment al template
5. Classificazione celle
"""

import sys
import os
from pathlib import Path

# Setup paths
SMART_OCR_DIR = Path(__file__).parent / "smart_ocr"
sys.path.insert(0, str(SMART_OCR_DIR))
os.chdir(str(SMART_OCR_DIR))

import cv2
import numpy as np
from config import Config, ClassificationMode
from core.preprocessor import preprocess_full_pipeline, load_image
from core.boundary_detector import detect_document_boundary, warp_to_a4
from core.template_aligner import TemplateAligner
from core.grid_extractor import extract_all_cells
from core.omr_classifier import classify_all_items_omr, classify_all_items_baseline
from core.classifier import get_classifier
from core.scorer import build_score_report, ALL_ITEMS, CBCL_SUBSCALES
from datetime import datetime

# Mapping immagini -> pagine
TEST4_DIR = Path(__file__).parent / "test4"
IMAGES = [
    ("WhatsApp Image 2026-04-03 at 13.00.26 (2).jpeg", "page_4"),
    ("WhatsApp Image 2026-04-03 at 13.00.26 (1).jpeg", "page_5"),
    ("WhatsApp Image 2026-04-03 at 13.00.26.jpeg", "page_6"),
]

MODES = {
    "Mode A (SVM)": "svm",
    "Mode B (YOLO)": "yolo",
    "Mode C (Ensemble)": "ensemble",
}


def get_aligner():
    aligner = TemplateAligner()
    for page in ["page_4", "page_5", "page_6"]:
        try:
            aligner.load_reference(page)
        except FileNotFoundError:
            pass
    return aligner


def preprocess_photo(img_path: str, page: str, aligner: TemplateAligner):
    """
    Pipeline completa preprocessing foto (fasi 1-4 di app.py).
    Ritorna (gray_aligned, align_info, ref_for_extraction).
    """
    # Fase 1: Boundary detection
    img = load_image(img_path)
    corners = None
    try:
        corners, conf, det_method = detect_document_boundary(img)
        h_img, w_img = img.shape[:2]
        margin = 5
        on_edge = any(
            c[0] < margin or c[1] < margin or
            c[0] > w_img - margin or c[1] > h_img - margin
            for c in corners
        )
        if on_edge or conf < 0.5:
            corners = None
    except Exception:
        corners = None

    # Fase 2: Perspective correction
    if corners is not None:
        warped = warp_to_a4(img, corners)
    else:
        warped = img

    # Fase 3: Preprocessing
    gray, meta = preprocess_full_pipeline(warped, debug=False)

    # Fase 4: SIFT+ECC alignment
    aligned, align_info = aligner.align(gray, page)
    if align_info.get("aligned"):
        gray = aligned

    ref_for_extraction = aligner._references.get(page) if align_info.get("aligned") else None

    return gray, align_info, ref_for_extraction


def classify_with_method(method: str, cells_dict: dict, ref_cells: dict = None, primary_results: dict = None):
    """Classifica le celle con il metodo specificato."""
    if method == "svm":
        classifier = get_classifier()
        results = {}
        for item_id, item_cells in cells_dict.items():
            results[item_id] = classifier.predict_item_cells(item_cells)
    elif method == "yolo":
        from pipeline.mode_b.yolo_classifier import YOLOClassifier
        yolo_clf = YOLOClassifier()
        results = {}
        for item_id, item_cells in cells_dict.items():
            results[item_id] = yolo_clf.predict_item_cells(item_cells)
    elif method == "ensemble":
        from pipeline.ensemble_classifier import EnsembleClassifier
        ens_clf = EnsembleClassifier()
        results = {}
        for item_id, item_cells in cells_dict.items():
            results[item_id] = ens_clf.predict_item_cells(item_cells)
    else:
        results = classify_all_items_omr(cells_dict)

    # Baseline fallback per recuperare items falliti
    if ref_cells is not None:
        baseline_results = classify_all_items_baseline(cells_dict, ref_cells)
        for item_id, primary in results.items():
            fallback = baseline_results.get(item_id, {})
            pv = primary.get("value")
            pf = primary.get("flag")
            fv = fallback.get("value")
            ff = fallback.get("flag")
            if pv is None or pf in ("missing", "multiple_marks", "ambiguous"):
                if fv is not None and ff in (None, "low_confidence", "multiple_marks"):
                    results[item_id] = fallback

    return results


def process_all_modes():
    """Processa TEST4 con tutti i modelli. Preprocessing fatto una sola volta."""
    aligner = get_aligner()
    results = {}

    # Preprocessing una sola volta per tutte le pagine
    print("Preprocessing foto (boundary + perspective + SIFT alignment)...")
    preprocessed = {}
    for img_name, page in IMAGES:
        img_path = str(TEST4_DIR / img_name)
        print(f"  -> {page}: {img_name}")
        gray, align_info, ref = preprocess_photo(img_path, page, aligner)
        aligned = align_info.get("aligned", False)
        print(f"     Aligned: {aligned}")

        # Estrai celle (uguale per tutti i metodi)
        cells_dict = extract_all_cells(gray, page, ref_img=ref)

        # Estrai celle reference per baseline fallback
        ref_cells = extract_all_cells(ref, page) if ref is not None else None

        preprocessed[page] = (cells_dict, ref_cells)

    # Classificazione con ciascun metodo
    for mode_name, method in MODES.items():
        print(f"\n{'='*60}")
        print(f"Classificazione con {mode_name}...")
        print(f"{'='*60}")

        all_classification = {}
        for img_name, page in IMAGES:
            cells_dict, ref_cells = preprocessed[page]
            print(f"  -> {page}...")
            try:
                classification = classify_with_method(method, cells_dict, ref_cells)
                for item_id, item_data in classification.items():
                    all_classification[item_id] = item_data
                print(f"     OK ({len(classification)} items)")
            except Exception as e:
                print(f"     ERROR: {e}")
                import traceback
                traceback.print_exc()

        # Build combined report
        combined = build_score_report(all_classification, session_id=f"test4_{method}")
        combined["_method"] = method
        results[mode_name] = combined
        print(f"  Total score: {combined['total_score']}")
        print(f"  Items scored: {combined['statistics']['items_scored']}/{combined['statistics']['items_total']}")

    return results


def export_markdown(results: dict):
    """Esporta i risultati in formato Markdown domanda-risposta."""
    lines = []
    lines.append("# SMART-OCR - Risultati Scansione TEST4")
    lines.append("")
    lines.append(f"**Data scansione:** {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"**Immagini:** test4/ (3 foto WhatsApp del 03/04/2026)")
    lines.append(f"**Modelli testati:** Mode A (SVM), Mode B (YOLO), Mode C (Ensemble)")
    lines.append("")

    # ---------- Riepilogo generale ----------
    lines.append("---")
    lines.append("")
    lines.append("## Riepilogo Generale")
    lines.append("")
    lines.append("| Domanda | Mode A (SVM) | Mode B (YOLO) | Mode C (Ensemble) |")
    lines.append("|---------|:---:|:---:|:---:|")

    mode_names = list(results.keys())

    scores = [str(results[m]["total_score"]) for m in mode_names]
    lines.append(f"| **Score Totale** | {' | '.join(scores)} |")

    scored = [f"{results[m]['statistics']['items_scored']}/{results[m]['statistics']['items_total']}" for m in mode_names]
    lines.append(f"| **Items classificati** | {' | '.join(scored)} |")

    missing = [str(results[m]['statistics']['items_missing']) for m in mode_names]
    lines.append(f"| **Items mancanti** | {' | '.join(missing)} |")

    flagged = [str(results[m]['statistics']['items_flagged']) for m in mode_names]
    lines.append(f"| **Items con flag** | {' | '.join(flagged)} |")

    conf = [f"{results[m]['statistics']['mean_confidence']:.3f}" for m in mode_names]
    lines.append(f"| **Confidence media** | {' | '.join(conf)} |")

    lines.append("")

    # ---------- Subscale ----------
    lines.append("## Subscale DSM-Oriented")
    lines.append("")
    lines.append("| Subscale | Mode A (SVM) | Mode B (YOLO) | Mode C (Ensemble) |")
    lines.append("|----------|:---:|:---:|:---:|")

    for subscale in CBCL_SUBSCALES:
        vals = []
        for m in mode_names:
            ss = results[m]["subscale_scores"].get(subscale, {})
            score = ss.get("score", 0)
            miss = ss.get("items_missing", 0)
            if miss > 0:
                vals.append(f"{score} ({miss} miss)")
            else:
                vals.append(str(score))
        lines.append(f"| **{subscale.replace('_', ' ')}** | {' | '.join(vals)} |")

    lines.append("")

    # ---------- Dettaglio per item ----------
    lines.append("## Dettaglio Item-per-Item (Domanda - Risposta)")
    lines.append("")
    lines.append("Legenda valori: **0** = Non vero, **1** = Qualche volta vero, **2** = Molto vero, **-** = Mancante/Non processato")
    lines.append("")
    lines.append("| Item | Mode A (SVM) | Mode B (YOLO) | Mode C (Ensemble) | Concordanza |")
    lines.append("|------|:---:|:---:|:---:|:---:|")

    discordant_items = []

    for item_id in ALL_ITEMS:
        vals = []
        raw_vals = []
        for m in mode_names:
            item_data = results[m]["items"].get(item_id, {})
            v = item_data.get("value")
            flag = item_data.get("flag", "")
            conf_val = item_data.get("confidence", 0)

            if v is not None:
                raw_vals.append(v)
                flag_mark = ""
                if flag and flag not in ("missing",):
                    flag_mark = f" [{flag}]"
                vals.append(f"{v}{flag_mark}")
            else:
                raw_vals.append(None)
                vals.append("-")

        # Concordanza
        non_none = [v for v in raw_vals if v is not None]
        if len(non_none) >= 2 and len(set(non_none)) == 1:
            concordance = "OK"
        elif len(non_none) >= 2 and len(set(non_none)) > 1:
            concordance = "DIFF"
            discordant_items.append(item_id)
        else:
            concordance = "-"

        lines.append(f"| **{item_id}** | {' | '.join(vals)} | {concordance} |")

    lines.append("")

    # ---------- Items discordanti ----------
    if discordant_items:
        lines.append("## Items Discordanti tra Modelli")
        lines.append("")
        lines.append(f"**{len(discordant_items)} item(s)** con valori diversi tra i modelli:")
        lines.append("")
        for item_id in discordant_items:
            vals_detail = []
            for m in mode_names:
                item_data = results[m]["items"].get(item_id, {})
                v = item_data.get("value", "-")
                c = item_data.get("confidence", 0)
                vals_detail.append(f"{m}: **{v}** (conf: {c:.3f})")
            lines.append(f"- Item **{item_id}**: {' | '.join(vals_detail)}")
        lines.append("")

    # ---------- Items con flag ----------
    lines.append("## Items con Flag (per modello)")
    lines.append("")
    for m in mode_names:
        flags = results[m].get("flags", [])
        lines.append(f"### {m}")
        if flags:
            for f in flags:
                lines.append(f"- Item **{f['item']}**: `{f['flag']}`")
        else:
            lines.append("- Nessun flag")
        lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    print("SMART-OCR - Test4 Full Scan (tutti i modelli)")
    print("=" * 60)

    results = process_all_modes()

    md_content = export_markdown(results)

    output_path = Path(__file__).parent / "test4_risultati.md"
    output_path.write_text(md_content, encoding="utf-8")
    print(f"\nRisultati esportati in: {output_path}")
    print("Done!")
