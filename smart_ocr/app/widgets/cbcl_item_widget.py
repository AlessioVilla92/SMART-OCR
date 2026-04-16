"""
Widget singolo item CBCL — design ergonomico ad alta leggibilità.

Migliorie ergonomiche basate su best practice UI mediche:
- Tipografia: testo 14px, numero 16px bold (sopra minimo WCAG)
- Spaziatura: padding 16px, line-height 1.4
- Altezza dinamica (no fixed height) → no troncamenti
- Background uniforme #141922 (no più "macchie" semi-trasparenti)
- Striscia laterale colorata 4px per identificare lo stato (verde/giallo/azzurro/rosso)
- Numero in pillola colorata per ancoraggio visivo
- Sempre editabile (anche stati verdi)
"""

from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel,
    QRadioButton, QButtonGroup, QSizePolicy
)
from PySide6.QtCore import Signal, Qt


# Colori stati (centralizzati per coerenza)
COLORS = {
    "confident": "#34D399",   # verde
    "multiple":  "#FBBF24",   # giallo
    "blank":     "#38BDF8",   # azzurro
    "error":     "#F87171",   # rosso
    "manual":    "#60A5FA",   # blu (modifica utente)
    "neutral":   "#7B8794",   # grigio (non processato)
}


class CBCLItemWidget(QFrame):

    value_changed = Signal(str, int)

    def __init__(self, item_id: str, question_text: str, parent=None,
                 *, display_id: str = None, disabled: bool = False):
        super().__init__(parent)
        self.item_id = item_id
        self.question_text = question_text
        self._display_id = display_id or item_id
        self._disabled = disabled
        self._value = None
        self._confidence = 0.0
        self._state = "pending"
        self._setup_ui()
        if self._disabled:
            # Item permanentemente disabilitato: valore forzato a 0, non modificabile.
            self._value = 0
            self.buttons[0].setChecked(True)
            for btn in self.buttons.values():
                btn.setEnabled(False)
            self.text_label.setStyleSheet(
                "font-size: 14px; color: #6B7280; line-height: 140%; font-style: italic;"
            )
            self._apply_state(COLORS["neutral"], "DISATTIVATA")
        else:
            # Stato iniziale neutro
            self._apply_state(COLORS["neutral"], "")

    def _setup_ui(self):
        # Layout principale orizzontale: striscia colorata + contenuto
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # === STRISCIA LATERALE COLORATA (4px) ===
        self.side_strip = QFrame()
        self.side_strip.setFixedWidth(4)
        self.side_strip.setStyleSheet(f"background: {COLORS['neutral']}; border-top-left-radius: 10px; border-bottom-left-radius: 10px;")
        root.addWidget(self.side_strip)

        # === CONTENUTO ===
        content = QFrame()
        content.setObjectName("itemContent")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(16, 12, 16, 12)
        content_layout.setSpacing(8)

        # Riga 1: pillola numero + testo + badge stato
        header = QHBoxLayout()
        header.setSpacing(12)

        # Numero in pillola colorata (display_id per override visuale; item_id resta l'ID logico)
        self.num_label = QLabel(self._display_id)
        self.num_label.setMinimumWidth(40)
        self.num_label.setAlignment(Qt.AlignCenter)
        self.num_label.setStyleSheet(self._num_pill_style(COLORS["neutral"]))
        header.addWidget(self.num_label)

        # Testo domanda (font grande, line-height generoso)
        self.text_label = QLabel(self.question_text)
        self.text_label.setWordWrap(True)
        self.text_label.setStyleSheet(
            "font-size: 14px; color: #E8ECF4; line-height: 140%;"
        )
        self.text_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        header.addWidget(self.text_label, 1)

        # Badge stato in alto a destra
        self.badge = QLabel("")
        self.badge.setMinimumWidth(110)
        self.badge.setFixedHeight(26)
        self.badge.setAlignment(Qt.AlignCenter)
        header.addWidget(self.badge, 0, Qt.AlignTop)

        content_layout.addLayout(header)

        # Riga 2: 3 radio buttons più grandi e leggibili
        choices = QHBoxLayout()
        choices.setSpacing(28)
        choices.setContentsMargins(52, 4, 0, 0)  # indent allineato sotto al testo

        self.button_group = QButtonGroup(self)
        self.buttons = {}

        labels = [
            ("0", "Non vero"),
            ("1", "A volte"),
            ("2", "Molto vero"),
        ]
        for val, (num, txt) in enumerate(labels):
            btn = QRadioButton(f"{num}  {txt}")
            btn.setStyleSheet(
                "QRadioButton { font-size: 13px; color: #A0A8B4; spacing: 8px; padding: 4px 0; }"
                "QRadioButton:checked { color: #E8ECF4; font-weight: 700; }"
                "QRadioButton::indicator { width: 18px; height: 18px; }"
                "QRadioButton::indicator:unchecked { "
                "  border: 2px solid #4A5568; border-radius: 11px; background: #1A1F2E; }"
                "QRadioButton::indicator:hover { border-color: #9B7FFF; }"
                "QRadioButton::indicator:checked { "
                "  border: 2px solid #9B7FFF; border-radius: 11px; "
                "  background: qradialgradient(cx:0.5, cy:0.5, radius:0.5, "
                "  stop:0 #9B7FFF, stop:0.4 #9B7FFF, stop:0.5 #1A1F2E, stop:1 #1A1F2E); }"
            )
            self.button_group.addButton(btn, val)
            self.buttons[val] = btn
            choices.addWidget(btn)

        choices.addStretch()
        content_layout.addLayout(choices)

        self.button_group.idClicked.connect(self._on_value_changed)

        root.addWidget(content, 1)

        # Stile base — niente macchie, sfondo uniforme scuro, hover sottile
        self.setStyleSheet("""
            CBCLItemWidget {
                background: #141922;
                border: 1px solid #1E2433;
                border-radius: 10px;
            }
            CBCLItemWidget:hover {
                background: #181E2A;
                border: 1px solid #2A3040;
            }
        """)
        # Altezza dinamica (no fixed) → adatta a testi lunghi
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.setMinimumHeight(96)

    @staticmethod
    def _num_pill_style(color: str) -> str:
        """Stile pillola numero domanda."""
        return (
            f"background: {color}1A; "  # 1A = 10% alpha hex
            f"color: {color}; "
            f"font-weight: 800; font-size: 15px; "
            f"border: 1.5px solid {color}; "
            f"border-radius: 10px; "
            f"padding: 4px 8px;"
        )

    @staticmethod
    def _badge_style(color: str) -> str:
        """Stile badge stato."""
        return (
            f"background: {color}26; "  # 26 = 15% alpha hex
            f"color: {color}; "
            f"font-size: 10px; font-weight: 800; "
            f"border-radius: 13px; padding: 4px 12px; "
            f"letter-spacing: 0.5px;"
        )

    def _apply_state(self, color: str, badge_text: str):
        """Applica colore stato a striscia laterale + numero + badge."""
        self.side_strip.setStyleSheet(
            f"background: {color}; "
            f"border-top-left-radius: 10px; border-bottom-left-radius: 10px;"
        )
        self.num_label.setStyleSheet(self._num_pill_style(color))
        if badge_text:
            self.badge.setText(badge_text)
            self.badge.setStyleSheet(self._badge_style(color))
        else:
            self.badge.setText("")
            self.badge.setStyleSheet("")

    def set_result(self, value, confidence, flag):
        """Determina lo stato del widget dai risultati del modello."""
        if self._disabled:
            # Item disattivato: il modello non puo' alterarne lo stato.
            return
        self._value = value
        self._confidence = confidence

        if value is None and flag == "missing":
            self._state = "blank"
            self._set_blank()
        elif flag == "multiple_marks":
            self._state = "multiple"
            self._set_multiple(value)
        elif value is None:
            self._state = "error"
            self._set_error()
        else:
            self._state = "confident"
            self._set_confident(value)

    def _set_confident(self, value):
        """VERDE: risposta letta correttamente. Sempre editabile."""
        if value is not None:
            self.buttons[value].setChecked(True)
        for btn in self.buttons.values():
            btn.setEnabled(True)
        self._apply_state(COLORS["confident"], f"OK {self._confidence:.0%}")

    def _set_multiple(self, value):
        """GIALLO: più segni trovati."""
        if value is not None:
            self.buttons[value].setChecked(True)
        for btn in self.buttons.values():
            btn.setEnabled(True)
        self._apply_state(COLORS["multiple"], "PIU' SEGNI")

    def _set_blank(self):
        """AZZURRO: nessun segno trovato — domanda non compilata."""
        for btn in self.buttons.values():
            btn.setChecked(False)
            btn.setEnabled(True)
        self._apply_state(COLORS["blank"], "NON COMPILATA")

    def _set_error(self):
        """ROSSO: il modello non è riuscito a dare un risultato."""
        for btn in self.buttons.values():
            btn.setChecked(False)
            btn.setEnabled(True)
        self._apply_state(COLORS["error"], "ERRORE")

    def _on_value_changed(self, id):
        """Quando l'utente cambia manualmente il valore."""
        self._value = id
        self.value_changed.emit(self.item_id, id)
        self._apply_state(COLORS["manual"], "MODIFICATA")

    def get_value(self):
        return self._value

    def get_state(self) -> str:
        """Stato corrente: confident/multiple/blank/error/manual/pending."""
        return self._state
