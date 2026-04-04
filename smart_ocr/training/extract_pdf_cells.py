"""
training/extract_pdf_cells.py

Estrae celle dai PDF sintetici e le salva nel dataset di training.
Usa la classificazione PDF (winner-takes-all) come ground truth.
Le celle marcate vanno in binary_generated/segnato/
Le celle vuote vanno in binary_generated/vuoto/

Uso:
    python training/extract_pdf_cells.py [path_pdf]

Default: cerca CBCL_synthetic_10sets.pdf nella root del progetto.
"""

import sys
import cv2
import numpy as np
from pathlib import Path

try:
    import fitz
except ImportError:
    print("PyMuPDF necessario: pip install pymupdf")
    sys.exit(1)

_PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from core.grid_extractor import extract_all_cells
from core.omr_classifier import count_dark_pixels
from config import Config


# Output directories
SEGNATO_DIR = _PROJECT_ROOT / "data" / "binary_generated" / "segnato"
VUOTO_DIR = _PROJECT_ROOT / "data" / "binary_generated" / "vuoto"

TARGET_W, TARGET_H = 2480, 3508
PAGE_NAMES = ["page_4", "page_5", "page_6"]


def classify_cell_for_training(cells: dict) -> dict:
    """
    Classifica le 3 celle di un item per generare ground truth.
    La cella con ratio massimo = segnato, le altre = vuoto.
    Restituisce solo se il winner e chiaro (gap > 5%).
    """
    ratios = {}
    for col, cell in cells.items():
        _, ratio = count_dark_pixels(cell)
        ratios[col] = ratio

    sorted_cols = sorted(ratios.items(), key=lambda x: x[1], reverse=True)
    best_col, best_r = sorted_cols[0]
    second_col, second_r = sorted_cols[1]

    if best_r < 0.06:
        return None  # all empty, skip

    gap = (best_r - second_r) / best_r if best_r > 0 else 0
    if gap < 0.05:
        return None  # too ambiguous for training

    labels = {}
    for col in cells:
        labels[col] = "segnato" if col == best_col else "vuoto"
    return labels


def extract_from_pdf(pdf_path: str):
    """Estrae tutte le celle da un PDF e le salva nel dataset."""
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        print(f"File non trovato: {pdf_path}")
        return

    SEGNATO_DIR.mkdir(parents=True, exist_ok=True)
    VUOTO_DIR.mkdir(parents=True, exist_ok=True)

    # Conta file esistenti per non sovrascrivere
    existing_segnato = len(list(SEGNATO_DIR.glob("pdf_*.png")))
    existing_vuoto = len(list(VUOTO_DIR.glob("pdf_*.png")))
    seg_idx = existing_segnato
    vuo_idx = existing_vuoto

    doc = fitz.open(str(pdf_path))
    n_pages = len(doc)
    n_sets = n_pages // len(PAGE_NAMES)

    print(f"PDF: {pdf_path.name} — {n_pages} pagine, {n_sets} set")
    print(f"Output: {SEGNATO_DIR.parent}")
    print(f"Celle esistenti: segnato={existing_segnato}, vuoto={existing_vuoto}")

    total_segnato = 0
    total_vuoto = 0
    total_skipped = 0

    for set_idx in range(n_sets):
        for page_offset, page_name in enumerate(PAGE_NAMES):
            pdf_page_idx = set_idx * len(PAGE_NAMES) + page_offset

            # Render pagina
            pix = doc[pdf_page_idx].get_pixmap(dpi=Config.PDF_RENDER_DPI)
            img = np.frombuffer(
                pix.samples, dtype=np.uint8
            ).reshape(pix.h, pix.w, pix.n)
            gray = cv2.cvtColor(img[:, :, :3], cv2.COLOR_RGB2GRAY)
            gray = cv2.resize(gray, (TARGET_W, TARGET_H), interpolation=cv2.INTER_AREA)

            # Estrai celle
            cells_dict = extract_all_cells(gray, page_name)

            for item_id, item_cells in cells_dict.items():
                labels = classify_cell_for_training(item_cells)
                if labels is None:
                    total_skipped += 1
                    continue

                for col, label in labels.items():
                    cell_img = item_cells[col]
                    if label == "segnato":
                        path = SEGNATO_DIR / f"pdf_s{set_idx:02d}_{page_name}_i{item_id}_c{col}.png"
                        cv2.imwrite(str(path), cell_img)
                        seg_idx += 1
                        total_segnato += 1
                    else:
                        path = VUOTO_DIR / f"pdf_s{set_idx:02d}_{page_name}_i{item_id}_c{col}.png"
                        cv2.imwrite(str(path), cell_img)
                        vuo_idx += 1
                        total_vuoto += 1

        print(f"  Set {set_idx + 1}/{n_sets}: +{total_segnato} segnato, +{total_vuoto} vuoto")

    doc.close()

    print(f"\nEstratte: {total_segnato} segnato + {total_vuoto} vuoto = {total_segnato + total_vuoto}")
    print(f"Skippate (ambigue): {total_skipped}")
    print(f"Totale dataset: segnato={seg_idx}, vuoto={vuo_idx}")


if __name__ == "__main__":
    pdf = sys.argv[1] if len(sys.argv) > 1 else str(
        _PROJECT_ROOT.parent / "CBCL_synthetic_10sets.pdf"
    )
    extract_from_pdf(pdf)
