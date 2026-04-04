"""
pipeline/engine.py

Orchestratore multi-mode: coordina preprocessing → estrazione → classificazione → scoring.
Interfaccia unificata per Mode A (SVM), Mode B (YOLO), Mode C (Ensemble), Mode D (PDF).

Uso da app.py:
    from pipeline.engine import OCREngine
    from config import ClassificationMode

    engine = OCREngine(ClassificationMode.MODE_A_SVM)
    report = engine.process_page(image_path, page, debug=False)

    # Per PDF digitali:
    engine = OCREngine(ClassificationMode.MODE_D_PDF)
    report = engine.process_page(gray_array, page, debug=False)
"""

import time
import cv2
import numpy as np
from pathlib import Path
from typing import Optional, Union, List

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import Config, ClassificationMode
from core.preprocessor import preprocess_full_pipeline, align_to_template, detect_grid_offsets
from core.grid_extractor import extract_all_cells, visualize_grid_overlay
from core.omr_classifier import classify_all_items_omr, classify_all_items_pdf
from core.scorer import build_score_report


# Target A4 300dpi
_TARGET_W, _TARGET_H = 2480, 3508


class OCREngine:
    """
    Interfaccia unificata per tutte le modalita.
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

        if self.mode == ClassificationMode.MODE_D_PDF:
            # PDF mode: usa OMR ottimizzato, nessun modello da caricare
            self._classifier = None
            return "pdf"

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
        Returns: "svm", "yolo", "ensemble", "pdf", o "omr"
        """
        method = self._load_classifier()
        return method

    @property
    def fallback_reason(self) -> Optional[str]:
        """Se il metodo richiesto non e disponibile, ritorna il motivo."""
        return self._fallback_reason

    @staticmethod
    def _preprocess_pdf_page(gray_image: np.ndarray) -> np.ndarray:
        """
        Preprocessing leggero per pagine PDF digitali.
        Niente prospettiva/deskew (gia perfette), solo resize a target A4.
        """
        if gray_image.shape != (_TARGET_H, _TARGET_W):
            gray_image = cv2.resize(
                gray_image, (_TARGET_W, _TARGET_H),
                interpolation=cv2.INTER_AREA
            )
        return gray_image

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
            image_path_or_array: path immagine o numpy array (grayscale per PDF)
            page: "page_4", "page_5", "page_6"
            debug: abilita info debug
            session_id: identificatore sessione

        Returns:
            report dict con items, score, flags, statistiche
        """
        start = time.time()
        method = self._load_classifier()

        # Step 1: Preprocessing
        if method == "pdf":
            # PDF mode: preprocessing leggero (solo resize)
            if isinstance(image_path_or_array, np.ndarray):
                gray = image_path_or_array
            else:
                img = cv2.imread(str(image_path_or_array))
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
            gray = self._preprocess_pdf_page(gray)
            meta = {"pdf_mode": True, "final_size": gray.shape}
        elif isinstance(image_path_or_array, np.ndarray):
            gray = image_path_or_array
            meta = {}
        else:
            gray, meta = preprocess_full_pipeline(image_path_or_array, debug=debug)

        # Step 1b: Allineamento SIFT al template (solo foto, non PDF)
        offsets = None
        if method != "pdf":
            gray, aligned_ok, align_info = align_to_template(gray, page)
            meta['sift_aligned'] = aligned_ok
            meta['alignment_info'] = align_info
            if not aligned_ok:
                meta.setdefault('warnings', []).append(
                    "Allineamento SIFT al template fallito. Accuratezza potrebbe essere ridotta."
                )

            # Step 1c: Correzione locale con Hough grid lines
            if aligned_ok:
                offsets = detect_grid_offsets(gray, page)
                meta['grid_offsets_success'] = offsets.get('success', False)

        # Step 2: Estrazione celle (con correzioni locali se disponibili)
        cells_dict = extract_all_cells(gray, page, offsets=offsets)

        # Step 3: Classificazione
        classification_results = {}

        if method == "pdf":
            classification_results = classify_all_items_pdf(
                cells_dict,
                empty_threshold=Config.PDF_EMPTY_THRESHOLD,
                min_ratio=Config.PDF_MIN_RATIO,
                ambiguity_gap=Config.PDF_AMBIGUITY_GAP
            )
        elif method in ("svm", "yolo") and self._classifier is not None:
            for item_id, item_cells in cells_dict.items():
                classification_results[item_id] = self._classifier.predict_item_cells(item_cells)
        elif method == "ensemble" and self._classifier is not None:
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
            report["_overlay"] = visualize_grid_overlay(gray, page, offsets=offsets)
            report["_preprocessed"] = gray
            report["_preprocess_meta"] = meta

        return report

    def process_pdf(
        self,
        pdf_path: str,
        pages: Optional[List[str]] = None,
        session_id: Optional[str] = None,
        debug: bool = False
    ) -> dict:
        """
        Processa un PDF completo (3 pagine = 1 questionario CBCL).
        Forza automaticamente Mode D (PDF).

        Args:
            pdf_path: path al file PDF
            pages: lista pagine da processare (default: tutte e 3)
            session_id: identificatore sessione
            debug: abilita info debug

        Returns:
            report combinato con tutti gli item delle 3 pagine
        """
        try:
            import fitz
        except ImportError:
            raise ImportError(
                "PyMuPDF (fitz) necessario per PDF mode. "
                "Installa con: pip install pymupdf"
            )

        if pages is None:
            pages = ["page_4", "page_5", "page_6"]

        # Forza PDF mode
        original_mode = self.mode
        self.mode = ClassificationMode.MODE_D_PDF

        doc = fitz.open(pdf_path)
        all_classification = {}
        total_time_ms = 0

        try:
            for page_offset, page_name in enumerate(pages):
                if page_offset >= len(doc):
                    break

                # Render pagina PDF a grayscale
                pix = doc[page_offset].get_pixmap(dpi=Config.PDF_RENDER_DPI)
                img = np.frombuffer(
                    pix.samples, dtype=np.uint8
                ).reshape(pix.h, pix.w, pix.n)

                if pix.n >= 3:
                    gray = cv2.cvtColor(img[:, :, :3], cv2.COLOR_RGB2GRAY)
                else:
                    gray = img.squeeze()

                report = self.process_page(
                    gray, page=page_name,
                    debug=debug, session_id=session_id
                )

                # Accumula risultati classificazione
                for item_id, item_data in report["items"].items():
                    if item_data.get("value") is not None or item_data.get("flag") != "not_processed":
                        all_classification[item_id] = {
                            "value": item_data["value"],
                            "confidence": item_data["confidence"],
                            "flag": item_data["flag"],
                            "marked_column": str(item_data["value"]) if item_data["value"] is not None else None
                        }

                total_time_ms += report.get("_processing_time_ms", 0)
        finally:
            doc.close()
            self.mode = original_mode

        # Build report combinato
        combined_report = build_score_report(
            all_classification,
            session_id=session_id
        )
        combined_report["_processing_time_ms"] = total_time_ms
        combined_report["_method"] = "pdf"
        combined_report["_mode_requested"] = "pdf"
        combined_report["_fallback_reason"] = None
        combined_report["_pages_processed"] = len(pages)

        return combined_report
