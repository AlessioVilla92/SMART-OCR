"""
core/preprocessor.py

Pipeline di pre-processing fotografico per questionari CBCL.
Input:  path immagine o array numpy BGR
Output: immagine numpy grayscale raddrizzata, pulita, normalizzata

PIPELINE v2.1:
  1. Caricamento e validazione formato
  2. White Balance automatico (xphoto)
  3. Rimozione inchiostro rosso
  4. Rimozione ombre (shadow removal)
  5. Conversione LAB → CLAHE su canale L → grayscale migliorato
  6. Denoising (bilateralFilter)
  7. Deskew (raddrizzamento rotazione)
  8. Normalizzazione risoluzione
  9. Miglioramento contrasto (CLAHE)

NOTE: Boundary detection e perspective correction sono ora in boundary_detector.py.
      Template alignment è ora in template_aligner.py.
"""

import cv2
import numpy as np
from pathlib import Path
from typing import Union, Tuple, Optional


# Risoluzione target: A4 a 300 DPI
TARGET_WIDTH = 2480
TARGET_HEIGHT = 3508
A4_ASPECT_RATIO = TARGET_HEIGHT / TARGET_WIDTH  # 1.4145


class PreprocessingError(Exception):
    """Eccezione specifica per errori di preprocessing."""
    pass


def load_image(source: Union[str, Path, np.ndarray]) -> np.ndarray:
    """
    Carica immagine da path o accetta array numpy.
    Gestisce JPEG, PNG, HEIC (via Pillow fallback).

    Returns: array BGR uint8
    Raises: PreprocessingError se il file non è leggibile
    """
    if isinstance(source, np.ndarray):
        return source.copy()

    path = Path(source)
    if not path.exists():
        raise PreprocessingError(f"File non trovato: {path}")

    # Prova cv2 diretto (JPEG, PNG, BMP, TIFF)
    img = cv2.imread(str(path))

    # Fallback Pillow per HEIC e formati non standard
    if img is None:
        try:
            from PIL import Image
            pil_img = Image.open(path).convert("RGB")
            img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
        except Exception as e:
            raise PreprocessingError(f"Impossibile aprire {path}: {e}")

    if img is None:
        raise PreprocessingError(f"Formato immagine non supportato: {path}")

    return img


def remove_red_ink(img_bgr: np.ndarray) -> np.ndarray:
    """
    Rimuove segni in inchiostro rosso dalla foto.
    Utile per feature matching: i segni dell'utente non devono
    interferire con il matching al template pulito.
    Usa inpainting sui pixel rossi in HSV.
    """
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    # Rosso wrappa in HSV: 0-10 e 170-180
    mask1 = cv2.inRange(hsv, (0, 50, 50), (10, 255, 255))
    mask2 = cv2.inRange(hsv, (170, 50, 50), (180, 255, 255))
    red_mask = mask1 | mask2

    if cv2.countNonZero(red_mask) > 0:
        return cv2.inpaint(img_bgr, red_mask, 3, cv2.INPAINT_TELEA)
    return img_bgr


def white_balance(img_bgr: np.ndarray) -> np.ndarray:
    """
    Applica white balance automatico per normalizzare il colore
    su foto con illuminazione calda/fredda/fluorescente.
    Usa SimpleWB da opencv-contrib (xphoto).
    """
    try:
        wb = cv2.xphoto.createSimpleWB()
        return wb.balanceWhite(img_bgr)
    except AttributeError:
        # opencv-contrib non disponibile, skip
        return img_bgr


