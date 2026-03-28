# SMART OCR — Istruzioni di Implementazione per Claude Code

> **Progetto:** Smart OCR  
> **Scopo:** Software per la lettura automatica di questionari CBCL cartacei fotografati  
> **Architettura:** Python 3.11 + OpenCV + SVM + Streamlit — completamente offline, no AI in produzione  
> **Compatibilità:** macOS (Intel + Apple Silicon M1/M2/M3) e Windows 10/11  
> **Data documento:** Marzo 2026

---

## INDICE

1. [Prerequisiti e Ambiente](#1-prerequisiti-e-ambiente)
2. [Struttura del Progetto](#2-struttura-del-progetto)
3. [Dipendenze e requirements.txt](#3-dipendenze-e-requirementstxt)
4. [Modulo: Preprocessor](#4-modulo-preprocessor)
5. [Modulo: Grid Extractor](#5-modulo-grid-extractor)
6. [Modulo: Classifier (HOG + SVM)](#6-modulo-classifier-hog--svm)
7. [Modulo: Scorer CBCL](#7-modulo-scorer-cbcl)
8. [Tool di Labeling per Training](#8-tool-di-labeling-per-training)
9. [Generazione Dati Sintetici](#9-generazione-dati-sintetici)
10. [Script di Training SVM](#10-script-di-training-svm)
11. [App Streamlit Principale](#11-app-streamlit-principale)
12. [Packaging Eseguibile](#12-packaging-eseguibile)
13. [Test e Validazione](#13-test-e-validazione)
14. [Note Critiche di Compatibilità](#14-note-critiche-di-compatibilità)

---

## 1. PREREQUISITI E AMBIENTE

### Python Version
**Usa Python 3.11 (NON 3.13 o superiore)**  
Python 3.12 è accettabile ma 3.11 è lo sweet spot per compatibilità di tutte le librerie.

### Setup Ambiente Virtuale

**macOS e Linux:**
```bash
python3.11 -m venv venv
source venv/bin/activate
pip install --upgrade pip setuptools wheel
```

**Windows:**
```cmd
python -m venv venv
venv\Scripts\activate
pip install --upgrade pip setuptools wheel
```

### Verifica Architettura macOS (CRITICO per Apple Silicon)
```bash
# Esegui questo PRIMA di installare qualsiasi cosa su Mac
python -c "import platform; print(platform.machine())"
# Output atteso su M1/M2/M3: arm64
# Output atteso su Intel Mac: x86_64
```

Se output è `arm64`, usa Miniforge invece di pip per OpenCV:
```bash
# Solo per Apple Silicon M1/M2/M3
# Prima installa Miniforge: https://github.com/conda-forge/miniforge
conda create -n smart_ocr python=3.11
conda activate smart_ocr
conda install -c conda-forge opencv scikit-learn numpy pillow
pip install streamlit pandas albumentations==2.0.8 joblib
```

---

## 2. STRUTTURA DEL PROGETTO

Crea questa struttura di cartelle ESATTA:

```
smart_ocr/
├── app.py                          # Entry point Streamlit UI
├── run.py                          # Wrapper per PyInstaller
├── requirements.txt
├── pyproject.toml
│
├── core/
│   ├── __init__.py
│   ├── preprocessor.py             # Pipeline OpenCV preprocessing foto
│   ├── grid_extractor.py           # Estrazione celle dalla griglia CBCL
│   ├── classifier.py               # HOG features + SVM predict
│   └── scorer.py                   # Mappa item→valore, calcola score CBCL
│
├── training/
│   ├── __init__.py
│   ├── label_tool.py               # UI Streamlit per etichettare celle
│   ├── augmentor.py                # Generazione varianti sintetiche
│   └── train_svm.py                # Script training + salvataggio model.pkl
│
├── models/
│   └── .gitkeep                    # model.pkl viene generato qui dopo training
│
├── templates/
│   └── cbcl_grid.json              # Coordinate celle CBCL (definite una volta)
│
├── data/
│   ├── raw_cells/                  # Celle ritagliate dalle foto reali
│   │   ├── cerchio/
│   │   ├── x_rossa/
│   │   ├── vuoto/
│   │   └── ambiguo/
│   └── synthetic/                  # Celle generate sinteticamente
│       ├── cerchio/
│       ├── x_rossa/
│       └── vuoto/
│
├── output/                         # CSV e JSON risultati (gitignore)
│   └── .gitkeep
│
├── tests/
│   ├── test_preprocessor.py
│   ├── test_classifier.py
│   └── sample_images/              # Immagini di test (non dati pazienti)
│
└── .gitignore
```

### .gitignore
```gitignore
venv/
__pycache__/
*.pyc
*.pkl
output/
data/raw_cells/
*.jpg
*.jpeg
*.png
*.heic
.DS_Store
```

---

## 3. DIPENDENZE E REQUIREMENTS.TXT

### requirements.txt (per Intel Mac e Windows)
```txt
# Core image processing
opencv-contrib-python==4.9.0.80

# Machine Learning
scikit-learn==1.8.0
numpy==1.26.4
scipy==1.13.0

# Data augmentation per training (ATTENZIONE: NON aggiornare oltre 2.0.8 - diventa AGPL)
albumentations==2.0.8

# UI
streamlit==1.32.0

# Data handling
pandas==2.2.1
Pillow==10.3.0

# Model persistence
joblib==1.4.0

# Packaging
pyinstaller==6.6.0
```

### requirements-arm64.txt (per Apple Silicon M1/M2/M3)
```txt
# Su Apple Silicon installa OpenCV via conda-forge (vedi sezione 1)
# Poi installa solo queste via pip:
scikit-learn==1.8.0
numpy==1.26.4
scipy==1.13.0
albumentations==2.0.8
streamlit==1.32.0
pandas==2.2.1
Pillow==10.3.0
joblib==1.4.0
```

### pyproject.toml
```toml
[project]
name = "smart-ocr"
version = "1.0.0"
description = "Lettura automatica questionari CBCL"
requires-python = ">=3.11,<3.13"

[tool.pyinstaller]
# Richiesto da streamlit-desktop-app
```

### Script install automatico: setup.py
```python
"""
Esegui: python setup.py
Rileva l'architettura e installa le dipendenze corrette.
"""
import subprocess
import sys
import platform

def main():
    machine = platform.machine().lower()
    system = platform.system().lower()
    
    print(f"Sistema: {system}, Architettura: {machine}")
    
    if system == "darwin" and machine == "arm64":
        print("⚠️  Rilevato Apple Silicon (M1/M2/M3)")
        print("Usa conda-forge per OpenCV. Vedi README sezione 1.")
        print("Esegui: conda install -c conda-forge opencv scikit-learn numpy pillow")
        print("Poi: pip install -r requirements-arm64.txt")
    else:
        print("✅ Installazione standard (Intel Mac / Windows / Linux x86)")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
    
    print("✅ Setup completato.")

if __name__ == "__main__":
    main()
```

---

## 4. MODULO: PREPROCESSOR

**File:** `core/preprocessor.py`

Questo modulo riceve la foto grezza dallo smartphone e la prepara per l'estrazione della griglia. Ogni passo è deterministico e reversibile.

```python
"""
core/preprocessor.py

Pipeline di pre-processing fotografico per questionari CBCL.
Input:  path immagine o array numpy BGR
Output: immagine numpy BGR raddrizzata, pulita, normalizzata

PIPELINE:
  1. Caricamento e validazione formato
  2. Conversione grayscale
  3. Denoising (fastNlMeans)
  4. Binarizzazione adattiva (Gaussian)
  5. Deskew (raddrizzamento rotazione)
  6. Rilevamento e crop del foglio (4 angoli)
  7. Correzione prospettiva (warpPerspective)
  8. Normalizzazione risoluzione a 2480px larghezza (A4 300dpi)
  9. Miglioramento contrasto (CLAHE)
"""

import cv2
import numpy as np
from pathlib import Path
from typing import Union, Tuple, Optional


# Risoluzione target: A4 a 300 DPI
TARGET_WIDTH = 2480
TARGET_HEIGHT = 3508


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


def find_document_corners(gray: np.ndarray) -> Optional[np.ndarray]:
    """
    Trova i 4 angoli del documento nel frame fotografico.
    Usa Canny + findContours per rilevare il rettangolo del foglio.
    
    Returns: array shape (4,2) con angoli [TL, TR, BR, BL] o None se non trovato
    """
    # Blur leggero per ridurre rumore sui bordi
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    
    # Canny con soglie automatiche (metodo Otsu)
    high_thresh, _ = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    low_thresh = high_thresh * 0.5
    edges = cv2.Canny(blurred, low_thresh, high_thresh)
    
    # Dilata per connettere bordi discontinui
    kernel = np.ones((3, 3), np.uint8)
    edges = cv2.dilate(edges, kernel, iterations=1)
    
    # Trova contorni
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    if not contours:
        return None
    
    # Ordina per area decrescente, prendi i più grandi
    contours = sorted(contours, key=cv2.contourArea, reverse=True)[:5]
    
    h, w = gray.shape
    min_area = (w * h) * 0.1  # Il foglio deve occupare almeno 10% del frame
    
    for contour in contours:
        area = cv2.contourArea(contour)
        if area < min_area:
            continue
        
        # Approssima poligono
        peri = cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, 0.02 * peri, True)
        
        if len(approx) == 4:
            pts = approx.reshape(4, 2).astype(np.float32)
            return _order_points(pts)
    
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
    
    Args:
        img: immagine originale (BGR o grayscale)
        corners: 4 angoli ordinati [TL, TR, BR, BL]
    Returns: immagine raddrizzata a dimensioni A4 proporzionali
    """
    tl, tr, br, bl = corners
    
    # Calcola larghezza e altezza del documento trasformato
    width_top = np.linalg.norm(tr - tl)
    width_bottom = np.linalg.norm(br - bl)
    max_width = int(max(width_top, width_bottom))
    
    height_left = np.linalg.norm(bl - tl)
    height_right = np.linalg.norm(br - tr)
    max_height = int(max(height_left, height_right))
    
    # Mantieni proporzione A4 se necessario
    a4_ratio = 297 / 210
    if max_height / max_width < a4_ratio * 0.8:
        max_height = int(max_width * a4_ratio)
    
    dst = np.array([
        [0, 0],
        [max_width - 1, 0],
        [max_width - 1, max_height - 1],
        [0, max_height - 1]
    ], dtype=np.float32)
    
    M = cv2.getPerspectiveTransform(corners, dst)
    return cv2.warpPerspective(img, M, (max_width, max_height))


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
    
    # Step 2: Grayscale
    gray = to_grayscale(img_bgr)
    
    # Step 3: Denoising
    gray = denoise(gray)
    if debug:
        _save_debug(gray, "02_denoised")
    
    # Step 4: Deskew
    gray, angle = deskew(gray)
    metadata['deskew_angle'] = angle
    if abs(angle) > 15:
        warnings.append(f"Rotazione elevata rilevata: {angle:.1f}°. Foto più diritta migliora l'accuratezza.")
    if debug:
        _save_debug(gray, f"03_deskewed_{angle:.1f}deg")
    
    # Step 5: Rileva angoli documento
    corners = find_document_corners(gray)
    
    if corners is not None:
        gray = correct_perspective(gray, corners)
        metadata['perspective_corrected'] = True
        if debug:
            _save_debug(gray, "04_perspective_corrected")
    else:
        metadata['perspective_corrected'] = False
        warnings.append("Bordi documento non rilevati. Usa tutta l'immagine. Foto con più contrasto tra foglio e sfondo migliora il risultato.")
    
    # Step 6: Normalizza risoluzione
    gray = normalize_resolution(gray, TARGET_WIDTH)
    
    # Step 7: Migliora contrasto
    gray = enhance_contrast(gray)
    
    h1, w1 = gray.shape
    metadata['final_size'] = (w1, h1)
    metadata['warnings'] = warnings
    
    if debug:
        _save_debug(gray, "05_final")
    
    return gray, metadata


def _save_debug(img: np.ndarray, name: str):
    """Salva immagine di debug."""
    import tempfile
    debug_dir = Path(tempfile.gettempdir()) / "smart_ocr_debug"
    debug_dir.mkdir(exist_ok=True)
    cv2.imwrite(str(debug_dir / f"{name}.jpg"), img)
```

---

## 5. MODULO: GRID EXTRACTOR

**File:** `core/grid_extractor.py`

Estrae le singole celle (0, 1, 2) per ogni item del questionario CBCL.

### Template JSON della Griglia

**File:** `templates/cbcl_grid.json`

Questo file definisce le coordinate relative (percentuali 0.0-1.0) di ogni gruppo di celle per ogni item. Va calibrato una volta su un questionario campione.

```json
{
  "version": "1.0",
  "questionnaire": "CBCL 6-18",
  "pages": {
    "page_4": {
      "items": {
        "1": {"row_y": 0.172, "col_0_x": 0.052, "col_1_x": 0.092, "col_2_x": 0.132},
        "2": {"row_y": 0.193, "col_0_x": 0.052, "col_1_x": 0.092, "col_2_x": 0.132},
        "3": {"row_y": 0.228, "col_0_x": 0.052, "col_1_x": 0.092, "col_2_x": 0.132},
        "4": {"row_y": 0.249, "col_0_x": 0.052, "col_1_x": 0.092, "col_2_x": 0.132}
      },
      "cell_width_rel": 0.030,
      "cell_height_rel": 0.018
    }
  },
  "note": "Le coordinate sono frazioni (0.0-1.0) rispetto a larghezza e altezza pagina normalizzata. Calibrate su questionario CBCL standard A4."
}
```

> **NOTA PER CLAUDE CODE:** Il file `cbcl_grid.json` completo con tutti i 112 item + sub-item 56a-56h deve essere calibrato eseguendo il tool di calibrazione (vedi sezione 8). Le coordinate di esempio qui sopra sono solo 4 item a scopo illustrativo.

### Codice Grid Extractor

```python
"""
core/grid_extractor.py

Estrae le celle (0, 1, 2) per ogni item del questionario CBCL.
Usa coordinate relative dal template cbcl_grid.json.

Input:  immagine preprocessata (grayscale numpy array)
Output: dict {item_id: {"0": cell_img, "1": cell_img, "2": cell_img}}
"""

import cv2
import numpy as np
import json
from pathlib import Path
from typing import Dict, Tuple, Optional


TEMPLATE_PATH = Path(__file__).parent.parent / "templates" / "cbcl_grid.json"
CELL_SIZE = (64, 64)  # Dimensione standard cella per classificatore HOG


class GridExtractionError(Exception):
    pass


def load_template(page: str = "page_4") -> dict:
    """Carica il template della griglia dal JSON."""
    if not TEMPLATE_PATH.exists():
        raise GridExtractionError(f"Template non trovato: {TEMPLATE_PATH}")
    
    with open(TEMPLATE_PATH, "r") as f:
        template = json.load(f)
    
    if page not in template["pages"]:
        raise GridExtractionError(f"Pagina '{page}' non trovata nel template.")
    
    return template["pages"][page]


def extract_cell(
    img: np.ndarray,
    center_x_rel: float,
    center_y_rel: float,
    cell_w_rel: float,
    cell_h_rel: float
) -> np.ndarray:
    """
    Ritaglia una singola cella dall'immagine.
    
    Args:
        img: immagine grayscale
        center_x_rel, center_y_rel: centro cella in coordinate relative (0-1)
        cell_w_rel, cell_h_rel: dimensioni cella in coordinate relative
    
    Returns: cella ridimensionata a CELL_SIZE (64x64)
    """
    h, w = img.shape
    
    cx = int(center_x_rel * w)
    cy = int(center_y_rel * h)
    cw = max(int(cell_w_rel * w), 20)  # minimo 20px
    ch = max(int(cell_h_rel * h), 20)
    
    x1 = max(0, cx - cw // 2)
    y1 = max(0, cy - ch // 2)
    x2 = min(w, x1 + cw)
    y2 = min(h, y1 + ch)
    
    cell = img[y1:y2, x1:x2]
    
    if cell.size == 0:
        # Cella vuota - ritorna array bianco
        return np.full(CELL_SIZE, 255, dtype=np.uint8)
    
    # Ridimensiona a dimensione standard per HOG
    cell_resized = cv2.resize(cell, CELL_SIZE, interpolation=cv2.INTER_AREA)
    return cell_resized


def extract_all_cells(
    img: np.ndarray,
    page: str = "page_4"
) -> Dict[str, Dict[str, np.ndarray]]:
    """
    Estrae tutte le celle per tutti gli item della pagina specificata.
    
    Returns:
        {
            "1": {"0": cell_img_64x64, "1": cell_img_64x64, "2": cell_img_64x64},
            "2": {...},
            ...
            "56a": {...},  # sub-items
            ...
        }
    """
    template = load_template(page)
    items = template["items"]
    cell_w = template["cell_width_rel"]
    cell_h = template["cell_height_rel"]
    
    result = {}
    
    for item_id, coords in items.items():
        row_y = coords["row_y"]
        
        cells = {}
        for col_label, col_key in [("0", "col_0_x"), ("1", "col_1_x"), ("2", "col_2_x")]:
            if col_key not in coords:
                continue
            col_x = coords[col_key]
            cells[col_label] = extract_cell(img, col_x, row_y, cell_w, cell_h)
        
        result[item_id] = cells
    
    return result


def visualize_grid_overlay(img: np.ndarray, page: str = "page_4") -> np.ndarray:
    """
    Genera immagine con overlay delle celle rilevate.
    Utile per debug e calibrazione del template.
    
    Returns: immagine BGR con rettangoli colorati sulle celle
    """
    vis = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    template = load_template(page)
    items = template["items"]
    cell_w = template["cell_width_rel"]
    cell_h = template["cell_height_rel"]
    h, w = img.shape
    
    colors = {
        "col_0_x": (255, 100, 100),  # Blu
        "col_1_x": (100, 255, 100),  # Verde
        "col_2_x": (100, 100, 255),  # Rosso
    }
    
    for item_id, coords in items.items():
        row_y = coords["row_y"]
        
        for col_key, color in colors.items():
            if col_key not in coords:
                continue
            
            cx = int(coords[col_key] * w)
            cy = int(row_y * h)
            cw = max(int(cell_w * w), 20)
            ch = max(int(cell_h * h), 20)
            
            x1 = cx - cw // 2
            y1 = cy - ch // 2
            x2 = x1 + cw
            y2 = y1 + ch
            
            cv2.rectangle(vis, (x1, y1), (x2, y2), color, 2)
            
            # Label item
            if col_key == "col_0_x":
                cv2.putText(vis, str(item_id), (x1 - 5, cy),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.3, (0, 0, 0), 1)
    
    return vis
```

---

## 6. MODULO: CLASSIFIER (HOG + SVM)

**File:** `core/classifier.py`

```python
"""
core/classifier.py

Classificatore basato su HOG features + SVM.
In produzione carica model.pkl pre-addestrato.
NON usa AI in produzione.

Classi:
    0 = "cerchio" (numero cerchiato con penna, stile ◯)
    1 = "x_rossa" (segno X rosso sopra il numero)
    2 = "vuoto"   (nessuna marcatura)
    3 = "ambiguo" (bassa confidence, richiede revisione umana)
"""

import cv2
import numpy as np
import joblib
from pathlib import Path
from typing import Tuple, Optional


MODEL_PATH = Path(__file__).parent.parent / "models" / "model.pkl"
CELL_SIZE = (64, 64)

# Soglia confidence sotto cui la cella è "ambigua"
AMBIGUITY_THRESHOLD = 0.65

# Etichette classi
CLASS_LABELS = {0: "cerchio", 1: "x_rossa", 2: "vuoto", 3: "ambiguo"}
CLASS_TO_VALUE = {"cerchio": None, "x_rossa": None, "vuoto": None}
# Il mapping cerchio/x → valore (0, 1, 2) avviene in scorer.py


def compute_hog_features(cell: np.ndarray) -> np.ndarray:
    """
    Estrae HOG (Histogram of Oriented Gradients) da una cella 64x64.
    
    Parametri HOG ottimizzati per simboli scritti a mano su carta:
    - winSize: deve corrispondere a CELL_SIZE
    - blockSize: 16x16 (25% della cella)
    - blockStride: 8x8 (50% di overlap tra blocchi)
    - cellSize: 8x8 (8 celle per asse → 64 celle totali)
    - nbins: 9 (orientamenti da 0° a 180°)
    
    Vettore output: 1764 features per cella 64x64
    """
    hog = cv2.HOGDescriptor(
        _winSize=(64, 64),
        _blockSize=(16, 16),
        _blockStride=(8, 8),
        _cellSize=(8, 8),
        _nbins=9
    )
    
    # Assicura dimensioni corrette
    if cell.shape != CELL_SIZE:
        cell = cv2.resize(cell, CELL_SIZE)
    
    features = hog.compute(cell)
    return features.flatten()


class CBCLClassifier:
    """Classificatore SVM per celle CBCL."""
    
    def __init__(self):
        self.model = None
        self.is_loaded = False
    
    def load(self, model_path: Optional[Path] = None) -> bool:
        """
        Carica il modello SVM dal file .pkl.
        Returns: True se caricato con successo, False altrimenti.
        """
        path = model_path or MODEL_PATH
        
        if not path.exists():
            return False
        
        try:
            self.model = joblib.load(path)
            self.is_loaded = True
            return True
        except Exception as e:
            print(f"Errore caricamento modello: {e}")
            return False
    
    def predict_cell(self, cell: np.ndarray) -> Tuple[str, float]:
        """
        Predice la classe di una singola cella.
        
        Returns:
            (classe, confidence)
            classe: "cerchio", "x_rossa", "vuoto", "ambiguo"
            confidence: float 0.0-1.0
        """
        if not self.is_loaded:
            raise RuntimeError("Modello non caricato. Esegui load() prima.")
        
        features = compute_hog_features(cell)
        features = features.reshape(1, -1)
        
        # SVM con probability=True restituisce probabilità per classe
        proba = self.model.predict_proba(features)[0]
        predicted_class_idx = np.argmax(proba)
        confidence = proba[predicted_class_idx]
        
        # Classi: 0=cerchio, 1=x_rossa, 2=vuoto
        class_names = ["cerchio", "x_rossa", "vuoto"]
        predicted_class = class_names[predicted_class_idx]
        
        if confidence < AMBIGUITY_THRESHOLD:
            return "ambiguo", confidence
        
        return predicted_class, float(confidence)
    
    def predict_item_cells(
        self,
        cells: dict  # {"0": cell_64x64, "1": cell_64x64, "2": cell_64x64}
    ) -> dict:
        """
        Predice per tutte e 3 le celle di un item.
        
        Returns:
            {
                "marked_column": "0" | "1" | "2" | None,
                "value": 0 | 1 | 2 | None,
                "confidence": float,
                "flag": None | "ambiguous" | "missing" | "multiple_marks",
                "raw_predictions": {"0": (class, conf), "1": (class, conf), "2": (class, conf)}
            }
        """
        raw = {}
        for col_label, cell_img in cells.items():
            raw[col_label] = self.predict_cell(cell_img)
        
        # Trova le celle marcate (non vuote)
        marked = [
            col for col, (cls, conf) in raw.items()
            if cls in ("cerchio", "x_rossa")
        ]
        
        flag = None
        value = None
        marked_column = None
        confidence = 0.0
        
        if len(marked) == 0:
            flag = "missing"
        elif len(marked) > 1:
            flag = "multiple_marks"
        else:
            marked_column = marked[0]
            cls, conf = raw[marked_column]
            
            if cls == "ambiguo":
                flag = "ambiguous"
            else:
                value = int(marked_column)  # La colonna 0/1/2 è il valore
                confidence = conf
        
        # Controlla ambiguità generale
        any_ambiguous = any(cls == "ambiguo" for cls, _ in raw.values())
        if any_ambiguous and flag is None:
            flag = "ambiguous"
        
        return {
            "marked_column": marked_column,
            "value": value,
            "confidence": confidence,
            "flag": flag,
            "raw_predictions": {col: {"class": cls, "confidence": conf}
                                for col, (cls, conf) in raw.items()}
        }


# Singleton per uso in produzione
_classifier_instance = None

def get_classifier() -> CBCLClassifier:
    """Ritorna istanza singleton del classificatore."""
    global _classifier_instance
    if _classifier_instance is None:
        _classifier_instance = CBCLClassifier()
        _classifier_instance.load()
    return _classifier_instance
```

---

## 7. MODULO: SCORER CBCL

**File:** `core/scorer.py`

```python
"""
core/scorer.py

Mappa i risultati della classificazione agli item CBCL.
Calcola score totali e per subscale.
Genera output JSON e CSV.

Il CBCL 6-18 ha le seguenti subscale (DSM-oriented):
- Affective Problems: items 14, 24, 56c, 56d, 56e, 56f, 56g
- Anxiety Problems: items 22, 29, 30, 31, 32, 33, 34, 35, 50, 52, 112
- Somatic Problems: items 51, 54, 56a, 56b, 56h
- ADHD Problems: items 1, 4, 8, 10, 13, 17, 41, 61, 78
- Oppositional Defiant: items 3, 22, 23, 68, 86, 95, 97
- Conduct Problems: items 2, 26, 28, 39, 43, 63, 67, 72, 73, 81, 82, 90, 96, 99, 101
"""

import json
import csv
import io
from datetime import datetime
from typing import Dict, List, Optional, Any


# Subscale CBCL 6-18 DSM-oriented
CBCL_SUBSCALES = {
    "Affective_Problems": [14, 24, "56c", "56d", "56e", "56f", "56g"],
    "Anxiety_Problems": [22, 29, 30, 31, 32, 33, 34, 35, 50, 52, 112],
    "Somatic_Problems": [51, 54, "56a", "56b", "56h"],
    "ADHD_Problems": [1, 4, 8, 10, 13, 17, 41, 61, 78],
    "Oppositional_Defiant": [3, 22, 23, 68, 86, 95, 97],
    "Conduct_Problems": [2, 26, 28, 39, 43, 63, 67, 72, 73, 81, 82, 90, 96, 99, 101],
    "Internalizing": list(range(1, 36)) + ["56a", "56b", "56c", "56d", "56e", "56f", "56g", "56h"],
    "Externalizing": list(range(86, 113)),
}

# Tutti gli item CBCL nell'ordine corretto
ALL_ITEMS = (
    [str(i) for i in range(1, 56)] +
    ["56a", "56b", "56c", "56d", "56e", "56f", "56g", "56h"] +
    [str(i) for i in range(57, 113)]
)


def build_score_report(
    classification_results: Dict[str, dict],
    session_id: Optional[str] = None,
    metadata: Optional[dict] = None
) -> dict:
    """
    Costruisce il report completo da risultati classificazione.
    
    Args:
        classification_results: output di CBCLClassifier.predict_item_cells()
                                 per ogni item
        session_id: identificatore sessione (NON nome paziente)
        metadata: metadati aggiuntivi (data, operatore, ecc.)
    
    Returns: report completo come dict Python
    """
    report = {
        "session_id": session_id or f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        "timestamp": datetime.now().isoformat(),
        "metadata": metadata or {},
        "items": {},
        "subscale_scores": {},
        "total_score": 0,
        "flags": [],
        "statistics": {}
    }
    
    total = 0
    flagged_items = []
    
    # Processa ogni item
    for item_id in ALL_ITEMS:
        if item_id not in classification_results:
            report["items"][item_id] = {
                "value": None,
                "flag": "not_processed",
                "confidence": 0.0
            }
            continue
        
        result = classification_results[item_id]
        value = result.get("value")
        flag = result.get("flag")
        confidence = result.get("confidence", 0.0)
        
        report["items"][item_id] = {
            "value": value,
            "flag": flag,
            "confidence": round(confidence, 3)
        }
        
        if value is not None:
            total += value
        
        if flag and flag not in ("missing",):
            flagged_items.append({"item": item_id, "flag": flag})
    
    report["total_score"] = total
    report["flags"] = flagged_items
    
    # Calcola subscale
    for subscale_name, items in CBCL_SUBSCALES.items():
        subscale_total = 0
        subscale_missing = 0
        
        for item in items:
            item_str = str(item)
            item_data = report["items"].get(item_str, {})
            val = item_data.get("value")
            
            if val is not None:
                subscale_total += val
            else:
                subscale_missing += 1
        
        report["subscale_scores"][subscale_name] = {
            "score": subscale_total,
            "items_missing": subscale_missing
        }
    
    # Statistiche generali
    all_values = [
        report["items"][i]["value"]
        for i in ALL_ITEMS
        if report["items"].get(i, {}).get("value") is not None
    ]
    
    report["statistics"] = {
        "items_total": len(ALL_ITEMS),
        "items_scored": len(all_values),
        "items_missing": len(ALL_ITEMS) - len(all_values),
        "items_flagged": len(flagged_items),
        "items_ambiguous": sum(1 for f in flagged_items if f["flag"] == "ambiguous"),
        "mean_confidence": round(
            sum(report["items"][i].get("confidence", 0) for i in ALL_ITEMS) / len(ALL_ITEMS), 3
        )
    }
    
    return report


def report_to_csv(report: dict) -> str:
    """
    Converte il report in formato CSV.
    Una riga con tutti i valori degli item in ordine.
    Compatibile con Excel per scoring manuale.
    """
    output = io.StringIO()
    
    # Header: session_id + tutti gli item nell'ordine standard
    header = ["session_id", "timestamp"] + ALL_ITEMS + ["total_score"]
    writer = csv.writer(output)
    writer.writerow(header)
    
    # Valori
    row = [
        report["session_id"],
        report["timestamp"]
    ]
    for item_id in ALL_ITEMS:
        val = report["items"].get(item_id, {}).get("value", "")
        row.append("" if val is None else val)
    
    row.append(report["total_score"])
    writer.writerow(row)
    
    return output.getvalue()


def report_to_json(report: dict) -> str:
    """Converte il report in JSON formattato."""
    return json.dumps(report, indent=2, ensure_ascii=False)
```

---

## 8. TOOL DI LABELING PER TRAINING

**File:** `training/label_tool.py`

Questo tool va eseguito PRIMA del training per etichettare le celle reali.

```python
"""
training/label_tool.py

Tool Streamlit per etichettare manualmente le celle estratte.

Uso:
    streamlit run training/label_tool.py

Funziona in due modalità:
1. CALIBRAZIONE GRIGLIA: carica un questionario pulito, mostra overlay celle,
   permette di aggiustare le coordinate nel template JSON
2. LABELING CELLE: processa le immagini già caricate, mostra ogni cella,
   l'utente clicca la classe corretta

Output: salva celle nelle cartelle data/raw_cells/{classe}/
"""

import streamlit as st
import cv2
import numpy as np
from pathlib import Path
import json
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.preprocessor import preprocess_full_pipeline
from core.grid_extractor import extract_all_cells, visualize_grid_overlay, load_template


DATA_DIR = Path(__file__).parent.parent / "data" / "raw_cells"
CLASSES = ["cerchio", "x_rossa", "vuoto", "ambiguo"]


def ensure_dirs():
    for cls in CLASSES:
        (DATA_DIR / cls).mkdir(parents=True, exist_ok=True)


def count_existing():
    counts = {}
    for cls in CLASSES:
        counts[cls] = len(list((DATA_DIR / cls).glob("*.png")))
    return counts


def save_cell(cell: np.ndarray, label: str, item_id: str, col: str):
    """Salva cella nella cartella corrispondente."""
    import time
    timestamp = int(time.time() * 1000)
    filename = f"item{item_id}_col{col}_{timestamp}.png"
    cv2.imwrite(str(DATA_DIR / label / filename), cell)


def main():
    st.set_page_config(page_title="Smart OCR — Labeling Tool", layout="wide")
    st.title("🏷️ Smart OCR — Tool di Labeling Celle")
    
    ensure_dirs()
    
    tab1, tab2, tab3 = st.tabs(["📤 Carica Immagini", "🔬 Calibra Griglia", "🏷️ Etichetta Celle"])
    
    with tab1:
        st.header("Carica questionari per il labeling")
        
        counts = count_existing()
        col1, col2, col3, col4 = st.columns(4)
        for col, cls in zip([col1, col2, col3, col4], CLASSES):
            col.metric(f"🔵 {cls}", counts[cls])
        
        uploaded = st.file_uploader(
            "Carica foto questionari CBCL",
            type=["jpg", "jpeg", "png"],
            accept_multiple_files=True
        )
        
        if uploaded:
            st.session_state['uploaded_files'] = uploaded
            st.success(f"{len(uploaded)} file caricati")
    
    with tab2:
        st.header("Calibrazione coordinate griglia")
        st.info("Carica un questionario PULITO (non compilato) per calibrare il template.")
        
        calib_file = st.file_uploader("Questionario per calibrazione", type=["jpg", "jpeg", "png"], key="calib")
        
        if calib_file:
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
                tmp.write(calib_file.read())
                tmp_path = tmp.name
            
            with st.spinner("Preprocessing..."):
                gray, meta = preprocess_full_pipeline(tmp_path)
            
            if meta.get("warnings"):
                for w in meta["warnings"]:
                    st.warning(w)
            
            overlay = visualize_grid_overlay(gray)
            st.image(overlay, caption="Overlay griglia (Verde=col1, Rosso=col2, Blu=col0)", use_column_width=True)
            st.info("Se i rettangoli non coincidono con le celle reali, modifica manualmente `templates/cbcl_grid.json`")
    
    with tab3:
        st.header("Etichettatura celle")
        
        if 'uploaded_files' not in st.session_state or not st.session_state['uploaded_files']:
            st.warning("Carica prima le immagini nella tab '📤 Carica Immagini'")
            return
        
        if 'labeled_count' not in st.session_state:
            st.session_state['labeled_count'] = 0
        
        # Selezione file
        file_idx = st.selectbox(
            "Seleziona questionario",
            range(len(st.session_state['uploaded_files'])),
            format_func=lambda i: st.session_state['uploaded_files'][i].name
        )
        
        selected_file = st.session_state['uploaded_files'][file_idx]
        
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            tmp.write(selected_file.read())
            tmp_path = tmp.name
        selected_file.seek(0)  # Reset per rilettura
        
        with st.spinner("Preprocessing e estrazione celle..."):
            try:
                gray, meta = preprocess_full_pipeline(tmp_path)
                cells_dict = extract_all_cells(gray)
            except Exception as e:
                st.error(f"Errore: {e}")
                return
        
        st.success(f"Estratte {sum(len(v) for v in cells_dict.values())} celle da {len(cells_dict)} item")
        
        # Labeling item per item
        item_ids = list(cells_dict.keys())
        item_idx = st.number_input("Item da etichettare (indice)", 0, len(item_ids)-1, 0)
        
        item_id = item_ids[item_idx]
        item_cells = cells_dict[item_id]
        
        st.subheader(f"Item {item_id}")
        
        cols = st.columns(3)
        for col_ui, (col_label, cell_img) in zip(cols, item_cells.items()):
            with col_ui:
                st.write(f"**Colonna {col_label}**")
                # Ingrandisci per visualizzazione
                display = cv2.resize(cell_img, (128, 128), interpolation=cv2.INTER_NEAREST)
                st.image(display, width=128)
                
                label = st.selectbox(
                    f"Classe cella col_{col_label}",
                    CLASSES,
                    key=f"label_{item_id}_{col_label}"
                )
                
                if st.button(f"✅ Salva col_{col_label}", key=f"save_{item_id}_{col_label}"):
                    save_cell(cell_img, label, item_id, col_label)
                    st.session_state['labeled_count'] += 1
                    st.success(f"Salvato come '{label}'!")
        
        st.metric("Celle etichettate in questa sessione", st.session_state['labeled_count'])


if __name__ == "__main__":
    main()
```

---

## 9. GENERAZIONE DATI SINTETICI

**File:** `training/augmentor.py`

```python
"""
training/augmentor.py

Genera varianti sintetiche delle celle reali per amplificare il dataset di training.
Usa albumentations==2.0.8 (MIT license - NON aggiornare oltre questa versione).

Input:  cartelle data/raw_cells/{classe}/ con immagini reali
Output: cartelle data/synthetic/{classe}/ con N varianti per immagine

Trasformazioni applicate:
- Rotazione ±15°
- Scala 0.85-1.15
- Luminosità/contrasto ±30%
- Sfocatura lieve (kernel 3-7px)
- Rumore gaussiano
- Distorsione prospettica lieve
- Spessore tratto (erosione/dilatazione morfologica)
"""

import cv2
import numpy as np
from pathlib import Path
import albumentations as A
from typing import Optional
import argparse


RAW_DIR = Path(__file__).parent.parent / "data" / "raw_cells"
SYNTHETIC_DIR = Path(__file__).parent.parent / "data" / "synthetic"
CLASSES = ["cerchio", "x_rossa", "vuoto"]
CELL_SIZE = (64, 64)

# Numero di varianti sintetiche per ogni immagine reale
AUGMENTATIONS_PER_IMAGE = 15


def get_augmentation_pipeline() -> A.Compose:
    """
    Pipeline di augmentazione calibrata per celle questionari CBCL.
    Ogni trasformazione simula una variabile reale (luce, mano, penna).
    """
    return A.Compose([
        # Rotazione: simula angolazione diversa del foglio o della cella
        A.Rotate(limit=15, p=0.8, border_mode=cv2.BORDER_REPLICATE),
        
        # Scala: simula distanza diversa della foto
        A.RandomScale(scale_limit=0.15, p=0.6),
        
        # Luminosità e contrasto: simula illuminazione ambiente variabile
        A.RandomBrightnessContrast(
            brightness_limit=0.3,
            contrast_limit=0.3,
            p=0.8
        ),
        
        # Sfocatura lieve: simula microtremito mano o autofocus imperfetto
        A.OneOf([
            A.Blur(blur_limit=3, p=0.5),
            A.GaussianBlur(blur_limit=(3, 7), p=0.5),
        ], p=0.4),
        
        # Rumore: simula granularità sensore fotografico
        A.GaussNoise(var_limit=(5.0, 30.0), p=0.4),
        
        # Distorsione prospettica lieve: simula foto leggermente di sbieco
        A.Perspective(scale=(0.02, 0.05), p=0.3),
        
        # Ridimensionamento finale a dimensione standard
        A.Resize(height=64, width=64),
    ])


def augment_class(
    class_name: str,
    n_per_image: int = AUGMENTATIONS_PER_IMAGE,
    verbose: bool = True
) -> int:
    """
    Genera varianti sintetiche per tutte le immagini di una classe.
    
    Returns: numero totale immagini sintetiche generate
    """
    source_dir = RAW_DIR / class_name
    target_dir = SYNTHETIC_DIR / class_name
    target_dir.mkdir(parents=True, exist_ok=True)
    
    source_images = list(source_dir.glob("*.png")) + list(source_dir.glob("*.jpg"))
    
    if not source_images:
        print(f"⚠️  Nessuna immagine reale trovata in {source_dir}")
        return 0
    
    pipeline = get_augmentation_pipeline()
    generated = 0
    
    for img_path in source_images:
        img = cv2.imread(str(img_path), cv2.IMREAD_GRAYSCALE)
        if img is None:
            continue
        
        # Assicura dimensione corretta
        img = cv2.resize(img, CELL_SIZE)
        
        for i in range(n_per_image):
            # albumentations richiede immagine con channel dimension
            img_rgb = cv2.cvtColor(img, cv2.COLOR_GRAY2RGB)
            
            augmented = pipeline(image=img_rgb)
            aug_img = cv2.cvtColor(augmented["image"], cv2.COLOR_RGB2GRAY)
            
            # Aggiungi variante morfologica (spessore tratto)
            if i % 3 == 0:
                kernel = np.ones((2, 2), np.uint8)
                aug_img = cv2.erode(aug_img, kernel, iterations=1)  # Tratto più fino
            elif i % 3 == 1:
                kernel = np.ones((2, 2), np.uint8)
                aug_img = cv2.dilate(aug_img, kernel, iterations=1)  # Tratto più spesso
            
            out_name = f"{img_path.stem}_aug{i:03d}.png"
            cv2.imwrite(str(target_dir / out_name), aug_img)
            generated += 1
    
    if verbose:
        print(f"✅ {class_name}: {len(source_images)} reali → {generated} sintetiche")
    
    return generated


def run_all_augmentations(n_per_image: int = AUGMENTATIONS_PER_IMAGE):
    """Esegue augmentazione per tutte le classi."""
    print(f"\n🔄 Avvio generazione dati sintetici ({n_per_image} varianti per immagine)...")
    total = 0
    
    for cls in CLASSES:
        n = augment_class(cls, n_per_image)
        total += n
    
    print(f"\n✅ Totale immagini sintetiche generate: {total}")
    
    # Verifica bilanciamento classi
    print("\n📊 Distribuzione dataset:")
    for cls in CLASSES:
        real = len(list((RAW_DIR / cls).glob("*.png")))
        synth = len(list((SYNTHETIC_DIR / cls).glob("*.png")))
        print(f"   {cls}: {real} reali + {synth} sintetiche = {real + synth} totali")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=AUGMENTATIONS_PER_IMAGE,
                       help="Varianti per immagine reale")
    args = parser.parse_args()
    run_all_augmentations(args.n)
```

---

## 10. SCRIPT DI TRAINING SVM

**File:** `training/train_svm.py`

```python
"""
training/train_svm.py

Addestra il modello SVM su HOG features e lo salva come model.pkl.

Uso:
    python training/train_svm.py

Output:
    models/model.pkl          - Modello SVM addestrato
    models/training_report.json - Metriche di accuracy

Il training usa ENTRAMBI i dataset: raw_cells (reali) + synthetic.
"""

import cv2
import numpy as np
import joblib
import json
from pathlib import Path
from sklearn.svm import SVC
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.metrics import classification_report, confusion_matrix
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from core.classifier import compute_hog_features


# Percorsi
RAW_DIR = Path("data/raw_cells")
SYNTHETIC_DIR = Path("data/synthetic")
MODEL_DIR = Path("models")
MODEL_PATH = MODEL_DIR / "model.pkl"
REPORT_PATH = MODEL_DIR / "training_report.json"

CLASSES = ["cerchio", "x_rossa", "vuoto"]
CELL_SIZE = (64, 64)

# Soglie minime per procedere al training
MIN_SAMPLES_PER_CLASS = 30
TARGET_ACCURACY = 0.88


def load_dataset():
    """
    Carica tutte le immagini da raw_cells + synthetic.
    Returns: (X numpy array, y numpy array, class_names list)
    """
    X = []
    y = []
    
    for class_idx, class_name in enumerate(CLASSES):
        images_loaded = 0
        
        # Carica immagini reali
        real_dir = RAW_DIR / class_name
        if real_dir.exists():
            for img_path in real_dir.glob("*.png"):
                img = cv2.imread(str(img_path), cv2.IMREAD_GRAYSCALE)
                if img is not None:
                    img = cv2.resize(img, CELL_SIZE)
                    features = compute_hog_features(img)
                    X.append(features)
                    y.append(class_idx)
                    images_loaded += 1
        
        # Carica immagini sintetiche
        synth_dir = SYNTHETIC_DIR / class_name
        if synth_dir.exists():
            for img_path in synth_dir.glob("*.png"):
                img = cv2.imread(str(img_path), cv2.IMREAD_GRAYSCALE)
                if img is not None:
                    img = cv2.resize(img, CELL_SIZE)
                    features = compute_hog_features(img)
                    X.append(features)
                    y.append(class_idx)
                    images_loaded += 1
        
        print(f"  {class_name}: {images_loaded} immagini caricate")
        
        if images_loaded < MIN_SAMPLES_PER_CLASS:
            print(f"  ⚠️  ATTENZIONE: {class_name} ha solo {images_loaded} immagini (minimo: {MIN_SAMPLES_PER_CLASS})")
            print(f"     Esegui: python training/augmentor.py per generare più dati")
    
    return np.array(X, dtype=np.float32), np.array(y, dtype=np.int32), CLASSES


def train():
    """Esegue il training completo."""
    print("\n🏋️  Smart OCR — Training SVM")
    print("=" * 50)
    
    MODEL_DIR.mkdir(exist_ok=True)
    
    # Carica dataset
    print("\n📂 Caricamento dataset...")
    X, y, class_names = load_dataset()
    print(f"\n📊 Dataset totale: {len(X)} campioni, {len(class_names)} classi")
    
    for i, cls in enumerate(class_names):
        count = np.sum(y == i)
        print(f"   {cls}: {count} campioni")
    
    if len(X) < MIN_SAMPLES_PER_CLASS * len(class_names):
        print("\n❌ Dataset insufficiente per il training affidabile.")
        print("   Esegui prima: python training/label_tool.py (etichetta almeno 30 celle per classe)")
        print("   Poi: python training/augmentor.py (genera dati sintetici)")
        return False
    
    # Pipeline: StandardScaler + SVM
    print("\n⚙️  Configurazione modello SVM (kernel RBF, C=10, gamma=scale)...")
    model_pipeline = Pipeline([
        ('scaler', StandardScaler()),
        ('svm', SVC(
            kernel='rbf',
            C=10.0,
            gamma='scale',
            probability=True,       # Necessario per predict_proba
            class_weight='balanced', # Gestisce squilibrio classi
            random_state=42
        ))
    ])
    
    # Cross-validation (5-fold stratificata)
    print("\n🔄 Cross-validation 5-fold...")
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    cv_scores = cross_val_score(model_pipeline, X, y, cv=cv, scoring='accuracy', n_jobs=-1)
    
    mean_acc = cv_scores.mean()
    std_acc = cv_scores.std()
    
    print(f"\n📈 Risultati Cross-Validation:")
    print(f"   Accuracy media: {mean_acc:.4f} ± {std_acc:.4f}")
    print(f"   Per fold: {[f'{s:.4f}' for s in cv_scores]}")
    
    if mean_acc < TARGET_ACCURACY:
        print(f"\n⚠️  Accuracy {mean_acc:.1%} < target {TARGET_ACCURACY:.1%}")
        print("   Suggerimenti:")
        print("   - Aggiungi più immagini reali (specialmente casi difficili)")
        print("   - Aumenta AUGMENTATIONS_PER_IMAGE in augmentor.py")
        print("   - Controlla qualità delle label (errori di etichettatura)")
    else:
        print(f"\n✅ Accuracy {mean_acc:.1%} soddisfa il target {TARGET_ACCURACY:.1%}")
    
    # Training finale su tutto il dataset
    print("\n💾 Training finale su dataset completo...")
    model_pipeline.fit(X, y)
    
    # Valutazione finale (in-sample, solo indicativa)
    y_pred = model_pipeline.predict(X)
    report = classification_report(y_pred, y, target_names=class_names, output_dict=True)
    cm = confusion_matrix(y, y_pred)
    
    print("\n📋 Classification Report (in-sample):")
    print(classification_report(y_pred, y, target_names=class_names))
    print("Confusion Matrix:")
    print(cm)
    
    # Salva modello
    joblib.dump(model_pipeline, MODEL_PATH)
    print(f"\n✅ Modello salvato: {MODEL_PATH}")
    print(f"   Dimensione file: {MODEL_PATH.stat().st_size / 1024:.1f} KB")
    
    # Salva report training
    training_report = {
        "timestamp": __import__('datetime').datetime.now().isoformat(),
        "dataset_size": len(X),
        "classes": class_names,
        "cv_accuracy_mean": float(mean_acc),
        "cv_accuracy_std": float(std_acc),
        "cv_scores_per_fold": cv_scores.tolist(),
        "classification_report": report,
        "confusion_matrix": cm.tolist()
    }
    
    with open(REPORT_PATH, "w") as f:
        json.dump(training_report, f, indent=2)
    
    print(f"📊 Report salvato: {REPORT_PATH}")
    
    return True


if __name__ == "__main__":
    success = train()
    sys.exit(0 if success else 1)
```

---

## 11. APP STREAMLIT PRINCIPALE

**File:** `app.py`

```python
"""
app.py

Smart OCR — Applicazione principale Streamlit.
Avvio: streamlit run app.py

Pagine:
1. 📤 Analisi Questionario — Upload foto e analisi automatica
2. 📊 Risultati — Tabella item con valori e flag
3. 💾 Export — Download JSON e CSV
4. ⚙️  Impostazioni — Soglia ambiguità, debug mode
"""

import streamlit as st
import cv2
import numpy as np
import pandas as pd
import json
import tempfile
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))

from core.preprocessor import preprocess_full_pipeline
from core.grid_extractor import extract_all_cells, visualize_grid_overlay
from core.classifier import get_classifier
from core.scorer import build_score_report, report_to_csv, report_to_json, ALL_ITEMS


# Configurazione pagina
st.set_page_config(
    page_title="Smart OCR — CBCL Scanner",
    page_icon="🧾",
    layout="wide",
    initial_sidebar_state="expanded"
)


def check_model_loaded() -> bool:
    """Verifica che il modello SVM sia disponibile."""
    classifier = get_classifier()
    if not classifier.is_loaded:
        st.error(
            "⚠️ Modello SVM non trovato (`models/model.pkl`).\n\n"
            "**Prima del primo utilizzo devi:**\n"
            "1. Etichettare celle: `streamlit run training/label_tool.py`\n"
            "2. Generare sintetici: `python training/augmentor.py`\n"
            "3. Addestrare modello: `python training/train_svm.py`"
        )
        return False
    return True


def process_uploaded_image(uploaded_file, debug: bool = False) -> dict:
    """
    Processa un questionario caricato e ritorna il report completo.
    """
    # Salva file temporaneo
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        tmp.write(uploaded_file.read())
        tmp_path = tmp.name
    uploaded_file.seek(0)
    
    with st.spinner("1/4 — Pre-processing immagine..."):
        gray, meta = preprocess_full_pipeline(tmp_path, debug=debug)
    
    if meta.get("warnings"):
        for w in meta["warnings"]:
            st.warning(f"⚠️ {w}")
    
    with st.spinner("2/4 — Estrazione celle griglia..."):
        cells_dict = extract_all_cells(gray)
    
    with st.spinner("3/4 — Classificazione celle (SVM)..."):
        classifier = get_classifier()
        classification_results = {}
        
        for item_id, item_cells in cells_dict.items():
            classification_results[item_id] = classifier.predict_item_cells(item_cells)
    
    with st.spinner("4/4 — Calcolo score CBCL..."):
        report = build_score_report(
            classification_results,
            session_id=f"upload_{uploaded_file.name}"
        )
    
    # Aggiungi immagine overlay per debug
    report['_overlay'] = visualize_grid_overlay(gray)
    report['_preprocessed'] = gray
    
    return report


def render_results_table(report: dict):
    """Mostra tabella risultati con colori per flag."""
    
    items_data = []
    for item_id in ALL_ITEMS:
        item = report["items"].get(item_id, {})
        value = item.get("value")
        flag = item.get("flag")
        confidence = item.get("confidence", 0.0)
        
        # Emoji per flag
        flag_emoji = {
            None: "✅",
            "ambiguous": "⚠️",
            "missing": "❌",
            "multiple_marks": "🔴",
            "not_processed": "⬜"
        }.get(flag, "❓")
        
        items_data.append({
            "Item": item_id,
            "Valore": value if value is not None else "-",
            "Confidence": f"{confidence:.0%}" if confidence > 0 else "-",
            "Status": f"{flag_emoji} {flag or 'ok'}"
        })
    
    df = pd.DataFrame(items_data)
    
    # Colorazione condizionale
    def color_row(row):
        if "❌" in str(row["Status"]):
            return ["background-color: #fff5f5"] * len(row)
        elif "⚠️" in str(row["Status"]):
            return ["background-color: #fffaf0"] * len(row)
        elif "🔴" in str(row["Status"]):
            return ["background-color: #ffe0e0"] * len(row)
        return [""] * len(row)
    
    styled = df.style.apply(color_row, axis=1)
    st.dataframe(styled, use_container_width=True, height=600)


def main():
    # Sidebar
    with st.sidebar:
        st.image("https://via.placeholder.com/200x60?text=Smart+OCR", width=200)
        st.markdown("---")
        st.markdown("### ⚙️ Impostazioni")
        debug_mode = st.checkbox("Modalità debug", False)
        st.markdown("---")
        st.markdown("### 📊 Modello")
        classifier = get_classifier()
        if classifier.is_loaded:
            st.success("✅ Modello caricato")
        else:
            st.error("❌ Modello non trovato")
    
    # Titolo
    st.title("🧾 Smart OCR — CBCL Scanner")
    st.markdown("Lettura automatica questionari CBCL 6-18 da foto smartphone")
    
    # Tab principali
    tab_upload, tab_results, tab_export = st.tabs([
        "📤 Analisi", "📊 Risultati", "💾 Export"
    ])
    
    with tab_upload:
        if not check_model_loaded():
            return
        
        st.header("Carica foto questionario")
        
        col_left, col_right = st.columns([1, 1])
        
        with col_left:
            uploaded = st.file_uploader(
                "Foto del questionario CBCL compilato",
                type=["jpg", "jpeg", "png"],
                help="Foto da smartphone. Tieni il foglio su superficie piana con buona illuminazione."
            )
            
            if uploaded:
                st.image(uploaded, caption="Foto originale", use_column_width=True)
        
        with col_right:
            if uploaded:
                if st.button("🔍 Analizza Questionario", type="primary", use_container_width=True):
                    try:
                        report = process_uploaded_image(uploaded, debug=debug_mode)
                        st.session_state['current_report'] = report
                        
                        # Mostra statistiche rapide
                        stats = report["statistics"]
                        c1, c2, c3, c4 = st.columns(4)
                        c1.metric("📝 Score Totale", report["total_score"])
                        c2.metric("✅ Item Completati", stats["items_scored"])
                        c3.metric("❌ Item Mancanti", stats["items_missing"])
                        c4.metric("⚠️ Ambigui", stats["items_ambiguous"])
                        
                        if debug_mode and '_overlay' in report:
                            st.image(report['_overlay'], caption="Overlay griglia rilevata", use_column_width=True)
                        
                        st.success("✅ Analisi completata! Vai alla tab 'Risultati'")
                        
                    except Exception as e:
                        st.error(f"❌ Errore durante l'analisi: {e}")
                        if debug_mode:
                            import traceback
                            st.code(traceback.format_exc())
    
    with tab_results:
        if 'current_report' not in st.session_state:
            st.info("Carica e analizza un questionario nella tab '📤 Analisi'")
            return
        
        report = st.session_state['current_report']
        
        st.header("Risultati Analisi")
        
        # Score subscale
        st.subheader("Score per Subscala")
        subscale_data = []
        for name, data in report["subscale_scores"].items():
            subscale_data.append({
                "Subscala": name.replace("_", " "),
                "Score": data["score"],
                "Item Mancanti": data["items_missing"]
            })
        st.dataframe(pd.DataFrame(subscale_data), use_container_width=True)
        
        # Tabella item completa
        st.subheader("Dettaglio Item")
        render_results_table(report)
        
        # Avviso per item che richiedono revisione
        flags = report.get("flags", [])
        if flags:
            st.subheader("⚠️ Item che richiedono revisione manuale")
            for f in flags:
                st.warning(f"Item {f['item']}: {f['flag']}")
    
    with tab_export:
        if 'current_report' not in st.session_state:
            st.info("Analizza prima un questionario")
            return
        
        report = st.session_state['current_report']
        # Rimuovi dati immagine prima dell'export
        export_report = {k: v for k, v in report.items() if not k.startswith('_')}
        
        st.header("Export Risultati")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("📄 Export JSON")
            json_str = report_to_json(export_report)
            st.download_button(
                "⬇️ Scarica JSON",
                data=json_str,
                file_name=f"{export_report['session_id']}.json",
                mime="application/json",
                use_container_width=True
            )
        
        with col2:
            st.subheader("📊 Export CSV")
            csv_str = report_to_csv(export_report)
            st.download_button(
                "⬇️ Scarica CSV",
                data=csv_str,
                file_name=f"{export_report['session_id']}.csv",
                mime="text/csv",
                use_container_width=True
            )


if __name__ == "__main__":
    main()
```

---

## 12. PACKAGING ESEGUIBILE

### run.py (wrapper per PyInstaller)
```python
"""
run.py — Wrapper per packaging con PyInstaller.
Avvia l'app Streamlit come applicazione desktop.
"""
import subprocess
import sys
import os
from pathlib import Path


def main():
    app_path = Path(__file__).parent / "app.py"
    
    subprocess.run([
        sys.executable, "-m", "streamlit", "run",
        str(app_path),
        "--global.developmentMode=false",
        "--server.headless=true",
        "--server.port=8501",
        "--browser.gatherUsageStats=false"
    ])


if __name__ == "__main__":
    main()
```

### Comando build Windows
```cmd
pyinstaller --collect-all streamlit --copy-metadata streamlit ^
  --name "SmartOCR" --onedir --windowed ^
  --add-data "templates;templates" ^
  --add-data "models;models" ^
  run.py
```

### Comando build macOS
```bash
pyinstaller --collect-all streamlit --copy-metadata streamlit \
  --name "SmartOCR" --onedir --windowed \
  --add-data "templates:templates" \
  --add-data "models:models" \
  run.py
```

> **NOTA:** Su macOS il separatore nei `--add-data` è `:` (due punti), su Windows è `;` (punto e virgola).

---

## 13. TEST E VALIDAZIONE

**File:** `tests/test_preprocessor.py`

```python
"""Test base per il modulo preprocessor."""
import pytest
import numpy as np
import cv2
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from core.preprocessor import (
    load_image, to_grayscale, denoise, binarize_adaptive,
    deskew, normalize_resolution, enhance_contrast
)


def make_test_image(w=800, h=1000) -> np.ndarray:
    """Crea immagine di test sintetica (foglio bianco con linee)."""
    img = np.full((h, w, 3), 240, dtype=np.uint8)
    for y in range(100, h-100, 80):
        cv2.line(img, (50, y), (w-50, y), (100, 100, 100), 1)
    return img


def test_load_numpy_array():
    img = make_test_image()
    result = load_image(img)
    assert result.shape == img.shape


def test_grayscale_conversion():
    img = make_test_image()
    gray = to_grayscale(img)
    assert len(gray.shape) == 2


def test_grayscale_already_gray():
    gray = np.random.randint(0, 255, (100, 100), dtype=np.uint8)
    result = to_grayscale(gray)
    assert len(result.shape) == 2


def test_normalize_resolution():
    img = make_test_image(w=1200, h=1600)
    gray = to_grayscale(img)
    normalized = normalize_resolution(gray, target_width=2480)
    assert normalized.shape[1] == 2480


def test_deskew_no_rotation():
    img = make_test_image()
    gray = to_grayscale(img)
    result, angle = deskew(gray)
    assert abs(angle) < 5.0  # Immagine già diritta


def test_full_pipeline_synthetic():
    """Test pipeline completa su immagine sintetica."""
    from core.preprocessor import preprocess_full_pipeline
    img = make_test_image(1200, 1600)
    result, meta = preprocess_full_pipeline(img)
    
    assert result is not None
    assert len(result.shape) == 2
    assert 'original_size' in meta
    assert 'final_size' in meta
    assert 'warnings' in meta
```

### Eseguire i test
```bash
pip install pytest
pytest tests/ -v
```

---

## 14. NOTE CRITICHE DI COMPATIBILITÀ

### ⚠️ Problemi noti e soluzioni

#### 1. ImportError: libGL.so.1 (Linux/Streamlit Cloud)
```
Causa: opencv-python dipende da libGL che non è presente in ambienti headless
Soluzione: usa opencv-contrib-python-headless al posto di opencv-contrib-python
```
> Su macOS e Windows questo problema NON si verifica.

#### 2. Apple Silicon M1/M2/M3
```
Causa: I wheel di opencv-python su PyPI per arm64 macOS possono avere problemi
Soluzione obbligatoria: installare OpenCV via conda-forge (vedi sezione 1)
Verifica: python -c "import cv2; print(cv2.__version__)"
```

#### 3. albumentations versione
```
⚠️ CRITICO: NON fare "pip install --upgrade albumentations"
La versione 2.1.0+ è diventata AGPL-3.0 (non compatibile con uso commerciale)
Fissa SEMPRE: albumentations==2.0.8 (MIT license)
```

#### 4. Python 3.13 incompatibilità
```
Causa: alcune dipendenze non hanno ancora wheel per Python 3.13
Soluzione: usa Python 3.11 o 3.12
Verifica: python --version
```

#### 5. ArUco API (se usata in futuro)
```
In OpenCV 4.8+, l'API ArUco è cambiata:
# VECCHIO (deprecato):
detector = cv2.aruco.detectMarkers(...)
# NUOVO (corretto):
detector = cv2.aruco.ArucoDetector(dictionary, parameters)
corners, ids, rejected = detector.detectMarkers(image)
```

#### 6. PyInstaller + Streamlit su macOS
```
Se il .app non si apre, esegui da terminale per vedere l'errore:
./dist/SmartOCR.app/Contents/MacOS/SmartOCR

Problema comune: gatekeeper blocca app non firmate
Soluzione: System Preferences → Security → "Apri comunque"
```

### Comandi rapidi di verifica installazione

```bash
# Verifica tutto l'ambiente
python -c "
import cv2; print(f'OpenCV: {cv2.__version__}')
import sklearn; print(f'scikit-learn: {sklearn.__version__}')
import numpy; print(f'NumPy: {numpy.__version__}')
import streamlit; print(f'Streamlit: {streamlit.__version__}')
import albumentations; print(f'albumentations: {albumentations.__version__}')
import joblib; print(f'joblib: {joblib.__version__}')
print('✅ Tutte le librerie importate correttamente')
"
```

---

## ORDINE DI IMPLEMENTAZIONE PER CLAUDE CODE

Implementa i moduli **in questo ordine esatto**:

1. `setup.py` e `requirements.txt` — Setup ambiente
2. Struttura cartelle completa
3. `core/__init__.py` (file vuoti)
4. `core/preprocessor.py`
5. `templates/cbcl_grid.json` (con coordinate COMPLETE di tutti i 112 item)
6. `core/grid_extractor.py`
7. `core/classifier.py`
8. `core/scorer.py`
9. `training/augmentor.py`
10. `training/label_tool.py`
11. `training/train_svm.py`
12. `app.py`
13. `run.py`
14. `tests/test_preprocessor.py`
15. `tests/test_classifier.py` (da implementare analogamente al test del preprocessor)

### Task prioritario per Claude Code

> Il file `templates/cbcl_grid.json` deve contenere le coordinate relative (frazioni 0.0-1.0) di TUTTE le righe del CBCL 6-18 (item 1-55, 56a-56h, 57-112) per entrambe le pagine (page_4 e page_5). Queste coordinate vanno calcolate analizzando il layout standard del questionario CBCL. Le colonne 0, 1, 2 per ogni item devono avere x incrementale da sinistra. Il template è il componente più critico dell'intero sistema.

---

*Fine documento — Smart OCR Implementation Guide v1.0*
