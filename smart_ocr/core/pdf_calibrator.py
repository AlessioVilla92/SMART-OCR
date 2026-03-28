"""
core/pdf_calibrator.py

Calibrazione automatica della griglia CBCL da PDF digitale.
Estrae le posizioni esatte dei digit "0", "1", "2" usando pdfplumber,
producendo coordinate pixel-perfect per ogni singolo item.

Uso:
    from core.pdf_calibrator import calibrate_from_pdf
    page_data, layout_info = calibrate_from_pdf("cbcl.pdf", page_index=1)
"""

import pdfplumber
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple, Optional


# Risoluzione target (A4 a 300 DPI) — deve corrispondere a preprocessor.py
TARGET_WIDTH = 2480
TARGET_HEIGHT = 3508
DPI = 300
PDF_POINTS_PER_INCH = 72
PT_TO_PX = DPI / PDF_POINTS_PER_INCH  # 4.1667


def _extract_response_chars(page) -> List[dict]:
    """
    Estrae i caratteri '0', '1', '2' che rappresentano le opzioni di risposta.

    Filtra per:
    - Testo: solo '0', '1', '2'
    - Font: Bold (le opzioni di risposta nel CBCL sono in grassetto)
    - Size: ~9.7pt (font tipico CBCL per i digit di risposta)
    """
    candidates = []

    # Trova il font size più comune per i digit bold '0','1','2'
    bold_digits = [c for c in page.chars
                   if c['text'] in ('0', '1', '2')
                   and 'Bold' in c.get('fontname', '')]

    if not bold_digits:
        raise ValueError("Nessun digit bold trovato nel PDF. "
                         "Verificare che il PDF contenga le opzioni di risposta.")

    # Trova il font size dominante tra i digit bold
    sizes = [round(c['size'], 1) for c in bold_digits]
    from collections import Counter
    size_counts = Counter(sizes)
    dominant_size = size_counts.most_common(1)[0][0]

    # Filtra per font size dominante (tolleranza ±0.5pt)
    for c in bold_digits:
        if abs(c['size'] - dominant_size) < 0.5:
            candidates.append(c)

    return candidates


def _group_into_rows(chars: List[dict], y_tolerance: float = 1.5) -> List[List[dict]]:
    """Raggruppa caratteri per coordinata y con tolleranza."""
    if not chars:
        return []

    sorted_chars = sorted(chars, key=lambda c: c['top'])
    rows = []
    current_row = [sorted_chars[0]]

    for c in sorted_chars[1:]:
        if c['top'] - current_row[-1]['top'] < y_tolerance:
            current_row.append(c)
        else:
            rows.append(current_row)
            current_row = [c]
    rows.append(current_row)

    return rows


def _split_columns(rows: List[List[dict]], page_width: float
                   ) -> Tuple[List[List[dict]], List[List[dict]]]:
    """
    Separa le righe in colonna sinistra e destra.
    Usa il punto medio della pagina come separatore.
    """
    midpoint = page_width / 2.0
    left_rows = []
    right_rows = []

    for row in rows:
        left_chars = [c for c in row if c['x0'] < midpoint]
        right_chars = [c for c in row if c['x0'] >= midpoint]

        if len(left_chars) == 3:
            left_rows.append(sorted(left_chars, key=lambda c: c['x0']))
        if len(right_chars) == 3:
            right_rows.append(sorted(right_chars, key=lambda c: c['x0']))

    # Ordina per y
    left_rows.sort(key=lambda r: r[0]['top'])
    right_rows.sort(key=lambda r: r[0]['top'])

    return left_rows, right_rows


def _find_item_labels(page, response_rows: List[List[dict]],
                      x_search_start: float, x_search_end: float,
                      y_tolerance: float = 3.0) -> List[str]:
    """
    Cerca il testo dell'item (numero) vicino a ogni riga di risposta.
    Restituisce la lista di label/numeri item trovati.
    """
    labels = []
    for row in response_rows:
        y = row[0]['top']
        nearby = [c for c in page.chars
                  if abs(c['top'] - y) < y_tolerance
                  and c['x0'] > x_search_start
                  and c['x0'] < x_search_end]
        nearby.sort(key=lambda c: c['x0'])
        text = ''.join(c['text'] for c in nearby).strip()

        # Estrai il numero dell'item (prima parte prima dello spazio)
        parts = text.split(' ', 1)
        item_num = parts[0] if parts else ''

        # Gestisci sub-item come "a.", "b." → "56a", "56b" etc.
        if item_num and item_num[0].isalpha() and len(item_num) <= 2:
            item_num = item_num.rstrip('.')

        labels.append(item_num)

    return labels


def _compute_cell_dimensions(response_rows: List[List[dict]],
                             page_width: float, page_height: float
                             ) -> Tuple[float, float]:
    """
    Calcola dimensioni cella dalle bounding box dei digit.
    La cella deve essere abbastanza grande da contenere un segno (cerchio/X)
    attorno al digit, ma non così grande da sovrapporsi.
    """
    if not response_rows:
        return 0.03, 0.012

    # Spaziatura tipica tra col_0 e col_1
    spacings = []
    for row in response_rows:
        if len(row) >= 2:
            spacings.append(row[1]['x0'] - row[0]['x0'])

    median_spacing = float(np.median(spacings)) if spacings else 19.0

    # Larghezza cella: ~90% della spaziatura tra colonne (per evitare overlap)
    cell_w_pt = median_spacing * 0.90

    # Altezza cella: basata sull'altezza del char + padding
    char_heights = [row[0]['bottom'] - row[0]['top'] for row in response_rows]
    median_char_h = float(np.median(char_heights))
    cell_h_pt = median_char_h * 1.5  # 50% padding sopra/sotto

    # Converti in coordinate relative rispetto all'immagine target
    cell_w_rel = (cell_w_pt * PT_TO_PX) / TARGET_WIDTH
    cell_h_rel = (cell_h_pt * PT_TO_PX) / TARGET_HEIGHT

    return cell_w_rel, cell_h_rel