def remove_shadows(img_bgr: np.ndarray) -> np.ndarray:
    """
    Rimuove ombre dalla foto stimando lo sfondo per canale.
    Utile per foto con illuminazione laterale o ombra della mano.
    Ottimizzato: stima sfondo su immagine ridotta, poi applica a full-res.
    """
    h, w = img_bgr.shape[:2]
    # Downsample per velocizzare medianBlur (bottleneck)
    scale = min(1.0, 800.0 / w)
    if scale < 1.0:
        small = cv2.resize(img_bgr, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    else:
        small = img_bgr

    result = np.zeros_like(img_bgr)
    for c in range(3):
        dilated = cv2.dilate(small[:, :, c], np.ones((7, 7), np.uint8))
        bg_small = cv2.medianBlur(dilated, 21)
        if scale < 1.0:
            bg = cv2.resize(bg_small, (w, h), interpolation=cv2.INTER_LINEAR)
        else:
            bg = bg_small
        diff = 255 - cv2.absdiff(img_bgr[:, :, c], bg)
        result[:, :, c] = cv2.normalize(diff, None, 0, 255, cv2.NORM_MINMAX)
    return result


def check_image_quality(gray: np.ndarray):
    """
    Verifica qualità minima dell'immagine (risoluzione e nitidezza).
    Raises PreprocessingError se sotto soglia.
    """
    h, w = gray.shape
    if w < 800 or h < 1000:
        raise PreprocessingError(f"Risoluzione troppo bassa ({w}x{h})")
    blur = cv2.Laplacian(gray, cv2.CV_64F).var()
    if blur < 80:
        raise PreprocessingError(f"Foto sfocata (score={blur:.0f}, min=80)")


def to_grayscale_via_lab(img_bgr: np.ndarray) -> np.ndarray:
    """
    Converte BGR in grayscale usando il canale L di LAB.
    Il canale L rappresenta la luminosita percepita,
    piu robusto alle variazioni di colore rispetto a cv2.cvtColor(BGR2GRAY).
    Applica CLAHE sul canale L per normalizzare illuminazione non uniforme.
    """
    if len(img_bgr.shape) == 2:
        return img_bgr

    lab = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2LAB)
    l_channel = lab[:, :, 0]

    # CLAHE sul canale L: normalizza illuminazione non uniforme
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(16, 16))
    l_enhanced = clahe.apply(l_channel)

    return l_enhanced


def to_grayscale(img: np.ndarray) -> np.ndarray:
    """Converte BGR in grayscale. Ignora se già grayscale."""
    if len(img.shape) == 2:
        return img
    return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)


def denoise(gray: np.ndarray) -> np.ndarray:
    """
    Riduce rumore fotografico mantenendo i bordi netti.
    bilateralFilter: ~50ms vs fastNlMeansDenoising ~6000ms.
    """
    return cv2.bilateralFilter(gray, d=5, sigmaColor=75, sigmaSpace=75)


def binarize_adaptive(gray: np.ndarray) -> np.ndarray:
    """
    Binarizzazione adattiva Gaussian.
    Gestisce illuminazione non uniforme (ombra sul foglio, luce laterale).
    blockSize=31 ottimale per font ~12pt a 300dpi.
    C=10 è l'offset di sottrazione dalla media locale.
    """
    return cv2.adaptiveThreshold(
        gray, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        blockSize=31,
        C=10
    )


