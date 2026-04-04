"""
core/preprocessor.py

Pipeline di pre-processing fotografico per questionari CBCL.
Input:  path immagine o array numpy BGR
Output: immagine numpy BGR raddrizzata, pulita, normalizzata

PIPELINE:
  1. Caricamento e validazione formato
  2. White Balance automatico (xphoto)
  3. Conversione LAB → CLAHE su canale L → grayscale migliorato
  4. Denoising (fastNlMeans)
  5. Deskew (raddrizzamento rotazione)
  6. Rilevamento bordi documento (HED deep learning + Canny fallback)
  7. Correzione prospettiva (warpPerspective) con forzatura A4
  8. Normalizzazione risoluzione a 2480x3508 (A4 300dpi)
  9. Miglioramento contrasto (CLAHE)
"""

import cv2
import numpy as np
from pathlib import Path
from typing import Union, Tuple, Optional


# Risoluzione target: A4 a 300 DPI
TARGET_WIDTH = 2480
TARGET_HEIGHT = 3508
A4_ASPECT_RATIO = TARGET_HEIGHT / TARGET_WIDTH  # 1.4145

# HED model paths
_HED_DIR = Path(__file__).parent.parent / "models" / "hed"
_HED_PROTOTXT = _HED_DIR / "deploy.prototxt"
_HED_MODEL = _HED_DIR / "hed_pretrained_bsds.caffemodel"
_hed_net = None  # Lazy-loaded singleton


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
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
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
    h=10 è il valore ottimale per foto da smartphone a 8-12 MP.
    """
    return cv2.fastNlMeansDenoising(gray, h=10, templateWindowSize=7, searchWindowSize=21)


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


def _load_hed_net():
    """Carica il modello HED (lazy singleton)."""
    global _hed_net
    if _hed_net is None and _HED_MODEL.exists() and _HED_PROTOTXT.exists():
        _hed_net = cv2.dnn.readNetFromCaffe(str(_HED_PROTOTXT), str(_HED_MODEL))
    return _hed_net


def _hed_edges(gray: np.ndarray) -> Optional[np.ndarray]:
    """
    Rileva bordi con HED (Holistically-Nested Edge Detection).
    Produce edge map molto piu pulita di Canny su foto con sfondi complessi.
    """
    net = _load_hed_net()
    if net is None:
        return None

    h, w = gray.shape
    # HED vuole BGR, riconverti da gray
    bgr = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)

    # Resize a dimensione standard per HED (larghezza 500px per velocita)
    scale = 500.0 / w
    inp = cv2.resize(bgr, (500, int(h * scale)))

    blob = cv2.dnn.blobFromImage(inp, scalefactor=1.0, size=inp.shape[1::-1],
                                  mean=(104.00698793, 116.66876762, 122.67891434),
                                  swapRB=False, crop=False)
    net.setInput(blob)
    hed_out = net.forward()
    hed_out = hed_out[0, 0]
    hed_out = (255 * hed_out).astype(np.uint8)

    # Resize back a dimensione originale
    hed_out = cv2.resize(hed_out, (w, h))

    # Threshold per ottenere edge binari
    _, edges = cv2.threshold(hed_out, 50, 255, cv2.THRESH_BINARY)

    # Dilata per collegare bordi interrotti
    kernel = np.ones((3, 3), np.uint8)
    edges = cv2.dilate(edges, kernel, iterations=1)

    return edges


def _find_corners_from_edges(edges: np.ndarray, min_area: float) -> Optional[np.ndarray]:
    """Trova il quadrilatero piu grande in una edge map."""
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None

    contours = sorted(contours, key=cv2.contourArea, reverse=True)[:5]
    for contour in contours:
        if cv2.contourArea(contour) < min_area:
            continue
        peri = cv2.arcLength(contour, True)
        for eps in [0.02, 0.04, 0.06, 0.08]:
            approx = cv2.approxPolyDP(contour, eps * peri, True)
            if len(approx) == 4:
                pts = approx.reshape(4, 2).astype(np.float32)
                return _order_points(pts)
    return None


def find_document_corners(gray: np.ndarray) -> Optional[np.ndarray]:
    """
    Trova i 4 angoli del documento nel frame fotografico.
    Strategia multi-livello:
      1. HED deep learning edge detection (piu robusto)
      2. Canny classico + contorni
      3. Fallback: soglia Otsu + morphology

    Returns: array shape (4,2) con angoli [TL, TR, BR, BL] o None se non trovato
    """
    h, w = gray.shape
    min_area = (w * h) * 0.1

    # --- Strategia 1: HED Deep Learning edges ---
    hed_edges = _hed_edges(gray)
    if hed_edges is not None:
        corners = _find_corners_from_edges(hed_edges, min_area)
        if corners is not None:
            return corners

    # --- Strategia 2: Canny classico + approxPolyDP ---
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    high_thresh, _ = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    low_thresh = high_thresh * 0.5
    edges = cv2.Canny(blurred, low_thresh, high_thresh)
    kernel = np.ones((3, 3), np.uint8)
    edges = cv2.dilate(edges, kernel, iterations=1)

    corners = _find_corners_from_edges(edges, min_area)
    if corners is not None:
        return corners

    # --- Strategia 3: Soglia Otsu + morphology ---
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    kernel_big = np.ones((5, 5), np.uint8)
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel_big, iterations=3)

    corners = _find_corners_from_edges(binary, min_area)
    if corners is not None:
        return corners

    return None


def _order_points(pts: np.ndarray) -> np.ndarray:
    """
    Ordina 4 punti come [top-left, top-right, bottom-right, bottom-left].
    """
    rect = np.zeros((4, 2), dtype=np.float32)
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]   # TL: somma minima
    rect[2] = pts[np.argmax(s)]   # BR: somma massima
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]  # TR: diff minima
    rect[3] = pts[np.argmax(diff)]  # BL: diff massima
    return rect


def correct_perspective(img: np.ndarray, corners: np.ndarray) -> np.ndarray:
    """
    Applica trasformazione prospettica per ottenere vista frontale del foglio.
    Forza sempre output con aspect ratio A4 (1.4145) per garantire
    compatibilita con le coordinate della griglia calibrate dal PDF.

    Args:
        img: immagine originale (BGR o grayscale)
        corners: 4 angoli ordinati [TL, TR, BR, BL]
    Returns: immagine raddrizzata a dimensioni A4 (TARGET_WIDTH x TARGET_HEIGHT)
    """
    # Output fisso A4: la griglia e calibrata su queste dimensioni esatte
    dst = np.array([
        [0, 0],
        [TARGET_WIDTH - 1, 0],
        [TARGET_WIDTH - 1, TARGET_HEIGHT - 1],
        [0, TARGET_HEIGHT - 1]
    ], dtype=np.float32)

    M = cv2.getPerspectiveTransform(corners, dst)
    return cv2.warpPerspective(img, M, (TARGET_WIDTH, TARGET_HEIGHT))


def align_to_template(gray: np.ndarray, page: str = "page_4") -> Tuple[np.ndarray, bool, dict]:
    """
    Allinea la foto preprocessata al template PDF usando feature matching.
    Strategia: SIFT con maschera estesa (header, footer, margini, bordi griglia)
    + fallback AKAZE se SIFT non trova abbastanza match.

    Args:
        gray: immagine grayscale gia con prospettiva corretta
        page: pagina del questionario ("page_4", "page_5", "page_6")

    Returns:
        (immagine_allineata, successo, info_dict)
    """
    page_to_file = {
        "page_4": "cbcl1_page_4.png",
        "page_5": "cbcl1_page_5.png",
        "page_6": "cbcl1_page_6.png",
    }

    template_dir = Path(__file__).parent.parent / "data" / "pdf_pages"
    template_file = template_dir / page_to_file.get(page, "cbcl1_page_4.png")
    info = {"method": None, "inliers": 0, "good_matches": 0}

    if not template_file.exists():
        return gray, False, info

    template = cv2.imread(str(template_file), cv2.IMREAD_GRAYSCALE)
    if template is None:
        return gray, False, info

    template = cv2.resize(template, (gray.shape[1], gray.shape[0]))
    h, w = gray.shape

    # Maschera estesa: header, footer, margini, divisore centrale, bordi griglia
    mask = np.zeros((h, w), dtype=np.uint8)
    mask[0:int(h * 0.22), :] = 255                    # header + intestazione griglia
    mask[int(h * 0.88):h, :] = 255                     # footer
    mask[:, 0:int(w * 0.06)] = 255                     # margine sinistro (numeri item)
    mask[:, int(w * 0.46):int(w * 0.55)] = 255         # divisore centrale tra colonne
    mask[:, int(w * 0.94):] = 255                      # margine destro

    def _try_match(detector, matcher, desc_name):
        """Prova feature matching con un detector specifico."""
        kp1, des1 = detector.detectAndCompute(template, mask)
        kp2, des2 = detector.detectAndCompute(gray, mask)

        if des1 is None or des2 is None or len(kp1) < 10 or len(kp2) < 10:
            return None, 0, 0

        raw_matches = matcher.knnMatch(des1, des2, k=2)
        good = [m for m, n in raw_matches if m.distance < 0.75 * n.distance]

        if len(good) < 8:
            return None, len(good), 0

        src_pts = np.float32([kp1[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
        dst_pts = np.float32([kp2[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)

        # USAC_MAGSAC se disponibile, altrimenti RANSAC
        try:
            H, mask_h = cv2.findHomography(dst_pts, src_pts, cv2.USAC_MAGSAC, 3.0)
        except (cv2.error, AttributeError):
            H, mask_h = cv2.findHomography(dst_pts, src_pts, cv2.RANSAC, 3.0)

        inliers = int(mask_h.ravel().sum()) if mask_h is not None else 0

        if H is None or inliers < 6:
            return None, len(good), inliers

        det = np.linalg.det(H[:2, :2])
        if det < 0.3 or det > 3.0:
            return None, len(good), inliers

        return H, len(good), inliers

    # --- Strategia 1: SIFT (piu accurato) ---
    sift = cv2.SIFT_create(nfeatures=10000)
    flann = cv2.FlannBasedMatcher(dict(algorithm=1, trees=5), dict(checks=80))
    H, good_n, inliers = _try_match(sift, flann, "sift")

    if H is not None:
        aligned = cv2.warpPerspective(gray, H, (w, h))
        info = {"method": "sift", "inliers": inliers, "good_matches": good_n}
        return aligned, True, info

    # --- Strategia 2: AKAZE fallback (piu robusto su immagini compresse) ---
    akaze = cv2.AKAZE_create()
    bf = cv2.BFMatcher(cv2.NORM_HAMMING)
    H, good_n, inliers = _try_match(akaze, bf, "akaze")

    if H is not None:
        aligned = cv2.warpPerspective(gray, H, (w, h))
        info = {"method": "akaze", "inliers": inliers, "good_matches": good_n}
        return aligned, True, info

    info = {"method": None, "inliers": inliers, "good_matches": good_n}
    return gray, False, info


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

    # --- Step 3: Per ogni item, trova la linea orizzontale piu vicina ---
    cell_h_rel = page_data["cell_height_rel"]
    cell_h_px = cell_h_rel * h

    for item_id, coords in items.items():
        expected_y_px = coords["row_y"] * h

        # Trova le due linee orizzontali che racchiudono la riga
        # (la riga dell'item si trova TRA due linee della griglia)
        diffs = y_clusters - expected_y_px
        above = y_clusters[diffs <= cell_h_px * 0.5]
        below = y_clusters[diffs >= -cell_h_px * 0.5]

        if len(above) > 0 and len(below) > 0:
            nearest_above = above[np.argmin(np.abs(above - expected_y_px))]
            nearest_below = below[np.argmin(np.abs(below - expected_y_px))]

            # Correggi solo se la linea rilevata è vicina (< 2x altezza cella)
            best_line = nearest_above if abs(nearest_above - expected_y_px) < abs(nearest_below - expected_y_px) else nearest_below
            delta = best_line - expected_y_px

            if abs(delta) < cell_h_px * 2:
                result["row_y_offsets"][item_id] = delta / h

        # Offset X per colonne: trova linee verticali vicine alle colonne attese
        if len(x_clusters) > 0:
            col_offsets = {}
            for col_key in ["col_0_x", "col_1_x", "col_2_x"]:
                if col_key not in coords:
                    continue
                expected_x_px = coords[col_key] * w
                nearest_idx = np.argmin(np.abs(x_clusters - expected_x_px))
                delta_x = x_clusters[nearest_idx] - expected_x_px
                cell_w_px = page_data["cell_width_rel"] * w

                if abs(delta_x) < cell_w_px * 2:
                    col_offsets[col_key] = delta_x / w

            if col_offsets:
                result["col_x_offsets"][item_id] = col_offsets

    result["success"] = len(result["row_y_offsets"]) > 5
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
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    return clahe.apply(gray)


def preprocess_full_pipeline(
    source: Union[str, Path, np.ndarray],
    debug: bool = False
) -> Tuple[np.ndarray, dict]:
    """
    Esegue l'intera pipeline di preprocessing.

    Args:
        source: path file immagine o array numpy
        debug: se True, salva immagini intermedie in /tmp/smart_ocr_debug/

    Returns:
        (immagine_elaborata_grayscale, metadata_dict)

        metadata_dict contiene:
        - 'original_size': (w, h) originale
        - 'final_size': (w, h) finale
        - 'deskew_angle': angolo correzione rotazione
        - 'perspective_corrected': True/False
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

    # Step 3: Conversione grayscale via LAB (illuminazione normalizzata)
    gray = to_grayscale_via_lab(img_bgr)

    # Step 4: Denoising
    gray = denoise(gray)
    if debug:
        _save_debug(gray, "03_denoised")

    # Step 5: Deskew
    gray, angle = deskew(gray)
    metadata['deskew_angle'] = angle
    if abs(angle) > 15:
        warnings.append(f"Rotazione elevata rilevata: {angle:.1f}°. Foto piu diritta migliora l'accuratezza.")

    # Step 6: Rileva angoli documento (HED + Canny + Otsu)
    corners = find_document_corners(gray)

    if corners is not None:
        gray = correct_perspective(gray, corners)
        metadata['perspective_corrected'] = True
    else:
        metadata['perspective_corrected'] = False
        warnings.append("Bordi documento non rilevati. Foto con piu contrasto tra foglio e sfondo migliora il risultato.")
        gray = normalize_resolution(gray, TARGET_WIDTH)

    # Step 7: Migliora contrasto
    gray = enhance_contrast(gray)

    h1, w1 = gray.shape
    metadata['final_size'] = (w1, h1)
    metadata['aspect_ratio'] = h1 / w1 if w1 > 0 else 0
    metadata['warnings'] = warnings

    if debug:
        _save_debug(gray, "06_final")

    return gray, metadata


def _save_debug(img: np.ndarray, name: str):
    """Salva immagine di debug."""
    import tempfile
    debug_dir = Path(tempfile.gettempdir()) / "smart_ocr_debug"
    debug_dir.mkdir(exist_ok=True)
    cv2.imwrite(str(debug_dir / f"{name}.jpg"), img)
