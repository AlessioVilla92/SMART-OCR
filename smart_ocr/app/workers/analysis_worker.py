"""
Worker thread per l'analisi OMR non-blocking.
Usa OCREngine con pipeline completa (boundary + SIFT + auto-centering + baseline fallback).
"""

from PySide6.QtCore import QThread, Signal
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from pipeline.engine import OCREngine
from config import ClassificationMode


class AnalysisWorker(QThread):
    """Thread separato per processing OCR completo."""

    progress = Signal(str, int)       # (fase_nome, percentuale)
    page_done = Signal(str, dict)     # (page_key, page_report)
    finished = Signal(dict)           # report combinato finale
    error = Signal(str)               # messaggio errore

    def __init__(self, photo_paths: dict, mode: ClassificationMode):
        """
        Args:
            photo_paths: {page_key: file_path} es. {"page_4": "foto1.jpg", ...}
            mode: ClassificationMode da usare
        """
        super().__init__()
        self.photo_paths = photo_paths
        self.mode = mode

    def run(self):
        try:
            engine = OCREngine(self.mode)
            OCREngine.clear_cache()

            total_pages = len(self.photo_paths)
            all_classification = {}
            total_time = 0

            for i, (page_key, photo_path) in enumerate(self.photo_paths.items()):
                pct_base = int(i / total_pages * 100)

                self.progress.emit(f"{page_key}: rilevamento bordi...", pct_base + 5)

                report = engine.process_page(
                    photo_path,
                    page=page_key,
                    debug=False,
                    session_id="desktop_scan"
                )

                self.progress.emit(f"{page_key}: completato", pct_base + int(100 / total_pages))
                self.page_done.emit(page_key, report)

                # Accumula items
                for item_id, item_data in report["items"].items():
                    if item_data.get("value") is not None or item_data.get("flag") != "not_processed":
                        all_classification[item_id] = item_data

                total_time += report.get("_processing_time_ms", 0)

            # Report combinato finale
            from core.scorer import build_score_report
            combined = build_score_report(all_classification, session_id="desktop_scan")
            combined["_processing_time_ms"] = total_time
            combined["_method"] = engine.get_active_method()
            combined["_mode_requested"] = self.mode.value

            self.progress.emit("Analisi completata!", 100)
            self.finished.emit(combined)

        except Exception as e:
            import traceback
            self.error.emit(f"{e}\n\n{traceback.format_exc()}")
