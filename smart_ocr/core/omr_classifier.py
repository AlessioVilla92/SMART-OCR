"""
core/omr_classifier.py

Classificatore OMR (Optical Mark Recognition) basato su pixel-counting.
NON richiede training — funziona subito dopo la calibrazione.

Per ogni riga di item (3 celle: colonna 0, 1, 2):
1. Binarizza ogni cella
2. Conta i pixel scuri (inchiostro)
3. La cella con più pixel scuri = risposta marcata
4. Se nessuna supera la soglia minima = "missing"
5. Se più di una supera la soglia = "multiple_marks"

Questo fornisce una baseline ~90-94% accurata.
Il classificatore SVM (classifier.py) è un upgrade opzionale.
"""

import cv2
import numpy as np
from typing import Dict, Tuple, Optional


# Soglia minima: % di pixel scuri per considerare una cella "marcata"
# Una cella 64x64 = 4096 pixel totali
# Un cerchio o X occupa tipicamente 15-40% della cella
MIN_MARK_RATIO = 0.08  # 8% dei pixel devono essere scuri
MAX_EMPTY_RATIO = 0.04  # sotto 4% la cella è sicuramente vuota

# Soglia per distinguere "ambiguo" — quando due celle hanno conteggi simili
AMBIGUITY_RATIO = 0.6  # la seconda cella più scura deve avere < 60% dei pixel della prima


def count_dark_pixels(cell: np.ndarray, threshold: int = 128) -> Tuple[int, float]:
    """
    Conta i pixel scuri in una cella.

    Args:
        cell: immagine grayscale della cella
        threshold: soglia sotto cui un pixel è "scuro"

    Returns: (conteggio_pixel_scuri, rapporto_pixel_scuri)
    """
    if cell is None or cell.size == 0:
        return 0, 0.0

    # Binarizza con soglia adattiva per gestire illuminazione variabile
    binary = cv2.adaptiveThreshold(
        cell, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        blockSize=15,
        C=8
    )

    dark_count = cv2.countNonZero(binary)
    total = cell.shape[0] * cell.shape[1]
    ratio = dark_count / total if total > 0 else 0.0

    return dark_count, ratio


def classify_item_omr(
    cells: Dict[str, np.ndarray]
) -> dict:
    """
    Classifica le 3 celle di un item usando pixel-counting.

    Args:
        cells: {"0": cell_64x64, "1": cell_64x64, "2": cell_64x64}

    Returns:
        {
            "marked_column": "0" | "1" | "2" | None,
            "value": 0 | 1 | 2 | None,
            "confidence": float 0.0-1.0,
            "flag": None | "ambiguous" | "missing" | "multiple_marks",
            "raw_counts": {"0": ratio, "1": ratio, "2": ratio},
            "method": "omr_pixel_counting"
        }
    """
    # Conta pixel scuri per ogni cella
    counts = {}
    for col_label, cell_img in cells.items():
        _, ratio = count_dark_pixels(cell_img)
        counts[col_label] = ratio

    # Trova celle marcate (sopra soglia minima)
    marked = {col: ratio for col, ratio in counts.items() if ratio >= MIN_MARK_RATIO}
    empty = {col: ratio for col, ratio in counts.items() if ratio < MAX_EMPTY_RATIO}

    flag = None
    value = None
    marked_column = None
    confidence = 0.0

    if len(marked) == 0:
        # Nessuna cella marcata
        flag = "missing"

    elif len(marked) == 1:
        # Esattamente una cella marcata — caso ideale
        marked_column = list(marked.keys())[0]
        value = int(marked_column)

        # Confidence basata su quanto è chiara la distinzione
        max_ratio = marked[marked_column]
        other_ratios = [r for c, r in counts.items() if c != marked_column]
        max_other = max(other_ratios) if other_ratios else 0.0

        if max_other > 0:
            confidence = min(1.0, (max_ratio - max_other) / max_ratio)
        else:
            confidence = min(1.0, max_ratio / MIN_MARK_RATIO)

    else:
        # Più celle marcate — verifica se una è chiaramente dominante
        sorted_marks = sorted(marked.items(), key=lambda x: x[1], reverse=True)
        best_col, best_ratio = sorted_marks[0]
        second_col, second_ratio = sorted_marks[1]

        if second_ratio < best_ratio * AMBIGUITY_RATIO:
            # La prima è chiaramente dominante
            marked_column = best_col
            value = int(best_col)
            confidence = (best_ratio - second_ratio) / best_ratio
        else:
            # Ambiguo: due celle con conteggi simili
            flag = "multiple_marks"

    # Se la confidence è troppo bassa, segna come ambiguo
    if value is not None and confidence < 0.3:
        flag = "ambiguous"

    return {
        "marked_column": marked_column,
        "value": value,
        "confidence": round(confidence, 3),
        "flag": flag,
        "raw_counts": {col: round(ratio, 4) for col, ratio in counts.items()},
        "method": "omr_pixel_counting"
    }


def classify_all_items_omr(
    all_cells: Dict[str, Dict[str, np.ndarray]]
) -> Dict[str, dict]:
    """
    Classifica tutti gli item usando OMR pixel-counting.

    Args:
        all_cells: output di grid_extractor.extract_all_cells()

    Returns:
        {item_id: classification_result} per ogni item
    """
    results = {}
    for item_id, cells in all_cells.items():
        results[item_id] = classify_item_omr(cells)
    return results
