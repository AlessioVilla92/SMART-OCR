"""Pagina Home — Upload foto e avvio analisi."""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QComboBox, QProgressBar, QGroupBox, QGridLayout
)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QPixmap
from pathlib import Path


class HomePage(QWidget):
    """Pagina caricamento foto e analisi."""

    analysis_requested = Signal(dict)  # {page: path}
    reset_requested = Signal()         # emesso quando l'utente vuole azzerare il progetto

    def __init__(self, parent=None):
        super().__init__(parent)
        self._photo_paths = {}
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        # Titolo
        title = QLabel("Carica le foto del questionario CBCL")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #F1F5F9;")
        layout.addWidget(title)

        # Griglia upload 3 pagine
        upload_group = QGroupBox("Foto questionario (3 pagine)")
        upload_group.setStyleSheet("QGroupBox { font-size: 13px; font-weight: bold; }")
        upload_grid = QGridLayout(upload_group)

        self._page_labels = {}
        self._page_previews = {}
        self._page_paths = {}

        pages = [
            ("page_4", "Pagina 4 (items 1-54)"),
            ("page_5", "Pagina 5 (items 55-85)"),
            ("page_6", "Pagina 6 (items 86-112, 113a-c)"),
        ]

        for col, (page_key, page_desc) in enumerate(pages):
            # Label
            lbl = QLabel(page_desc)
            lbl.setStyleSheet("font-size: 11px; color: #94A3B8;")
            upload_grid.addWidget(lbl, 0, col)

            # Preview
            preview = QLabel("Nessuna foto")
            preview.setFixedSize(200, 280)
            preview.setAlignment(Qt.AlignCenter)
            preview.setStyleSheet(
                "background: #1E293B; border: 2px dashed #334155; "
                "border-radius: 8px; color: #64748B; font-size: 11px;"
            )
            self._page_previews[page_key] = preview
            upload_grid.addWidget(preview, 1, col)

            # Button
            btn = QPushButton(f"Carica {page_key[-1]}")
            btn.setStyleSheet("padding: 8px 16px;")
            btn.clicked.connect(lambda checked, pk=page_key: self._load_photo(pk))
            upload_grid.addWidget(btn, 2, col)

            # Status
            status = QLabel("")
            status.setStyleSheet("font-size: 10px; color: #4ade80;")
            self._page_labels[page_key] = status
            upload_grid.addWidget(status, 3, col)

        layout.addWidget(upload_group)

        # Barra inferiore: opzioni + pulsante analizza
        bottom = QHBoxLayout()

        # Selezione modello
        model_group = QGroupBox("Modello")
        model_layout = QVBoxLayout(model_group)
        self.mode_combo = QComboBox()
        self.mode_combo.addItems([
            "A - SVM (classico)",
            "B - YOLO (AI)",
            "C - Ensemble (massima accuratezza)",
        ])
        self.mode_combo.setCurrentIndex(2)
        model_layout.addWidget(self.mode_combo)
        bottom.addWidget(model_group)

        bottom.addStretch()

        # Progress
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedWidth(300)
        self.progress_bar.setVisible(False)
        bottom.addWidget(self.progress_bar)

        self.progress_label = QLabel("")
        self.progress_label.setStyleSheet("color: #94A3B8; font-size: 11px;")
        bottom.addWidget(self.progress_label)

        bottom.addStretch()

        # Pulsante RESET (azzera tutto)
        self.reset_btn = QPushButton("RESET")
        self.reset_btn.setFixedSize(120, 50)
        self.reset_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #F87171;
                border: 1.5px solid #F87171;
                border-radius: 10px;
                padding: 10px 18px;
                font-size: 13px;
                font-weight: 800;
                letter-spacing: 1px;
            }
            QPushButton:hover {
                background: rgba(248,113,113,0.10);
                color: #FCA5A5;
                border-color: #FCA5A5;
            }
            QPushButton:pressed {
                background: rgba(248,113,113,0.20);
            }
        """)
        self.reset_btn.clicked.connect(self._reset_project)
        bottom.addWidget(self.reset_btn)

        # Pulsante analizza
        self.analyze_btn = QPushButton("ANALIZZA")
        self.analyze_btn.setObjectName("analyze_btn")
        self.analyze_btn.setFixedSize(200, 50)
        self.analyze_btn.clicked.connect(self._start_analysis)
        self.analyze_btn.setEnabled(False)
        bottom.addWidget(self.analyze_btn)

        layout.addLayout(bottom)
        layout.addStretch()

    def _load_photo(self, page_key: str):
        path, _ = QFileDialog.getOpenFileName(
            self, f"Seleziona foto {page_key}",
            "", "Immagini (*.jpg *.jpeg *.png *.bmp)"
        )
        if not path:
            return

        # Validazione: file esistente, non vuoto, leggibile come immagine
        from PySide6.QtWidgets import QMessageBox
        try:
            file_path = Path(path)
            if not file_path.exists() or file_path.stat().st_size == 0:
                raise ValueError("File vuoto o inesistente")
            pixmap = QPixmap(path)
            if pixmap.isNull():
                raise ValueError("Formato immagine non valido o file corrotto")
        except Exception as e:
            QMessageBox.warning(
                self, "Errore caricamento",
                f"Impossibile caricare l'immagine:\n{e}"
            )
            return

        self._photo_paths[page_key] = path
        scaled = pixmap.scaled(200, 280, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self._page_previews[page_key].setPixmap(scaled)
        self._page_labels[page_key].setText(Path(path).name)

        # Richiede TUTTE e 3 le foto per l'analisi (questionario completo)
        self.analyze_btn.setEnabled(len(self._photo_paths) == 3)

    def _start_analysis(self):
        if not self._photo_paths:
            return
        self.analysis_requested.emit(dict(self._photo_paths))

    def set_photos_from_paths(self, photo_paths: dict):
        """
        Carica foto da paths (es. da un progetto .cbcl caricato).
        Aggiorna preview e stato interno senza passare dal file dialog.
        """
        self._photo_paths.clear()
        for page_key, path in photo_paths.items():
            file_path = Path(path)
            if not file_path.exists():
                continue
            pixmap = QPixmap(path)
            if pixmap.isNull():
                continue

            self._photo_paths[page_key] = path
            scaled = pixmap.scaled(200, 280, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            if page_key in self._page_previews:
                self._page_previews[page_key].setPixmap(scaled)
                self._page_labels[page_key].setText(file_path.name)

        self.analyze_btn.setEnabled(len(self._photo_paths) == 3)

    def get_photo_paths(self) -> dict:
        """Ritorna le foto correnti {page_key: path}."""
        return dict(self._photo_paths)

    def _reset_project(self):
        """Azzera foto, preview e stato per ricominciare un nuovo progetto."""
        from PySide6.QtWidgets import QMessageBox
        # Se ci sono foto caricate, chiedi conferma
        if self._photo_paths:
            reply = QMessageBox.question(
                self, "Nuovo progetto",
                "Vuoi cancellare tutte le foto e ricominciare un nuovo progetto?\n\n"
                "I risultati correnti verranno persi.",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                return

        # Pulisci stato interno
        self._photo_paths.clear()

        # Pulisci preview
        for page_key, preview in self._page_previews.items():
            preview.clear()
            preview.setText("Nessuna foto")
            preview.setStyleSheet(
                "background: #1E293B; border: 2px dashed #334155; "
                "border-radius: 8px; color: #64748B; font-size: 11px;"
            )

        # Pulisci label status
        for lbl in self._page_labels.values():
            lbl.setText("")

        # Disabilita pulsante analizza
        self.analyze_btn.setEnabled(False)

        # Nascondi progress bar
        self.progress_bar.setVisible(False)
        self.progress_bar.setValue(0)
        self.progress_label.setText("")

        # Notifica la main window per resettare anche questionario e risultati
        self.reset_requested.emit()

    def get_selected_mode(self) -> str:
        idx = self.mode_combo.currentIndex()
        return ["svm", "yolo", "ensemble"][idx]

    def set_progress(self, text: str, value: int):
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(value)
        self.progress_label.setText(text)

    def analysis_complete(self):
        self.progress_bar.setVisible(False)
        self.progress_label.setText("Analisi completata!")
