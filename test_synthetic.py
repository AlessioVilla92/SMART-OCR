"""
Test SMART-OCR pipeline on CBCL_synthetic_10sets.pdf
Tests both PDF mode (Mode D) and SVM mode (Mode A) on 10 synthetic sets.
"""

import sys
import json
import fitz  # PyMuPDF
import numpy as np
import cv2
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "smart_ocr"))

from pipeline.engine import OCREngine
from config import ClassificationMode
from core.scorer import ALL_ITEMS

PDF_PATH = "CBCL_synthetic_10sets.pdf"
PAGES_PER_SET = 3
PAGE_NAMES = ["page_4", "page_5", "page_6"]
TARGET_W, TARGET_H = 2480, 3508


def pdf_page_to_gray(doc, page_idx, dpi=300):
    """Convert a PDF page to a grayscale numpy array at A4 target size."""
    pix = doc[page_idx].get_pixmap(dpi=dpi)
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.h, pix.w, pix.n)
    if pix.n >= 3:
        gray = cv2.cvtColor(img[:, :, :3], cv2.COLOR_RGB2GRAY)
    else:
        gray = img
    return cv2.resize(gray, (TARGET_W, TARGET_H), interpolation=cv2.INTER_AREA)


def test_mode(engine, doc, mode_label):
    """Test a mode on all 10 sets."""
    n_sets = len(doc) // PAGES_PER_SET
    all_results = []

    print(f"\n{'=' * 75}")
    print(f"  TEST: {mode_label}")
    print(f"  Engine mode: {engine.mode.value}, active: {engine.get_active_method()}")
    print(f"{'=' * 75}")

    for set_idx in range(n_sets):
        set_classification = {}
        set_ambiguous = 0

        for page_offset, page_name in enumerate(PAGE_NAMES):
            pdf_page_idx = set_idx * PAGES_PER_SET + page_offset
            gray = pdf_page_to_gray(doc, pdf_page_idx)

            report = engine.process_page(
                gray, page=page_name,
                session_id=f"syn_set{set_idx + 1}"
            )

            for item_id, item_data in report["items"].items():
                if item_data.get("value") is not None or item_data.get("flag") != "not_processed":
                    set_classification[item_id] = item_data

            set_ambiguous += report["statistics"]["items_ambiguous"]

        # Calculate total score
        total_score = sum(
            d["value"] for d in set_classification.values()
            if d.get("value") is not None
        )
        scored = sum(1 for d in set_classification.values() if d.get("value") is not None)
        flagged = sum(1 for d in set_classification.values() if d.get("flag") and d["flag"] != "not_processed")

        all_results.append({
            "set": set_idx + 1,
            "total_score": total_score,
            "items_scored": scored,
            "items_ambiguous": set_ambiguous,
            "items_flagged": flagged
        })

    # Summary
    print(f"\n{'Set':<5} {'Score':<7} {'Scored':<8} {'Ambig':<7} {'Flagged':<8}")
    print("-" * 40)
    for r in all_results:
        print(f"{r['set']:<5} {r['total_score']:<7} {r['items_scored']:<8} "
              f"{r['items_ambiguous']:<7} {r['items_flagged']:<8}")

    total_scored = sum(r["items_scored"] for r in all_results)
    total_possible = n_sets * len(ALL_ITEMS)
    total_ambig = sum(r["items_ambiguous"] for r in all_results)
    total_flagged = sum(r["items_flagged"] for r in all_results)

    print(f"\nTotals: {total_scored}/{total_possible} scored ({total_scored/total_possible*100:.1f}%), "
          f"{total_ambig} ambig, {total_flagged} flagged")

    return all_results


def test_process_pdf():
    """Test the new process_pdf() convenience method."""
    print(f"\n{'=' * 75}")
    print(f"  TEST: process_pdf() (single-call full PDF processing)")
    print(f"{'=' * 75}")

    engine = OCREngine(ClassificationMode.MODE_D_PDF)

    doc = fitz.open(PDF_PATH)
    n_sets = len(doc) // PAGES_PER_SET
    doc.close()

    # Test on first set (pages 0-2)
    # process_pdf processes pages 0,1,2 of the given PDF
    # For multi-set PDFs, we'd need to split. Test on a conceptual level.
    print("\n  Testing process_pdf on full PDF (first 3 pages = set 1):")
    report = engine.process_pdf(PDF_PATH, session_id="pdf_test")

    stats = report["statistics"]
    print(f"    Total score: {report['total_score']}")
    print(f"    Items scored: {stats['items_scored']}/{stats['items_total']}")
    print(f"    Items ambiguous: {stats['items_ambiguous']}")
    print(f"    Processing time: {report['_processing_time_ms']}ms")
    print(f"    Method: {report['_method']}")
    print(f"    Pages processed: {report.get('_pages_processed', 'N/A')}")

    return report


def run_test():
    doc = fitz.open(PDF_PATH)
    print(f"PDF: {PDF_PATH} - {len(doc)} pages, {len(doc) // PAGES_PER_SET} sets")

    # Test 1: PDF Mode (Mode D) - new optimized mode
    engine_pdf = OCREngine(ClassificationMode.MODE_D_PDF)
    results_pdf = test_mode(engine_pdf, doc, "Mode D - PDF (OMR ottimizzato)")

    # Test 2: SVM Mode (Mode A) - existing mode
    engine_svm = OCREngine(ClassificationMode.MODE_A_SVM)
    results_svm = test_mode(engine_svm, doc, "Mode A - SVM")

    doc.close()

    # Test 3: process_pdf() method
    report_pdf = test_process_pdf()

    # Comparison
    print(f"\n{'=' * 75}")
    print("COMPARISON: PDF Mode vs SVM Mode")
    print(f"{'=' * 75}")
    print(f"{'Set':<5} {'PDF Score':<10} {'PDF Scored':<11} {'SVM Score':<10} {'SVM Scored':<11}")
    print("-" * 50)
    for rp, rs in zip(results_pdf, results_svm):
        print(f"{rp['set']:<5} {rp['total_score']:<10} {rp['items_scored']:<11} "
              f"{rs['total_score']:<10} {rs['items_scored']:<11}")

    # Save results
    output = {
        "pdf_mode": results_pdf,
        "svm_mode": results_svm
    }
    with open("test_synthetic_results.json", "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"\nResults saved to test_synthetic_results.json")


if __name__ == "__main__":
    run_test()
