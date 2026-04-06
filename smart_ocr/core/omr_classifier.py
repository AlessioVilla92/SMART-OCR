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
MIN_MARK_RATIO = 0.12  # 12% dei pixel devono essere scuri (alzato da 0.08 per ridurre falsi positivi)
MAX_EMPTY_RATIO = 0.05  # sotto 5% la cella è sicuramente vuota

# Soglia per distinguere "ambiguo" — quando due celle hanno conteggi simili
AMBIGUITY_RATIO = 0.6  # la seconda cella più scura deve avere < 60% dei pixel della prima


def count_dark_pixels(cell: np.ndarray, threshold: int = 128) -> Tuple[int, float]:
    """
    Conta i pixel scuri in una cella usando Sauvola thresholding.
    Sauvola e superiore all'adaptive threshold di OpenCV su
    illuminazione non uniforme (ombre, luce laterale su foto smartphone).

    Args:
        cell: immagine grayscale della cella
        threshold: soglia sotto cui un pixel è "scuro" (unused, kept for API)

    Returns: (conteggio_pixel_scuri, rapporto_pixel_scuri)
    """
    if cell is None or cell.size == 0:
        return 0, 0.0

    try:
        from skimage.filters import threshold_sauvola
        # Sauvola: window_size deve essere dispari e <= dimensione immagine
        win = min(15, cell.shape[0] - 1, cell.shape[1] - 1)
        if win % 2 == 0:
            win -= 1
        if win < 3:
            win = 3
        thresh_val = threshold_sauvola(cell, window_size=win, k=0.2)
        binary = (cell < thresh_val).astype(np.uint8) * 255
    except ImportError:
        # Fallback a OpenCV adaptive threshold se scikit-image non disponibile
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

    # Doppia conferma: le altre celle devono essere vuote per confermare il mark
    if value is not None:
        other_ratios = [r for col, r in counts.items() if col != marked_column]
        max_other = max(other_ratios) if other_ratios else 0
        if max_other < 0.05:
            # Conferma forte: 1 marcata + 2 vuote
            confidence = min(1.0, confidence * 1.2)
        elif max_other < 0.08:
            pass  # Conferma OK
        else:
            # Conferma debole: altra cella con pixel significativi
            confidence *= 0.6
            if flag is None:
                flag = "low_confidence"

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


# ---------------------------------------------------------------------------
# Baseline-subtracted classification (usa reference PDF per eliminare testo stampato)
# ---------------------------------------------------------------------------

BASELINE_MARK_DELTA = 0.04   # delta minimo sopra baseline per considerare marcato
BASELINE_AMBIGUITY = 0.6     # secondo delta deve essere < 60% del primo
LOCAL_ALIGN_PAD = 5           # pixel di padding per local alignment matchTemplate


def _local_align_cell(cell: np.ndarray, ref_cell: np.ndarray) -> np.ndarray:
    """
    Allinea localmente una cella al suo reference con matchTemplate.

    Compensa micro-shift di 1-5px causato da distorsione prospettica locale
    non corretta dall'alignment SIFT globale.

    Usa TM_CCOEFF_NORMED: il metodo piu robusto a variazioni di luminosita.
    Costo: ~0.2ms per cella (trascurabile).
    """
    pad = LOCAL_ALIGN_PAD
    cell_padded = cv2.copyMakeBorder(cell, pad, pad, pad, pad, cv2.BORDER_REPLICATE)
    result = cv2.matchTemplate(cell_padded, ref_cell, cv2.TM_CCOEFF_NORMED)
    _, _, _, max_loc = cv2.minMaxLoc(result)
    dx = max_loc[0] - pad
    dy = max_loc[1] - pad

    if abs(dx) <= pad and abs(dy) <= pad and (dx != 0 or dy != 0):
        M = np.float32([[1, 0, -dx], [0, 1, -dy]])
        return cv2.warpAffine(cell, M, (cell.shape[1], cell.shape[0]),
                              borderMode=cv2.BORDER_REPLICATE)
    return cell


def classify_item_baseline(
    cells: Dict[str, np.ndarray],
    ref_cells: Dict[str, np.ndarray]
) -> dict:
    """
    Classifica un item sottraendo il baseline del testo stampato (dal reference PDF).

    Per ogni cella: delta = ratio_foto - ratio_reference.
    Il delta isola solo i mark scritti a mano, eliminando il rumore del testo stampato.

    Args:
        cells: {"0": cell_foto, "1": cell_foto, "2": cell_foto}
        ref_cells: {"0": cell_ref, "1": cell_ref, "2": cell_ref}

    Returns: dict con value, confidence, flag, raw_counts, deltas, method
    """
    counts = {}
    ref_counts = {}
    deltas = {}

    for col in cells:
        cell = cells[col]
        if col in ref_cells:
            ref_cell = ref_cells[col]
            # Local alignment: compensa micro-shift da distorsione prospettica
            cell = _local_align_cell(cell, ref_cell)
            _, ratio = count_dark_pixels(cell)
            _, ref_ratio = count_dark_pixels(ref_cell)
            ref_counts[col] = ref_ratio
            deltas[col] = ratio - ref_ratio
        else:
            _, ratio = count_dark_pixels(cell)
            ref_counts[col] = 0.0
            deltas[col] = ratio
        counts[col] = ratio

    # Trova celle marcate: delta sopra soglia
    marked = {col: d for col, d in deltas.items() if d > BASELINE_MARK_DELTA}

    flag = None
    value = None
    marked_column = None
    confidence = 0.0

    if len(marked) == 0:
        flag = "missing"

    elif len(marked) == 1:
        marked_column = list(marked.keys())[0]
        value = int(marked_column)
        # Confidence: quanto il delta è forte rispetto agli altri
        max_delta = marked[marked_column]
        other_deltas = [d for col, d in deltas.items() if col != marked_column]
        max_other = max(other_deltas) if other_deltas else 0.0
        confidence = min(1.0, max_delta / BASELINE_MARK_DELTA)
        # Boost se le altre celle hanno delta negativo o molto basso
        if max_other < 0.02:
            confidence = min(1.0, confidence * 1.2)

    else:
        sorted_marks = sorted(marked.items(), key=lambda x: x[1], reverse=True)
        best_col, best_delta = sorted_marks[0]
        second_delta = sorted_marks[1][1]

        if second_delta < best_delta * BASELINE_AMBIGUITY:
            marked_column = best_col
            value = int(best_col)
            confidence = (best_delta - second_delta) / best_delta
        else:
            flag = "multiple_marks"

    if value is not None and confidence < 0.3:
        flag = "ambiguous"

    return {
        "marked_column": marked_column,
        "value": value,
        "confidence": round(confidence, 3),
        "flag": flag,
        "raw_counts": {col: round(ratio, 4) for col, ratio in counts.items()},
        "deltas": {col: round(d, 4) for col, d in deltas.items()},
        "method": "omr_baseline_subtracted"
    }


