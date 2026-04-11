"""
Pagina CBCL Form — Replica digitale interattiva del questionario.

Layout 2 colonne (stessa struttura del questionario cartaceo) con:
- Sticky header con stats live (items completati, score, da verificare)
- Filtri rapidi per stato (tutti / da verificare / verdi / gialli / azzurri / rossi)
- Quick-jump per pagina (page_4 / page_5 / page_6)
- Section headers per separare visivamente le 3 pagine
- Spaziatura ergonomica + tipografia accessibile
"""

import json
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea,
    QGridLayout, QPushButton, QFrame, QButtonGroup
)
from PySide6.QtCore import Signal, Qt

from app.widgets.cbcl_item_widget import CBCLItemWidget, COLORS


QUESTIONS_PATH = Path(__file__).parent.parent.parent / "resources" / "cbcl_questions_it.json"


class CBCLFormPage(QWidget):
    """Griglia CBCL a 2 colonne con tutti i 122 items."""

    values_updated = Signal()  # emesso quando l'utente modifica un valore

    def __init__(self, parent=None):
        super().__init__(parent)
        self._item_widgets = {}              # item_id -> CBCLItemWidget
        self._current_filter = "all"
        self._questions = self._load_questions()
        self._setup_ui()

    def _load_questions(self) -> dict:
        if not QUESTIONS_PATH.exists():
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(
                self, "Errore Configurazione",
                f"File domande CBCL non trovato:\n{QUESTIONS_PATH}\n\n"
                "L'applicazione non può funzionare senza questo file."
            )
            return {}
        try:
            with open(QUESTIONS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict) or not data:
                raise ValueError("File domande vuoto o malformato")
            return data
        except (json.JSONDecodeError, ValueError) as e:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(
                self, "Errore Configurazione",
                f"Impossibile leggere {QUESTIONS_PATH.name}:\n{e}"
            )
            return {}

    # ────────────────────────────────────────────────────────────────────
    # SETUP UI
    # ────────────────────────────────────────────────────────────────────

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # === STICKY HEADER ===
        layout.addWidget(self._build_sticky_header())

        # === FILTRI E QUICK JUMP ===
        layout.addWidget(self._build_filter_bar())

        # === SCROLL AREA CON DOMANDE ===
        self.scroll = QScrollArea()
        self.scroll.setObjectName("cbcl_scroll")
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet("QScrollArea { border: none; background: #0B0F19; }")

        self._scroll_content = QWidget()
        self.grid = QGridLayout(self._scroll_content)
        self.grid.setSpacing(10)
        self.grid.setContentsMargins(20, 16, 20, 24)

        self._build_questionnaire_grid()

        self.scroll.setWidget(self._scroll_content)
        layout.addWidget(self.scroll, 1)

    def _build_sticky_header(self) -> QWidget:
        """Header sempre visibile con titolo + stats colorate live."""
        header = QFrame()
        header.setStyleSheet(
            "background: #101420; border-bottom: 1px solid #1E2433;"
        )
        h = QHBoxLayout(header)
        h.setContentsMargins(24, 14, 24, 14)
        h.setSpacing(20)

        # Titolo
        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        title = QLabel("CBCL 6-18")
        title.setStyleSheet("font-size: 18px; font-weight: 800; color: #E8ECF4;")
        title_box.addWidget(title)
        subtitle = QLabel("Verifica e modifica le risposte")
        subtitle.setStyleSheet("font-size: 11px; color: #7B8794;")
        title_box.addWidget(subtitle)
        h.addLayout(title_box)

        h.addStretch()

        # Stats colorate (5 contatori)
        self._stat_widgets = {}
        stats_def = [
            ("score",    "Score",       "#E8ECF4"),
            ("total",    "Items",       "#E8ECF4"),
            ("green",    "Verdi",       COLORS["confident"]),
            ("yellow",   "Gialli",      COLORS["multiple"]),
            ("blue",     "Azzurri",     COLORS["blank"]),
            ("red",      "Rossi",       COLORS["error"]),
        ]
        for key, label, color in stats_def:
            stat = self._build_stat_pill(label, "0", color)
            self._stat_widgets[key] = stat
            h.addWidget(stat["container"])

        return header

    def _build_stat_pill(self, label: str, value: str, color: str) -> dict:
        """Pillola compatta con label + valore colorato."""
        container = QFrame()
        container.setStyleSheet(
            f"background: #1A1F2E; border: 1px solid #2A3040; border-radius: 10px;"
        )
        v = QVBoxLayout(container)
        v.setContentsMargins(14, 6, 14, 6)
        v.setSpacing(0)

        val_lbl = QLabel(value)
        val_lbl.setAlignment(Qt.AlignCenter)
        val_lbl.setStyleSheet(f"font-size: 18px; font-weight: 800; color: {color};")
        v.addWidget(val_lbl)

        name_lbl = QLabel(label.upper())
        name_lbl.setAlignment(Qt.AlignCenter)
        name_lbl.setStyleSheet("font-size: 9px; color: #7B8794; font-weight: 700; letter-spacing: 1px;")
        v.addWidget(name_lbl)

        return {"container": container, "value": val_lbl}

    def _build_filter_bar(self) -> QWidget:
        """Barra con filtri rapidi e quick-jump alle pagine."""
        bar = QFrame()
        bar.setStyleSheet("background: #0F141F; border-bottom: 1px solid #1E2433;")
        h = QHBoxLayout(bar)
        h.setContentsMargins(24, 10, 24, 10)
        h.setSpacing(8)

        # Label filtro
        filter_lbl = QLabel("MOSTRA:")
        filter_lbl.setStyleSheet("font-size: 10px; color: #4A5568; font-weight: 700; letter-spacing: 1px;")
        h.addWidget(filter_lbl)

        # Filtri stato
        self._filter_group = QButtonGroup(self)
        self._filter_group.setExclusive(True)
        filters = [
            ("all",       "Tutti",        "#9B7FFF"),
            ("review",    "Da verificare", "#FBBF24"),
            ("confident", "Verdi",        COLORS["confident"]),
            ("multiple",  "Gialli",       COLORS["multiple"]),
            ("blank",     "Azzurri",      COLORS["blank"]),
            ("error",     "Rossi",        COLORS["error"]),
        ]
        for i, (key, label, color) in enumerate(filters):
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setProperty("filter_key", key)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    color: #7B8794;
                    border: 1px solid #2A3040;
                    border-radius: 14px;
                    padding: 6px 14px;
                    font-size: 11px;
                    font-weight: 600;
                }}
                QPushButton:hover {{
                    color: {color};
                    border-color: {color};
                }}
                QPushButton:checked {{
                    background: {color}26;
                    color: {color};
                    border: 1.5px solid {color};
                    font-weight: 700;
                }}
            """)
            if i == 0:
                btn.setChecked(True)
            self._filter_group.addButton(btn, i)
            btn.clicked.connect(lambda _checked=False, k=key: self._apply_filter(k))
            h.addWidget(btn)

        h.addStretch()
        return bar

    def _build_questionnaire_grid(self):
        """Crea i widget item in 2 colonne, senza separazioni per pagina."""
        # Raccogli TUTTI gli items in un unico flusso
        all_items = []
        for page_key in ["page_4", "page_5", "page_6"]:
            page_qs = self._questions.get(page_key, {})
            for item_id, text in page_qs.items():
                all_items.append((item_id, text))

        # Layout 2 colonne: prima metà a sinistra, seconda metà a destra
        mid = (len(all_items) + 1) // 2
        for i, (item_id, text) in enumerate(all_items):
            widget = CBCLItemWidget(item_id, text)
            widget.value_changed.connect(self._on_item_changed)
            self._item_widgets[item_id] = widget

            if i < mid:
                self.grid.addWidget(widget, i, 0)
            else:
                self.grid.addWidget(widget, i - mid, 1)

    # ────────────────────────────────────────────────────────────────────
    # FILTRI E NAVIGAZIONE
    # ────────────────────────────────────────────────────────────────────

    def _apply_filter(self, filter_key: str):
        """Mostra/nasconde gli item in base al filtro."""
        self._current_filter = filter_key
        for item_id, widget in self._item_widgets.items():
            state = widget.get_state()
            if filter_key == "all":
                visible = True
            elif filter_key == "review":
                # Da verificare = giallo + azzurro + rosso
                visible = state in ("multiple", "blank", "error")
            else:
                visible = (state == filter_key)
            widget.setVisible(visible)

    # ────────────────────────────────────────────────────────────────────
    # APPLICA RISULTATI E STATS
    # ────────────────────────────────────────────────────────────────────

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
        """Aggiorna i contatori dell'header sticky."""
        total = len(self._item_widgets)
        completed = sum(1 for w in self._item_widgets.values() if w.get_value() is not None)
        score = sum(w.get_value() for w in self._item_widgets.values() if w.get_value() is not None)

        green = sum(1 for w in self._item_widgets.values() if w.get_state() == "confident")
        yellow = sum(1 for w in self._item_widgets.values() if w.get_state() == "multiple")
        blue = sum(1 for w in self._item_widgets.values() if w.get_state() == "blank")
        red = sum(1 for w in self._item_widgets.values() if w.get_state() == "error")

        self._stat_widgets["score"]["value"].setText(str(score))
        self._stat_widgets["total"]["value"].setText(f"{completed}/{total}")
        self._stat_widgets["green"]["value"].setText(str(green))
        self._stat_widgets["yellow"]["value"].setText(str(yellow))
        self._stat_widgets["blue"]["value"].setText(str(blue))
        self._stat_widgets["red"]["value"].setText(str(red))

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
