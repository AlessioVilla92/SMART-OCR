# SMART OCR — PIANO IMPLEMENTATIVO COMPLETO
# Documento per Claude Code · Versione 2.0 · Dual-Mode
# =====================================================
# Da leggere interamente prima di scrivere una sola riga di codice.

---

## 1. IDENTITÀ DEL PROGETTO

**Nome**: Smart OCR  
**Scopo**: Lettura automatica offline di questionari CBCL 6-18 fotografati con smartphone.  
**Utente finale**: Psicologi clinici su PC Windows o macOS.  
**Sviluppatore**: Windows, RTX 3070 (8GB VRAM), Python 3.11.

### Vincoli assoluti non negoziabili
- Nessun dato del paziente esce dalla macchina locale (GDPR clinico).
- Nessuna chiamata API cloud in produzione.
- Distribuzione cross-platform: Windows .exe + macOS .app (Intel e Apple Silicon).
- `albumentations` DEVE essere pinned a `==2.0.8` (MIT). Versioni successive sono AGPL.
- In distribuzione NON includere PyTorch/Ultralytics. Solo ONNX Runtime.

---

## 2. ARCHITETTURA GENERALE — VISIONE D'INSIEME

Il software ha due motori di riconoscimento intercambiabili (Modalità A e B)
che condividono lo stesso preprocessing e lo stesso output scorer.

```
┌─────────────────────────────────────────────────────────┐
│                    STREAMLIT UI (app.py)                 │
│  Tab: Analisi | Tab: Training | Tab: Risultati | Tab: Config │
└──────────────────────┬──────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────┐
│              PIPELINE ORCHESTRATOR (pipeline/engine.py)  │
│  Riceve: foto JPG/PNG                                    │
│  Restituisce: {item_1: 0, item_2: 1, ..., item_112: 2}  │
└──────┬─────────────────────────────────────┬────────────┘
       │                                     │
┌──────▼──────────┐                 ┌────────▼────────────┐
│  SHARED LAYER   │                 │   SHARED LAYER      │
│  preprocessor   │                 │   grid_extractor    │
│  (OpenCV)       │                 │   (cbcl_grid.json)  │
└──────┬──────────┘                 └────────┬────────────┘
       │                                     │
       └────────────────┬────────────────────┘
                        │ celle 64x64px estratte
              ┌─────────┴──────────┐
              │                    │
     ┌────────▼───────┐   ┌────────▼──────────┐
     │  MODALITÀ A    │   │  MODALITÀ B        │
     │  HOG + SVM     │   │  YOLOv8n ONNX      │
     │  scikit-learn  │   │  (fine-tuned)      │
     │  ~100KB model  │   │  ~6MB model        │
     │  no GPU        │   │  no GPU needed     │
     └────────┬───────┘   └────────┬──────────┘
              │                    │
              └─────────┬──────────┘
                        │ {item: valore, confidence, flag}
              ┌─────────▼──────────┐
              │   CBCL SCORER      │
              │   scorer.py        │
              │   JSON + CSV out   │
              └────────────────────┘
```

**Principio chiave**: le due modalità sono intercambiabili. Lo stesso preprocessing
alimenta entrambe. Lo stesso scorer riceve l'output di entrambe. L'utente cambia
modalità con un toggle nella sidebar senza riavviare il software.

---

## 3. STRUTTURA DIRECTORY COMPLETA

```
smart_ocr/
│
├── app.py                          # Entry point Streamlit
├── config.py                       # Configurazione globale
│
├── pipeline/
│   ├── __init__.py
│   ├── engine.py                   # Orchestratore: coordina tutti i moduli
│   ├── preprocessor.py             # OpenCV preprocessing
│   ├── perspective_corrector.py    # Correzione prospettiva documento
│   ├── grid_extractor.py           # Estrazione celle da cbcl_grid.json
│   │
│   ├── mode_a/                     # MODALITÀ A — HOG + SVM
│   │   ├── __init__.py
│   │   ├── hog_extractor.py        # Estrae HOG features da cella 64x64
│   │   └── svm_classifier.py       # Wrapper per models/svm_classifier.pkl
│   │
│   └── mode_b/                     # MODALITÀ B — YOLOv8n ONNX
│       ├── __init__.py
│       └── yolo_classifier.py      # Inferenza ONNX Runtime (no PyTorch)
│
├── training/
│   ├── __init__.py
│   │
│   ├── shared/
│   │   ├── labeling_tool.py        # UI Streamlit per etichettare celle
│   │   └── augmentor.py            # albumentations==2.0.8 augmentation
│   │
│   ├── mode_a/
│   │   └── train_svm.py            # Addestra e salva svm_classifier.pkl
│   │
│   └── mode_b/
│       ├── prepare_yolo_dataset.py # Celle etichettate → formato YOLO
│       ├── train_yolo.py           # Fine-tuning YOLOv8n su GPU
│       └── export_onnx.py          # .pt → .onnx per distribuzione
│
├── scorer/
│   ├── __init__.py
│   └── cbcl_scorer.py              # Calcolo score CBCL, subscale, totali
│
├── utils/
│   ├── __init__.py
│   ├── logger.py                   # Logging anonimizzato (no dati paziente)
│   ├── validators.py               # Validazione input/output
│   └── platform_utils.py          # Rilevamento OS e path cross-platform
│
├── templates/
│   └── cbcl_grid.json              # CRITICO — coordinate relative 112 item
│
├── models/
│   ├── .gitkeep
│   ├── svm_classifier.pkl          # Generato da training/mode_a/train_svm.py
│   ├── yolo_cbcl.pt                # Checkpoint training (solo dev)
│   └── yolo_cbcl.onnx              # Produzione (incluso nella distribuzione)
│
├── data/
│   ├── raw_photos/                 # Foto originali (non committare su git)
│   ├── labeled_cells/
│   │   ├── cerchio/                # Celle con cerchio (label 0)
│   │   ├── croce/                  # Celle con X (label 1)
│   │   └── vuota/                  # Celle vuote (label 2)
│   ├── augmented/                  # Output augmentation
│   └── yolo_dataset/
│       ├── images/train/
│       ├── images/val/
│       ├── labels/train/
│       ├── labels/val/
│       └── data.yaml
│
├── output/                         # Output analisi (non committare su git)
│   └── .gitkeep
│
├── requirements/
│   ├── requirements_base.txt       # Produzione (no GPU, no PyTorch)
│   ├── requirements_training.txt   # Dev + training (GPU, PyTorch, Ultralytics)
│   └── requirements_mac_arm.txt    # Apple Silicon (opencv da conda-forge)
│
├── tests/
│   ├── test_preprocessor.py
│   ├── test_grid_extractor.py
│   ├── test_mode_a.py
│   └── test_mode_b.py
│
├── packaging/
│   ├── smart_ocr_windows.spec      # PyInstaller spec Windows
│   ├── smart_ocr_macos.spec        # PyInstaller spec macOS
│   └── build.py                    # Script build cross-platform
│
├── .gitignore
└── README.md
```

