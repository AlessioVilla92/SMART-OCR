# SMART OCR v2.1 — Istruzioni Claude Code (VERIFICATE su dati reali)

> **Data:** Aprile 2026 | **Repository:** github.com/AlessioVilla92/SMART-OCR
> **Testato su:** 7 foto reali CBCL da smartphone (progetto /mnt/project)
> **Tutte le librerie testate e confermate funzionanti**

---

## RISULTATI TEST VERIFICATI

### Boundary Detection — Confronto metodi testati su 7 foto reali:

| Metodo | Successo | Note |
|--------|----------|------|
| **Threshold+Morphology (nostro)** | **7/7 (100%)** | Più robusto per foglio bianco |
| DocAligner fastvit_sa24 (79MB ONNX) | 4/7 (57%) | Fallisce quando foglio riempie il frame |
| DocAligner lcnet100 (4.5MB ONNX) | 1/7 (14%) | Troppo piccolo, inaffidabile |
| Canny classico (preprocessor.py attuale) | 0/7 (0%) | Completamente inutile |

**Conclusione:** Il nostro metodo threshold è PRIMARY. DocAligner è SECONDARY
come fallback per casi difficili (sfondo bianco, basso contrasto).

### OMR Reading — Il gap critico confermato:
- Boundary detection funziona, ma dopo il warp le coordinate template
  NON corrispondono → 55-85% degli item risulta "missing"
- **Serve SIFT+ECC alignment** per registrare la foto al template PDF
- Quando le celle sono centrate, fill_ratio separa bene: marked 0.15-0.29 vs vuoto 0.00-0.05

### Performance:
- fastNlMeansDenoising: 6000ms → **SOSTITUIRE** con bilateralFilter (50ms)
- DocAligner: ~200ms per foto (accettabile come fallback)
- SIFT matching stimato: ~500ms
- Pipeline totale target: **<2 secondi**

---

## DIPENDENZE

### Già nel progetto (NON cambiare):
```
opencv-contrib-python==4.9.0.80   # SIFT, FLANN, ECC, Hough, matchTemplate
scikit-learn==1.8.0                # HOG+SVM classifier
numpy==1.26.4
streamlit>=1.32.0
pandas==2.2.1
Pillow==10.3.0
joblib==1.4.0
albumentations==2.0.8              # MIT! NON aggiornare
pdfplumber>=0.11.0
```

### Da AGGIUNGERE al requirements.txt:
```
# Boundary detection neurale (fallback)
docaligner-docsaid>=1.1.0          # Apache 2.0, include ONNX models
PyTurboJPEG<2.0                    # Dipendenza DocAligner (versione 1.x per compatibilità!)

# Generazione riferimenti PDF (una tantum)
PyMuPDF>=1.24.0                    # MIT, per renderizzare PDF a 300 DPI
```

### ATTENZIONE PyTurboJPEG:
DocAligner dipende da `capybara-docsaid` che usa `PyTurboJPEG`.
La versione 2.0 richiede libturbojpeg 3.0 (non disponibile su Ubuntu 24).
**FISSARE `PyTurboJPEG<2.0`** nel requirements.txt.
Su Windows: installare libjpeg-turbo da https://github.com/libjpeg-turbo/libjpeg-turbo/releases
Su macOS: `brew install jpeg-turbo`

---

## STEP 1: Generare immagini di riferimento da PDF

**File da creare:**
- `templates/cbcl_page4_ref.png` (2480×3508 px, grayscale)
- `templates/cbcl_page5_ref.png` (2480×3508 px, grayscale)

```python
# Script: scripts/generate_references.py
import fitz  # PyMuPDF
from pathlib import Path

def generate_references():
    pdf_path = Path(__file__).parent.parent / "cbcl.pdf"
    doc = fitz.open(str(pdf_path))
    
    # A4 a 300 DPI: scala = 300/72 = 4.1667
    mat = fitz.Matrix(300/72, 300/72)
    
    pages = {
        "page_4": 3,  # indice 0-based → pagina 4 del PDF
        "page_5": 4,  # indice 0-based → pagina 5 del PDF
    }
    
    templates_dir = Path(__file__).parent.parent / "templates"
    
    for page_key, page_idx in pages.items():
        page = doc[page_idx]
        pix = page.get_pixmap(matrix=mat, colorspace=fitz.csGRAY)
        
        out_path = templates_dir / f"cbcl_{page_key}_ref.png"
        pix.save(str(out_path))
        
        print(f"✅ {out_path.name}: {pix.width}x{pix.height}")
        assert pix.width == 2480 or pix.height == 3508, \
            f"Dimensioni inattese: {pix.width}x{pix.height}"
    
    doc.close()

if __name__ == "__main__":
    generate_references()
```

