"""
config.py

Configurazione globale Smart OCR — Multi-Mode.
Tutte le costanti, path e impostazioni centralizzate.

Mode A: HOG + SVM (classico, per foto)
Mode B: YOLOv8n ONNX (AI fine-tuned, per foto)
Mode C: Ensemble SVM + YOLO (massima accuratezza, per foto)
Mode D: PDF digitale (OMR ottimizzato, no preprocessing)
"""

from pathlib import Path
from enum import Enum


class ClassificationMode(Enum):
    MODE_A_SVM = "svm"          # HOG features + SVM classifier
    MODE_B_YOLO = "yolo"        # YOLOv8n ONNX fine-tuned
    MODE_C_ENSEMBLE = "ensemble" # SVM + YOLO soft voting + TTA
    MODE_D_PDF = "pdf"          # OMR ottimizzato per PDF digitali


class Config:
    # === Paths ===
    BASE_DIR = Path(__file__).parent
    MODELS_DIR = BASE_DIR / "models"
    TEMPLATES_DIR = BASE_DIR / "templates"
    DATA_DIR = BASE_DIR / "data"
    OUTPUT_DIR = BASE_DIR / "output"

    # --- Mode A (SVM) ---
    SVM_MODEL_NEW_PATH = MODELS_DIR / "svm_classifier.pkl"
    SVM_MODEL_OLD_PATH = MODELS_DIR / "model.pkl"
    SVM_TRAINING_REPORT_PATH = MODELS_DIR / "training_report.json"

    # --- Mode B (YOLO) ---
    YOLO_ONNX_PATH = MODELS_DIR / "yolo_cbcl.onnx"
    YOLO_PT_PATH = MODELS_DIR / "yolo_cbcl.pt"  # solo dev, non distribuire
    YOLO_TRAINING_REPORT_PATH = MODELS_DIR / "training_report_yolo.json"
    YOLO_DATASET_DIR = DATA_DIR / "yolo_dataset"

    # Template griglia (condiviso tra i due mode)
    CBCL_GRID_PATH = TEMPLATES_DIR / "cbcl_grid.json"

    # === Preprocessing (condiviso) ===
    CELL_SIZE = (64, 64)

    # === Classificazione ===
    # Soglie confidence sotto cui la cella e "ambigua"
    SVM_CONFIDENCE_THRESHOLD = 0.65
    YOLO_CONFIDENCE_THRESHOLD = 0.55

    # HOG parameters (Mode A)
    HOG_WIN_SIZE = (64, 64)
    HOG_BLOCK_SIZE = (16, 16)
    HOG_BLOCK_STRIDE = (8, 8)
    HOG_CELL_SIZE = (8, 8)
    HOG_NBINS = 9

    # === Classi (mapping binario) ===
    # Classificazione binaria: segnato (qualsiasi mark) vs vuoto
    CLASSES = {0: "segnato", 1: "vuoto"}
    CLASSES_INV = {"segnato": 0, "vuoto": 1}

    # Legacy 3-classi (per compatibilita con modelli vecchi)
    CLASSES_LEGACY = {0: "cerchio", 1: "x_rossa", 2: "vuoto"}
    CLASSES_LEGACY_INV = {"cerchio": 0, "x_rossa": 1, "vuoto": 2}

    # === PDF Mode (Mode D) ===
    # Soglia sotto cui una cella e considerata vuota (nessun mark)
    PDF_EMPTY_THRESHOLD = 0.08
    # Rapporto minimo di pixel scuri per considerare la cella non vuota
    PDF_MIN_RATIO = 0.06
    # Gap relativo minimo per classificazione non-ambigua (winner-takes-all)
    PDF_AMBIGUITY_GAP = 0.0  # 0 = puro winner-takes-all
    # Risoluzione target per rendering PDF
    PDF_RENDER_DPI = 300

    # Output
    OUTPUT_CSV_SEPARATOR = ";"  # Punto e virgola per Excel italiano

    # Default
    DEFAULT_MODE = ClassificationMode.MODE_A_SVM

    @classmethod
    def get_svm_model_path(cls) -> Path:
        """
        Ritorna il path del modello SVM con fallback.
        Cerca prima svm_classifier.pkl, poi model.pkl.
        """
        if cls.SVM_MODEL_NEW_PATH.exists():
            return cls.SVM_MODEL_NEW_PATH
        if cls.SVM_MODEL_OLD_PATH.exists():
            return cls.SVM_MODEL_OLD_PATH
        return cls.SVM_MODEL_NEW_PATH  # path default (anche se non esiste)

    @classmethod
    def svm_model_available(cls) -> bool:
        return cls.SVM_MODEL_NEW_PATH.exists() or cls.SVM_MODEL_OLD_PATH.exists()

    @classmethod
    def yolo_model_available(cls) -> bool:
        return cls.YOLO_ONNX_PATH.exists()
