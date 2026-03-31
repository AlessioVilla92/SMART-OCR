"""
scripts/calibrate_from_pdf_definitive.py

Calibrazione definitiva della griglia CBCL dal PDF ufficiale (Cbcl1.pdf).
Estrae le posizioni esatte dei digit "0","1","2" usando pdfplumber
e genera cbcl_grid.json v2.0 con coordinate pixel-perfect per tutte
e 3 le pagine scoring.

Uso:
    python smart_ocr/scripts/calibrate_from_pdf_definitive.py
    python smart_ocr/scripts/calibrate_from_pdf_definitive.py --pdf path/to/cbcl.pdf
    python smart_ocr/scripts/calibrate_from_pdf_definitive.py --verify
"""

import json
import sys
import argparse
from pathlib import Path

# Setup path
SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_DIR))

from core.pdf_calibrator import (
    _extract_response_chars,
    _group_into_rows,
    _split_columns,
    _compute_cell_dimensions,
    TARGET_WIDTH,
    TARGET_HEIGHT,
    PT_TO_PX,
)

import pdfplumber
import numpy as np

# ============================================================
# Layout CBCL 6-18 ufficiale — verificato da Cbcl1.pdf
# ============================================================

PAGE_4_LEFT = [str(i) for i in range(1, 25)]  # Items 1-24

PAGE_4_RIGHT = [str(i) for i in range(25, 48)]  # Items 25-47

PAGE_5_LEFT = (
    [str(i) for i in range(48, 56)]  # Items 48-55
    + ["56a", "56b", "56c", "56d", "56e", "56f", "56g", "56h"]  # Sub-items
    + [str(i) for i in range(57, 69)]  # Items 57-68
)

PAGE_5_RIGHT = [str(i) for i in range(69, 97)]  # Items 69-96

PAGE_6_LEFT = (
    [str(i) for i in range(97, 113)]  # Items 97-112
    + ["113a", "113b", "113c"]  # Item 113: 3 righe aperte
)

PAGE_6_RIGHT = []  # Pagina a colonna singola

# Mappa pagine: (pdf_page_index_0based, left_items, right_items)
PAGES_CONFIG = [
    ("page_4", 3, PAGE_4_LEFT, PAGE_4_RIGHT),
    ("page_5", 4, PAGE_5_LEFT, PAGE_5_RIGHT),
    ("page_6", 5, PAGE_6_LEFT, PAGE_6_RIGHT),
]


def _row_to_coords(row: list) -> dict:
    """Converte una riga di 3 char pdfplumber in coordinate relative."""
    coords = {}
    for i, c in enumerate(row):
        cx = ((c["x0"] + c["x1"]) / 2.0) * PT_TO_PX
        cy = ((c["top"] + c["bottom"]) / 2.0) * PT_TO_PX
        if i == 0:
            coords["row_y"] = cy / TARGET_HEIGHT
        coords[f"col_{i}_x"] = cx / TARGET_WIDTH
    return coords