---

## 4. DIPENDENZE E LICENZE

### requirements/requirements_base.txt
```
# Core — produzione, nessuna GPU richiesta
opencv-python==4.9.0.80         # Apache 2.0
numpy==1.26.4                   # BSD
scikit-learn==1.4.2             # BSD
joblib==1.4.2                   # BSD
onnxruntime==1.18.0             # MIT — inferenza ONNX senza GPU
Pillow==10.3.0                  # HPND (MIT-like)
streamlit==1.35.0               # Apache 2.0
pandas==2.2.2                   # BSD
```

### requirements/requirements_training.txt
```
# Aggiuntive per training — solo macchina sviluppatore
-r requirements_base.txt
albumentations==2.0.8           # MIT — PINNED, non aggiornare mai
torch==2.3.0+cu121              # BSD (con CUDA 12.1 per RTX 3070)
torchvision==0.18.0+cu121       # BSD
ultralytics==8.2.0              # AGPL-3.0 — solo training, non distribuire
opencv-contrib-python==4.9.0.80 # Apache 2.0 — per ArUco se necessario
scikit-image==0.23.2            # BSD
matplotlib==3.9.0               # PSF
```

### requirements/requirements_mac_arm.txt
```
# Apple Silicon — OpenCV DEVE venire da conda-forge, non pip
# Installare con: conda install -c conda-forge opencv
numpy==1.26.4
scikit-learn==1.4.2
joblib==1.4.2
onnxruntime==1.18.0             # Versione ARM disponibile
Pillow==10.3.0
streamlit==1.35.0
pandas==2.2.2
```

### NOTA CRITICA sulle licenze
- `albumentations==2.0.8`: MIT. Versioni 2.1+ sono AGPL — incompatibili con uso clinico.
- `ultralytics`: AGPL-3.0. Va usato SOLO durante il training sul PC sviluppatore.
  NON va incluso nel software distribuito. L'output del training (file .onnx) è tuo.
- `onnxruntime`: MIT. Questo è ciò che gira in produzione per la Modalità B.

---

## 5. MODULI — IMPLEMENTAZIONE DETTAGLIATA

---

### 5.1 config.py

```python
"""
Configurazione globale Smart OCR.
Tutte le costanti e impostazioni centralizzate qui.
"""
import os
from pathlib import Path
from enum import Enum

class ClassificationMode(Enum):
    MODE_A_SVM = "svm"      # OpenCV + HOG + SVM
    MODE_B_YOLO = "yolo"    # YOLOv8n ONNX fine-tuned

class Config:
    # Paths
    BASE_DIR = Path(__file__).parent
    MODELS_DIR = BASE_DIR / "models"
    TEMPLATES_DIR = BASE_DIR / "templates"
    DATA_DIR = BASE_DIR / "data"
    OUTPUT_DIR = BASE_DIR / "output"

    # Modelli
    SVM_MODEL_PATH = MODELS_DIR / "svm_classifier.pkl"
    YOLO_ONNX_PATH = MODELS_DIR / "yolo_cbcl.onnx"
    YOLO_PT_PATH = MODELS_DIR / "yolo_cbcl.pt"  # solo dev

    # Template griglia
    CBCL_GRID_PATH = TEMPLATES_DIR / "cbcl_grid.json"

    # Preprocessing
    CELL_SIZE = (64, 64)             # Dimensione standard celle estratte
    GRAYSCALE = True
    ADAPTIVE_THRESHOLD_BLOCK = 11
    ADAPTIVE_THRESHOLD_C = 2

    # HOG (Modalità A)
    HOG_ORIENTATIONS = 9
    HOG_PIXELS_PER_CELL = (8, 8)
    HOG_CELLS_PER_BLOCK = (2, 2)

    # SVM (Modalità A)
    SVM_CONFIDENCE_THRESHOLD = 0.75   # Sotto questa soglia → flag "ambiguo"

    # YOLO (Modalità B)
    YOLO_CONFIDENCE_THRESHOLD = 0.80  # Sotto questa soglia → flag "ambiguo"
    YOLO_INPUT_SIZE = 64              # Dimensione input modello YOLO

    # Classi classificazione
    CLASSES = {0: "cerchio", 1: "croce", 2: "vuota"}
    CLASSES_INV = {"cerchio": 0, "croce": 1, "vuota": 2}

    # Output
    OUTPUT_CSV_SEPARATOR = ";"        # Punto e virgola per Excel italiano

    # Default modalità
    DEFAULT_MODE = ClassificationMode.MODE_A_SVM

    # Logging (NESSUN dato identificativo paziente)
    LOG_LEVEL = "INFO"
    LOG_FILE = BASE_DIR / "smart_ocr.log"
```

---

### 5.2 pipeline/preprocessor.py

```python
"""
Preprocessing delle foto del questionario CBCL.
Pipeline OpenCV completa: dalla foto grezza alla immagine normalizzata.
"""
import cv2
import numpy as np
from pathlib import Path
from config import Config

class Preprocessor:
    """
    Trasforma una foto smartphone del questionario CBCL in un'immagine
    normalizzata, raddrizzata e pulita pronta per l'estrazione della griglia.
    """

    def process(self, image_path: str | Path) -> np.ndarray:
        """
        Entry point principale. Ritorna immagine preprocessata o solleva
        PreprocessingError se l'immagine non è recuperabile.
        """
        img = self._load(image_path)
        img = self._auto_rotate(img)           # Corregge orientamento EXIF
        img = self._to_grayscale(img)
        img = self._denoise(img)
        img = self._enhance_contrast(img)
        img = self._binarize(img)
        return img

    def _load(self, path):
        img = cv2.imread(str(path))
        if img is None:
            raise ValueError(f"Impossibile leggere: {path}")
        # Ridimensiona se troppo grande (>4000px lato lungo) per velocità
        h, w = img.shape[:2]
        max_dim = 3000
        if max(h, w) > max_dim:
            scale = max_dim / max(h, w)
            img = cv2.resize(img, None, fx=scale, fy=scale,
                           interpolation=cv2.INTER_AREA)
        return img

    def _auto_rotate(self, img):
        """Corregge orientamento basandosi su metadati EXIF se presenti."""
        # Implementare con PIL/Pillow per leggere EXIF orientation tag
        # e ruotare di conseguenza prima di passare a OpenCV
        try:
            from PIL import Image, ExifTags
            import io
            # ... implementazione lettura EXIF e rotazione
        except Exception:
            pass  # Se EXIF non disponibile, procedi senza rotazione
        return img

    def _to_grayscale(self, img):
        if len(img.shape) == 3:
            return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        return img

    def _denoise(self, img):
        """
        fastNlMeansDenoising: riduce il rumore foto mantenendo i bordi
        dei segni. h=10 è buon bilanciamento velocità/qualità.
        """
        return cv2.fastNlMeansDenoising(img, h=10, templateWindowSize=7,
                                         searchWindowSize=21)

    def _enhance_contrast(self, img):
        """CLAHE: equalizzazione locale del contrasto, gestisce ombre e luci."""
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        return clahe.apply(img)

    def _binarize(self, img):
        """
        Threshold adattivo: binarizza l'immagine in modo robusto rispetto
        alle variazioni di illuminazione locali (ombre del telefono, ecc).
        """
        return cv2.adaptiveThreshold(
            img,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            Config.ADAPTIVE_THRESHOLD_BLOCK,
            Config.ADAPTIVE_THRESHOLD_C
        )
```