**NOTA:** Verificare gli indici pagina! Il CBCL italiano potrebbe avere
layout diverso. Pagina 4 = quella con items 1-54 (due colonne),
Pagina 5 = quella con items 55-112 (due colonne).
Confrontare con il PDF `Cbcl_618_GENITORI.pdf` nel progetto.

---

## STEP 2: Fix templates/cbcl_grid.json

### Modifiche:
1. **AGGIUNGERE** 56e, 56f, 56g, 56h (interpolazione tra 56d e 57)
2. **RIMUOVERE** `"page_4_photo"` (duplicato con coordinate shiftate errate)
3. **RIMUOVERE** item `"56"` generico (è un header, non ha celle)

```python
# Script per calcolare coordinate 56e-56h:
import json

with open("templates/cbcl_grid.json") as f:
    data = json.load(f)

# Trova la pagina che contiene 56d
for page_key, page_data in data["pages"].items():
    items = page_data["items"]
    if "56d" in items:
        y_56d = items["56d"]["row_y"]
        
        # Trova il prossimo item dopo 56d (potrebbe essere 57 o 56e se esiste)
        # Usa lo spacing tipico tra sub-items
        y_56c = items.get("56c", {}).get("row_y", y_56d - 0.016)
        spacing = y_56d - y_56c  # spacing tra sub-items
        
        for i, sub in enumerate(["56e", "56f", "56g", "56h"]):
            items[sub] = {
                "row_y": round(y_56d + spacing * (i + 1), 6),
                "col_0_x": items["56d"]["col_0_x"],
                "col_1_x": items["56d"]["col_1_x"],
                "col_2_x": items["56d"]["col_2_x"],
            }
        
        print(f"Aggiunti 56e-56h in {page_key}")
        break

# Rimuovi page_4_photo se esiste
if "page_4_photo" in data["pages"]:
    del data["pages"]["page_4_photo"]
    print("Rimosso page_4_photo")

# Rimuovi item "56" generico (è un header)
for page_data in data["pages"].values():
    if "56" in page_data["items"]:
        del page_data["items"]["56"]
        print("Rimosso item 56 generico")

with open("templates/cbcl_grid.json", "w") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
```

---

## STEP 3: Aggiornare core/calibrator.py

Aggiungere 56e-56h al CBCL_LAYOUT. Verificare sul PDF fisico in quale
pagina/colonna cadono (nel CBCL standard: pagina 5, colonna sinistra,
tra item 56 e item 57).

```python
# In CBCL_LAYOUT, aggiornare right_column di page_4:
"right_column": {
    "items": [str(i) for i in range(30, 56)] + 
             ["56a", "56b", "56c", "56d", "56e", "56f", "56g", "56h"],
}
```

---

## STEP 4: Creare core/boundary_detector.py

Questo modulo implementa il rilevamento bordi A4 con 4 livelli:

**Livello 0: DocAligner ONNX** (fallback neurale, 200ms)
- `DocAligner(model_cfg='fastvit_sa24')` — 79MB, 57% sulle nostre foto
- Utile quando lo sfondo è bianco o il contrasto è basso
- Restituisce np.ndarray shape (4,2) con i 4 angoli

**Livello 1: Threshold+Morphology** (metodo primario, 3-270ms)
- Soglia a 160 sul grayscale → morphological close+open → convexHull
- 100% successo sulle nostre foto, il più robusto
- Gestisce foto storte (trapezoidali) perfettamente

**Livello 2: Canny migliorato** (fallback classico)
- Border padding 5px + morphological close + Canny + dilate
- Risolve il bug del Canny attuale che fallisce al 100%

**Livello 3: Hough Lines** (fallback ultimo)
- Linee orizzontali/verticali → intersezioni → quadrilatero