def calibrate_page(
    pdf_path: str,
    page_index: int,
    item_ids_left: list,
    item_ids_right: list,
) -> dict:
    """
    Calibra una singola pagina del PDF.

    Returns:
        dict con cell_width_rel, cell_height_rel, items
    """
    pdf = pdfplumber.open(pdf_path)
    page = pdf.pages[page_index]
    page_w = page.width

    # 1. Estrai digit di risposta (bold 0/1/2)
    response_chars = _extract_response_chars(page)
    print(f"  Digit bold trovati: {len(response_chars)}")

    # 2. Raggruppa in righe
    rows = _group_into_rows(response_chars)
    print(f"  Righe raggruppate: {len(rows)}")

    # 2b. Fix righe incomplete: cerca digit bold con font size leggermente diverso
    for row in rows:
        if len(row) == 2:
            y = row[0]["top"]
            existing_texts = {c["text"] for c in row}
            missing_text = ({"0", "1", "2"} - existing_texts)
            if missing_text:
                target = missing_text.pop()
                candidates = [
                    c for c in page.chars
                    if c["text"] == target
                    and "Bold" in c.get("fontname", "")
                    and abs(c["top"] - y) < 3.0
                ]
                if candidates:
                    row.append(candidates[0])
                    print(f"  Fix: aggiunto '{target}' mancante alla riga y={y:.1f}")

    # 3. Separa colonne (o singola colonna)
    if item_ids_right:
        left_rows, right_rows = _split_columns(rows, page_w)
    else:
        # Singola colonna: tutte le righe con esattamente 3 char sono "left"
        left_rows = []
        for row in rows:
            sorted_row = sorted(row, key=lambda c: c["x0"])
            if len(sorted_row) == 3:
                left_rows.append(sorted_row)
        left_rows.sort(key=lambda r: r[0]["top"])
        right_rows = []

    print(f"  Righe colonna SX: {len(left_rows)}, attese: {len(item_ids_left)}")
    if item_ids_right:
        print(f"  Righe colonna DX: {len(right_rows)}, attese: {len(item_ids_right)}")

    # 4. Validazione conteggio
    if len(left_rows) != len(item_ids_left):
        raise ValueError(
            f"Mismatch colonna SX: trovate {len(left_rows)} righe, "
            f"attese {len(item_ids_left)}"
        )
    if len(right_rows) != len(item_ids_right):
        raise ValueError(
            f"Mismatch colonna DX: trovate {len(right_rows)} righe, "
            f"attese {len(item_ids_right)}"
        )

    # 5. Calcola dimensioni cella
    all_rows = left_rows + right_rows
    cell_w_rel, cell_h_rel = _compute_cell_dimensions(all_rows, page_w, page.height)

    # 6. Costruisci coordinate
    items = {}
    for item_id, row in zip(item_ids_left, left_rows):
        coords = _row_to_coords(row)
        items[item_id] = {k: round(v, 6) for k, v in coords.items()}

    for item_id, row in zip(item_ids_right, right_rows):
        coords = _row_to_coords(row)
        items[item_id] = {k: round(v, 6) for k, v in coords.items()}

    # 7. Validazione range [0, 1]
    for item_id, coords in items.items():
        for key, val in coords.items():
            if val < 0.0 or val > 1.0:
                raise ValueError(
                    f"Coordinata fuori range: item {item_id}, "
                    f"{key}={val:.6f}"
                )

    pdf.close()

    return {
        "pdf_page_index": page_index,
        "cell_width_rel": round(cell_w_rel, 6),
        "cell_height_rel": round(cell_h_rel, 6),
        "items": items,
    }


def calibrate_all(pdf_path: str) -> dict:
    """
    Calibra tutte e 3 le pagine scoring dal PDF ufficiale.

    Returns:
        dict completo per cbcl_grid.json
    """
    template = {
        "version": "2.0",
        "questionnaire": "CBCL 6-18",
        "source_pdf": Path(pdf_path).name,
        "note": (
            "Calibrato dal PDF ufficiale con pdfplumber. "
            "Coordinate relative (0.0-1.0) pixel-perfect, "
            "nessun offset fotografico applicato."
        ),
        "target_resolution": [TARGET_WIDTH, TARGET_HEIGHT],
        "pages": {},
    }

    total_items = 0

    for page_key, page_idx, left_ids, right_ids in PAGES_CONFIG:
        print(f"\n{'='*50}")
        print(f"Calibrazione {page_key} (PDF page {page_idx + 1})...")
        print(f"{'='*50}")

        page_data = calibrate_page(pdf_path, page_idx, left_ids, right_ids)
        template["pages"][page_key] = page_data

        n_items = len(page_data["items"])
        total_items += n_items
        print(f"  Items calibrati: {n_items}")
        print(f"  Cell size: {page_data['cell_width_rel']:.6f} x {page_data['cell_height_rel']:.6f}")

    print(f"\n{'='*50}")
    print(f"TOTALE: {total_items} items su 3 pagine")
    print(f"{'='*50}")

    return template