---

### 5.3 pipeline/perspective_corrector.py

```python
"""
Correzione prospettiva: raddrizza il documento fotografato obliquamente.
Questa è la fase più critica per l'accuratezza dell'estrazione griglia.
"""
import cv2
import numpy as np

class PerspectiveCorrector:
    """
    Rileva i 4 angoli del foglio A4 nella foto e applica una trasformazione
    prospettica per ottenere una vista frontale perfetta.

    Strategia:
    1. Trova il contorno più grande nell'immagine (il foglio)
    2. Approssima a quadrilatero (4 angoli)
    3. Applica cv2.getPerspectiveTransform
    4. Warp verso dimensioni A4 standard (proporzionali)
    """

    TARGET_WIDTH = 2100     # Larghezza output in pixel (proporzionale A4)
    TARGET_HEIGHT = 2970    # Altezza output in pixel (proporzionale A4)

    def correct(self, img: np.ndarray) -> np.ndarray:
        """
        Ritorna l'immagine corretta prospetticamente.
        Se non riesce a trovare il documento, ritorna l'originale.
        """
        corners = self._find_document_corners(img)
        if corners is None:
            return img  # Fallback: usa immagine originale
        return self._apply_warp(img, corners)

    def _find_document_corners(self, img):
        # Edge detection
        edges = cv2.Canny(img, 50, 150)
        kernel = np.ones((5, 5), np.uint8)
        edges = cv2.dilate(edges, kernel, iterations=1)

        # Trova contorni
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL,
                                        cv2.CHAIN_APPROX_SIMPLE)
        contours = sorted(contours, key=cv2.contourArea, reverse=True)

        for contour in contours[:5]:  # Prova i 5 contorni più grandi
            peri = cv2.arcLength(contour, True)
            approx = cv2.approxPolyDP(contour, 0.02 * peri, True)
            if len(approx) == 4:
                return self._order_corners(approx.reshape(4, 2))

        return None

    def _order_corners(self, pts):
        """Ordina i corner: top-left, top-right, bottom-right, bottom-left."""
        rect = np.zeros((4, 2), dtype=np.float32)
        s = pts.sum(axis=1)
        rect[0] = pts[np.argmin(s)]   # top-left
        rect[2] = pts[np.argmax(s)]   # bottom-right
        diff = np.diff(pts, axis=1)
        rect[1] = pts[np.argmin(diff)]  # top-right
        rect[3] = pts[np.argmax(diff)]  # bottom-left
        return rect

    def _apply_warp(self, img, corners):
        dst = np.array([
            [0, 0],
            [self.TARGET_WIDTH - 1, 0],
            [self.TARGET_WIDTH - 1, self.TARGET_HEIGHT - 1],
            [0, self.TARGET_HEIGHT - 1]
        ], dtype=np.float32)
        M = cv2.getPerspectiveTransform(corners, dst)
        return cv2.warpPerspective(img, M,
                                   (self.TARGET_WIDTH, self.TARGET_HEIGHT))
```

---

### 5.4 templates/cbcl_grid.json — STRUTTURA CRITICA

```json
{
  "version": "1.0",
  "questionnaire": "CBCL_6-18_IT",
  "description": "Coordinate relative (0.0-1.0) delle celle risposta per ogni item CBCL",
  "coordinate_system": "relative_to_corrected_page",
  "pages": {
    "4": {
      "description": "Pagina 4 — Item 1-54",
      "items": {
        "1": {
          "label": "Agisco in modo infantile per la mia età",
          "options": {
            "0": {"x": 0.052, "y": 0.183, "w": 0.025, "h": 0.016},
            "1": {"x": 0.091, "y": 0.183, "w": 0.025, "h": 0.016},
            "2": {"x": 0.131, "y": 0.183, "w": 0.025, "h": 0.016}
          }
        },
        "2": {
          "label": "Bevo alcolici senza l'approvazione dei miei genitori",
          "options": {
            "0": {"x": 0.052, "y": 0.210, "w": 0.025, "h": 0.016},
            "1": {"x": 0.091, "y": 0.210, "w": 0.025, "h": 0.016},
            "2": {"x": 0.131, "y": 0.210, "w": 0.025, "h": 0.016}
          }
        }
      }
    },
    "5": {
      "description": "Pagina 5 — Item 55-102",
      "items": {
        "55": {
          "label": "Sono in soprappeso",
          "options": {
            "0": {"x": 0.052, "y": 0.109, "w": 0.025, "h": 0.016},
            "1": {"x": 0.091, "y": 0.109, "w": 0.025, "h": 0.016},
            "2": {"x": 0.131, "y": 0.109, "w": 0.025, "h": 0.016}
          }
        }
      }
    },
    "6": {
      "description": "Pagina 6 — Item 103-112",
      "items": {
        "103": {
          "label": "Sono scontento, triste, o depresso",
          "options": {
            "0": {"x": 0.052, "y": 0.138, "w": 0.025, "h": 0.016},
            "1": {"x": 0.091, "y": 0.138, "w": 0.025, "h": 0.016},
            "2": {"x": 0.131, "y": 0.138, "w": 0.025, "h": 0.016}
          }
        }
      }
    }
  }
}
```

**ISTRUZIONI PER COSTRUIRE cbcl_grid.json COMPLETO:**

Scrivi uno script `tools/grid_calibrator.py` che:
1. Apre ogni foto reale con OpenCV
2. Mostra la foto con griglia sovrapposta (trasparente)
3. Permette di cliccare sui centri delle celle 0, 1, 2 per ogni item
4. Registra automaticamente le coordinate normalizzate (x/larghezza, y/altezza)
5. Salva il JSON aggiornando progressivamente

Esegui il calibratore su 3 foto diverse e media le coordinate: questo rende
il JSON robusto alle piccole variazioni di stampa tra diversi uffici/scanner.

---

### 5.5 pipeline/grid_extractor.py

