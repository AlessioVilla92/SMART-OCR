"""MainWindow — Sidebar moderna + Stacked Pages + Status Bar."""

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QButtonGroup, QStackedWidget, QLabel, QFrame
)
from PySide6.QtCore import Qt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import ClassificationMode
from app.pages.home_page import HomePage
from app.pages.cbcl_form_page import CBCLFormPage
from app.pages.results_page import ResultsPage
from app.pages.settings_page import SettingsPage
from app.workers.analysis_worker import AnalysisWorker


class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Smart OCR — CBCL Scanner v3.0")
        self._worker = None
        self._current_report = None
        self._setup_ui()

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # === SIDEBAR ===
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 16)
        sidebar_layout.setSpacing(2)

        # Logo
        logo = QLabel("SMART OCR")
        logo.setObjectName("sidebar_logo")
        logo.setAlignment(Qt.AlignCenter)
        logo.setStyleSheet(
            "font-size: 18px; font-weight: 800; padding: 24px 0 4px; "
            "color: #9B7FFF; letter-spacing: 2px;"
        )
        sidebar_layout.addWidget(logo)

        subtitle = QLabel("CBCL Scanner")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet("font-size: 10px; color: #4A5568; padding-bottom: 16px;")
        sidebar_layout.addWidget(subtitle)

        # Separatore
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background-color: #1E2433; margin: 0 16px;")
        sidebar_layout.addWidget(sep)

        # Nav buttons con icone
        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        nav_items = [
            ("home",     "  Upload Foto"),
            ("cbcl",     "  Questionario"),
            ("results",  "  Risultati"),
            ("settings", "  Impostazioni"),
        ]

        for i, (key, label) in enumerate(nav_items):
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setObjectName(f"nav_{key}")
            if i == 0:
                btn.setChecked(True)
            self.nav_group.addButton(btn, i)
            sidebar_layout.addWidget(btn)

        sidebar_layout.addStretch()

        # Versione + Powered by
        ver = QLabel("v3.0")
        ver.setAlignment(Qt.AlignCenter)
        ver.setStyleSheet("color: #2A3040; font-size: 10px; font-weight: 600;")
        sidebar_layout.addWidget(ver)

        powered = QLabel("Powered by Tivanio")
        powered.setAlignment(Qt.AlignCenter)
        powered.setStyleSheet("color: #4A5568; font-size: 9px; font-weight: 500; padding-top: 4px;")
        sidebar_layout.addWidget(powered)

        main_layout.addWidget(sidebar)

        # === CONTENT ===
        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        self.stack = QStackedWidget()
        self.home_page = HomePage()
        self.cbcl_page = CBCLFormPage()
        self.results_page = ResultsPage()
        self.settings_page = SettingsPage()

        self.stack.addWidget(self.home_page)
        self.stack.addWidget(self.cbcl_page)
        self.stack.addWidget(self.results_page)
        self.stack.addWidget(self.settings_page)
        content_layout.addWidget(self.stack, 1)

        # Status bar con "Powered by Tivanio" a destra
        status_container = QFrame()
        status_container.setObjectName("status_bar")
        status_h = QHBoxLayout(status_container)
        status_h.setContentsMargins(16, 4, 16, 4)
        status_h.setSpacing(8)

        self.status_bar = QLabel("Pronto")
        self.status_bar.setStyleSheet("color: #7B8794; font-size: 11px;")
        status_h.addWidget(self.status_bar)
        status_h.addStretch()

        powered_status = QLabel("Powered by Tivanio")
        powered_status.setStyleSheet(
            "color: #4A5568; font-size: 10px; font-weight: 600; "
            "letter-spacing: 0.5px;"
        )
        status_h.addWidget(powered_status)

        content_layout.addWidget(status_container)

        main_layout.addLayout(content_layout, 1)

        # === CONNECTIONS ===
        self.nav_group.idClicked.connect(self.stack.setCurrentIndex)
        self.home_page.analysis_requested.connect(self._start_analysis)
        self.cbcl_page.values_updated.connect(self._on_form_updated)

    def _start_analysis(self, photo_paths: dict):
        # Previene race condition: se un worker è già in esecuzione, non avvia un secondo
        if self._worker is not None and self._worker.isRunning():
            return

        mode_str = self.home_page.get_selected_mode()
        mode_map = {
            "svm": ClassificationMode.MODE_A_SVM,
            "yolo": ClassificationMode.MODE_B_YOLO,
            "ensemble": ClassificationMode.MODE_C_ENSEMBLE,
        }
        mode = mode_map.get(mode_str, ClassificationMode.MODE_C_ENSEMBLE)

        self.status_bar.setText(f"Analisi in corso ({mode_str.upper()})...")
        self.home_page.analyze_btn.setEnabled(False)

        # Cleanup vecchio worker se esiste
        if self._worker is not None:
            self._worker.deleteLater()

        self._worker = AnalysisWorker(photo_paths, mode)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_analysis_done)
        self._worker.error.connect(self._on_analysis_error)
        # Cleanup automatico alla fine
        self._worker.finished.connect(self._worker.deleteLater)
        self._worker.start()

    def closeEvent(self, event):
        """Cleanup worker thread alla chiusura della finestra."""
        if self._worker is not None and self._worker.isRunning():
            self._worker.quit()
            if not self._worker.wait(3000):  # Aspetta max 3 sec
                self._worker.terminate()
                self._worker.wait()
        event.accept()

    def _on_progress(self, text: str, pct: int):
        self.home_page.set_progress(text, pct)
        self.status_bar.setText(f"  {text}")

    def _on_analysis_done(self, report: dict):
        self._current_report = report
        self.cbcl_page.apply_results(report)
        self.results_page.update_results(report)

        stats = report.get("statistics", {})
        method = report.get("_method", "?")
        time_ms = report.get("_processing_time_ms", 0)
        self.status_bar.setText(
            f"  Completato  |  {method.upper()}  |  "
            f"{stats.get('items_scored', 0)}/{stats.get('items_total', 0)} items  |  "
            f"Score: {report.get('total_score', 0)}  |  {time_ms}ms"
        )

        self.home_page.analysis_complete()
        self.home_page.analyze_btn.setEnabled(True)

        # Vai al form CBCL
        self.stack.setCurrentIndex(1)
        self.nav_group.button(1).setChecked(True)

    def _on_analysis_error(self, msg: str):
        self.status_bar.setText("Errore durante l'analisi")
        self.home_page.analyze_btn.setEnabled(True)
        self.home_page.analysis_complete()
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.critical(self, "Errore Analisi", msg)

    def _on_form_updated(self):
        form_items = self.cbcl_page.get_report_items()
        self.results_page.update_from_form(form_items)
