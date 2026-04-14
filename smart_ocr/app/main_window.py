"""
MainWindow — Sidebar moderna + Stacked Pages + Status Bar.

Struttura UI (v4.0):
    ┌──────────────────────────────────────────┐
    │  SIDEBAR         │    CONTENT AREA       │
    │  ────────        │    ────────────       │
    │  Logo            │    [Stack Widget]     │
    │  ───             │      - HomePage       │
    │  [Nuovo]         │      - CBCLFormPage   │
    │  [Apri]          │      - ResultsPage    │
    │  [Salva]         │      - SettingsPage   │
    │  ───             │                       │
    │  NAVIGAZIONE     │                       │
    │  [Upload Foto]   │                       │
    │  [Questionario]  │                       │
    │  [Risultati]     │                       │
    │  [Impostazioni]  │                       │
    │  ───             │                       │
    │  v4.0            │                       │
    │  Powered by...   │                       │
    ├──────────────────┴───────────────────────┤
    │  Status Bar  |  Powered by Tivanio       │
    └──────────────────────────────────────────┘

Shortcuts globali:
    Ctrl+N → Nuovo progetto (reset)
    Ctrl+O → Apri progetto .cbcl
    Ctrl+S → Salva progetto .cbcl
    Ctrl+Shift+S → Salva con nome
"""

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QButtonGroup, QStackedWidget, QLabel, QFrame,
    QFileDialog, QMessageBox
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QKeySequence, QShortcut, QIcon
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import ClassificationMode
from app.pages.home_page import HomePage
from app.pages.cbcl_form_page import CBCLFormPage
from app.pages.results_page import ResultsPage
from app.pages.settings_page import SettingsPage
from app.workers.analysis_worker import AnalysisWorker
from core.project_file import save_project, load_project, PROJECT_EXTENSION
from scorer.cbcl_scorer import Compilatore