```python
"""
Estrazione delle singole celle risposta dal documento preprocessato.
Usa cbcl_grid.json per sapere dove si trovano le celle di ogni item.
"""
import json
import cv2
import numpy as np
from pathlib import Path
from config import Config

class GridExtractor:
    """
    Dato il documento preprocessato e corretto prospetticamente,
    estrae ogni singola cella 64x64px pronta per il classificatore.
    """

    def __init__(self):
        with open(Config.CBCL_GRID_PATH, 'r', encoding='utf-8') as f:
            self.grid = json.load(f)

    def extract_all_cells(self, page_img: np.ndarray,
                          page_number: str) -> dict:
        """
        Ritorna: {item_id: {option: cell_img_64x64, ...}, ...}
        Es: {"1": {"0": array, "1": array, "2": array}, "2": {...}, ...}
        """
        h, w = page_img.shape[:2]
        result = {}

        page_data = self.grid["pages"].get(str(page_number), {})
        items = page_data.get("items", {})

        for item_id, item_data in items.items():
            result[item_id] = {}
            for option, coords in item_data["options"].items():
                cell = self._extract_cell(page_img, coords, h, w)
                result[item_id][option] = cell

        return result

    def _extract_cell(self, img, coords, img_h, img_w):
        """Estrae e ridimensiona a 64x64 la singola cella."""
        x = int(coords["x"] * img_w)
        y = int(coords["y"] * img_h)
        w = int(coords["w"] * img_w)
        h = int(coords["h"] * img_h)

        # Padding di sicurezza (±3px) per tollerare piccole imprecisioni
        pad = 3
        x1 = max(0, x - pad)
        y1 = max(0, y - pad)
        x2 = min(img_w, x + w + pad)
        y2 = min(img_h, y + h + pad)

        cell = img[y1:y2, x1:x2]
        return cv2.resize(cell, Config.CELL_SIZE,
                         interpolation=cv2.INTER_AREA)
```

---

### 5.6 pipeline/mode_a/hog_extractor.py

```python
"""
Estrazione HOG (Histogram of Oriented Gradients) features.
HOG cattura la distribuzione delle direzioni dei contorni — perfetto
per distinguere la forma di un cerchio vs una X vs una cella vuota.
"""
import numpy as np
from skimage.feature import hog
from config import Config

class HOGExtractor:
    """
    Trasforma una cella 64x64 in un vettore di features HOG.
    Il vettore risultante ha dimensione fissa = 1764 features.
    """

    def extract(self, cell: np.ndarray) -> np.ndarray:
        """
        Input: immagine grayscale 64x64
        Output: array 1D di features HOG (1764 elementi)
        """
        features = hog(
            cell,
            orientations=Config.HOG_ORIENTATIONS,        # 9
            pixels_per_cell=Config.HOG_PIXELS_PER_CELL,  # (8,8)
            cells_per_block=Config.HOG_CELLS_PER_BLOCK,  # (2,2)
            block_norm='L2-Hys',
            visualize=False,
            feature_vector=True
        )
        return features

    def extract_batch(self, cells: list) -> np.ndarray:
        """Estrae features da una lista di celle. Ritorna array 2D."""
        return np.array([self.extract(c) for c in cells])
```

---

### 5.7 pipeline/mode_a/svm_classifier.py

```python
"""
Classificatore SVM per Modalità A.
Wrapper attorno al modello scikit-learn salvato in models/svm_classifier.pkl
"""
import joblib
import numpy as np
from config import Config, ClassificationMode
from pipeline.mode_a.hog_extractor import HOGExtractor

class SVMClassifier:
    """
    Carica il modello SVM pre-addestrato e classifica le celle.
    Il modello usa SVM con kernel RBF e probabilistic output (predict_proba).
    """

    def __init__(self):
        if not Config.SVM_MODEL_PATH.exists():
            raise FileNotFoundError(
                f"Modello SVM non trovato: {Config.SVM_MODEL_PATH}\n"
                "Eseguire prima: python training/mode_a/train_svm.py"
            )
        self.model = joblib.load(Config.SVM_MODEL_PATH)
        self.hog = HOGExtractor()

    def classify_cell(self, cell: np.ndarray) -> dict:
        """
        Input: cella 64x64 grayscale
        Output: {"class": "cerchio", "value": 0, "confidence": 0.94, "flag": None}
        """
        features = self.hog.extract(cell).reshape(1, -1)
        probabilities = self.model.predict_proba(features)[0]
        predicted_idx = np.argmax(probabilities)
        confidence = probabilities[predicted_idx]

        class_name = Config.CLASSES[predicted_idx]
        flag = None

        if confidence < Config.SVM_CONFIDENCE_THRESHOLD:
            flag = "ambiguous"

        return {
            "class": class_name,
            "value": predicted_idx,
            "confidence": float(confidence),
            "flag": flag,
            "mode": ClassificationMode.MODE_A_SVM.value,
            "all_probs": {
                Config.CLASSES[i]: float(p)
                for i, p in enumerate(probabilities)
            }
        }

    def classify_item(self, cells_dict: dict) -> dict:
        """
        Classifica le 3 celle (0,1,2) di un singolo item.
        Ritorna quale opzione è stata marcata.

        Strategia: la cella con la confidence di "marcato" più alta
        è quella selezionata. Se nessuna supera la soglia → "missing".
        """
        results = {}
        for option, cell in cells_dict.items():
            results[option] = self.classify_cell(cell)

        # Trova l'opzione marcata (non vuota con confidence più alta)
        marked_option = None
        best_confidence = 0.0

        for option, result in results.items():
            if result["class"] != "vuota":
                if result["confidence"] > best_confidence:
                    best_confidence = result["confidence"]
                    marked_option = option

        if marked_option is None:
            return {"value": None, "confidence": 0.0, "flag": "missing"}

        return {
            "value": int(marked_option),
            "confidence": best_confidence,
            "flag": results[marked_option]["flag"],
            "details": results
        }
```

---

### 5.8 pipeline/mode_b/yolo_classifier.py

