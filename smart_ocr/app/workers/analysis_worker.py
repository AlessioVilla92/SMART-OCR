"""
Worker thread per l'analisi OMR non-blocking.

CRITICO — Perché usa process_photos() e NON process_page():
    process_photos() fa preprocessing UNA SOLA VOLTA per foto e lo condivide
    tra classificazione e baseline fallback. Questo è identico al test originale
    che ha dato 122/122 items, score 68, concordanza 100% su test4.

    Se invece si chiama process_page() separatamente per ogni pagina,
    SIFT/RANSAC (non-deterministico) può produrre allineamenti diversi
    ad ogni chiamata, causando ~7 items con valori oscillanti.

CRITICO — Perché NON si chiama clear_cache():
    La cache di preprocessing (_preprocess_cache) garantisce che la stessa
    foto produca sempre lo stesso allineamento SIFT. Senza cache, esecuzioni
    successive sulle stesse foto possono dare score diversi (64-68)
    a causa del non-determinismo di RANSAC.
    La cache si auto-invalida quando l'utente carica foto diverse (path diverso).
"""

from PySide6.QtCore import QThread, Signal
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from pipeline.engine import OCREngine
from config import ClassificationMode


class AnalysisWorker(QThread):
    """Thread separato per processing OCR completo su QThread."""

    progress = Signal(str, int)       # (fase_nome, percentuale 0-100)
    finished = Signal(dict)           # report combinato finale con tutti i 122 items
    error = Signal(str)               # messaggio errore con traceback

    def __init__(self, photo_paths: dict, mode: ClassificationMode):
        """
        Args:
            photo_paths: {page_key: file_path}
                         es. {"page_4": "foto1.jpg", "page_5": "foto2.jpg", "page_6": "foto3.jpg"}
            mode: ClassificationMode (MODE_A_SVM, MODE_B_YOLO, MODE_C_ENSEMBLE)
        """
        super().__init__()
        self.photo_paths = photo_paths
        self.mode = mode

    def run(self):
        try:
            engine = OCREngine(self.mode)
            # NOTA: NON chiamare OCREngine.clear_cache() qui.
            # La cache garantisce risultati deterministici (stessa foto = stesso risultato).

            self.progress.emit("Preprocessing e analisi in corso...", 10)

            # process_photos() esegue:
            # 1. Boundary detection + validazione (margin=5, conf>=0.5)
            # 2. Perspective correction warp_to_a4()
            # 3. Preprocessing completo (white balance, shadow removal, denoise, CLAHE)
            # 4. SIFT+ECC alignment al template (TemplateAligner)
            # 5. Cell extraction con auto-centering (ref_img dalla reference)
            # 6. Classificazione con il modello scelto (SVM/YOLO/Ensemble)
            # 7. Baseline fallback: recupera items missing/ambiguous/multiple_marks
            #    usando pixel-counting sulla differenza foto-reference
            report = engine.process_photos(
                self.photo_paths,
                session_id="desktop_scan",
                debug=False
            )

            self.progress.emit("Analisi completata!", 100)
            self.finished.emit(report)

        except Exception as e:
            import traceback
            tb = traceback.format_exc()[:800]
            self.error.emit(f"{type(e).__name__}: {e}\n\n{tb}")
