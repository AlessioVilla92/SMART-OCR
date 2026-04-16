"""Pagina Home — Upload foto o PDF (con drag & drop) e avvio analisi."""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QComboBox, QProgressBar, QGroupBox, QGridLayout,
    QSpinBox
)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QPixmap, QDragEnterEvent, QDropEvent
from pathlib import Path

_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".webp"}
_PDF_EXTENSIONS = {".pdf"}

_DROP_IDLE_STYLE = (
    "background: #1E293B; border: 2px dashed #334155; "
    "border-radius: 8px; color: #64748B; font-size: 11px;"
)
_DROP_HOVER_STYLE = (
    "background: rgba(124,92,252,0.12); border: 2px dashed #7C5CFC; "
    "border-radius: 8px; color: #C8B5FF; font-size: 11px;"
)


class _DropZone(QLabel):
    """Area di preview che accetta drag & drop di un'immagine."""

    file_dropped = Signal(str)   # emette il path del file droppato

    def __init__(self, parent=None):
        super().__init__("Trascina foto qui\no clicca Carica", parent)
        self.setFixedSize(200, 280)
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet(_DROP_IDLE_STYLE)
        self.setAcceptDrops(True)

    # ── drag enter ──
    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if urls and Path(urls[0].toLocalFile()).suffix.lower() in _IMAGE_EXTENSIONS:
                event.acceptProposedAction()
                self.setStyleSheet(_DROP_HOVER_STYLE)
                return
        event.ignore()

    def dragLeaveEvent(self, event):
        self.setStyleSheet(_DROP_IDLE_STYLE)

    # ── drop ──
    def dropEvent(self, event: QDropEvent):
        self.setStyleSheet(_DROP_IDLE_STYLE)
        urls = event.mimeData().urls()
        if not urls:
            return
        path = urls[0].toLocalFile()
        if Path(path).suffix.lower() in _IMAGE_EXTENSIONS:
            event.acceptProposedAction()
            self.file_dropped.emit(path)


class _PdfDropZone(QLabel):
    """Area di drop dedicata ai file PDF."""

    file_dropped = Signal(str)

    def __init__(self, parent=None):
        super().__init__("Trascina PDF qui\no clicca\nCARICA PDF", parent)
        self.setFixedSize(200, 280)
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet(
            "background: #1E293B; border: 2px dashed #7C5CFC; "
            "border-radius: 8px; color: #9B7FFF; font-size: 11px; font-weight: bold;"
        )
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if urls and Path(urls[0].toLocalFile()).suffix.lower() in _PDF_EXTENSIONS:
                event.acceptProposedAction()
                self.setStyleSheet(
                    "background: rgba(124,92,252,0.18); border: 2px dashed #A78BFA; "
                    "border-radius: 8px; color: #C8B5FF; font-size: 11px; font-weight: bold;"
                )
                return
        event.ignore()

    def dragLeaveEvent(self, event):
        self.setStyleSheet(
            "background: #1E293B; border: 2px dashed #7C5CFC; "
            "border-radius: 8px; color: #9B7FFF; font-size: 11px; font-weight: bold;"
        )

    def dropEvent(self, event: QDropEvent):
        self.setStyleSheet(
            "background: #1E293B; border: 2px dashed #7C5CFC; "
            "border-radius: 8px; color: #9B7FFF; font-size: 11px; font-weight: bold;"
        )
        urls = event.mimeData().urls()
        if not urls:
            return
        path = urls[0].toLocalFile()
        if Path(path).suffix.lower() in _PDF_EXTENSIONS:
            event.acceptProposedAction()
            self.file_dropped.emit(path)