```python
"""
Classificatore YOLOv8n ONNX per Modalità B.
Usa ONNX Runtime — NESSUNA dipendenza da PyTorch o Ultralytics in produzione.
Gira su CPU o GPU (ONNX Runtime sceglie automaticamente).
"""
import numpy as np
import onnxruntime as ort
from config import Config, ClassificationMode

class YOLOClassifier:
    """
    Esegue inferenza con il modello YOLOv8n fine-tuned esportato in ONNX.
    Il modello è stato addestrato specificamente su celle CBCL:
    Classe 0: cerchio
    Classe 1: croce (X)
    Classe 2: vuota
    """

    def __init__(self):
        if not Config.YOLO_ONNX_PATH.exists():
            raise FileNotFoundError(
                f"Modello ONNX non trovato: {Config.YOLO_ONNX_PATH}\n"
                "Eseguire: python training/mode_b/export_onnx.py"
            )

        # ONNX Runtime usa GPU se disponibile, altrimenti CPU automaticamente
        providers = ['CUDAExecutionProvider', 'CPUExecutionProvider']
        self.session = ort.InferenceSession(
            str(Config.YOLO_ONNX_PATH),
            providers=providers
        )
        self.input_name = self.session.get_inputs()[0].name
        self.output_name = self.session.get_outputs()[0].name

    def _preprocess(self, cell: np.ndarray) -> np.ndarray:
        """
        Prepara la cella per YOLOv8: normalizza [0,255] → [0,1],
        aggiunge batch e channel dimensions.
        """
        # YOLOv8 si aspetta RGB anche se la cella è grayscale
        if len(cell.shape) == 2:
            cell = np.stack([cell, cell, cell], axis=-1)
        cell = cell.astype(np.float32) / 255.0
        # HWC → CHW → BCHW
        cell = np.transpose(cell, (2, 0, 1))
        cell = np.expand_dims(cell, axis=0)
        return cell

    def classify_cell(self, cell: np.ndarray) -> dict:
        """
        Input: cella 64x64 grayscale
        Output: {"class": "cerchio", "value": 0, "confidence": 0.97, "flag": None}
        """
        input_tensor = self._preprocess(cell)
        outputs = self.session.run([self.output_name],
                                   {self.input_name: input_tensor})

        # YOLOv8 classification output: shape [1, num_classes]
        logits = outputs[0][0]
        probabilities = self._softmax(logits)
        predicted_idx = int(np.argmax(probabilities))
        confidence = float(probabilities[predicted_idx])

        flag = None
        if confidence < Config.YOLO_CONFIDENCE_THRESHOLD:
            flag = "ambiguous"

        return {
            "class": Config.CLASSES[predicted_idx],
            "value": predicted_idx,
            "confidence": confidence,
            "flag": flag,
            "mode": ClassificationMode.MODE_B_YOLO.value,
            "all_probs": {
                Config.CLASSES[i]: float(p)
                for i, p in enumerate(probabilities)
            }
        }

    def _softmax(self, x):
        e_x = np.exp(x - np.max(x))
        return e_x / e_x.sum()

    def classify_item(self, cells_dict: dict) -> dict:
        """Identico all'SVMClassifier per interfaccia uniforme."""
        results = {}
        for option, cell in cells_dict.items():
            results[option] = self.classify_cell(cell)

        marked_option = None
        best_confidence = 0.0

        for option, result in results.items():
            if result["class"] != "vuota":
                if result["confidence"] > best_confidence:
                    best_confidence = result["confidence"]
                    marked_option = option

        if marked_option is None:
            return {"value": None, "confidence": 0.0, "flag": "missing"}

        return {
            "value": int(marked_option),
            "confidence": best_confidence,
            "flag": results[marked_option]["flag"],
            "details": results
        }
```

---

### 5.9 pipeline/engine.py — ORCHESTRATORE

```python
"""
Engine principale: coordina preprocessing → correzione → estrazione → classificazione.
Questo è il modulo che app.py chiama per processare una foto.
"""
from pathlib import Path
import numpy as np
from config import Config, ClassificationMode
from pipeline.preprocessor import Preprocessor
from pipeline.perspective_corrector import PerspectiveCorrector
from pipeline.grid_extractor import GridExtractor

class OCREngine:
    """
    Interfaccia unificata per entrambe le modalità.
    Cambiare modalità è trasparente: stessa API, motore diverso.
    """

    def __init__(self, mode: ClassificationMode = Config.DEFAULT_MODE):
        self.mode = mode
        self.preprocessor = Preprocessor()
        self.corrector = PerspectiveCorrector()
        self.extractor = GridExtractor()
        self.classifier = self._load_classifier(mode)

    def _load_classifier(self, mode):
        if mode == ClassificationMode.MODE_A_SVM:
            from pipeline.mode_a.svm_classifier import SVMClassifier
            return SVMClassifier()
        elif mode == ClassificationMode.MODE_B_YOLO:
            from pipeline.mode_b.yolo_classifier import YOLOClassifier
            return YOLOClassifier()
        else:
            raise ValueError(f"Modalità non supportata: {mode}")

    def switch_mode(self, new_mode: ClassificationMode):
        """Cambia modalità a runtime senza riavviare."""
        if new_mode != self.mode:
            self.mode = new_mode
            self.classifier = self._load_classifier(new_mode)

    def process_questionnaire(self, photo_path: str | Path,
                              pages: list = ["4", "5", "6"]) -> dict:
        """
        Processa un intero questionario CBCL da una o più foto.

        Input: path foto + lista pagine da processare
        Output: {
            "items": {"1": {"value": 0, "confidence": 0.94, "flag": None}, ...},
            "missing": [lista item non compilati],
            "ambiguous": [lista item ambigui],
            "mode_used": "svm" | "yolo",
            "processing_time_ms": 450
        }
        """
        import time
        start = time.time()

        # Step 1: Preprocessing
        img = self.preprocessor.process(photo_path)

        # Step 2: Correzione prospettiva
        img = self.corrector.correct(img)

        # Step 3: Estrazione e classificazione per pagina
        all_results = {}
        for page in pages:
            cells = self.extractor.extract_all_cells(img, page)
            for item_id, cells_dict in cells.items():
                result = self.classifier.classify_item(cells_dict)
                all_results[item_id] = result

        # Step 4: Organizza output
        missing = [iid for iid, r in all_results.items()
                   if r.get("flag") == "missing"]
        ambiguous = [iid for iid, r in all_results.items()
                     if r.get("flag") == "ambiguous"]

        elapsed_ms = int((time.time() - start) * 1000)

        return {
            "items": all_results,
            "missing": missing,
            "ambiguous": ambiguous,
            "mode_used": self.mode.value,
            "processing_time_ms": elapsed_ms
        }
```

---

## 6. TRAINING — MODALITÀ A (HOG + SVM)

### 6.1 training/shared/labeling_tool.py

```python
"""
Tool di labeling per creare il dataset di training.
Interfaccia Streamlit: mostra le celle estratte una alla volta,
l'utente clicca su 'Cerchio', 'X', o 'Vuota'.

Salva le celle in:
  data/labeled_cells/cerchio/
  data/labeled_cells/croce/
  data/labeled_cells/vuota/
"""
# Implementare come pagina Streamlit con:
# - Visualizzazione cella corrente (ingrandita 8x per visibilità)
# - 3 bottoni colorati: Verde=Cerchio, Rosso=X, Grigio=Vuota
# - Progressbar: "Item 45/336 completati"
# - Possibilità di tornare indietro e correggere
# - Auto-salvataggio ogni 10 label
# - Export CSV etichette per backup
```

### 6.2 training/shared/augmentor.py