class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Smart OCR — CBCL Scanner v4.0")
        self._worker = None
        self._current_report = None
        self._current_project_path = None   # path del progetto corrente (se aperto/salvato)
        self._setup_ui()
        self._setup_shortcuts()

    def _icon(self, name: str) -> QIcon:
        """Carica icona SVG dalle risorse. Ritorna QIcon vuoto se manca."""
        icon_path = Path(__file__).parent.parent / "resources" / "icons" / name
        if icon_path.exists():
            return QIcon(str(icon_path))
        return QIcon()

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
        subtitle.setStyleSheet("font-size: 10px; color: #8B95A7; padding-bottom: 16px;")
        sidebar_layout.addWidget(subtitle)

        # Separatore
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background-color: #1E2433; margin: 0 16px;")
        sidebar_layout.addWidget(sep)

        # === AZIONI PROGETTO (sopra i bottoni di navigazione) ===
        # Spacer sopra i bottoni azione
        sidebar_layout.addSpacing(12)

        # Stile unificato bottoni azione (viola chiaro, icona 18px)
        action_style = """
            QPushButton {
                text-align: left;
                padding: 11px 16px;
                border: none;
                border-radius: 10px;
                color: #C8B5FF;
                font-size: 12px;
                font-weight: 600;
                margin: 1px 8px;
            }
            QPushButton:hover {
                background: rgba(124,92,252,0.14);
                color: #E0D4FF;
            }
            QPushButton:pressed {
                background: rgba(124,92,252,0.24);
            }
        """

        icon_size = QSize(18, 18)

        # Nuovo Progetto
        self.btn_new = QPushButton("  Nuovo Progetto")
        self.btn_new.setIcon(self._icon("action_new.svg"))
        self.btn_new.setIconSize(icon_size)
        self.btn_new.setStyleSheet(action_style)
        self.btn_new.setToolTip("Reset completo per nuovo questionario (Ctrl+N)")
        self.btn_new.clicked.connect(self._reset_all)
        sidebar_layout.addWidget(self.btn_new)

        # Apri Progetto
        self.btn_open = QPushButton("  Apri Progetto")
        self.btn_open.setIcon(self._icon("action_open.svg"))
        self.btn_open.setIconSize(icon_size)
        self.btn_open.setStyleSheet(action_style)
        self.btn_open.setToolTip("Apri un file progetto .cbcl (Ctrl+O)")
        self.btn_open.clicked.connect(self._open_project)
        sidebar_layout.addWidget(self.btn_open)

        # Salva Progetto
        self.btn_save = QPushButton("  Salva Progetto")
        self.btn_save.setIcon(self._icon("action_save.svg"))
        self.btn_save.setIconSize(icon_size)
        self.btn_save.setStyleSheet(action_style)
        self.btn_save.setToolTip("Salva il progetto corrente in file .cbcl (Ctrl+S)")
        self.btn_save.clicked.connect(self._save_project)
        sidebar_layout.addWidget(self.btn_save)

        # Separatore
        sep2 = QFrame()
        sep2.setFixedHeight(1)
        sep2.setStyleSheet("background-color: #262D3E; margin: 14px 16px 4px;")
        sidebar_layout.addWidget(sep2)

        # Label sezione navigazione
        nav_lbl = QLabel("  NAVIGAZIONE")
        nav_lbl.setStyleSheet(
            "color: #8B95A7; font-size: 9px; font-weight: 800; "
            "letter-spacing: 1.5px; padding: 6px 20px;"
        )
        sidebar_layout.addWidget(nav_lbl)

        # === NAV BUTTONS (cambiano pagina) ===
        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        nav_items = [
            ("home",     "  Upload Foto",   "nav_upload2.svg"),
            ("cbcl",     "  Questionario",  "nav_form2.svg"),
            ("results",  "  Risultati",     "nav_results2.svg"),
            ("settings", "  Impostazioni",  "nav_settings2.svg"),
        ]

        for i, (key, label, icon_name) in enumerate(nav_items):
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setObjectName(f"nav_{key}")
            btn.setIcon(self._icon(icon_name))
            btn.setIconSize(icon_size)
            if i == 0:
                btn.setChecked(True)
            self.nav_group.addButton(btn, i)
            sidebar_layout.addWidget(btn)

        sidebar_layout.addStretch()

        # Versione + Powered by (colori più chiari per leggibilità)
        ver = QLabel("v4.0")
        ver.setAlignment(Qt.AlignCenter)
        ver.setStyleSheet("color: #7B8794; font-size: 10px; font-weight: 700;")
        sidebar_layout.addWidget(ver)

        powered = QLabel("Powered by Tivanio")
        powered.setAlignment(Qt.AlignCenter)
        powered.setStyleSheet("color: #8B95A7; font-size: 9px; font-weight: 600; padding-top: 4px;")
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
        self.status_bar.setStyleSheet("color: #A0A8B4; font-size: 11px; font-weight: 500;")
        status_h.addWidget(self.status_bar)
        status_h.addStretch()

        powered_status = QLabel("Powered by Tivanio")
        powered_status.setStyleSheet(
            "color: #8B95A7; font-size: 10px; font-weight: 700; "
            "letter-spacing: 0.5px;"
        )
        status_h.addWidget(powered_status)

        content_layout.addWidget(status_container)

        main_layout.addLayout(content_layout, 1)

        # === CONNECTIONS ===
        self.nav_group.idClicked.connect(self.stack.setCurrentIndex)
        self.home_page.analysis_requested.connect(self._start_analysis)
        self.home_page.reset_requested.connect(self._reset_all)
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

    def _get_compilatore(self) -> Compilatore:
        """Restituisce il compilatore selezionato nella pagina Upload."""
        return Compilatore.MADRE if self.home_page.get_compilatore_index() == 0 else Compilatore.PADRE

    def _get_child_sex(self) -> str:
        return self.home_page.get_child_sex()

    def _get_child_age(self) -> int:
        return self.home_page.get_child_age()

    def _on_analysis_done(self, report: dict):
        # Ricalcola con il compilatore/anagrafica selezionati
        from core.scorer import build_full_profile
        profile = build_full_profile(
            report.get("items", {}),
            compilatore=self._get_compilatore(),
            sex=self._get_child_sex(),
            age=self._get_child_age(),
        )
        report["_profile"] = profile
        report["compilatore"] = self._get_compilatore().value

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
        self.results_page.update_from_form(
            form_items,
            compilatore=self._get_compilatore(),
            sex=self._get_child_sex(),
            age=self._get_child_age(),
        )

    # ────────────────────────────────────────────────────────────────────
    # SHORTCUTS PROGETTO (Ctrl+N / Ctrl+O / Ctrl+S / Ctrl+Shift+S)
    # ────────────────────────────────────────────────────────────────────

    def _setup_shortcuts(self):
        """Shortcut globali per le azioni progetto (senza menu bar)."""
        QShortcut(QKeySequence.New, self, activated=self._reset_all)           # Ctrl+N
        QShortcut(QKeySequence.Open, self, activated=self._open_project)       # Ctrl+O
        QShortcut(QKeySequence.Save, self, activated=self._save_project)       # Ctrl+S
        QShortcut(QKeySequence.SaveAs, self, activated=self._save_project_as)  # Ctrl+Shift+S

    def _open_project(self):
        """Apre un progetto .cbcl esistente."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Apri Progetto",
            "", f"Progetti SmartOCR (*{PROJECT_EXTENSION})"
        )
        if not path:
            return

        try:
            project = load_project(path)
        except (FileNotFoundError, ValueError) as e:
            QMessageBox.warning(self, "Errore apertura", f"Impossibile aprire il progetto:\n{e}")
            return

        # Ripristina compilatore/anagrafica dai metadata
        meta = project.get("metadata", {})
        comp_val = meta.get("compilatore", "MD")
        self.home_page.set_compilatore_index(0 if comp_val == "MD" else 1)
        child_sex = meta.get("child_sex", "M")
        self.home_page.set_child_sex(child_sex)
        child_age = meta.get("child_age", 10)
        if isinstance(child_age, int) and 6 <= child_age <= 18:
            self.home_page.set_child_age(child_age)

        # Reset corrente (senza conferma, l'utente ha già scelto)
        self.cbcl_page.reset()
        self.results_page.reset()

        # Carica foto nella home page
        photo_paths = project.get("photo_paths", {})
        self.home_page.set_photos_from_paths(photo_paths)

        # Carica form values nel questionario
        form_values = project.get("form_values", {})
        if form_values:
            self.cbcl_page.load_form_values(form_values)

        # Carica report nella pagina risultati
        report = project.get("report", {})
        if report:
            self.results_page.update_results(report)
            self._current_report = report

        self._current_project_path = path

        # Vai al questionario se ci sono dati, altrimenti home
        if form_values:
            self.stack.setCurrentIndex(1)
            self.nav_group.button(1).setChecked(True)

        name = Path(path).name
        self.status_bar.setText(f"Progetto aperto: {name}")
        self.setWindowTitle(f"Smart OCR — {name}")

    def _save_project(self):
        """Salva il progetto corrente (usa path esistente se già salvato)."""
        if self._current_project_path:
            self._do_save(self._current_project_path)
        else:
            self._save_project_as()

    def _save_project_as(self):
        """Apre dialog 'Salva con nome' e salva."""
        photo_paths = self.home_page.get_photo_paths()
        if not photo_paths:
            QMessageBox.warning(
                self, "Nessuna foto",
                "Nessuna foto caricata.\nCarica prima le 3 foto del questionario."
            )
            return

        default_name = f"progetto_{self._current_report.get('session_id', 'cbcl')}.cbcl" \
            if self._current_report else "nuovo_progetto.cbcl"

        path, _ = QFileDialog.getSaveFileName(
            self, "Salva Progetto",
            default_name,
            f"Progetti SmartOCR (*{PROJECT_EXTENSION})"
        )
        if not path:
            return

        self._do_save(path)

    def _do_save(self, path: str):
        """Esegue il salvataggio sul path specificato."""
        photo_paths = self.home_page.get_photo_paths()
        form_values = self.cbcl_page.get_form_values_for_save()
        mode = self.home_page.get_selected_mode()

        success = save_project(
            output_path=path,
            photo_paths=photo_paths,
            report=self._current_report or {},
            form_values=form_values,
            mode=mode,
            compilatore=self._get_compilatore().value,
            child_sex=self._get_child_sex(),
            child_age=self._get_child_age(),
        )

        if success:
            # Il path salvato può avere .cbcl aggiunto automaticamente
            saved_path = path if path.lower().endswith(PROJECT_EXTENSION) else path + PROJECT_EXTENSION
            self._current_project_path = saved_path
            name = Path(saved_path).name
            self.status_bar.setText(f"Progetto salvato: {name}")
            self.setWindowTitle(f"Smart OCR — {name}")
            QMessageBox.information(self, "Salvato", f"Progetto salvato:\n{saved_path}")
        else:
            QMessageBox.warning(self, "Errore salvataggio", "Impossibile salvare il progetto.")

    def _reset_all(self):
        """Reset completo del progetto: foto, questionario, risultati, cache."""
        # Cleanup worker se in corso
        if self._worker is not None and self._worker.isRunning():
            self._worker.quit()
            self._worker.wait(2000)

        # Reset pagine
        self.cbcl_page.reset()
        self.results_page.reset()

        # Svuota cache preprocessing (foto nuove = preprocessing fresco)
        from pipeline.engine import OCREngine
        OCREngine.clear_cache()

        # Reset report e path progetto
        self._current_report = None
        self._current_project_path = None

        # Torna alla pagina Upload
        self.stack.setCurrentIndex(0)
        self.nav_group.button(0).setChecked(True)

        self.status_bar.setText("Nuovo progetto: carica le 3 foto del questionario")
        self.setWindowTitle("Smart OCR — CBCL Scanner v4.0")