def verify_grid(template: dict):
    """Verifica integrita della griglia generata."""
    errors = []
    all_item_ids = set()

    for page_key, page_data in template["pages"].items():
        items = page_data["items"]

        for item_id, coords in items.items():
            # Duplicati cross-page
            if item_id in all_item_ids:
                errors.append(f"Item duplicato: {item_id}")
            all_item_ids.add(item_id)

            # Range check
            for key, val in coords.items():
                if val < 0.0 or val > 1.0:
                    errors.append(f"{page_key}/{item_id}: {key}={val:.6f} fuori range")

    # Verifica completezza
    expected = set(
        [str(i) for i in range(1, 56)]
        + ["56a", "56b", "56c", "56d", "56e", "56f", "56g", "56h"]
        + [str(i) for i in range(57, 113)]
        + ["113a", "113b", "113c"]
    )
    missing = expected - all_item_ids
    extra = all_item_ids - expected

    if missing:
        errors.append(f"Items mancanti: {sorted(missing, key=str)}")
    if extra:
        errors.append(f"Items extra: {sorted(extra, key=str)}")

    if errors:
        print("\nERRORI DI VALIDAZIONE:")
        for e in errors:
            print(f"  - {e}")
        return False

    print("\nValidazione OK: tutti gli items presenti, coordinate in range.")
    return True


def generate_overlay(template: dict, pdf_path: str, output_dir: str = None):
    """Genera immagini di overlay per verifica visiva."""
    import cv2

    if output_dir is None:
        output_dir = str(PROJECT_DIR / "data" / "pdf_pages")

    for page_key, page_data in template["pages"].items():
        page_idx = page_data["pdf_page_index"]
        png_path = Path(output_dir) / f"cbcl1_page_{page_idx + 1}.png"

        if not png_path.exists():
            print(f"  PNG non trovato: {png_path}, skip overlay")
            continue

        img = cv2.imread(str(png_path))
        if img is None:
            continue

        h, w = img.shape[:2]
        cell_w = page_data["cell_width_rel"]
        cell_h = page_data["cell_height_rel"]

        colors = {
            "col_0_x": (255, 100, 100),  # Blu
            "col_1_x": (100, 255, 100),  # Verde
            "col_2_x": (100, 100, 255),  # Rosso
        }

        for item_id, coords in page_data["items"].items():
            row_y = coords["row_y"]

            for col_key, color in colors.items():
                cx = int(coords[col_key] * w)
                cy = int(row_y * h)
                cw = max(int(cell_w * w), 10)
                ch = max(int(cell_h * h), 10)

                x1 = cx - cw // 2
                y1 = cy - ch // 2
                x2 = x1 + cw
                y2 = y1 + ch

                cv2.rectangle(img, (x1, y1), (x2, y2), color, 2)

                if col_key == "col_0_x":
                    cv2.putText(
                        img, str(item_id), (x1 - 40, cy + 4),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 0, 200), 1
                    )

        overlay_path = Path(output_dir) / f"overlay_{page_key}.png"
        cv2.imwrite(str(overlay_path), img)
        print(f"  Overlay salvato: {overlay_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Calibrazione definitiva griglia CBCL dal PDF ufficiale"
    )
    parser.add_argument(
        "--pdf", default=str(PROJECT_DIR.parent / "Cbcl1.pdf"),
        help="Path al PDF ufficiale CBCL"
    )
    parser.add_argument(
        "--verify", action="store_true",
        help="Genera overlay visivo per verifica"
    )
    args = parser.parse_args()

    pdf_path = args.pdf
    if not Path(pdf_path).exists():
        print(f"ERRORE: PDF non trovato: {pdf_path}")
        sys.exit(1)

    print(f"PDF sorgente: {pdf_path}")

    # Calibra tutte le pagine
    template = calibrate_all(pdf_path)

    # Verifica
    ok = verify_grid(template)
    if not ok:
        print("\nCalibrazione FALLITA. Correggere gli errori.")
        sys.exit(1)

    # Salva
    output_path = PROJECT_DIR / "templates" / "cbcl_grid.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(template, f, indent=2, ensure_ascii=False)
    print(f"\nGriglia salvata in: {output_path}")

    # Overlay (se richiesto o di default)
    if args.verify:
        print("\nGenerazione overlay...")
        generate_overlay(template, pdf_path)

    print("\nCalibrazione completata con successo!")


if __name__ == "__main__":
    main()