def calibrate_from_pdf(
    pdf_path: str,
    page_index: int = 1,
    item_ids_left: Optional[List[str]] = None,
    item_ids_right: Optional[List[str]] = None,
) -> Tuple[dict, dict]:
    """
    Calibra la griglia CBCL estraendo le posizioni dei digit dal PDF.

    Args:
        pdf_path: percorso al file PDF
        page_index: indice pagina (0-based), default=1 (pagina 2)
        item_ids_left: lista ID item colonna sinistra (se None, auto-detect)
        item_ids_right: lista ID item colonna destra (se None, auto-detect)

    Returns:
        (page_data, layout_info)
        - page_data: dict compatibile con cbcl_grid.json
        - layout_info: dict con metadati sulla calibrazione
    """
    pdf = pdfplumber.open(pdf_path)

    if page_index >= len(pdf.pages):
        raise ValueError(f"Il PDF ha solo {len(pdf.pages)} pagine, "
                         f"richiesta pagina {page_index + 1}")

    page = pdf.pages[page_index]
    page_w = page.width   # in punti PDF
    page_h = page.height

    # 1. Estrai digit di risposta
    response_chars = _extract_response_chars(page)

    # 2. Raggruppa in righe
    rows = _group_into_rows(response_chars)

    # 3. Separa colonne
    left_rows, right_rows = _split_columns(rows, page_w)

    # 4. Trova etichette item dal testo PDF
    # Left: testo dopo x~85pt, Right: testo dopo x~365pt
    left_digit_x = left_rows[0][2]['x1'] if left_rows else 80
    right_digit_x = right_rows[0][2]['x1'] if right_rows else 360

    left_labels = _find_item_labels(page, left_rows,
                                    left_digit_x + 5, page_w / 2 - 10)
    right_labels = _find_item_labels(page, right_rows,
                                     right_digit_x + 5, page_w - 10)

    # 5. Assegna item IDs
    if item_ids_left is None:
        # Auto-detect: usa i numeri trovati nel testo
        item_ids_left = []
        last_numeric = 0
        for label in left_labels:
            if label.isdigit():
                last_numeric = int(label)
                item_ids_left.append(label)
            elif label and label[0].isalpha():
                # Sub-item: prefisso con ultimo numero
                item_ids_left.append(f"{last_numeric}{label}")
            else:
                item_ids_left.append(label or f"?{len(item_ids_left)+1}")

    if item_ids_right is None:
        item_ids_right = []
        last_numeric = 0
        for label in right_labels:
            if label.isdigit():
                last_numeric = int(label)
                item_ids_right.append(label)
            elif label and label[0].isalpha():
                item_ids_right.append(f"{last_numeric}{label}")
            else:
                item_ids_right.append(label or f"?{len(item_ids_right)+1}")

    # Validazione conteggio
    if len(item_ids_left) != len(left_rows):
        raise ValueError(
            f"Mismatch: {len(item_ids_left)} item IDs left vs "
            f"{len(left_rows)} righe rilevate")
    if len(item_ids_right) != len(right_rows):
        raise ValueError(
            f"Mismatch: {len(item_ids_right)} item IDs right vs "
            f"{len(right_rows)} righe rilevate")

    # 6. Calcola dimensioni cella
    all_rows = left_rows + right_rows
    cell_w_rel, cell_h_rel = _compute_cell_dimensions(all_rows, page_w, page_h)

    # 7. Costruisci coordinate relative per ogni item
    items = {}

    def row_to_coords(row):
        """Converte una riga di 3 char in coordinate relative."""
        centers = []
        for c in row:
            cx = ((c['x0'] + c['x1']) / 2.0) * PT_TO_PX
            cy = ((c['top'] + c['bottom']) / 2.0) * PT_TO_PX
            centers.append((cx, cy))

        return {
            "row_y": centers[0][1] / TARGET_HEIGHT,
            "col_0_x": centers[0][0] / TARGET_WIDTH,
            "col_1_x": centers[1][0] / TARGET_WIDTH,
            "col_2_x": centers[2][0] / TARGET_WIDTH,
        }

    for item_id, row in zip(item_ids_left, left_rows):
        items[item_id] = row_to_coords(row)

    for item_id, row in zip(item_ids_right, right_rows):
        items[item_id] = row_to_coords(row)

    # 8. Costruisci output
    page_data = {
        "cell_width_rel": round(cell_w_rel, 6),
        "cell_height_rel": round(cell_h_rel, 6),
        "items": {k: {kk: round(vv, 6) for kk, vv in v.items()}
                  for k, v in items.items()}
    }

    layout_info = {
        "pdf_path": str(pdf_path),
        "page_index": page_index,
        "page_size_pt": (page_w, page_h),
        "left_column_items": item_ids_left,
        "right_column_items": item_ids_right,
        "total_items": len(items),
        "col_spacing_left_pt": _median_spacing(left_rows),
        "col_spacing_right_pt": _median_spacing(right_rows),
        "cell_size_px": (
            round(cell_w_rel * TARGET_WIDTH, 1),
            round(cell_h_rel * TARGET_HEIGHT, 1)
        ),
    }

    pdf.close()
    return page_data, layout_info


def _median_spacing(rows):
    """Calcola spaziatura mediana tra col_0 e col_1."""
    if not rows:
        return 0.0
    spacings = [r[1]['x0'] - r[0]['x0'] for r in rows if len(r) >= 2]
    return round(float(np.median(spacings)), 2) if spacings else 0.0
