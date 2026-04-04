"""
core/grid_extractor.py

Estrae le celle (0, 1, 2) per ogni item del questionario CBCL.
Usa coordinate relative dal template cbcl_grid.json.

Input:  immagine preprocessata (grayscale numpy array)
Output: dict {item_id: {"0": cell_img, "1": cell_img, "2": cell_img}}
"""

import cv2
import numpy as np
import json
from pathlib import Path
from typing import Dict, Tuple, Optional


TEMPLATE_PATH = Path(__file__).parent.parent / "templates" / "cbcl_grid.json"
CELL_SIZE = (64, 64)  # Dimensione standard cella per classificatore HOG

# CLAHE per-cella: normalizza contrasto individuale di ogni cella.
# clipLimit=1.5 (conservativo per non amplificare rumore su celle vuote)
# tileGridSize=(2,2) su 64x64 = tile 32x32 (normalizzazione grossolana)
_cell_clahe = cv2.createCLAHE(clipLimit=1.5, tileGridSize=(2, 2))


class GridExtractionError(Exception):
    pass


def load_template(page: str = "page_4") -> dict:
    """Carica il template della griglia dal JSON."""
    if not TEMPLATE_PATH.exists():
        raise GridExtractionError(f"Template non trovato: {TEMPLATE_PATH}")

    with open(TEMPLATE_PATH, "r") as f:
        template = json.load(f)

    if page not in template["pages"]:
        raise GridExtractionError(f"Pagina '{page}' non trovata nel template.")

    return template["pages"][page]


def extract_cell(
    img: np.ndarray,
    center_x_rel: float,
    center_y_rel: float,
    cell_w_rel: float,
    cell_h_rel: float
) -> np.ndarray:
    """
    Ritaglia una singola cella dall'immagine.

    Args:
        img: immagine grayscale
        center_x_rel, center_y_rel: centro cella in coordinate relative (0-1)
        cell_w_rel, cell_h_rel: dimensioni cella in coordinate relative

    Returns: cella ridimensionata a CELL_SIZE (64x64)
    """
    h, w = img.shape

    cx = int(center_x_rel * w)
    cy = int(center_y_rel * h)
    cw = max(int(cell_w_rel * w), 20)  # minimo 20px
    ch = max(int(cell_h_rel * h), 20)

    x1 = max(0, cx - cw // 2)
    y1 = max(0, cy - ch // 2)
    x2 = min(w, x1 + cw)
    y2 = min(h, y1 + ch)

    cell = img[y1:y2, x1:x2]

    if cell.size == 0:
        # Cella vuota - ritorna array bianco
        return np.full(CELL_SIZE, 255, dtype=np.uint8)

    # Ridimensiona a dimensione standard per HOG
    cell_resized = cv2.resize(cell, CELL_SIZE, interpolation=cv2.INTER_AREA)

    # Normalizzazione contrasto per-cella
    cell_resized = _cell_clahe.apply(cell_resized)

    return cell_resized


def extract_all_cells(
    img: np.ndarray,
    page: str = "page_4",
    offsets: Optional[dict] = None
) -> Dict[str, Dict[str, np.ndarray]]:
    """
    Estrae tutte le celle per tutti gli item della pagina specificata.

    Args:
        img: immagine grayscale preprocessata
        page: pagina del questionario
        offsets: correzioni locali da detect_grid_offsets()
                 {"row_y_offsets": {item_id: dy}, "col_x_offsets": {item_id: {col_key: dx}}, "success": bool}

    Returns:
        {
            "1": {"0": cell_img_64x64, "1": cell_img_64x64, "2": cell_img_64x64},
            "2": {...},
            ...
            "56a": {...},  # sub-items
            ...
        }
    """
    template = load_template(page)
    items = template["items"]
    cell_w = template["cell_width_rel"]
    cell_h = template["cell_height_rel"]

    use_offsets = offsets and offsets.get("success", False)
    row_offsets = offsets.get("row_y_offsets", {}) if use_offsets else {}
    col_offsets = offsets.get("col_x_offsets", {}) if use_offsets else {}

    result = {}

    for item_id, coords in items.items():
        row_y = coords["row_y"]

        # Applica offset Y per-riga
        if item_id in row_offsets:
            row_y += row_offsets[item_id]

        item_col_offsets = col_offsets.get(item_id, {})

        cells = {}
        for col_label, col_key in [("0", "col_0_x"), ("1", "col_1_x"), ("2", "col_2_x")]:
            if col_key not in coords:
                continue
            col_x = coords[col_key]

            # Applica offset X per-colonna
            if col_key in item_col_offsets:
                col_x += item_col_offsets[col_key]

            cells[col_label] = extract_cell(img, col_x, row_y, cell_w, cell_h)

        result[item_id] = cells

    return result


def visualize_grid_overlay(
    img: np.ndarray,
    page: str = "page_4",
    offsets: Optional[dict] = None
) -> np.ndarray:
    """
    Genera immagine con overlay delle celle rilevate.
    Utile per debug e calibrazione del template.

    Returns: immagine BGR con rettangoli colorati sulle celle
    """
    vis = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    template = load_template(page)
    items = template["items"]
    cell_w = template["cell_width_rel"]
    cell_h = template["cell_height_rel"]
    h, w = img.shape

    use_offsets = offsets and offsets.get("success", False)
    row_offsets = offsets.get("row_y_offsets", {}) if use_offsets else {}
    col_offsets = offsets.get("col_x_offsets", {}) if use_offsets else {}

    colors = {
        "col_0_x": (255, 100, 100),  # Blu
        "col_1_x": (100, 255, 100),  # Verde
        "col_2_x": (100, 100, 255),  # Rosso
    }

    for item_id, coords in items.items():
        row_y = coords["row_y"]
        if item_id in row_offsets:
            row_y += row_offsets[item_id]

        item_col_offsets = col_offsets.get(item_id, {})

        for col_key, color in colors.items():
            if col_key not in coords:
                continue

            col_x = coords[col_key]
            if col_key in item_col_offsets:
                col_x += item_col_offsets[col_key]

            cx = int(col_x * w)
            cy = int(row_y * h)
            cw = max(int(cell_w * w), 20)
            ch = max(int(cell_h * h), 20)

            x1 = cx - cw // 2
            y1 = cy - ch // 2
            x2 = x1 + cw
            y2 = y1 + ch

            cv2.rectangle(vis, (x1, y1), (x2, y2), color, 2)

            # Label item
            if col_key == "col_0_x":
                cv2.putText(vis, str(item_id), (x1 - 5, cy),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.3, (0, 0, 0), 1)

    return vis
