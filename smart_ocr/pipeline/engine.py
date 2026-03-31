"""
pipeline/engine.py

Orchestratore dual-mode: coordina preprocessing → estrazione → classificazione → scoring.
Interfaccia unificata per Mode A (SVM) e Mode B (YOLO ONNX).

Uso da app.py:
    from pipeline.engine import OCREngine
    from config import ClassificationMode

    engine = OCREngine(ClassificationMode.MODE_A_SVM)
    report = engine.process_page(image_path, page, debug=False)
"""

import time
from pathlib import Path
from typing import Optional
import numpy as np

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import Config, ClassificationMode
from core.preprocessor import preprocess_full_pipeline
from core.grid_extractor import extract_all_cells, visualize_grid_overlay
from core.omr_classifier import classify_all_items_omr
from core.scorer import build_score_report


class OCREngine:
    """
    Interfaccia unificata per entrambe le modalita.
    Cambiare modalita e trasparente: stessa API, motore diverso.
    """

    def __init__(self, mode: ClassificationMode = Config.DEFAULT_MODE):
        self.mode = mode
        self._classifier = None
        self._fallback_reason = None

    def _load_classifier(self):
        """
        Carica il classificatore per la modalita corrente.
        Se il modello non e disponibile, fallback a OMR.
        """
        self._fallback_reason = None

        if self.mode == ClassificationMode.MODE_A_SVM:
            if Config.svm_model_available():
                try:
                    from pipeline.mode_a.svm_classifier import SVMClassifier
                    self._classifier = SVMClassifier()
                    return "svm"
                except Exception as e:
                    self._fallback_reason = f"Errore caricamento SVM: {e}"
            else:
                self._fallback_reason = "Modello SVM non trovato"

        elif self.mode == ClassificationMode.MODE_B_YOLO:
            if Config.yolo_model_available():
                try:
                    from pipeline.mode_b.yolo_classifier import YOLOClassifier
                    self._classifier = YOLOClassifier()
                    return "yolo"
                except Exception as e:
                    self._fallback_reason = f"Errore caricamento YOLO: {e}"
            else:
                self._fallback_reason = "Modello YOLO ONNX non trovato"

        elif self.mode == ClassificationMode.MODE_C_ENSEMBLE:
            if Config.svm_model_available() or Config.yolo_model_available():
                try:
                    from pipeline.ensemble_classifier import EnsembleClassifier
                    self._classifier = EnsembleClassifier()
                    return "ensemble"
                except Exception as e:
                    self._fallback_reason = f"Errore caricamento Ensemble: {e}"
            else:
                self._fallback_reason = "Nessun modello disponibile per Ensemble"

        # Fallback: OMR pixel-counting
        self._classifier = None
        return "omr"

    def switch_mode(self, new_mode: ClassificationMode):
        """Cambia modalita a runtime senza riavviare."""
        if new_mode != self.mode:
            self.mode = new_mode
            self._classifier = None  # Force reload

    def get_active_method(self) -> str:
        """
        Ritorna il metodo effettivamente attivo.
        Returns: "svm", "yolo", o "omr"
        """
        method = self._load_classifier()
        return method

    @property
    def fallback_reason(self) -> Optional[str]:
        """Se il metodo richiesto non e disponibile, ritorna il motivo."""
        return self._fallback_reason

    def process_page(
        self,
        image_path_or_array,
        page: str = "page_4",
        debug: bool = False,
        session_id: Optional[str] = None
    ) -> dict:
        """
        Processa una pagina di questionario CBCL.

        Args:
            image_path_or_array: path immagine o numpy array gia preprocessato
            page: "page_4", "page_5", "page_6"
            debug: abilita info debug
            session_id: identificatore sessione

        Returns:
            report dict con items, score, flags, statistiche
        """
        start = time.time()

        # Step 1: Preprocessing
        if isinstance(image_path_or_array, np.ndarray):
            gray = image_path_or_array
            meta = {}
        else:
            gray, meta = preprocess_full_pipeline(image_path_or_array, debug=debug)

        # Step 2: Estrazione celle
        cells_dict = extract_all_cells(gray, page)

        # Step 3: Classificazione
        method = self._load_classifier()
        classification_results = {}

        if method in ("svm", "yolo") and self._classifier is not None:
            for item_id, item_cells in cells_dict.items():
                classification_results[item_id] = self._classifier.predict_item_cells(item_cells)
        else:
            # Fallback OMR
            classification_results = classify_all_items_omr(cells_dict)

        # Step 4: Scoring
        report = build_score_report(
            classification_results,
            session_id=session_id
        )

        # Metadata aggiuntivi
        elapsed_ms = int((time.time() - start) * 1000)
        report["_processing_time_ms"] = elapsed_ms
        report["_method"] = method
        report["_mode_requested"] = self.mode.value
        report["_fallback_reason"] = self._fallback_reason

        if debug:
            report["_overlay"] = visualize_grid_overlay(gray, page)
            report["_preprocessed"] = gray
            report["_preprocess_meta"] = meta

        return report