```python
"""
Augmentation dati con albumentations==2.0.8 (MIT — NON aggiornare).
Genera varianti sintetiche dalle celle reali etichettate.
Obiettivo: almeno 300 esempi per classe (cerchio/croce/vuota).
"""
import albumentations as A
import cv2
import numpy as np
from pathlib import Path

# TRASFORMAZIONI RILEVANTI per foto di questionari
# Solo quelle che simulano condizioni reali di fotografare a mano
AUGMENTATION_PIPELINE = A.Compose([
    A.Rotate(limit=15, p=0.7),               # Rotazione ±15°
    A.RandomBrightnessContrast(
        brightness_limit=0.3,
        contrast_limit=0.3,
        p=0.8),                               # Variazioni illuminazione
    A.GaussNoise(var_limit=(10, 50), p=0.5), # Rumore foto smartphone
    A.Blur(blur_limit=3, p=0.3),             # Leggero blur
    A.ElasticTransform(
        alpha=1, sigma=5,
        alpha_affine=5, p=0.3),              # Deformazione elastica lieve
    A.Perspective(scale=(0.02, 0.05), p=0.4),# Prospettiva lieve
    A.GridDistortion(p=0.2),                  # Distorsione griglia
])

def augment_class(input_dir: Path, output_dir: Path,
                  target_count: int = 300, multiplier: int = 10):
    """
    Genera `target_count` immagini augmentate partendo dalle immagini in input_dir.
    Ogni immagine originale viene trasformata `multiplier` volte.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    images = list(input_dir.glob("*.png")) + list(input_dir.glob("*.jpg"))

    count = 0
    for img_path in images:
        img = cv2.imread(str(img_path), cv2.IMREAD_GRAYSCALE)
        for i in range(multiplier):
            augmented = AUGMENTATION_PIPELINE(image=img)["image"]
            out_path = output_dir / f"{img_path.stem}_aug_{i:04d}.png"
            cv2.imwrite(str(out_path), augmented)
            count += 1
            if count >= target_count:
                return count
    return count
```

### 6.3 training/mode_a/train_svm.py

```python
"""
Training del classificatore SVM per Modalità A.
Eseguire una sola volta (o quando si aggiunge nuovo training data).
Richiede: celle etichettate in data/labeled_cells/ + augmentation eseguita.
"""
import numpy as np
import joblib
from pathlib import Path
from sklearn.svm import SVC
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from skimage.feature import hog
import cv2

from config import Config

def load_dataset(labeled_dir: Path):
    X, y = [], []
    class_map = {"cerchio": 0, "croce": 1, "vuota": 2}
    for class_name, label in class_map.items():
        class_dir = labeled_dir / class_name
        for img_path in class_dir.glob("*.png"):
            img = cv2.imread(str(img_path), cv2.IMREAD_GRAYSCALE)
            img = cv2.resize(img, Config.CELL_SIZE)
            features = hog(
                img,
                orientations=Config.HOG_ORIENTATIONS,
                pixels_per_cell=Config.HOG_PIXELS_PER_CELL,
                cells_per_block=Config.HOG_CELLS_PER_BLOCK,
                block_norm='L2-Hys',
                feature_vector=True
            )
            X.append(features)
            y.append(label)
    return np.array(X), np.array(y)

def train():
    print("Caricamento dataset...")
    X, y = load_dataset(Config.DATA_DIR / "augmented")
    print(f"Dataset: {len(X)} esempi, classi: {np.bincount(y)}")

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    # Pipeline: normalizzazione + SVM con kernel RBF + probabilistic output
    pipeline = Pipeline([
        ('scaler', StandardScaler()),
        ('svm', SVC(
            kernel='rbf',
            C=10.0,
            gamma='scale',
            probability=True,    # OBBLIGATORIO per confidence scores
            random_state=42
        ))
    ])

    print("Training SVM...")
    pipeline.fit(X_train, y_train)

    # Valutazione
    accuracy = pipeline.score(X_test, y_test)
    cv_scores = cross_val_score(pipeline, X, y, cv=5)
    print(f"Accuracy test set: {accuracy:.3f}")
    print(f"Cross-val: {cv_scores.mean():.3f} ± {cv_scores.std():.3f}")

    # Salva modello
    Config.MODELS_DIR.mkdir(exist_ok=True)
    joblib.dump(pipeline, Config.SVM_MODEL_PATH)
    print(f"Modello salvato: {Config.SVM_MODEL_PATH}")

    # Target: accuracy > 0.90, se sotto → aggiungere più dati
    if accuracy < 0.90:
        print("⚠️  Accuracy sotto 90%. Aggiungere più esempi di training.")

if __name__ == "__main__":
    train()
```

---

## 7. TRAINING — MODALITÀ B (YOLOv8n)

### 7.1 training/mode_b/prepare_yolo_dataset.py

```python
"""
Converte le celle etichettate in formato YOLO per il fine-tuning.
Struttura output:
  data/yolo_dataset/
    images/train/   → immagini celle
    images/val/     → 20% per validazione
    labels/train/   → file .txt con class_id (0/1/2)
    labels/val/
    data.yaml       → configurazione dataset
"""
# Per classificazione (non detection), ogni immagine ha un solo label.
# Il formato YOLO classification è semplicissimo:
# - immagini in cartelle nominate con la classe
# - data.yaml descrive le classi

DATA_YAML = """
path: data/yolo_dataset
train: images/train
val: images/val
nc: 3
names:
  0: cerchio
  1: croce
  2: vuota
"""
```

### 7.2 training/mode_b/train_yolo.py

```python
"""
Fine-tuning YOLOv8n per classificazione celle CBCL.
Richiede: Ultralytics, PyTorch con CUDA, RTX 3070.
Eseguire SOLO sul PC sviluppatore. NON includere nella distribuzione.

NOTA LICENZA: Ultralytics è AGPL-3.0. Il modello addestrato (.pt e .onnx)
è tuo e puoi distribuirlo. Il codice Ultralytics NON va nel software finale.
"""
from ultralytics import YOLO

def train_yolo():
    # Parte da YOLOv8n pre-trained su ImageNet (scarica ~6MB)
    model = YOLO('yolov8n-cls.pt')  # versione classificazione, non detection

    results = model.train(
        data='data/yolo_dataset',
        task='classify',          # Task: classificazione immagini
        epochs=100,
        imgsz=64,                 # Celle piccole 64x64
        batch=64,                 # RTX 3070 regge batch grandi
        device=0,                 # GPU 0 = RTX 3070
        patience=20,              # Early stopping
        lr0=0.001,               # Learning rate iniziale
        lrf=0.01,                # Learning rate finale (cosine decay)
        weight_decay=0.0005,
        warmup_epochs=3,
        dropout=0.3,             # Regularizzazione
        save=True,
        project='models',
        name='yolo_cbcl',
        exist_ok=True,
        pretrained=True,         # Fine-tuning da ImageNet weights
        verbose=True,
    )

    print(f"Training completato. Miglior accuracy: {results.results_dict}")
    print(f"Modello salvato in: models/yolo_cbcl/weights/best.pt")
    return results

if __name__ == "__main__":
    train_yolo()
```

