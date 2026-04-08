"""Pagina Impostazioni — Soglie, modelli, info sistema."""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QGroupBox, QFormLayout
)
from PySide6.QtCore import Qt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config import Config


class SettingsPage(QWidget):
    """Mostra stato sistema e impostazioni."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        title = QLabel("Impostazioni")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #F1F5F9;")
        layout.addWidget(title)

        # Stato modelli
        models_group = QGroupBox("Stato Modelli")
        models_layout = QFormLayout(models_group)

        svm_status = "Disponibile" if Config.svm_model_available() else "Non trovato"
        svm_color = "#4ade80" if Config.svm_model_available() else "#f87171"
        svm_label = QLabel(svm_status)
        svm_label.setStyleSheet(f"color: {svm_color}; font-weight: bold;")
        models_layout.addRow("SVM (Mode A):", svm_label)

        yolo_status = "Disponibile" if Config.yolo_model_available() else "Non trovato"
        yolo_color = "#4ade80" if Config.yolo_model_available() else "#f87171"
        yolo_label = QLabel(yolo_status)
        yolo_label.setStyleSheet(f"color: {yolo_color}; font-weight: bold;")
        models_layout.addRow("YOLO ONNX (Mode B):", yolo_label)

        layout.addWidget(models_group)

        # Soglie
        thresh_group = QGroupBox("Soglie Classificazione")
        thresh_layout = QFormLayout(thresh_group)
        thresh_layout.addRow("SVM confidence:", QLabel(str(Config.SVM_CONFIDENCE_THRESHOLD)))
        thresh_layout.addRow("YOLO confidence:", QLabel(str(Config.YOLO_CONFIDENCE_THRESHOLD)))
        thresh_layout.addRow("PDF empty:", QLabel(str(Config.PDF_EMPTY_THRESHOLD)))
        layout.addWidget(thresh_group)

        # Info
        info_group = QGroupBox("Informazioni")
        info_layout = QFormLayout(info_group)
        info_layout.addRow("Versione:", QLabel("Smart OCR v3.0"))
        info_layout.addRow("Cell size:", QLabel(f"{Config.CELL_SIZE[0]}x{Config.CELL_SIZE[1]}"))
        info_layout.addRow("HOG bins:", QLabel(str(Config.HOG_NBINS)))
        layout.addWidget(info_group)

        layout.addStretch()