```python
"""
core/boundary_detector.py

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
    lines = cv2.HoughLinesP(edges, 1, np.pi/180, 80,
                            minLineLength=min(w, h)//5, maxLineGap=30)
    if lines is None or len(lines) < 4:
        return None, 0.0
    
    horiz_ys, vert_xs = [], []
    for line in lines:
        x1, y1, x2, y2 = line[0]
        angle = abs(np.degrees(np.arctan2(y2-y1, x2-x1)))
        if angle < 20 or angle > 160:
            horiz_ys.append((y1+y2)/2)
        elif 70 < angle < 110:
            vert_xs.append((x1+x2)/2)
    
    if len(horiz_ys) < 2 or len(vert_xs) < 2:
        return None, 0.0
    
    horiz_ys.sort()
    vert_xs.sort()
    n_h, n_v = max(1, len(horiz_ys)//4), max(1, len(vert_xs)//4)
    top = np.median(horiz_ys[:n_h])
    bottom = np.median(horiz_ys[-n_h:])
    left = np.median(vert_xs[:n_v])
    right = np.median(vert_xs[-n_v:])
    
    if bottom - top < h * 0.3 or right - left < w * 0.3:
        return None, 0.0
    
    corners = np.array([[left, top], [right, top],
                        [right, bottom], [left, bottom]], dtype=np.float32)
    return corners, 0.5


def warp_to_a4(img, corners):
    """Perspective correction → A4 300DPI (2480×3508)."""
    dst = np.array([[0, 0], [TARGET_WIDTH-1, 0],
                    [TARGET_WIDTH-1, TARGET_HEIGHT-1],
                    [0, TARGET_HEIGHT-1]], dtype=np.float32)
    M = cv2.getPerspectiveTransform(corners, dst)
    return cv2.warpPerspective(img, M, (TARGET_WIDTH, TARGET_HEIGHT))


def draw_boundary_overlay(img, corners, color=(0, 255, 255), thickness=3):
    """Disegna bordino giallo per conferma UI."""
    vis = img.copy()
    pts = corners.astype(int)
    cv2.polylines(vis, [pts], True, color, thickness)
    for i, pt in enumerate(pts):
        cv2.circle(vis, tuple(pt), 8, (0, 0, 255), -1)
        cv2.putText(vis, ["TL","TR","BR","BL"][i], (pt[0]+10, pt[1]-10),
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
    avg_w, avg_h = (w1+w2)/2, (h1+h2)/2
    return max(avg_w, avg_h) / max(min(avg_w, avg_h), 1)
```

---

## STEP 5: Creare core/template_aligner.py

**SIFT + ECC confermato dalla ricerca:**
- SIFT: 128-dim float descriptors, migliore per form stampati (IEEE Tareen & Saleem 2018)
- FLANN: matching veloce con KD-Tree
- RANSAC: homography robusta (filtra outlier)
- ECC: sub-pixel refinement (usato in Accusoft FormFix per US Census, 2px accuracy)
- Tutto in opencv-contrib-python, ZERO dipendenze aggiuntive

Il codice completo per `template_aligner.py` è nel file di verifica precedente
(SMART_OCR_ISTRUZIONI_CLAUDE_CODE.md, STEP 5). Copiare integralmente.

---

## STEP 6: Aggiornare core/preprocessor.py

### Modifiche precise:

1. **RIMUOVERE** `find_document_corners()`, `_order_points()`,
   `correct_perspective()` → ora in boundary_detector.py

2. **SOSTITUIRE** fastNlMeansDenoising (6000ms) con bilateralFilter (50ms):
```python
# PRIMA (LENTO):
# gray = cv2.fastNlMeansDenoising(gray, h=10, templateWindowSize=7, searchWindowSize=21)
# DOPO (VELOCE):
gray = cv2.bilateralFilter(gray, d=5, sigmaColor=75, sigmaSpace=75)
```

3. **AGGIUNGERE** shadow removal PRIMA del grayscale:
```python
def remove_shadows(img_bgr):
    result = np.zeros_like(img_bgr)
    for c in range(3):
        dilated = cv2.dilate(img_bgr[:,:,c], np.ones((7,7), np.uint8))
        bg = cv2.medianBlur(dilated, 21)
        diff = 255 - cv2.absdiff(img_bgr[:,:,c], bg)
        result[:,:,c] = cv2.normalize(diff, None, 0, 255, cv2.NORM_MINMAX)
    return result
```

4. **AGGIORNARE** CLAHE: `tileGridSize=(16, 16)` (era 8×8)

5. **AGGIUNGERE** quality gates:
```python
def check_image_quality(gray):
    h, w = gray.shape
    if w < 800 or h < 1000:
        raise PreprocessingError(f"Risoluzione troppo bassa ({w}x{h})")
    blur = cv2.Laplacian(gray, cv2.CV_64F).var()
    if blur < 80:
        raise PreprocessingError(f"Foto sfocata (score={blur:.0f}, min=80)")
```

---