def deskew(gray: np.ndarray) -> Tuple[np.ndarray, float]:
    """
    Rileva e corregge la rotazione del foglio.
    Usa momenti dell'immagine binarizzata per calcolare l'angolo.

    Returns: (immagine raddrizzata, angolo_correzione_gradi)
    """
    # Inverti per avere testo bianco su nero (necessario per momenti)
    thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]

    # Trova coordinate dei pixel bianchi
    coords = np.column_stack(np.where(thresh > 0))
    if len(coords) < 100:
        return gray, 0.0

    # Calcola angolo con minAreaRect
    angle = cv2.minAreaRect(coords)[-1]

    # Normalizza angolo tra -45 e 45
    if angle < -45:
        angle = 90 + angle
    elif angle > 45:
        angle = angle - 90

    # Limita correzione a max ±30° (oltre è probabilmente un errore)
    if abs(angle) > 30:
        return gray, 0.0

    # Applica rotazione
    h, w = gray.shape
    center = (w // 2, h // 2)
    M = cv2.getRotationMatrix2D(center, -angle, 1.0)
    rotated = cv2.warpAffine(
        gray, M, (w, h),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_REPLICATE
    )
    return rotated, angle


def detect_grid_offsets(
    gray: np.ndarray,
    page: str = "page_4"
) -> dict:
    """
    Rileva le linee orizzontali/verticali della griglia con Hough transform,
    confronta con le posizioni attese dal template, e calcola offset
    per-riga Y e per-colonna X per correzione locale.

    Returns:
        {
            "row_y_offsets": {item_id: delta_y_rel, ...},
            "col_x_offsets": {item_id: {"col_0_x": dx, "col_1_x": dx, "col_2_x": dx}, ...},
            "success": bool
        }
    """
    import json as _json

    h, w = gray.shape
    result = {"row_y_offsets": {}, "col_x_offsets": {}, "success": False}

    # Carica template
    template_path = Path(__file__).parent.parent / "templates" / "cbcl_grid.json"
    if not template_path.exists():
        return result

    with open(template_path) as f:
        grid = _json.load(f)

    if page not in grid["pages"]:
        return result

    page_data = grid["pages"][page]
    items = page_data["items"]

    # --- Step 1: Rileva linee orizzontali ---
    binary = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV, 15, 5
    )

    # Kernel orizzontale largo per isolare linee della griglia
    h_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (w // 15, 1))
    horizontal = cv2.morphologyEx(binary, cv2.MORPH_OPEN, h_kernel)

    h_lines = cv2.HoughLinesP(
        horizontal, 1, np.pi / 180,
        threshold=80, minLineLength=w // 8, maxLineGap=30
    )

    # Kernel verticale alto per isolare linee verticali
    v_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, h // 25))
    vertical = cv2.morphologyEx(binary, cv2.MORPH_OPEN, v_kernel)

    v_lines = cv2.HoughLinesP(
        vertical, 1, np.pi / 180,
        threshold=80, minLineLength=h // 15, maxLineGap=30
    )

    # --- Step 2: Clusterizza Y delle linee orizzontali ---
    detected_y = []
    if h_lines is not None:
        for line in h_lines:
            y_mid = (line[0][1] + line[0][3]) / 2.0
            detected_y.append(y_mid)

    detected_x = []
    if v_lines is not None:
        for line in v_lines:
            x_mid = (line[0][0] + line[0][2]) / 2.0
            detected_x.append(x_mid)

    if len(detected_y) < 3:
        return result

    # Clusterizza Y con tolleranza di 8px
    detected_y.sort()
    y_clusters = []
    cluster = [detected_y[0]]
    for y in detected_y[1:]:
        if y - cluster[-1] < 8:
            cluster.append(y)
        else:
            y_clusters.append(np.median(cluster))
            cluster = [y]
    y_clusters.append(np.median(cluster))

    # Clusterizza X
    detected_x.sort()
    x_clusters = []
    if detected_x:
        cluster = [detected_x[0]]
        for x in detected_x[1:]:
            if x - cluster[-1] < 8:
                cluster.append(x)
            else:
                x_clusters.append(np.median(cluster))
                cluster = [x]
        x_clusters.append(np.median(cluster))

    y_clusters = np.array(y_clusters)
    x_clusters = np.array(x_clusters)

    # --- Step 3: Calcola offset globale smooth (non per-item) ---
    # Strategia: calcola la mediana dell'offset Y tra linee rilevate e attese,
    # poi applica un singolo offset globale. Evita il problema di snappare
    # piu items alla stessa linea.
    cell_h_rel = page_data["cell_height_rel"]
    cell_h_px = cell_h_rel * h
    cell_w_px = page_data["cell_width_rel"] * w

    # Raccogli tutti i row_y attesi
    expected_ys = sorted(set(coords["row_y"] for coords in items.values()))
    expected_ys_px = [y * h for y in expected_ys]

    # Per ogni posizione Y attesa, trova la linea rilevata piu vicina
    y_deltas = []
    for ey_px in expected_ys_px:
        dists = np.abs(y_clusters - ey_px)
        nearest_idx = np.argmin(dists)
        delta = y_clusters[nearest_idx] - ey_px
        # Solo se il delta e ragionevole (< 1 altezza cella)
        if abs(delta) < cell_h_px * 1.5:
            y_deltas.append(delta)

    # Calcola offset Y globale come mediana dei delta
    global_dy = np.median(y_deltas) / h if len(y_deltas) >= 3 else 0.0

    # Applica offset Y globale a tutti gli items
    if abs(global_dy) > 0.001:
        for item_id in items:
            result["row_y_offsets"][item_id] = global_dy

    # Calcola offset X globale per ogni gruppo di colonne
    # (colonna sinistra vs colonna destra del questionario)
    if len(x_clusters) > 0:
        # Raggruppa items per posizione X (sinistra ~0.06-0.14, destra ~0.54-0.62)
        col_groups = {}
        for item_id, coords in items.items():
            for col_key in ["col_0_x", "col_1_x", "col_2_x"]:
                if col_key not in coords:
                    continue
                expected_x_px = coords[col_key] * w
                dists = np.abs(x_clusters - expected_x_px)
                nearest_idx = np.argmin(dists)
                delta_x = x_clusters[nearest_idx] - expected_x_px
                if abs(delta_x) < cell_w_px * 1.5:
                    group_key = "left" if coords[col_key] < 0.4 else "right"
                    col_groups.setdefault((group_key, col_key), []).append(delta_x / w)

        # Mediana per gruppo
        for (group, col_key), deltas in col_groups.items():
            if len(deltas) >= 3:
                median_dx = np.median(deltas)
                if abs(median_dx) > 0.001:
                    for item_id, coords in items.items():
                        if col_key in coords:
                            item_group = "left" if coords[col_key] < 0.4 else "right"
                            if item_group == group:
                                result["col_x_offsets"].setdefault(item_id, {})[col_key] = median_dx

    result["success"] = abs(global_dy) > 0.001 or len(result["col_x_offsets"]) > 0
    return result


def normalize_resolution(img: np.ndarray, target_width: int = TARGET_WIDTH) -> np.ndarray:
    """
    Ridimensiona a larghezza standard mantenendo aspect ratio.
    Necessario per garantire che le coordinate della griglia siano sempre valide.
    """
    h, w = img.shape[:2]
    if w == target_width:
        return img

    scale = target_width / w
    new_h = int(h * scale)

    # Usa INTER_AREA per downscale, INTER_CUBIC per upscale
    interp = cv2.INTER_AREA if scale < 1 else cv2.INTER_CUBIC
    return cv2.resize(img, (target_width, new_h), interpolation=interp)


def enhance_contrast(gray: np.ndarray) -> np.ndarray:
    """
    Migliora il contrasto locale con CLAHE.
    clipLimit=2.0 evita amplificazione del rumore.
    tileGridSize=(8,8) opera su zone di ~300px su A4 300dpi.
    """
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(16, 16))
    return clahe.apply(gray)


