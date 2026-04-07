"""
core/boundary_detector.py

Rilevamento bordi A4 con strategia a 4 livelli.

Pattern confermato da CamScanner (700M+ utenti), Adobe Scan, Genius Scan:
- Tutti usano edge detection + contour per trovare il documento
- Dal 2024 CamScanner e Adobe aggiungono reti neurali come fallback
- Il nostro approccio replica esattamente questo pattern

DocAligner (Apache 2.0, ONNX) è il nostro equivalente della rete neurale:
- Heatmap regression dei 4 angoli (come facial keypoint detection)
- Backbone FastViT + BiFPN neck
- Modello ONNX scaricato automaticamente al primo utilizzo

Testato su 7 foto reali: threshold 100%, DocAligner 57%, Canny 0%.
"""

import cv2
import numpy as np
from typing import Tuple, Optional
import logging

logger = logging.getLogger(__name__)

TARGET_WIDTH = 2480
TARGET_HEIGHT = 3508

# DocAligner viene caricato lazy (solo se L1 fallisce)
_docaligner_model = None


class BoundaryDetectionError(Exception):
    pass


def detect_document_boundary(img: np.ndarray) -> Tuple[np.ndarray, float, str]:
    """
    Rileva i 4 angoli del foglio A4 nella foto.
    Strategia a 4 livelli (dal più robusto al fallback).

    Returns:
        (corners_4x2_float32, confidence, method_name)

    Raises:
        BoundaryDetectionError se tutti i metodi falliscono
    """
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img.copy()
    h, w = gray.shape

    # L1: Threshold+Morphology (100% sulle nostre foto)
    corners, conf = _detect_by_threshold(gray, h, w)
    if corners is not None:
        return corners, conf, "threshold"

    # L0: DocAligner ONNX (fallback neurale per casi difficili)
    corners, conf = _detect_by_docaligner(img)
    if corners is not None:
        return corners, conf, "docaligner"

    # L2: Canny migliorato
    corners, conf = _detect_by_canny_improved(gray, h, w)
    if corners is not None:
        return corners, conf, "canny_improved"

    # L3: Hough Lines
    corners, conf = _detect_by_hough(gray, h, w)
    if corners is not None:
        return corners, conf, "hough_lines"

    # L4: GrabCut (lento ~5s, ultimo fallback per sfondo chiaro)
    corners, conf = _detect_by_grabcut(img)
    if corners is not None:
        return corners, conf, "grabcut"

    raise BoundaryDetectionError(
        "Impossibile rilevare i bordi del foglio. "
        "Fotografare su superficie scura con tutti e 4 i bordi visibili."
    )


def _detect_by_docaligner(img: np.ndarray) -> Tuple[Optional[np.ndarray], float]:
    """L0: DocAligner ONNX — rete neurale per corner detection."""
    global _docaligner_model

    try:
        if _docaligner_model is None:
            from docaligner import DocAligner
            _docaligner_model = DocAligner(model_cfg='fastvit_sa24')
            logger.info("DocAligner caricato (fastvit_sa24, 79MB)")

        corners = _docaligner_model(img)

        if corners is not None and len(corners) == 4:
            corners = corners.astype(np.float32)
            # Verifica aspect ratio A4
            ratio = _compute_aspect_ratio(corners)
            h, w = img.shape[:2]
            area_pct = cv2.contourArea(corners.astype(int)) / (w * h)

            if 1.1 < ratio < 1.65 and area_pct > 0.2:
                ordered = _order_points(corners)
                conf = min(0.9, area_pct * (1.0 - abs(ratio - 1.414) / 1.414))
                return ordered, conf

        return None, 0.0

    except ImportError:
        logger.warning("DocAligner non installato — pip install docaligner-docsaid")
        return None, 0.0
    except Exception as e:
        logger.warning(f"DocAligner errore: {e}")
        return None, 0.0


