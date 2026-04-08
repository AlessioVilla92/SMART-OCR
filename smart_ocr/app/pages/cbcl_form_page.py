"""Pagina CBCL Form — Replica digitale interattiva del questionario."""

import json
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea,
    QGridLayout, QPushButton, QFrame
)
from PySide6.QtCore import Signal, Qt

from app.widgets.cbcl_item_widget import CBCLItemWidget


QUESTIONS_PATH = Path(__file__).parent.parent.parent / "resources" / "cbcl_questions_it.json"


class CBCLFormPage(QWidget):
    """Griglia CBCL a 2 colonne con tutti i 122 items."""

    values_updated = Signal()  # emesso quando l'utente modifica un valore

    def __init__(self, parent=None):
        super().__init__(parent)
        self._item_widgets = {}  # item_id -> CBCLItemWidget
        self._questions = self._load_questions()
        self._setup_ui()

    def _load_questions(self) -> dict:
        if QUESTIONS_PATH.exists():
            with open(QUESTIONS_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Header con contatori
        header = QHBoxLayout()
        self.title_label = QLabel("CBCL 6-18 — Questionario")
        self.title_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #F1F5F9;")
        header.addWidget(self.title_label)
        header.addStretch()

        self.stats_label = QLabel("Items: 0/0 | Score: 0")
        self.stats_label.setStyleSheet("font-size: 12px; color: #94A3B8;")
        header.addWidget(self.stats_label)
        layout.addLayout(header)

        # Scroll area con griglia
        scroll = QScrollArea()
        scroll.setObjectName("cbcl_scroll")
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        scroll_content = QWidget()
        self.grid = QGridLayout(scroll_content)
        self.grid.setSpacing(4)
        self.grid.setContentsMargins(8, 8, 8, 8)

        # Crea widgets per tutti gli items
        all_items = []
        for page_key in ["page_4", "page_5", "page_6"]:
            page_qs = self._questions.get(page_key, {})
            for item_id, text in page_qs.items():
                all_items.append((item_id, text))

        # Layout a 2 colonne
        mid = (len(all_items) + 1) // 2
        for i, (item_id, text) in enumerate(all_items):
            widget = CBCLItemWidget(item_id, text)
            widget.value_changed.connect(self._on_item_changed)
            self._item_widgets[item_id] = widget

            if i < mid:
                self.grid.addWidget(widget, i, 0)
            else:
                self.grid.addWidget(widget, i - mid, 1)

        scroll.setWidget(scroll_content)
        layout.addWidget(scroll, 1)

    def apply_results(self, report: dict):
        """Applica i risultati del modello a tutti gli item widgets."""
        items = report.get("items", {})
        for item_id, widget in self._item_widgets.items():
            item_data = items.get(item_id, {})
            value = item_data.get("value")
            confidence = item_data.get("confidence", 0.0)
            flag = item_data.get("flag")

            if flag != "not_processed":
                widget.set_result(value, confidence, flag)

        self._update_stats()

    def _on_item_changed(self, item_id: str, new_value: int):
        self._update_stats()
        self.values_updated.emit()

    def _update_stats(self):
        total = len(self._item_widgets)
        completed = sum(1 for w in self._item_widgets.values() if w.get_value() is not None)
        score = sum(w.get_value() for w in self._item_widgets.values() if w.get_value() is not None)
        self.stats_label.setText(f"Items: {completed}/{total} | Score: {score}")

    def get_all_values(self) -> dict:
        """Ritorna tutti i valori correnti {item_id: value}."""
        return {
            item_id: widget.get_value()
            for item_id, widget in self._item_widgets.items()
        }

    def get_report_items(self) -> dict:
        """Ritorna items nel formato report per scoring."""
        result = {}
        for item_id, widget in self._item_widgets.items():
            val = widget.get_value()
            result[item_id] = {
                "value": val,
                "confidence": widget._confidence,
                "flag": None if val is not None else "missing"
            }
        return result