def classify_all_items_baseline(
    all_cells: Dict[str, Dict[str, np.ndarray]],
    all_ref_cells: Dict[str, Dict[str, np.ndarray]]
) -> Dict[str, dict]:
    """
    Classifica tutti gli item con baseline subtraction dal reference PDF.

    Args:
        all_cells: celle dalla foto allineata
        all_ref_cells: celle dal reference PDF (template pulito)

    Returns: {item_id: classification_result}
    """
    results = {}
    for item_id, cells in all_cells.items():
        ref_cells = all_ref_cells.get(item_id, {})
        if ref_cells:
            results[item_id] = classify_item_baseline(cells, ref_cells)
        else:
            results[item_id] = classify_item_omr(cells)
    return results


# ---------------------------------------------------------------------------
# PDF-optimized classification (Mode D)
# ---------------------------------------------------------------------------
# I PDF digitali hanno celle con numeri stampati (0, 1, 2) che producono
# un baseline di pixel scuri ~5-10%. Il mark (X) aggiunge ~10-20%.
# Strategia: logica inversa (2 celle vuote → la terza e il mark)
# + winner-takes-all (la cella col ratio piu alto vince).
# ---------------------------------------------------------------------------

def classify_item_pdf(
    cells: Dict[str, np.ndarray],
    empty_threshold: float = 0.08,
    min_ratio: float = 0.06,
    ambiguity_gap: float = 0.0
) -> dict:
    """
    Classifica le 3 celle di un item da PDF digitale.

    Strategia combinata:
    1. Se 2 celle sono chiaramente vuote (< empty_threshold) → la terza e il mark
    2. Altrimenti winner-takes-all: la cella col ratio piu alto vince
    3. Flag ambiguous solo se gap < ambiguity_gap (default 0 = mai ambiguo)

    Args:
        cells: {"0": cell_64x64, "1": cell_64x64, "2": cell_64x64}
        empty_threshold: ratio sotto cui una cella e considerata vuota
        min_ratio: ratio sotto cui TUTTE le celle → missing
        ambiguity_gap: gap relativo minimo per non flaggare come ambiguo

    Returns: dict con value, confidence, flag, raw_counts, method
    """
    ratios = {}
    for col, cell in cells.items():
        _, ratio = count_dark_pixels(cell)
        ratios[col] = ratio

    sorted_cols = sorted(ratios.items(), key=lambda x: x[1], reverse=True)
    best_col, best_r = sorted_cols[0]
    second_col, second_r = sorted_cols[1]
    third_col, third_r = sorted_cols[2]

    flag = None
    value = None
    marked_column = None
    confidence = 0.0

    if best_r < min_ratio:
        # Tutte le celle essenzialmente vuote
        flag = "missing"

    elif second_r < empty_threshold and third_r < empty_threshold:
        # Logica inversa: 2 celle vuote → la terza e il mark
        marked_column = best_col
        value = int(best_col)
        confidence = 1.0 - (second_r / best_r) if best_r > 0 else 1.0

    else:
        # Winner-takes-all: la cella con piu pixel scuri vince
        marked_column = best_col
        value = int(best_col)
        gap = (best_r - second_r) / best_r if best_r > 0 else 0
        confidence = gap

        if ambiguity_gap > 0 and gap < ambiguity_gap:
            flag = "ambiguous"

    return {
        "marked_column": marked_column,
        "value": value,
        "confidence": round(confidence, 3),
        "flag": flag,
        "raw_counts": {col: round(ratio, 4) for col, ratio in ratios.items()},
        "method": "omr_pdf_optimized"
    }


def classify_all_items_pdf(
    all_cells: Dict[str, Dict[str, np.ndarray]],
    empty_threshold: float = 0.08,
    min_ratio: float = 0.06,
    ambiguity_gap: float = 0.0
) -> Dict[str, dict]:
    """
    Classifica tutti gli item con strategia ottimizzata per PDF digitali.

    Args:
        all_cells: output di grid_extractor.extract_all_cells()
        empty_threshold: ratio sotto cui una cella e vuota
        min_ratio: ratio minimo assoluto
        ambiguity_gap: gap minimo per non-ambiguo

    Returns:
        {item_id: classification_result} per ogni item
    """
    results = {}
    for item_id, cells in all_cells.items():
        results[item_id] = classify_item_pdf(
            cells, empty_threshold, min_ratio, ambiguity_gap
        )
    return results