## STEP 7: Aggiornare core/omr_classifier.py

### Soglie ottimizzate (testate):
```python
MIN_MARK_RATIO = 0.12   # era 0.08 — alzato per ridurre falsi positivi
MAX_EMPTY_RATIO = 0.05  # era 0.04
AMBIGUITY_RATIO = 0.6   # invariato
```

### AGGIUNGERE doppia conferma nella logica di decisione:
```python
# Dopo aver determinato marked_column e value:
if value is not None:
    other_ratios = [r for col, r in counts.items() if col != marked_column]
    max_other = max(other_ratios) if other_ratios else 0
    
    if max_other < 0.05:
        # ✅ CONFERMA FORTE: 1 marcata + 2 vuote
        confidence = min(1.0, confidence * 1.2)
    elif max_other < 0.08:
        # ⚠️ CONFERMA OK
        pass
    else:
        # 🔴 CONFERMA DEBOLE
        confidence *= 0.6
        if flag is None:
            flag = "low_confidence"
```

---

## STEP 8: Aggiornare app.py — Pipeline 5 fasi

```python
from core.boundary_detector import detect_document_boundary, warp_to_a4, draw_boundary_overlay
from core.template_aligner import TemplateAligner

# Singleton aligner (caricato una volta)
@st.cache_resource
def get_aligner():
    aligner = TemplateAligner()
    aligner.load_reference("page_4")
    aligner.load_reference("page_5")
    return aligner

def process_uploaded_image(uploaded_file, page, method, debug=False):
    img = cv2.imread(tmp_path)
    
    # FASE 1: Boundary detection + bordino giallo
    corners, conf, det_method = detect_document_boundary(img)
    overlay = draw_boundary_overlay(img, corners)
    st.image(cv2.cvtColor(overlay, cv2.COLOR_BGR2RGB),
             caption=f"Bordi: {det_method} (conf={conf:.0%})")
    
    # FASE 2: Perspective correction A4
    warped = warp_to_a4(img, corners)
    
    # FASE 3: Preprocessing (shadow removal + denoise + CLAHE)
    gray, meta = preprocess_full_pipeline(warped, debug=debug)
    
    # FASE 4: SIFT Alignment al template PDF
    aligner = get_aligner()
    aligned, align_info = aligner.align(gray, page)
    
    if debug:
        st.json(align_info)
        grid_vis = visualize_grid_overlay(aligned, page)
        st.image(grid_vis, caption="Griglia sovrapposta dopo alignment")
    
    # FASE 5: OMR Reading con doppia conferma
    cells_dict = extract_all_cells(aligned, page)
    
    if method == "svm":
        classifier = get_classifier()
        results = {item: classifier.predict_item_cells(cells)
                   for item, cells in cells_dict.items()}
    else:
        results = classify_all_items_omr(cells_dict)
    
    return build_score_report(results, session_id=f"upload_{uploaded_file.name}")
```

---

## CHECKLIST FINALE

Dopo implementazione, verificare TUTTI questi punti:

- [ ] `cbcl_page4_ref.png` esiste, è 2480×3508, grayscale
- [ ] `cbcl_page5_ref.png` esiste, è 2480×3508, grayscale
- [ ] `cbcl_grid.json` contiene 56e, 56f, 56g, 56h
- [ ] `cbcl_grid.json` NON contiene "page_4_photo"
- [ ] `cbcl_grid.json` NON contiene item "56" generico
- [ ] `calibrator.py` CBCL_LAYOUT include 56e-56h
- [ ] `boundary_detector.py` ha 4 livelli (threshold, DocAligner, Canny, Hough)
- [ ] `template_aligner.py` ha SIFT + ECC + anchor validation
- [ ] `preprocessor.py` NON usa fastNlMeansDenoising (usa bilateralFilter)
- [ ] `preprocessor.py` ha shadow removal e quality gates
- [ ] `omr_classifier.py` ha doppia conferma (2 vuote confermano 1 marcata)
- [ ] `omr_classifier.py` ha soglie MIN_MARK=0.12, MAX_EMPTY=0.05
- [ ] `requirements.txt` include docaligner-docsaid e PyTurboJPEG<2.0
- [ ] `requirements.txt` include PyMuPDF
- [ ] `app.py` mostra bordino giallo dopo boundary detection
- [ ] `app.py` mostra overlay griglia in debug mode
- [ ] Il tempo totale per foto è <3 secondi
- [ ] Testare su TUTTE le foto in /mnt/project/ e TEST1/
