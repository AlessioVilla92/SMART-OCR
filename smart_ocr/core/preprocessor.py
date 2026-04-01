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

    # Step 3: Conversione grayscale via LAB (illuminazione normalizzata)
    gray = to_grayscale_via_lab(img_bgr)
    if debug:
        _save_debug(gray, "03_lab_grayscale")

    # Step 4: Denoising
    gray = denoise(gray)
    if debug:
        _save_debug(gray, "04_denoised")

    # Step 5: Deskew
    gray, angle = deskew(gray)
    metadata['deskew_angle'] = angle
    if abs(angle) > 15:
        warnings.append(f"Rotazione elevata rilevata: {angle:.1f}°. Foto piu diritta migliora l'accuratezza.")
    if debug:
        _save_debug(gray, f"05_deskewed_{angle:.1f}deg")

    # Step 6: Rileva angoli documento (HED + Canny + Otsu)
    corners = find_document_corners(gray)

    if corners is not None:
        # Warp direttamente a TARGET_WIDTH x TARGET_HEIGHT (A4)
        gray = correct_perspective(gray, corners)
        metadata['perspective_corrected'] = True
        if debug:
            _save_debug(gray, "06_perspective_corrected")
    else:
        metadata['perspective_corrected'] = False
        warnings.append("Bordi documento non rilevati. Usa tutta l'immagine. Foto con piu contrasto tra foglio e sfondo migliora il risultato.")
        # Normalizza a larghezza target (senza forzare altezza)
        gray = normalize_resolution(gray, TARGET_WIDTH)

    # Step 7: Migliora contrasto finale
    gray = enhance_contrast(gray)

    h1, w1 = gray.shape
    metadata['final_size'] = (w1, h1)
    metadata['aspect_ratio'] = h1 / w1 if w1 > 0 else 0
    metadata['warnings'] = warnings

    if debug:
        _save_debug(gray, "07_final")

    return gray, metadata


def _save_debug(img: np.ndarray, name: str):
    """Salva immagine di debug."""
    import tempfile
    debug_dir = Path(tempfile.gettempdir()) / "smart_ocr_debug"
    debug_dir.mkdir(exist_ok=True)
    cv2.imwrite(str(debug_dir / f"{name}.jpg"), img)