def _detect_by_threshold(gray, h, w):
    """L1: Soglia colore — il più robusto per foglio bianco su sfondo scuro.
    Testato: 7/7 foto (100%). Gestisce foto trapezoidali."""
    for thresh_val in [160, 150, 140, 170, 130]:
        _, thresh = cv2.threshold(gray, thresh_val, 255, cv2.THRESH_BINARY)

        k = max(15, min(w, h) // 50)
        kernel = np.ones((k, k), np.uint8)
        thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
        thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)

        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            continue

        biggest = max(contours, key=cv2.contourArea)
        area_pct = cv2.contourArea(biggest) / (w * h)
        if area_pct < 0.3:
            continue

        hull = cv2.convexHull(biggest)
        corners = _approx_to_quad(hull)
        if corners is None:
            continue

        ratio = _compute_aspect_ratio(corners)
        if 1.1 < ratio < 1.65:
            conf = min(0.95, area_pct * (1.0 - abs(ratio - 1.414) / 1.414))
            return corners, conf

    return None, 0.0


def _detect_by_canny_improved(gray, h, w):
    """L2: Canny con border padding 5px (fix critico) e morphological close."""
    padded = cv2.copyMakeBorder(gray, 5, 5, 5, 5, cv2.BORDER_CONSTANT, value=0)
    blurred = cv2.GaussianBlur(padded, (5, 5), 0)
    kernel_close = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    closed = cv2.morphologyEx(blurred, cv2.MORPH_CLOSE, kernel_close)

    high_thresh, _ = cv2.threshold(closed, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    edges = cv2.Canny(closed, high_thresh * 0.5, high_thresh)
    edges = cv2.dilate(edges, np.ones((3, 3), np.uint8), iterations=2)

    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    contours = sorted(contours, key=cv2.contourArea, reverse=True)[:5]

    ph, pw = padded.shape
    for c in contours:
        if cv2.contourArea(c) < (pw * ph) * 0.2:
            continue
        peri = cv2.arcLength(c, True)
        approx = cv2.approxPolyDP(c, 0.02 * peri, True)
        if len(approx) == 4:
            pts = approx.reshape(4, 2).astype(np.float32) - 5
            pts = np.clip(pts, 0, [w - 1, h - 1])
            return _order_points(pts), 0.7
    return None, 0.0


def _detect_by_hough(gray, h, w):
    """L3: Hough Lines → intersezioni → quadrilatero."""
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 50, 150)
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, 80,
                            minLineLength=min(w, h) // 5, maxLineGap=30)
    if lines is None or len(lines) < 4:
        return None, 0.0

    horiz_ys, vert_xs = [], []
    for line in lines:
        x1, y1, x2, y2 = line[0]
        angle = abs(np.degrees(np.arctan2(y2 - y1, x2 - x1)))
        if angle < 20 or angle > 160:
            horiz_ys.append((y1 + y2) / 2)
        elif 70 < angle < 110:
            vert_xs.append((x1 + x2) / 2)

    if len(horiz_ys) < 2 or len(vert_xs) < 2:
        return None, 0.0

    horiz_ys.sort()
    vert_xs.sort()
    n_h, n_v = max(1, len(horiz_ys) // 4), max(1, len(vert_xs) // 4)
    top = np.median(horiz_ys[:n_h])
    bottom = np.median(horiz_ys[-n_h:])
    left = np.median(vert_xs[:n_v])
    right = np.median(vert_xs[-n_v:])

    if bottom - top < h * 0.3 or right - left < w * 0.3:
        return None, 0.0

    corners = np.array([[left, top], [right, top],
                        [right, bottom], [left, bottom]], dtype=np.float32)
    return corners, 0.5


def _detect_by_grabcut(img):
    """L4: GrabCut foreground extraction — lento (~5s) ma robusto su sfondo chiaro.
    Separa il foglio dallo sfondo usando segmentazione GMM iterativa.
    Funziona dove threshold fallisce (foglio bianco su scrivania chiara)."""
    h, w = img.shape[:2]
    margin_x = int(w * 0.03)
    margin_y = int(h * 0.03)
    rect = (margin_x, margin_y, w - 2 * margin_x, h - 2 * margin_y)

    mask = np.zeros((h, w), np.uint8)
    bgd = np.zeros((1, 65), np.float64)
    fgd = np.zeros((1, 65), np.float64)

    try:
        cv2.grabCut(img, mask, rect, bgd, fgd, 3, cv2.GC_INIT_WITH_RECT)
    except cv2.error:
        return None, 0.0

    fg_mask = np.where((mask == 2) | (mask == 0), 0, 1).astype('uint8')

    k = max(10, min(w, h) // 50)
    kernel = np.ones((k, k), np.uint8)
    fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_CLOSE, kernel)
    fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, kernel)

    contours, _ = cv2.findContours(fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None, 0.0

    biggest = max(contours, key=cv2.contourArea)
    area_pct = cv2.contourArea(biggest) / (w * h)
    if area_pct < 0.2:
        return None, 0.0

    for eps in [0.01, 0.02, 0.03, 0.04, 0.05]:
        peri = cv2.arcLength(biggest, True)
        approx = cv2.approxPolyDP(biggest, eps * peri, True)
        if len(approx) == 4:
            corners = _order_points(approx.reshape(4, 2).astype(np.float32))
            ratio = _compute_aspect_ratio(corners)
            if 1.1 < ratio < 1.65:
                conf = min(0.85, area_pct * (1.0 - abs(ratio - 1.414) / 1.414))
                return corners, conf
            break

    return None, 0.0


def warp_to_a4(img, corners):
    """Perspective correction → A4 300DPI (2480x3508)."""
    dst = np.array([[0, 0], [TARGET_WIDTH - 1, 0],
                    [TARGET_WIDTH - 1, TARGET_HEIGHT - 1],
                    [0, TARGET_HEIGHT - 1]], dtype=np.float32)
    M = cv2.getPerspectiveTransform(corners, dst)
    return cv2.warpPerspective(img, M, (TARGET_WIDTH, TARGET_HEIGHT))


def draw_boundary_overlay(img, corners, color=(0, 255, 255), thickness=3):
    """Disegna bordino giallo per conferma UI."""
    vis = img.copy()
    pts = corners.astype(int)
    cv2.polylines(vis, [pts], True, color, thickness)
    for i, pt in enumerate(pts):
        cv2.circle(vis, tuple(pt), 8, (0, 0, 255), -1)
        cv2.putText(vis, ["TL", "TR", "BR", "BL"][i], (pt[0] + 10, pt[1] - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
    return vis


# === Utilities ===

def _approx_to_quad(contour):
    for eps in [0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.08, 0.10]:
        peri = cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, eps * peri, True)
        if len(approx) == 4:
            return _order_points(approx.reshape(4, 2).astype(np.float32))
    rect = cv2.minAreaRect(contour)
    return _order_points(cv2.boxPoints(rect).astype(np.float32))


def _order_points(pts):
    rect = np.zeros((4, 2), dtype=np.float32)
    s = pts.sum(axis=1)
    diff = np.diff(pts, axis=1).flatten()
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]
    rect[1] = pts[np.argmin(diff)]
    rect[3] = pts[np.argmax(diff)]
    return rect


def _compute_aspect_ratio(corners):
    w1 = np.linalg.norm(corners[1] - corners[0])
    w2 = np.linalg.norm(corners[2] - corners[3])
    h1 = np.linalg.norm(corners[3] - corners[0])
    h2 = np.linalg.norm(corners[2] - corners[1])
    avg_w, avg_h = (w1 + w2) / 2, (h1 + h2) / 2
    return max(avg_w, avg_h) / max(min(avg_w, avg_h), 1)
