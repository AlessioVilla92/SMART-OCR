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
        subtitle.setStyleSheet("font-size: 11px; color: #A0A8B4; font-weight: 500;")
        title_box.addWidget(subtitle)
        h.addLayout(title_box)

        h.addStretch()

        # Stats colorate: score + completati% + 4 stati + verificati + da verificare
        self._stat_widgets = {}
        stats_def = [
            ("score",        "Score",         "#E8ECF4"),
            ("total",        "Items",         "#E8ECF4"),
            ("percent",      "Completati",    "#9B7FFF"),
            ("green",        "Verdi",         COLORS["confident"]),
            ("yellow",       "Gialli",        COLORS["multiple"]),
            ("blue",         "Azzurri",       COLORS["blank"]),
            ("red",          "Rossi",         COLORS["error"]),
            ("to_review",    "Da verificare", "#FBBF24"),
            ("verified",     "Verificati",    COLORS["manual"]),
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
        name_lbl.setStyleSheet("font-size: 9px; color: #A0A8B4; font-weight: 800; letter-spacing: 1px;")
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
        filter_lbl.setStyleSheet("font-size: 10px; color: #8B95A7; font-weight: 800; letter-spacing: 1px;")
        h.addWidget(filter_lbl)

        # Filtri stato
        self._filter_group = QButtonGroup(self)
        self._filter_group.setExclusive(True)
        filters = [
            ("all",       "Tutti",         "#9B7FFF"),
            ("review",    "Da verificare", "#FBBF24"),
            ("verified",  "Verificati",    COLORS["manual"]),
            ("confident", "Verdi",         COLORS["confident"]),
            ("multiple",  "Gialli",        COLORS["multiple"]),
            ("blank",     "Azzurri",       COLORS["blank"]),
            ("error",     "Rossi",         COLORS["error"]),
        ]
        for i, (key, label, color) in enumerate(filters):
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setProperty("filter_key", key)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    color: #A0A8B4;
                    border: 1px solid #343B4D;
                    border-radius: 14px;
                    padding: 6px 14px;
                    font-size: 11px;
                    font-weight: 700;
                }}
                QPushButton:hover {{
                    color: {color};
                    border-color: {color};
                    background: {color}14;
                }}
                QPushButton:checked {{
                    background: {color}30;
                    color: {color};
                    border: 1.5px solid {color};
                    font-weight: 800;
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
        # Item 113 unificato: mostriamo 113a come "113" (unico attivo);
        # 113b/113c restano presenti ma disattivati (sempre 0) per non alterare
        # la griglia OMR ne' il modello YOLO.
        mid = (len(all_items) + 1) // 2
        for i, (item_id, text) in enumerate(all_items):
            if item_id == "113a":
                widget = CBCLItemWidget(item_id, text, display_id="113")
            elif item_id in ("113b", "113c"):
                widget = CBCLItemWidget(item_id, text, disabled=True)
            else:
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
                # Da verificare = giallo + azzurro + rosso (NON i già verificati manualmente)
                visible = state in ("multiple", "blank", "error")
            elif filter_key == "verified":
                # Verificati = solo quelli modificati manualmente dall'utente
                visible = (state == "manual")
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
        """
        Chiamato quando l'utente clicca un radio button.
        Aggiorna stats + riapplica filtro corrente per nascondere
        automaticamente l'item verificato dalla lista "Da verificare".
        """
        self._update_stats()
        # Riapplica filtro: l'item ora è in stato "manual", quindi se il filtro
        # è "review" sparisce dalla lista, se è "verified" appare.
        self._apply_filter(self._current_filter)
        self.values_updated.emit()

    def _update_stats(self):
        """Aggiorna TUTTI i contatori dell'header sticky in tempo reale."""
        widgets = list(self._item_widgets.values())
        total = len(widgets)

        # Conta per stato
        green = yellow = blue = red = manual = 0
        for w in widgets:
            st = w.get_state()
            if st == "confident":
                green += 1
            elif st == "multiple":
                yellow += 1
            elif st == "blank":
                blue += 1
            elif st == "error":
                red += 1
            elif st == "manual":
                manual += 1

        # Items con valore assegnato (include verdi + gialli + manual)
        completed = sum(1 for w in widgets if w.get_value() is not None)

        # Score totale (somma di TUTTI i valori: include anche quelli modificati)
        score = sum(w.get_value() for w in widgets if w.get_value() is not None)

        # Da verificare = giallo + azzurro + rosso (non-verificati)
        to_review = yellow + blue + red

        # Percentuale completamento
        percent = int((completed / total) * 100) if total > 0 else 0

        # Aggiorna tutti i widget
        self._stat_widgets["score"]["value"].setText(str(score))
        self._stat_widgets["total"]["value"].setText(f"{completed}/{total}")
        self._stat_widgets["percent"]["value"].setText(f"{percent}%")
        self._stat_widgets["green"]["value"].setText(str(green))
        self._stat_widgets["yellow"]["value"].setText(str(yellow))
        self._stat_widgets["blue"]["value"].setText(str(blue))
        self._stat_widgets["red"]["value"].setText(str(red))
        self._stat_widgets["to_review"]["value"].setText(str(to_review))
        self._stat_widgets["verified"]["value"].setText(str(manual))

    def get_form_values_for_save(self) -> dict:
        """
        Ritorna tutti i valori del form per salvataggio progetto.
        Include: valore, confidence, flag, stato UI.
        """
        result = {}
        for item_id, widget in self._item_widgets.items():
            result[item_id] = {
                "value": widget.get_value(),
                "confidence": widget._confidence,
                "state": widget.get_state(),
            }
        return result

    def load_form_values(self, form_values: dict):
        """
        Carica i valori del form da un progetto salvato.
        Ripristina valore, confidence e stato UI (incluso 'manual').
        """
        from app.widgets.cbcl_item_widget import COLORS
        for item_id, widget in self._item_widgets.items():
            data = form_values.get(item_id, {})
            value = data.get("value")
            confidence = data.get("confidence", 0.0)
            state = data.get("state", "pending")

            widget._value = value
            widget._confidence = confidence
            widget._state = state

            # Ripristina radio button
            widget.button_group.blockSignals(True)
            for btn in widget.buttons.values():
                btn.setChecked(False)
            if value is not None and value in widget.buttons:
                widget.buttons[value].setChecked(True)
            for btn in widget.buttons.values():
                btn.setEnabled(True)
            widget.button_group.blockSignals(False)

            # Ripristina stile in base allo stato
            if state == "confident":
                widget._apply_state(COLORS["confident"], f"OK {confidence:.0%}")
            elif state == "multiple":
                widget._apply_state(COLORS["multiple"], "PIU' SEGNI")
            elif state == "blank":
                widget._apply_state(COLORS["blank"], "NON COMPILATA")
            elif state == "error":
                widget._apply_state(COLORS["error"], "ERRORE")
            elif state == "manual":
                widget._apply_state(COLORS["manual"], "MODIFICATA")
            else:
                widget._apply_state(COLORS["neutral"], "")

        self._update_stats()
        self._apply_filter(self._current_filter)

    def reset(self):
        """Azzera tutti gli item widgets allo stato iniziale (pending/neutral)."""
        from app.widgets.cbcl_item_widget import COLORS
        for widget in self._item_widgets.values():
            widget._value = None
            widget._confidence = 0.0
            widget._state = "pending"
            widget.button_group.blockSignals(True)
            for btn in widget.buttons.values():
                btn.setChecked(False)
                btn.setEnabled(True)
            widget.button_group.blockSignals(False)
            widget._apply_state(COLORS["neutral"], "")

        # Reset filtro a "Tutti"
        self._current_filter = "all"
        for btn in self._filter_group.buttons():
            btn.setChecked(self._filter_group.id(btn) == 0)
        self._apply_filter("all")
        self._update_stats()

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
