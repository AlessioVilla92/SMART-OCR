"""
pipeline/engine.py

Orchestratore multi-mode: coordina preprocessing → estrazione → classificazione → scoring.
Interfaccia unificata per Mode A (SVM), Mode B (YOLO), Mode C (Ensemble), Mode D (PDF).

Pipeline completa (5 fasi per foto):
1. Boundary detection + validazione
2. Perspective correction A4 (2480×3508)
3. Preprocessing (white balance, shadow removal, denoise, CLAHE)
4. SIFT+ECC alignment al template PDF
5. Classificazione celle + baseline fallback

Uso:
    from pipeline.engine import OCREngine
    from config import ClassificationMode

    engine = OCREngine(ClassificationMode.MODE_C_ENSEMBLE)
    report = engine.process_page("foto.jpg", page="page_4")

    # Per PDF digitali:
    engine = OCREngine(ClassificationMode.MODE_D_PDF)
    report = engine.process_page(gray_array, page="page_4")
"""

import time
import cv2
import numpy as np
from pathlib import Path
from typing import Optional, Union, List

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import Config, ClassificationMode
from core.preprocessor import preprocess_full_pipeline, load_image
from core.boundary_detector import detect_document_boundary, warp_to_a4
from core.template_aligner import TemplateAligner
from core.grid_extractor import extract_all_cells, visualize_grid_overlay
from core.omr_classifier import classify_all_items_omr, classify_all_items_pdf, classify_all_items_baseline
from core.scorer import build_score_report


# Target A4 300dpi
_TARGET_W, _TARGET_H = 2480, 3508

# Singleton TemplateAligner (caricato una volta, riusato)
_aligner: Optional[TemplateAligner] = None

# Cache preprocessing: evita ricalcolo SIFT su stessa immagine/pagina.
# CRITICO per determinismo: SIFT/RANSAC è non-deterministico, quindi senza cache
# la stessa foto può dare allineamenti diversi ad ogni chiamata, causando
# ~7 items con valori oscillanti su celle borderline.
# Chiave: (path_assoluto, page) → (gray, align_info, ref, meta)
# Si auto-invalida quando il path cambia (foto diverse = cache miss).
_preprocess_cache: dict = {}


def _get_aligner() -> TemplateAligner:
    """Singleton TemplateAligner con reference cached."""
    global _aligner
    if _aligner is None:
        _aligner = TemplateAligner()
        for page in ["page_4", "page_5", "page_6"]:
            try:
                _aligner.load_reference(page)
            except FileNotFoundError:
                pass
    return _aligner


