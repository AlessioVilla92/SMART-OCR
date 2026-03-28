"""
core/photo_aligner.py

Allineamento interattivo delle foto al template calibrato.
L'utente indica 4 punti di riferimento nella foto (digit "0" di 4 item noti).
Il sistema calcola la trasformazione prospettica e allinea la foto al template.

Uso:
    from core.photo_aligner import align_photo_to_template
    aligned = align_photo_to_template(gray_photo, page_key, reference_points)
"""

import cv2
import numpy as np
import json
from pathlib import Path
from typing import List, Tuple, Dict, Optional


TEMPLATE_PATH = Path(__file__).parent.parent / "templates" / "cbcl_grid.json"
TARGET_WIDTH = 2480
TARGET_HEIGHT = 3508


def get_reference_items(page_key: str) -> List[dict]:
    """
    Restituisce i 4 item di riferimento per l'allineamento.
    Sceglie i 4 angoli della griglia: primo/ultimo di colonna SX e DX.
    """
    with open(TEMPLATE_PATH, "r") as f:
        template = json.load(f)

    page = template["pages"][page_key]
    items = page["items"]

    # Separa colonne
    left_items = [(k, v) for k, v in items.items() if v["col_0_x"] < 0.3]
    right_items = [(k, v) for k, v in items.items() if v["col_0_x"] > 0.3]

    left_items.sort(key=lambda x: x[1]["row_y"])
    right_items.sort(key=lambda x: x[1]["row_y"])

    refs = [
        {"item_id": left_items[0][0], "label": f"Item {left_items[0][0]} col 0 (SX primo)",
         "template_x": left_items[0][1]["col_0_x"], "template_y": left_items[0][1]["row_y"]},
        {"item_id": left_items[-1][0], "label": f"Item {left_items[-1][0]} col 0 (SX ultimo)",
         "template_x": left_items[-1][1]["col_0_x"], "template_y": left_items[-1][1]["row_y"]},
        {"item_id": right_items[0][0], "label": f"Item {right_items[0][0]} col 0 (DX primo)",
         "template_x": right_items[0][1]["col_0_x"], "template_y": right_items[0][1]["row_y"]},
        {"item_id": right_items[-1][0], "label": f"Item {right_items[-1][0]} col 0 (DX ultimo)",
         "template_x": right_items[-1][1]["col_0_x"], "template_y": right_items[-1][1]["row_y"]},
    ]
    return refs


def align_photo_to_template(
    gray: np.ndarray,
    page_key: str,
    photo_points: List[Tuple[float, float]],
) -> np.ndarray:
    """
    Allinea la foto al template usando 4 punti di riferimento.

    Args:
        gray: immagine foto grayscale (qualsiasi dimensione)
        page_key: "page_4" o "page_5"
        photo_points: 4 punti (x, y) in pixel nella foto, nello stesso ordine
                      dei reference items (SX primo, SX ultimo, DX primo, DX ultimo)

    Returns:
        immagine allineata a TARGET_WIDTH x TARGET_HEIGHT
    """
    refs = get_reference_items(page_key)

    if len(photo_points) != 4:
        raise ValueError(f"Servono 4 punti, ricevuti {len(photo_points)}")

    # Punti sorgente (nella foto)
    src = np.float32(photo_points)

    # Punti destinazione (nel template target)
    dst = np.float32([
        [r["template_x"] * TARGET_WIDTH, r["template_y"] * TARGET_HEIGHT]
        for r in refs
    ])

    # Homography
    H, mask = cv2.findHomography(src, dst, cv2.RANSAC, 5.0)

    if H is None:
        raise ValueError("Impossibile calcolare la trasformazione. "
                         "Verificare che i 4 punti siano corretti.")

    # Warp
    aligned = cv2.warpPerspective(gray, H, (TARGET_WIDTH, TARGET_HEIGHT))

    # CLAHE per migliorare contrasto
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    aligned = clahe.apply(aligned)

    return aligned


def align_and_extract(
    photo_path: str,
    page_key: str,
    photo_points: List[Tuple[float, float]],
) -> Tuple[np.ndarray, dict]:
    """
    Carica foto, allinea, estrae celle e classifica.

    Returns:
        (aligned_image, results_dict)
    """
    from core.grid_extractor import extract_all_cells
    from core.omr_classifier import classify_all_items_omr

    # Carica
    img = cv2.imread(photo_path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise ValueError(f"Impossibile caricare: {photo_path}")

    # Denoising
    img = cv2.fastNlMeansDenoising(img, h=10)

    # Allinea
    aligned = align_photo_to_template(img, page_key, photo_points)

    # Estrai e classifica
    cells = extract_all_cells(aligned, page_key)
    results = classify_all_items_omr(cells)

    return aligned, results
