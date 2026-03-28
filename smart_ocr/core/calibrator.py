"""
core/calibrator.py

Tool di calibrazione della griglia CBCL.
L'utente indica pochi punti di ancoraggio sull'immagine e il sistema
calcola automaticamente le coordinate di tutte le 357 celle (119 item x 3 colonne).

Struttura CBCL 6-18:
- Pagina 4: 2 colonne di item (sx: 1-34, dx: 35-55 + 56a-56h)
- Pagina 5: 2 colonne di item (sx: 57-90, dx: 91-112)
- Ogni item ha 3 celle di risposta (0, 1, 2) allineate orizzontalmente

CALIBRAZIONE:
Per ogni pagina servono 6 punti di ancoraggio:
  - Colonna sinistra: top-left prima cella item 1 (o 57), bottom-left ultima cella item 34 (o 90)
  - Colonna destra: top-left prima cella item 35 (o 91), bottom-left ultima cella item 55/56h (o 112)
  - Spaziatura colonne: centro cella col_0 e centro cella col_2 di un qualsiasi item
    (per calcolare la distanza tra le 3 colonne di risposta)

Il sistema interpola linearmente tutte le righe tra i punti di ancoraggio.
"""

import json
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple, Optional


TEMPLATE_PATH = Path(__file__).parent.parent / "templates" / "cbcl_grid.json"

# Layout CBCL 6-18: definizione delle colonne e degli item per pagina
# Aggiornato in base al facsimile reale (cbcl.pdf pagina 2)
CBCL_LAYOUT = {
    "page_4": {
        "left_column": {
            "items": [str(i) for i in range(1, 30)],  # 1-29
        },
        "right_column": {
            "items": [str(i) for i in range(30, 57)] + ["56a", "56b", "56c", "56d"],  # 30-56 + 56a-56d
        }
    },
    "page_5": {
        "left_column": {
            "items": [str(i) for i in range(57, 91)],  # 57-90
        },
        "right_column": {
            "items": [str(i) for i in range(91, 113)],  # 91-112
        }
    }
}


def calculate_grid_from_anchors(
    page: str,
    left_top: Tuple[float, float],
    left_bottom: Tuple[float, float],
    right_top: Tuple[float, float],
    right_bottom: Tuple[float, float],
    col_spacing: float,
    cell_width: float,
    cell_height: float,
    img_width: int,
    img_height: int
) -> dict:
    """
    Calcola tutte le coordinate della griglia da punti di ancoraggio.

    Args:
        page: "page_4" o "page_5"
        left_top: (x, y) in pixel del centro della prima cella col_0, primo item colonna SX
        left_bottom: (x, y) in pixel del centro della prima cella col_0, ultimo item colonna SX
        right_top: (x, y) in pixel del centro della prima cella col_0, primo item colonna DX
        right_bottom: (x, y) in pixel del centro della prima cella col_0, ultimo item colonna DX
        col_spacing: distanza in pixel tra centro col_0 e centro col_1 (uguale tra col_1 e col_2)
        cell_width: larghezza cella in pixel
        cell_height: altezza cella in pixel
        img_width: larghezza immagine normalizzata
        img_height: altezza immagine normalizzata

    Returns:
        dict con struttura compatibile con cbcl_grid.json per la pagina specificata
    """
    layout = CBCL_LAYOUT[page]
    items = {}

    # Colonna sinistra: interpola tra left_top e left_bottom
    left_items = layout["left_column"]["items"]
    n_left = len(left_items)
    for i, item_id in enumerate(left_items):
        t = i / max(n_left - 1, 1)  # 0.0 -> 1.0
        cx = left_top[0] + t * (left_bottom[0] - left_top[0])
        cy = left_top[1] + t * (left_bottom[1] - left_top[1])

        items[item_id] = {
            "row_y": cy / img_height,
            "col_0_x": cx / img_width,
            "col_1_x": (cx + col_spacing) / img_width,
            "col_2_x": (cx + 2 * col_spacing) / img_width,
        }

    # Colonna destra: interpola tra right_top e right_bottom
    right_items = layout["right_column"]["items"]
    n_right = len(right_items)
    for i, item_id in enumerate(right_items):
        t = i / max(n_right - 1, 1)
        cx = right_top[0] + t * (right_bottom[0] - right_top[0])
        cy = right_top[1] + t * (right_bottom[1] - right_top[1])

        items[item_id] = {
            "row_y": cy / img_height,
            "col_0_x": cx / img_width,
            "col_1_x": (cx + col_spacing) / img_width,
            "col_2_x": (cx + 2 * col_spacing) / img_width,
        }

    return {
        "cell_width_rel": cell_width / img_width,
        "cell_height_rel": cell_height / img_height,
        "items": items
    }


def save_calibration(page: str, page_data: dict):
    """
    Salva la calibrazione nel file cbcl_grid.json.
    Aggiorna solo la pagina specificata, preserva il resto.
    """
    if TEMPLATE_PATH.exists():
        with open(TEMPLATE_PATH, "r") as f:
            template = json.load(f)
    else:
        template = {
            "version": "1.0",
            "questionnaire": "CBCL 6-18",
            "note": "Calibrato automaticamente con calibrator.py",
            "pages": {}
        }

    template["pages"][page] = page_data

    with open(TEMPLATE_PATH, "w") as f:
        json.dump(template, f, indent=2, ensure_ascii=False)

    return TEMPLATE_PATH


def get_calibration_status() -> dict:
    """
    Verifica lo stato della calibrazione.
    Returns: {page: num_items} per ogni pagina calibrata
    """
    if not TEMPLATE_PATH.exists():
        return {}

    with open(TEMPLATE_PATH, "r") as f:
        template = json.load(f)

    status = {}
    for page, data in template.get("pages", {}).items():
        status[page] = len(data.get("items", {}))

    return status


def calibrate_from_pdf_auto(
    pdf_path: str,
    page_index: int,
    page_key: str,
    item_ids_left: Optional[list] = None,
    item_ids_right: Optional[list] = None,
) -> dict:
    """
    Calibrazione automatica da PDF digitale.
    Estrae le posizioni esatte dei digit di risposta e salva in cbcl_grid.json.

    Args:
        pdf_path: percorso al PDF
        page_index: indice pagina (0-based)
        page_key: chiave pagina per cbcl_grid.json (es. "page_4")
        item_ids_left: lista ID item colonna sx (None = auto-detect)
        item_ids_right: lista ID item colonna dx (None = auto-detect)

    Returns:
        page_data con coordinate calibrate
    """
    from core.pdf_calibrator import calibrate_from_pdf

    page_data, layout_info = calibrate_from_pdf(
        pdf_path, page_index, item_ids_left, item_ids_right
    )
    save_calibration(page_key, page_data)
    return page_data, layout_info


def estimate_cell_dimensions(img_width: int, img_height: int) -> Tuple[float, float]:
    """
    Stima dimensioni cella tipiche per CBCL su A4.
    Una cella di risposta CBCL è circa 7mm x 5mm su A4.
    A4 = 210mm x 297mm.
    """
    # 7mm / 210mm * img_width
    cell_w = (7.0 / 210.0) * img_width
    cell_h = (5.0 / 297.0) * img_height
    return cell_w, cell_h


def estimate_col_spacing(img_width: int) -> float:
    """
    Stima spaziatura tipica tra colonne risposte CBCL.
    Le 3 colonne (0,1,2) sono spaziate di circa 10mm su A4.
    """
    return (10.0 / 210.0) * img_width