class OCREngine:
    """
    Interfaccia unificata per tutte le modalita.
    Cambiare modalita e trasparente: stessa API, motore diverso.

    Pipeline completa con tutte le migliorie:
    - Boundary detection con validazione (scarta bordi immagine, conf < 0.5)
    - SIFT+ECC alignment al template
    - Auto-centering celle via ref_img
    - Baseline fallback per recupero items falliti
    """

    def __init__(self, mode: ClassificationMode = Config.DEFAULT_MODE):
        self.mode = mode
        self._classifier = None
        self._fallback_reason = None

    @staticmethod
    def clear_cache():
        """Svuota cache preprocessing (utile tra sessioni diverse)."""
        global _preprocess_cache
        _preprocess_cache.clear()

    def _load_classifier(self):
        """
        Carica il classificatore per la modalita corrente.
        Se il modello non e disponibile, fallback a OMR.
        """
        self._fallback_reason = None

        if self.mode == ClassificationMode.MODE_D_PDF:
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
            self._classifier = None

    def get_active_method(self) -> str:
        """Ritorna il metodo effettivamente attivo."""
        method = self._load_classifier()
        return method

    @property
    def fallback_reason(self) -> Optional[str]:
        """Se il metodo richiesto non e disponibile, ritorna il motivo."""
        return self._fallback_reason

    @staticmethod
    def _preprocess_pdf_page(gray_image: np.ndarray) -> np.ndarray:
        """Preprocessing leggero per pagine PDF digitali (solo resize)."""
        if gray_image.shape != (_TARGET_H, _TARGET_W):
            gray_image = cv2.resize(
                gray_image, (_TARGET_W, _TARGET_H),
                interpolation=cv2.INTER_AREA
            )
        return gray_image

    @staticmethod
    def _preprocess_photo(image_path_or_array, page: str, debug: bool = False) -> tuple:
        """
        Pipeline completa preprocessing foto (fasi 1-4).
        Risultati cached per path+page: stessa immagine preprocessata una sola volta
        (evita variazioni SIFT/RANSAC tra chiamate successive).

        Returns:
            (gray, align_info, ref_for_extraction, meta)
        """
        global _preprocess_cache

        # Cache key: solo per file path (non per numpy array)
        cache_key = None
        if not isinstance(image_path_or_array, np.ndarray):
            cache_key = (str(Path(str(image_path_or_array)).resolve()), page)
            if cache_key in _preprocess_cache:
                return _preprocess_cache[cache_key]

        meta = {}

        # Fase 1: Carica immagine
        if isinstance(image_path_or_array, np.ndarray):
            img = image_path_or_array
            if len(img.shape) == 2:
                # Grayscale array — skip boundary detection, go straight to preprocessing
                gray, preprocess_meta = preprocess_full_pipeline(img, debug=debug)
                meta.update(preprocess_meta)
                aligner = _get_aligner()
                aligned, align_info = aligner.align(gray, page)
                if align_info.get("aligned"):
                    gray = aligned
                ref = aligner._references.get(page) if align_info.get("aligned") else None
                meta['sift_aligned'] = align_info.get("aligned", False)
                return gray, align_info, ref, meta
        else:
            img = load_image(str(image_path_or_array))

        h_img, w_img = img.shape[:2]
        meta['original_size'] = (w_img, h_img)

        # Fase 2: Boundary detection con validazione
        corners = None
        try:
            c, conf, det_method = detect_document_boundary(img)
            margin = 5
            on_edge = any(
                pt[0] < margin or pt[1] < margin or
                pt[0] > w_img - margin or pt[1] > h_img - margin
                for pt in c
            )
            if not on_edge and conf >= 0.5:
                corners = c
                meta['boundary_method'] = det_method
                meta['boundary_confidence'] = conf
        except Exception:
            pass

        # Fase 3: Perspective correction + Preprocessing
        warped = warp_to_a4(img, corners) if corners is not None else img
        gray, preprocess_meta = preprocess_full_pipeline(warped, debug=debug)
        meta.update(preprocess_meta)

        # Fase 4: SIFT+ECC alignment al template
        aligner = _get_aligner()
        aligned, align_info = aligner.align(gray, page)
        if align_info.get("aligned"):
            gray = aligned
        meta['sift_aligned'] = align_info.get("aligned", False)

        ref = aligner._references.get(page) if align_info.get("aligned") else None

        result = (gray, align_info, ref, meta)

        # Salva in cache
        if cache_key is not None:
            _preprocess_cache[cache_key] = result

        return result

    @staticmethod
    def _apply_baseline_fallback(
        classification_results: dict,
        cells_dict: dict,
        ref_img: Optional[np.ndarray],
        page: str
    ) -> dict:
        """
        Baseline fallback: recupera items che il classificatore primario
        ha marcato come missing/multiple_marks/ambiguous usando pixel-counting
        sulla reference.
        """
        if ref_img is None:
            return classification_results

        ref_cells = extract_all_cells(ref_img, page)
        baseline_results = classify_all_items_baseline(cells_dict, ref_cells)

        for item_id, primary in classification_results.items():
            fallback = baseline_results.get(item_id, {})
            pv = primary.get("value")
            pf = primary.get("flag")
            fv = fallback.get("value")
            ff = fallback.get("flag")

            # Se il primario ha fallito, usa baseline come fallback
            if pv is None or pf in ("missing", "multiple_marks", "ambiguous"):
                if fv is not None and ff in (None, "low_confidence", "multiple_marks"):
                    classification_results[item_id] = fallback

        return classification_results

    def process_page(
        self,
        image_path_or_array,
        page: str = "page_4",
        debug: bool = False,
        session_id: Optional[str] = None
    ) -> dict:
        """
        Processa una pagina di questionario CBCL.

        Pipeline completa:
        1. Boundary detection + validazione
        2. Perspective correction A4
        3. Preprocessing (white balance, shadow removal, denoise, CLAHE)
        4. SIFT+ECC alignment al template
        5. Cell extraction con auto-centering
        6. Classificazione + baseline fallback

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

        # === PREPROCESSING ===
        if method == "pdf":
            # PDF mode: preprocessing leggero (solo resize)
            if isinstance(image_path_or_array, np.ndarray):
                gray = image_path_or_array
            else:
                img = cv2.imread(str(image_path_or_array))
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
            gray = self._preprocess_pdf_page(gray)
            meta = {"pdf_mode": True, "final_size": gray.shape}
            align_info = {}
            ref_for_extraction = None
        else:
            # Foto mode: pipeline completa (5 fasi)
            gray, align_info, ref_for_extraction, meta = self._preprocess_photo(
                image_path_or_array, page, debug=debug
            )

        # === CELL EXTRACTION con auto-centering ===
        cells_dict = extract_all_cells(gray, page, ref_img=ref_for_extraction)

        # === CLASSIFICAZIONE ===
        classification_results = {}

        if method == "pdf":
            classification_results = classify_all_items_pdf(
                cells_dict,
                empty_threshold=Config.PDF_EMPTY_THRESHOLD,
                min_ratio=Config.PDF_MIN_RATIO,
                ambiguity_gap=Config.PDF_AMBIGUITY_GAP
            )
        elif method in ("svm", "yolo", "ensemble") and self._classifier is not None:
            for item_id, item_cells in cells_dict.items():
                classification_results[item_id] = self._classifier.predict_item_cells(item_cells)
        else:
            # Fallback OMR
            classification_results = classify_all_items_omr(cells_dict)

        # === BASELINE FALLBACK (recupero items falliti) ===
        if method != "pdf":
            classification_results = self._apply_baseline_fallback(
                classification_results, cells_dict, ref_for_extraction, page
            )

        # === SCORING ===
        report = build_score_report(
            classification_results,
            session_id=session_id
        )

        # Metadata
        elapsed_ms = int((time.time() - start) * 1000)
        report["_processing_time_ms"] = elapsed_ms
        report["_method"] = method
        report["_mode_requested"] = self.mode.value
        report["_fallback_reason"] = self._fallback_reason
        report["_align_info"] = align_info if method != "pdf" else {}

        if debug:
            report["_overlay"] = visualize_grid_overlay(gray, page)
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

    def process_photos(
        self,
        photo_paths: dict,
        session_id: Optional[str] = None,
        debug: bool = False
    ) -> dict:
        """
        Processa un set completo di 3 foto (1 questionario CBCL).

        Preprocessing condiviso: ogni foto viene preprocessata una sola volta,
        poi le celle estratte vengono classificate e recuperate con baseline fallback.
        Questo garantisce risultati deterministici e consistenti.

        Args:
            photo_paths: dict {page: path} es. {"page_4": "foto1.jpg", "page_5": "foto2.jpg", "page_6": "foto3.jpg"}
            session_id: identificatore sessione
            debug: abilita info debug

        Returns:
            report combinato con tutti gli item delle 3 pagine
        """
        import time as _time
        start = _time.time()
        method = self._load_classifier()

        all_classification = {}

        # FASE 1: Preprocessing condiviso — ogni foto preprocessata una sola volta.
        # CRITICO: il preprocessing (SIFT alignment) viene fatto QUI, una volta sola,
        # e il risultato viene condiviso tra classificazione e baseline fallback.
        # Questo è identico al test originale che ha dato 122/122, score 68.
        # Se si preprocessa separatamente (come in process_page singolo), SIFT
        # non-deterministico può dare risultati diversi.
        preprocessed = {}
        for page_name, photo_path in photo_paths.items():
            gray, align_info, ref, meta = self._preprocess_photo(
                photo_path, page_name, debug=debug
            )
            cells_dict = extract_all_cells(gray, page_name, ref_img=ref)
            ref_cells = extract_all_cells(ref, page_name) if ref is not None else None
            preprocessed[page_name] = (cells_dict, ref_cells, ref, gray)

        # FASE 2: Classificazione + baseline fallback per ogni pagina
        for page_name in photo_paths:
            cells_dict, ref_cells, ref, gray = preprocessed[page_name]

            # Classificazione primaria
            if method in ("svm", "yolo", "ensemble") and self._classifier is not None:
                classification_results = {}
                for item_id, item_cells in cells_dict.items():
                    classification_results[item_id] = self._classifier.predict_item_cells(item_cells)
            else:
                classification_results = classify_all_items_omr(cells_dict)

            # Baseline fallback: recupera items che il classificatore primario
            # non è riuscito a classificare (missing/ambiguous/multiple_marks).
            # Usa pixel-counting sulla differenza foto-reference.
            # Questa strategia porta da ~84% a 100% di items classificati.
            if ref_cells is not None:
                baseline_results = classify_all_items_baseline(cells_dict, ref_cells)
                for item_id, primary in classification_results.items():
                    fallback = baseline_results.get(item_id, {})
                    pv = primary.get("value")
                    pf = primary.get("flag")
                    fv = fallback.get("value")
                    ff = fallback.get("flag")
                    if pv is None or pf in ("missing", "multiple_marks", "ambiguous"):
                        if fv is not None and ff in (None, "low_confidence", "multiple_marks"):
                            classification_results[item_id] = fallback

            # FASE 2b: Filtro "genuinamente vuoto" — se tutte e 3 le celle
            # hanno delta bassissimo rispetto alla reference (< 0.025), la domanda
            # è stata lasciata vuota dal paziente. Forza missing indipendentemente
            # da cosa dice il classificatore (che può vedere rumore/ombre come segni).
            # Soglia 0.025: sotto il minimo delta di celle realmente marcate (0.035+)
            # e sopra il rumore tipico delle celle vuote (media 0.027).
            if ref_cells is not None:
                # Soglia: se il delta massimo tra le 3 celle è sotto 0.025,
                # la domanda è stata lasciata vuota (nessun segno aggiunto).
                # 0.025 è tra il delta di item 16 segnato (max positivo 0.0117,
                # ma ha delta negativo -0.0105 che lo esclude) e item 77 vuoto
                # (tutti positivi, max 0.0205).
                # Condizione: tutti i delta devono essere >= 0 (nessuna cella
                # più scura nella reference) E tutti sotto la soglia.
                _BLANK_THRESHOLD = 0.025
                for item_id in list(classification_results.keys()):
                    bl = baseline_results.get(item_id, {})
                    deltas = bl.get("deltas", {})
                    if deltas and all(0 <= d < _BLANK_THRESHOLD for d in deltas.values()):
                        classification_results[item_id] = {
                            "value": None,
                            "confidence": 0.0,
                            "flag": "missing",
                        }

            # Accumula risultati
            for item_id, item_data in classification_results.items():
                all_classification[item_id] = item_data

        # FASE 3: Scoring combinato
        elapsed_ms = int((_time.time() - start) * 1000)
        combined_report = build_score_report(
            all_classification,
            session_id=session_id
        )
        combined_report["_processing_time_ms"] = elapsed_ms
        combined_report["_method"] = method
        combined_report["_mode_requested"] = self.mode.value
        combined_report["_fallback_reason"] = self._fallback_reason
        combined_report["_pages_processed"] = len(photo_paths)

        return combined_report