class HomePage(QWidget):
    """Pagina caricamento foto/PDF e analisi."""

    analysis_requested = Signal(dict)  # {page: path}
    reset_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._photo_paths = {}
        self.setAcceptDrops(True)
        self._setup_ui()

    # ── drag & drop sulla pagina intera (immagini + PDF) ──
    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                ext = Path(url.toLocalFile()).suffix.lower()
                if ext in _IMAGE_EXTENSIONS or ext in _PDF_EXTENSIONS:
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dropEvent(self, event: QDropEvent):
        urls = event.mimeData().urls()
        if not urls:
            return
        first = urls[0].toLocalFile()
        if Path(first).suffix.lower() in _PDF_EXTENSIONS:
            event.acceptProposedAction()
            self._open_pdf(first)
            return
        page_order = ["page_4", "page_5", "page_6"]
        free = [p for p in page_order if p not in self._photo_paths]
        for url in urls:
            path = url.toLocalFile()
            if Path(path).suffix.lower() not in _IMAGE_EXTENSIONS:
                continue
            if not free:
                break
            self._apply_photo(free.pop(0), path)
        event.acceptProposedAction()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        # Titolo
        title = QLabel("Carica le foto del questionario CBCL")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #F1F5F9;")
        layout.addWidget(title)

        # Griglia upload: col 0 = PDF, col 1-3 = foto singole, col separatore
        upload_group = QGroupBox("Foto questionario (3 pagine)")
        upload_group.setStyleSheet("QGroupBox { font-size: 13px; font-weight: bold; }")
        upload_grid = QGridLayout(upload_group)
        upload_grid.setSpacing(12)

        # ── COLONNA 0: PDF ──
        pdf_label = QLabel("Scansione PDF")
        pdf_label.setStyleSheet("font-size: 11px; color: #A78BFA; font-weight: bold;")
        pdf_label.setAlignment(Qt.AlignCenter)
        upload_grid.addWidget(pdf_label, 0, 0)

        self._pdf_preview = _PdfDropZone()
        self._pdf_preview.file_dropped.connect(self._open_pdf)
        upload_grid.addWidget(self._pdf_preview, 1, 0)

        pdf_btn = QPushButton("CARICA PDF")
        pdf_btn.setStyleSheet(
            "QPushButton { padding: 8px 16px; background: #7C5CFC; color: white; "
            "border-radius: 6px; font-weight: bold; }"
            "QPushButton:hover { background: #9B7FFF; }"
        )
        pdf_btn.clicked.connect(self._load_pdf)
        upload_grid.addWidget(pdf_btn, 2, 0)

        self._pdf_status = QLabel("")
        self._pdf_status.setStyleSheet("font-size: 10px; color: #A78BFA;")
        self._pdf_status.setAlignment(Qt.AlignCenter)
        upload_grid.addWidget(self._pdf_status, 3, 0)

        # ── Separatore "oppure" ──
        sep_label = QLabel("oppure")
        sep_label.setAlignment(Qt.AlignCenter)
        sep_label.setStyleSheet(
            "font-size: 10px; color: #4A5568; font-style: italic; padding: 0 8px;"
        )
        upload_grid.addWidget(sep_label, 1, 1, Qt.AlignCenter)

        # ── COLONNE 2-4: foto singole ──
        self._page_labels = {}
        self._page_previews = {}
        self._page_paths = {}

        pages = [
            ("page_4", "Pagina 4 (items 1-54)"),
            ("page_5", "Pagina 5 (items 55-85)"),
            ("page_6", "Pagina 6 (items 86-113)"),
        ]

        for i, (page_key, page_desc) in enumerate(pages):
            col = i + 2

            lbl = QLabel(page_desc)
            lbl.setStyleSheet("font-size: 11px; color: #94A3B8;")
            upload_grid.addWidget(lbl, 0, col)

            preview = _DropZone()
            preview.file_dropped.connect(lambda path, pk=page_key: self._apply_photo(pk, path))
            self._page_previews[page_key] = preview
            upload_grid.addWidget(preview, 1, col)

            btn = QPushButton(f"Carica {page_key[-1]}")
            btn.setStyleSheet("padding: 8px 16px;")
            btn.clicked.connect(lambda checked, pk=page_key: self._load_photo(pk))
            upload_grid.addWidget(btn, 2, col)

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

        # Compilatore (Madre / Padre)
        comp_group = QGroupBox("Compilatore")
        comp_layout = QVBoxLayout(comp_group)
        self.combo_compilatore = QComboBox()
        self.combo_compilatore.addItems(["Madre (MD)", "Padre (PD)"])
        comp_layout.addWidget(self.combo_compilatore)
        bottom.addWidget(comp_group)

        # Sesso
        sex_group = QGroupBox("Sesso")
        sex_layout = QVBoxLayout(sex_group)
        self.combo_sex = QComboBox()
        self.combo_sex.addItems(["M", "F"])
        sex_layout.addWidget(self.combo_sex)
        bottom.addWidget(sex_group)

        # Età
        age_group = QGroupBox("Età")
        age_layout = QVBoxLayout(age_group)
        self.spin_age = QSpinBox()
        self.spin_age.setRange(6, 18)
        self.spin_age.setValue(10)
        self.spin_age.setSuffix(" anni")
        age_layout.addWidget(self.spin_age)
        bottom.addWidget(age_group)

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

    def _load_pdf(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Seleziona scansione PDF",
            "", "PDF (*.pdf)"
        )
        if path:
            self._open_pdf(path)

    def _open_pdf(self, pdf_path: str):
        from app.widgets.pdf_page_assigner import PdfPageAssigner
        dialog = PdfPageAssigner(pdf_path, parent=self)
        if dialog.exec() == PdfPageAssigner.Accepted:
            image_paths = dialog.get_image_paths()
            for page_key, img_path in image_paths.items():
                self._apply_photo(page_key, img_path)
            self._pdf_status.setText(Path(pdf_path).name)
            self._pdf_preview.setText("PDF caricato")

    def _load_photo(self, page_key: str):
        path, _ = QFileDialog.getOpenFileName(
            self, f"Seleziona foto {page_key}",
            "", "Immagini (*.jpg *.jpeg *.png *.bmp *.tiff *.webp)"
        )
        if path:
            self._apply_photo(page_key, path)

    def _apply_photo(self, page_key: str, path: str):
        """Valida e applica una foto (da file dialog o drag & drop)."""
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

        # Pulisci preview foto
        for page_key, preview in self._page_previews.items():
            preview.clear()
            preview.setText("Trascina foto qui\no clicca Carica")
            preview.setStyleSheet(_DROP_IDLE_STYLE)

        # Pulisci preview PDF
        self._pdf_preview.clear()
        self._pdf_preview.setText("Trascina PDF qui\no clicca\nCARICA PDF")
        self._pdf_preview.setStyleSheet(
            "background: #1E293B; border: 2px dashed #7C5CFC; "
            "border-radius: 8px; color: #9B7FFF; font-size: 11px; font-weight: bold;"
        )
        self._pdf_status.setText("")

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

    def get_compilatore_index(self) -> int:
        """0 = Madre, 1 = Padre."""
        return self.combo_compilatore.currentIndex()

    def get_child_sex(self) -> str:
        return self.combo_sex.currentText()

    def get_child_age(self) -> int:
        return self.spin_age.value()

    def set_compilatore_index(self, idx: int):
        self.combo_compilatore.setCurrentIndex(idx)

    def set_child_sex(self, sex: str):
        self.combo_sex.setCurrentIndex(0 if sex == "M" else 1)

    def set_child_age(self, age: int):
        if 6 <= age <= 18:
            self.spin_age.setValue(age)

    def set_progress(self, text: str, value: int):
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(value)
        self.progress_label.setText(text)

    def analysis_complete(self):
        self.progress_bar.setVisible(False)
        self.progress_label.setText("Analisi completata!")
