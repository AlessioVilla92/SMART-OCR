"""
Pagina Impostazioni — Soglie editabili per modello e stato.

Tutte le soglie sono organizzate per:
- Modello (SVM / YOLO / Ensemble): soglie classificazione e confidence
- Stati questionario (Verde/Giallo/Azzurro/Rosso): soglie colorazione UI
- Pipeline globale: boundary detection, baseline fallback, ecc.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGroupBox, QFormLayout,
    QDoubleSpinBox, QSlider, QPushButton, QFrame, QScrollArea, QTabWidget
)
from PySide6.QtCore import Qt, Signal


class NoWheelDoubleSpinBox(QDoubleSpinBox):
    """SpinBox che ignora la rotella del mouse (solo input manuale)."""
    def wheelEvent(self, event):
        event.ignore()


class NoWheelSlider(QSlider):
    """Slider che ignora la rotella del mouse (solo trascinamento)."""
    def wheelEvent(self, event):
        event.ignore()
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config import Config


class ThresholdSlider(QWidget):
    """Slider + spinbox sincronizzati con label colorata e descrizione."""

    value_changed = Signal(float)

    def __init__(self, label: str, default: float, min_val: float = 0.0,
                 max_val: float = 1.0, step: float = 0.01,
                 color: str = "#9B7FFF", description: str = "",
                 decimals: int = 3, parent=None):
        super().__init__(parent)
        self._default = default
        self._color = color
        self._setup_ui(label, default, min_val, max_val, step, color, description, decimals)

    def _setup_ui(self, label, default, min_val, max_val, step, color, description, decimals):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 8)
        layout.setSpacing(4)

        # Header: pallino colorato + label + valore
        header = QHBoxLayout()
        header.setSpacing(8)

        # Pallino colorato (indicatore visivo)
        dot = QLabel("●")
        dot.setStyleSheet(f"color: {color}; font-size: 14px;")
        dot.setFixedWidth(16)
        header.addWidget(dot)

        lbl = QLabel(label)
        lbl.setStyleSheet(f"color: {color}; font-weight: 700; font-size: 12px;")
        header.addWidget(lbl)
        header.addStretch()

        self.spinbox = NoWheelDoubleSpinBox()
        self.spinbox.setRange(min_val, max_val)
        self.spinbox.setSingleStep(step)
        self.spinbox.setDecimals(decimals)
        self.spinbox.setValue(default)
        self.spinbox.setFixedWidth(95)
        self.spinbox.setStyleSheet(
            f"QDoubleSpinBox {{ background: #1A1F2E; border: 1px solid {color}; "
            f"border-radius: 6px; padding: 4px 8px; color: #E8ECF4; "
            f"font-weight: 700; font-size: 11px; }}"
        )
        header.addWidget(self.spinbox)
        layout.addLayout(header)

        # Slider
        self.slider = NoWheelSlider(Qt.Horizontal)
        self.slider.setRange(int(min_val * 1000), int(max_val * 1000))
        self.slider.setValue(int(default * 1000))
        self.slider.setStyleSheet(f"""
            QSlider::groove:horizontal {{
                border: none; height: 6px;
                background: #1A1F2E; border-radius: 3px;
            }}
            QSlider::handle:horizontal {{
                background: {color}; border: 2px solid {color};
                width: 14px; height: 14px; margin: -5px 0;
                border-radius: 8px;
            }}
            QSlider::sub-page:horizontal {{
                background: {color}; border-radius: 3px;
            }}
        """)
        layout.addWidget(self.slider)

        # Descrizione
        if description:
            desc = QLabel(description)
            desc.setStyleSheet("color: #7B8794; font-size: 10px; font-style: italic; padding-left: 24px;")
            desc.setWordWrap(True)
            layout.addWidget(desc)

        # Sync slider <-> spinbox
        self.slider.valueChanged.connect(lambda v: self.spinbox.setValue(v / 1000))
        self.spinbox.valueChanged.connect(
            lambda v: (self.slider.setValue(int(v * 1000)), self.value_changed.emit(v))
        )

    def value(self) -> float:
        return self.spinbox.value()

    def set_value(self, v: float):
        self.spinbox.setValue(v)

    def reset(self):
        self.set_value(self._default)


def _model_panel(model_name: str, accent: str, defaults: dict) -> tuple:
    """
    Crea un pannello con tutte le soglie per un modello.
    Returns: (widget_panel, dict_di_slider)
    """
    panel = QWidget()
    layout = QVBoxLayout(panel)
    layout.setContentsMargins(16, 16, 16, 16)
    layout.setSpacing(4)

    # Header modello
    header = QLabel(f"{model_name}")
    header.setStyleSheet(
        f"font-size: 16px; font-weight: 800; color: {accent}; "
        f"padding-bottom: 8px; border-bottom: 2px solid {accent};"
    )
    layout.addWidget(header)
    layout.addSpacing(8)

    sliders = {}

    # === SOGLIE CLASSIFICAZIONE ===
    cls_lbl = QLabel("CLASSIFICAZIONE CELLA")
    cls_lbl.setStyleSheet("color: #4A5568; font-size: 9px; font-weight: 700; letter-spacing: 1px;")
    layout.addWidget(cls_lbl)

    sliders['confidence_min'] = ThresholdSlider(
        "Confidence minima per riconoscere mark",
        default=defaults.get('confidence_min', 0.65),
        min_val=0.0, max_val=1.0, step=0.05, decimals=2,
        color="#9B7FFF",
        description="Sotto questa confidence, il mark NON viene riconosciuto e si attiva il baseline fallback."
    )
    layout.addWidget(sliders['confidence_min'])

    sliders['delta_min'] = ThresholdSlider(
        "Delta pixel minimo per cella marcata",
        default=defaults.get('delta_min', 0.035),
        min_val=0.0, max_val=0.20, step=0.005, decimals=3,
        color="#9B7FFF",
        description="Differenza minima di pixel scuri rispetto alla reference per considerare la cella marcata."
    )
    layout.addWidget(sliders['delta_min'])

    layout.addSpacing(12)

    # === STATI WIDGET (colori) ===
    states_lbl = QLabel("STATI DOMANDA (COLORI)")
    states_lbl.setStyleSheet("color: #4A5568; font-size: 9px; font-weight: 700; letter-spacing: 1px;")
    layout.addWidget(states_lbl)

    sliders['green_threshold'] = ThresholdSlider(
        "VERDE — Risposta certa",
        default=defaults.get('green_threshold', 0.85),
        min_val=0.5, max_val=1.0, step=0.01, decimals=2,
        color="#34D399",
        description="Sopra questa confidence: domanda VERDE (risposta letta correttamente)."
    )
    layout.addWidget(sliders['green_threshold'])

    sliders['blank_threshold'] = ThresholdSlider(
        "AZZURRO — Domanda non compilata",
        default=defaults.get('blank_threshold', 0.025),
        min_val=0.005, max_val=0.10, step=0.001, decimals=3,
        color="#38BDF8",
        description="Se delta max < soglia: domanda AZZURRA (nessun mark trovato sulle 3 celle)."
    )
    layout.addWidget(sliders['blank_threshold'])

    sliders['error_threshold'] = ThresholdSlider(
        "ROSSO — Soglia errore modello",
        default=defaults.get('error_threshold', 0.30),
        min_val=0.0, max_val=0.6, step=0.05, decimals=2,
        color="#F87171",
        description="Sotto questa confidence: domanda ROSSA (errore, modello non sa decidere)."
    )
    layout.addWidget(sliders['error_threshold'])

    sliders['multiple_min_cells'] = ThresholdSlider(
        "GIALLO — Min celle marcate per 'più segni'",
        default=defaults.get('multiple_min_cells', 2.0),
        min_val=2.0, max_val=3.0, step=1.0, decimals=0,
        color="#FBBF24",
        description="Numero minimo di celle marcate per attivare lo stato GIALLO 'più segni' (correzioni paziente)."
    )
    layout.addWidget(sliders['multiple_min_cells'])

    layout.addStretch()
    return panel, sliders


class SettingsPage(QWidget):
    """
    Pagina impostazioni con soglie editabili per ogni modello e stato.
    Organizzata in tab: SVM / YOLO / Ensemble / Pipeline.
    """

    settings_changed = Signal(dict)  # emesso quando l'utente applica modifiche

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; background: #0B0F19; }")

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        # === TITOLO ===
        title = QLabel("Impostazioni Avanzate")
        title.setStyleSheet("font-size: 22px; font-weight: 800; color: #E8ECF4;")
        layout.addWidget(title)

        subtitle = QLabel(
            "Personalizza le soglie di classificazione per ogni modello e stato delle domande.\n"
            "I colori indicano lo stato del questionario: verde=corretto, giallo=verifica, azzurro=vuoto, rosso=errore."
        )
        subtitle.setStyleSheet("color: #7B8794; font-size: 11px;")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        # === STATO MODELLI ===
        models_group = QGroupBox("Stato Modelli")
        models_layout = QFormLayout(models_group)

        svm_status = "Disponibile" if Config.svm_model_available() else "Non trovato"
        svm_color = "#34D399" if Config.svm_model_available() else "#F87171"
        svm_label = QLabel(svm_status)
        svm_label.setStyleSheet(f"color: {svm_color}; font-weight: 700;")
        models_layout.addRow("SVM (Mode A):", svm_label)

        yolo_status = "Disponibile" if Config.yolo_model_available() else "Non trovato"
        yolo_color = "#34D399" if Config.yolo_model_available() else "#F87171"
        yolo_label = QLabel(yolo_status)
        yolo_label.setStyleSheet(f"color: {yolo_color}; font-weight: 700;")
        models_layout.addRow("YOLO ONNX (Mode B):", yolo_label)

        layout.addWidget(models_group)

        # === TAB PER MODELLO ===
        tabs = QTabWidget()
        tabs.setStyleSheet("""
            QTabWidget::pane {
                background: #141922;
                border: 1px solid #1E2433;
                border-radius: 12px;
                padding: 8px;
            }
            QTabBar::tab {
                background: #1A1F2E;
                color: #7B8794;
                padding: 10px 20px;
                margin-right: 4px;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                font-weight: 600;
                font-size: 12px;
            }
            QTabBar::tab:selected {
                background: #141922;
                color: #9B7FFF;
                border-top: 2px solid #9B7FFF;
            }
        """)

        # Default per ogni modello
        svm_defaults = {
            'confidence_min': Config.SVM_CONFIDENCE_THRESHOLD,
            'delta_min': 0.035,
            'green_threshold': 0.85,
            'blank_threshold': 0.025,
            'error_threshold': 0.30,
            'multiple_min_cells': 2.0,
        }
        yolo_defaults = {
            'confidence_min': Config.YOLO_CONFIDENCE_THRESHOLD,
            'delta_min': 0.035,
            'green_threshold': 0.85,
            'blank_threshold': 0.025,
            'error_threshold': 0.30,
            'multiple_min_cells': 2.0,
        }
        ensemble_defaults = {
            'confidence_min': 0.60,
            'delta_min': 0.035,
            'green_threshold': 0.85,
            'blank_threshold': 0.025,
            'error_threshold': 0.30,
            'multiple_min_cells': 2.0,
        }

        svm_panel, self.svm_sliders = _model_panel("Mode A — SVM (HOG + classico)", "#818CF8", svm_defaults)
        yolo_panel, self.yolo_sliders = _model_panel("Mode B — YOLO (AI)", "#A78BFA", yolo_defaults)
        ens_panel, self.ens_sliders = _model_panel("Mode C — Ensemble (SVM + YOLO)", "#C084FC", ensemble_defaults)

        tabs.addTab(svm_panel, "  SVM  ")
        tabs.addTab(yolo_panel, "  YOLO  ")
        tabs.addTab(ens_panel, "  Ensemble  ")

        layout.addWidget(tabs)

        # === PIPELINE GLOBALE ===
        pipeline_group = QGroupBox("Pipeline Globale (tutti i modelli)")
        pl = QVBoxLayout(pipeline_group)
        pl.setSpacing(4)

        self.boundary_threshold = ThresholdSlider(
            "Boundary detection — Confidence minima",
            default=0.50,
            min_val=0.0, max_val=1.0, step=0.05, decimals=2,
            color="#FBBF24",
            description="Confidence minima per accettare il rilevamento dei bordi del documento."
        )
        pl.addWidget(self.boundary_threshold)

        self.pdf_empty = ThresholdSlider(
            "PDF Mode — Soglia cella vuota",
            default=Config.PDF_EMPTY_THRESHOLD,
            min_val=0.0, max_val=0.5, step=0.01, decimals=2,
            color="#60A5FA",
            description="Solo per Mode D PDF: rapporto pixel scuri sotto cui la cella è considerata vuota."
        )
        pl.addWidget(self.pdf_empty)

        layout.addWidget(pipeline_group)

        # === BOTTONI ===
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)

        self.reset_btn = QPushButton("RESET TO DEFAULT")
        self.reset_btn.setFixedHeight(44)
        self.reset_btn.setMinimumWidth(200)
        self.reset_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #FBBF24;
                border: 1.5px solid #FBBF24;
                border-radius: 10px;
                padding: 10px 24px;
                font-size: 12px;
                font-weight: 800;
                letter-spacing: 1px;
            }
            QPushButton:hover {
                background: rgba(251,191,36,0.10);
                color: #FCD34D;
                border-color: #FCD34D;
            }
            QPushButton:pressed {
                background: rgba(251,191,36,0.20);
            }
        """)
        self.reset_btn.clicked.connect(self._reset_defaults)
        btn_row.addWidget(self.reset_btn)

        btn_row.addStretch()

        self.apply_btn = QPushButton("APPLICA MODIFICHE")
        self.apply_btn.setObjectName("analyze_btn")
        self.apply_btn.setFixedSize(220, 44)
        self.apply_btn.clicked.connect(self._apply_settings)
        btn_row.addWidget(self.apply_btn)

        layout.addLayout(btn_row)
        layout.addSpacing(8)

        scroll.setWidget(content)
        outer.addWidget(scroll)

    def _reset_defaults(self):
        """Ripristina valori di default per tutti i modelli."""
        for sliders in [self.svm_sliders, self.yolo_sliders, self.ens_sliders]:
            for s in sliders.values():
                s.reset()
        self.boundary_threshold.reset()
        self.pdf_empty.reset()

    def get_settings(self) -> dict:
        """Restituisce tutte le soglie correnti come dict."""
        return {
            "svm": {k: s.value() for k, s in self.svm_sliders.items()},
            "yolo": {k: s.value() for k, s in self.yolo_sliders.items()},
            "ensemble": {k: s.value() for k, s in self.ens_sliders.items()},
            "pipeline": {
                "boundary_threshold": self.boundary_threshold.value(),
                "pdf_empty": self.pdf_empty.value(),
            }
        }

    def _apply_settings(self):
        """Applica le nuove soglie e notifica."""
        from PySide6.QtWidgets import QMessageBox
        settings = self.get_settings()
        self.settings_changed.emit(settings)
        QMessageBox.information(
            self, "Impostazioni Applicate",
            "Le nuove soglie sono state salvate.\n"
            "Verranno utilizzate al prossimo upload."
        )