### 7.3 training/mode_b/export_onnx.py

```python
"""
Esporta il modello .pt addestrato in formato ONNX per la distribuzione.
Il file .onnx NON richiede PyTorch o Ultralytics per l'inferenza.
"""
from ultralytics import YOLO

def export():
    model = YOLO('models/yolo_cbcl/weights/best.pt')
    model.export(
        format='onnx',
        imgsz=64,
        dynamic=False,     # Static shapes per compatibilità massima
        simplify=True,     # Ottimizza il grafo ONNX
        opset=17,          # ONNX opset compatibile con onnxruntime 1.18
    )
    print("Esportato: models/yolo_cbcl/weights/best.onnx")
    print("Copia in: models/yolo_cbcl.onnx")

if __name__ == "__main__":
    export()
```

---

## 8. SCORER CBCL

### 8.1 scorer/cbcl_scorer.py

```python
"""
Calcola i punteggi CBCL 6-18 dalle risposte estratte.
Implementa la struttura di scoring ufficiale con subscale e totali.

NOTA: Le formule di scoring CBCL sono proprietà Achenbach System of
Empirically Based Assessment (ASEBA). Implementare secondo il manuale
ufficiale in possesso del clinico.
"""
import pandas as pd
from pathlib import Path

# Mapping subscale CBCL 6-18 (item → subscala)
# Compilare secondo il manuale CBCL
SUBSCALE_MAPPING = {
    "ansia_depressione": [14, 29, 30, 31, 32, 33, 35, 45, 50, 52, 71, 91, 112],
    "isolamento_depressione": [5, 42, 65, 69, 75, 102, 103, 111],
    "lamentele_somatiche": [47, 51, 54, 56, 58],
    "problemi_sociali": [11, 12, 25, 27, 34, 36, 38, 48],
    "problemi_pensiero": [9, 18, 40, 46, 58, 66, 70, 76, 83, 84, 85],
    "problemi_attenzione": [1, 4, 8, 10, 13, 17, 41, 61, 78],
    "comportamento_trasgressivo": [2, 26, 28, 39, 43, 63, 67, 72, 73, 81, 82, 90, 96, 99, 101, 105],
    "comportamento_aggressivo": [3, 7, 16, 19, 20, 21, 22, 23, 37, 57, 68, 86, 87, 88, 89, 94, 95, 97],
}

INTERNALIZING = ["ansia_depressione", "isolamento_depressione", "lamentele_somatiche"]
EXTERNALIZING = ["comportamento_trasgressivo", "comportamento_aggressivo"]

class CBCLScorer:
    def score(self, items_result: dict) -> dict:
        """
        Input: {"1": {"value": 0, ...}, "2": {"value": 1, ...}, ...}
        Output: punteggi subscale, internalizzanti, esternalizzanti, totale
        """
        # Estrai solo i valori numerici
        values = {}
        for item_id, result in items_result.items():
            v = result.get("value")
            if v is not None:
                values[int(item_id)] = int(v)

        scores = {}

        # Subscale
        for subscala, item_list in SUBSCALE_MAPPING.items():
            raw = sum(values.get(i, 0) for i in item_list)
            scores[subscala] = raw

        # Punteggi compositi
        scores["internalizzanti"] = sum(
            scores[s] for s in INTERNALIZING
        )
        scores["esternalizzanti"] = sum(
            scores[s] for s in EXTERNALIZING
        )
        scores["totale"] = sum(values.values())
        scores["item_compilati"] = len(values)
        scores["item_mancanti"] = 112 - len(values)

        return scores

    def to_dataframe(self, items_result: dict) -> pd.DataFrame:
        """Export a DataFrame per CSV."""
        rows = []
        for item_id, result in sorted(items_result.items(),
                                       key=lambda x: int(x[0])):
            rows.append({
                "item": item_id,
                "valore": result.get("value", ""),
                "confidence": round(result.get("confidence", 0), 3),
                "flag": result.get("flag", ""),
            })
        return pd.DataFrame(rows)
```

---

## 9. INTERFACCIA STREAMLIT

### 9.1 app.py — struttura principale

```python
"""
Entry point Smart OCR.
Avviare con: streamlit run app.py
"""
import streamlit as st
from pathlib import Path
from config import Config, ClassificationMode
from pipeline.engine import OCREngine
from scorer.cbcl_scorer import CBCLScorer
import pandas as pd

st.set_page_config(
    page_title="Smart OCR — CBCL Scanner",
    page_icon="🧾",
    layout="wide"
)

# ── SIDEBAR ──────────────────────────────────────────────
with st.sidebar:
    st.title("⚙️ Configurazione")

    mode_label = st.radio(
        "Modalità di classificazione",
        options=["A — Classico (HOG + SVM)", "B — AI Fine-tuned (YOLOv8n)"],
        help="Modalità A: robusta, no GPU. Modalità B: più accurata, richiede modello addestrato."
    )
    selected_mode = (ClassificationMode.MODE_A_SVM
                     if "A" in mode_label
                     else ClassificationMode.MODE_B_YOLO)

    st.divider()
    # Mostra stato modelli
    svm_ok = Config.SVM_MODEL_PATH.exists()
    yolo_ok = Config.YOLO_ONNX_PATH.exists()
    st.write("**Stato modelli:**")
    st.write(f"{'✅' if svm_ok else '❌'} SVM (Modalità A)")
    st.write(f"{'✅' if yolo_ok else '❌'} YOLO ONNX (Modalità B)")

# ── TAB PRINCIPALI ───────────────────────────────────────
tab_analisi, tab_training, tab_risultati, tab_info = st.tabs([
    "📷 Analisi", "🏋️ Training", "📊 Risultati", "ℹ️ Info"
])

with tab_analisi:
    st.header("Analisi Questionario")
    uploaded = st.file_uploader(
        "Carica foto questionario CBCL",
        type=["jpg", "jpeg", "png"],
        accept_multiple_files=True
    )

    if uploaded and st.button("▶️ Avvia Analisi"):
        engine = OCREngine(mode=selected_mode)
        scorer = CBCLScorer()

        for photo_file in uploaded:
            with st.spinner(f"Processing {photo_file.name}..."):
                # Salva temporaneamente (in memoria, non su disco persistente)
                import tempfile
                with tempfile.NamedTemporaryFile(suffix=".jpg",
                                                  delete=False) as tmp:
                    tmp.write(photo_file.read())
                    tmp_path = tmp.name

                result = engine.process_questionnaire(tmp_path)
                Path(tmp_path).unlink()  # Cancella immediato

                # Mostra risultati
                st.success(
                    f"✅ Completato in {result['processing_time_ms']}ms "
                    f"| Modalità: {result['mode_used'].upper()} "
                    f"| Mancanti: {len(result['missing'])} "
                    f"| Ambigui: {len(result['ambiguous'])}"
                )

                scores = scorer.score(result["items"])
                df = scorer.to_dataframe(result["items"])

                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Punteggio Totale", scores["totale"])
                    st.metric("Internalizzanti", scores["internalizzanti"])
                    st.metric("Esternalizzanti", scores["esternalizzanti"])
                with col2:
                    st.dataframe(df, use_container_width=True)

                # Export CSV
                csv = df.to_csv(index=False,
                                sep=Config.OUTPUT_CSV_SEPARATOR)
                st.download_button(
                    "⬇️ Scarica CSV",
                    data=csv,
                    file_name=f"cbcl_{photo_file.name}.csv",
                    mime="text/csv"
                )

with tab_training:
    st.header("🏋️ Training Modelli")
    st.info("Usa questa sezione per addestrare/aggiornare i modelli.")

    subtab_label, subtab_train_a, subtab_train_b = st.tabs([
        "1️⃣ Etichettatura", "2️⃣ Train Modalità A", "3️⃣ Train Modalità B"
    ])

    with subtab_label:
        st.write("**Tool di etichettatura celle**")
        # Importare e rendere disponibile il labeling_tool qui
        # ...

    with subtab_train_a:
        if st.button("🚀 Avvia Training SVM"):
            import subprocess
            subprocess.run(["python", "training/mode_a/train_svm.py"])

    with subtab_train_b:
        st.warning("Richiede RTX 3070 e requirements_training.txt installato.")
        if st.button("🚀 Avvia Fine-tuning YOLOv8n"):
            import subprocess
            subprocess.run(["python", "training/mode_b/train_yolo.py"])
```