def preprocess_full_pipeline(
    source: Union[str, Path, np.ndarray],
    debug: bool = False
) -> Tuple[np.ndarray, dict]:
    """
    Esegue l'intera pipeline di preprocessing v2.1.

    NOTE: Boundary detection e perspective correction sono gestiti esternamente
    da boundary_detector.py (FASE 1-2 in app.py). Questa funzione assume
    che l'input sia già perspective-corrected oppure raw.

    Args:
        source: path file immagine o array numpy (BGR o grayscale)
        debug: se True, salva immagini intermedie in /tmp/smart_ocr_debug/

    Returns:
        (immagine_elaborata_grayscale, metadata_dict)

        metadata_dict contiene:
        - 'original_size': (w, h) originale
        - 'final_size': (w, h) finale
        - 'deskew_angle': angolo correzione rotazione
        - 'warnings': lista di avvisi
    """
    warnings = []
    metadata = {}

    # Step 1: Carica
    img_bgr = load_image(source)
    h0, w0 = img_bgr.shape[:2]
    metadata['original_size'] = (w0, h0)

    if debug:
        _save_debug(img_bgr, "01_original")

    # Step 2: White Balance automatico
    img_bgr = white_balance(img_bgr)
    if debug:
        _save_debug(img_bgr, "02_white_balanced")

    # Step 2b: Rimozione inchiostro rosso
    img_bgr = remove_red_ink(img_bgr)

    # Step 3: Rimozione ombre
    img_bgr = remove_shadows(img_bgr)
    if debug:
        _save_debug(img_bgr, "03_shadow_removed")

    # Step 4: Conversione grayscale via LAB (illuminazione normalizzata)
    gray = to_grayscale_via_lab(img_bgr)

    # Step 5: Denoising (bilateralFilter, ~50ms)
    gray = denoise(gray)
    if debug:
        _save_debug(gray, "04_denoised")

    # Step 6: Deskew
    gray, angle = deskew(gray)
    metadata['deskew_angle'] = angle
    if abs(angle) > 15:
        warnings.append(f"Rotazione elevata rilevata: {angle:.1f}. Foto piu diritta migliora l'accuratezza.")

    # Step 7: Normalizza risoluzione se necessario
    gray = normalize_resolution(gray, TARGET_WIDTH)

    # Step 8: Migliora contrasto
    gray = enhance_contrast(gray)

    h1, w1 = gray.shape
    metadata['final_size'] = (w1, h1)
    metadata['aspect_ratio'] = h1 / w1 if w1 > 0 else 0
    metadata['warnings'] = warnings

    if debug:
        _save_debug(gray, "08_final")

    return gray, metadata


def _save_debug(img: np.ndarray, name: str):
    """Salva immagine di debug."""
    import tempfile
    debug_dir = Path(tempfile.gettempdir()) / "smart_ocr_debug"
    debug_dir.mkdir(exist_ok=True)
    cv2.imwrite(str(debug_dir / f"{name}.jpg"), img)