---

## 10. PACKAGING E DISTRIBUZIONE

### 10.1 packaging/smart_ocr_windows.spec (PyInstaller)

```python
# PyInstaller spec per Windows .exe
# Include: modelli .pkl e .onnx, cbcl_grid.json
# Esclude: PyTorch, Ultralytics, CUDA (non necessari in runtime)

block_cipher = None

a = Analysis(
    ['app.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('templates/cbcl_grid.json', 'templates'),
        ('models/svm_classifier.pkl', 'models'),
        ('models/yolo_cbcl.onnx', 'models'),
    ],
    hiddenimports=[
        'streamlit', 'cv2', 'sklearn', 'onnxruntime',
        'skimage.feature', 'PIL', 'pandas', 'numpy'
    ],
    excludes=[
        'torch', 'torchvision', 'ultralytics',
        'tensorflow', 'keras', 'matplotlib'
    ],
    ...
)
```

### 10.2 Note cross-platform

**Windows**: pip install tutto da requirements_base.txt → PyInstaller → .exe
**macOS Intel**: uguale a Windows, opencv da pip ok
**macOS Apple Silicon (M1/M2/M3)**:
```bash
conda create -n smartocr python=3.11
conda install -c conda-forge opencv   # OBBLIGATORIO per arm64
pip install -r requirements/requirements_mac_arm.txt
```

---

## 11. SEQUENZA IMPLEMENTAZIONE — ORDINE ESATTO

### FASE 1 — Fondamenta (inizia qui)
1. Crea struttura directory completa
2. Scrivi `config.py`
3. Scrivi `utils/platform_utils.py`
4. Setup `requirements/` con le 3 varianti
5. Inizializza `.gitignore` (escludi data/, models/, output/)

### FASE 2 — Calibrazione griglia (CRITICA)
6. Scrivi `tools/grid_calibrator.py` (tool interattivo click-to-label)
7. Esegui su 3 foto reali in `data/raw_photos/`
8. Media le coordinate e costruisci `templates/cbcl_grid.json` completo (112 item)
9. Valida visivamente con overlay su tutte le foto disponibili

### FASE 3 — Pipeline preprocessing
10. Scrivi e testa `pipeline/preprocessor.py` su tutte le foto reali
11. Scrivi e testa `pipeline/perspective_corrector.py`
12. Scrivi e testa `pipeline/grid_extractor.py`
13. Test visivo: estrarre celle da tutte le foto, verificare che siano corrette

### FASE 4 — Modalità A (SVM)
14. Scrivi `pipeline/mode_a/hog_extractor.py`
15. Scrivi `pipeline/mode_a/svm_classifier.py`
16. Scrivi `training/shared/labeling_tool.py`
17. Etichetta manualmente ~50 celle reali (10 per classe almeno)
18. Scrivi `training/shared/augmentor.py` (albumentations==2.0.8)
19. Genera augmented dataset (target: 300 per classe)
20. Scrivi e esegui `training/mode_a/train_svm.py`
21. Verifica accuracy > 90%

### FASE 5 — Engine e Scorer
22. Scrivi `pipeline/engine.py`
23. Scrivi `scorer/cbcl_scorer.py` (subscale complete secondo manuale)
24. Test end-to-end: foto → JSON → punteggi

### FASE 6 — Modalità B (YOLOv8n)
25. Scrivi `training/mode_b/prepare_yolo_dataset.py`
26. Genera dataset YOLO dal labeled dataset di Fase 4
27. Scrivi e esegui `training/mode_b/train_yolo.py` su RTX 3070
28. Scrivi e esegui `training/mode_b/export_onnx.py`
29. Scrivi `pipeline/mode_b/yolo_classifier.py`
30. Test end-to-end Modalità B

### FASE 7 — UI e Packaging
31. Scrivi `app.py` completo con tutte le tab
32. Test UI con foto reali in entrambe le modalità
33. Scrivi `packaging/smart_ocr_windows.spec`
34. Build .exe con PyInstaller
35. Test .exe su macchina pulita senza Python

---

## 12. CHECKLIST QUALITÀ PRIMA DEL RILASCIO

- [ ] Accuracy Modalità A > 90% su test set
- [ ] Accuracy Modalità B > 95% su test set
- [ ] Nessun dato paziente scritto in log o file temporanei
- [ ] .exe gira su Windows senza Python installato
- [ ] App gira su macOS Intel senza GPU
- [ ] App gira su macOS Apple Silicon (conda-forge opencv)
- [ ] albumentations==2.0.8 (non 2.1+)
- [ ] onnxruntime in distribuzione (non ultralytics/torch)
- [ ] Celle ambigue mostrate chiaramente nella UI per revisione umana
- [ ] Export CSV compatibile con Excel italiano (separatore ;)
- [ ] cbcl_grid.json coperto tutti i 112 item su pagine 4, 5, 6
```
