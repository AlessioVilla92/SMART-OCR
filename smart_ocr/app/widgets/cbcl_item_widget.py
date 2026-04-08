"""Widget singolo item CBCL — design moderno glassmorphism."""

from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel,
    QRadioButton, QButtonGroup
)
from PySide6.QtCore import Signal, Qt


class CBCLItemWidget(QFrame):

    value_changed = Signal(str, int)

    def __init__(self, item_id: str, question_text: str, parent=None):
        super().__init__(parent)
        self.item_id = item_id
        self.question_text = question_text
        self._value = None
        self._confidence = 0.0
        self._state = "pending"
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(3)

        # Riga 1: numero + testo
        header = QHBoxLayout()
        self.num_label = QLabel(f"{self.item_id}.")
        self.num_label.setFixedWidth(38)
        self.num_label.setStyleSheet(
            "font-weight: 800; font-size: 13px; color: #7B8794;")

        self.text_label = QLabel(self.question_text)
        self.text_label.setWordWrap(True)
        self.text_label.setStyleSheet("font-size: 11px; color: #C8CED6;")

        header.addWidget(self.num_label)
        header.addWidget(self.text_label, 1)
        layout.addLayout(header)

        # Riga 2: radio 0, 1, 2 + badge
        choices = QHBoxLayout()
        choices.setSpacing(16)
        self.button_group = QButtonGroup(self)
        self.buttons = {}

        labels = ["0 - Non vero", "1 - A volte", "2 - Molto vero"]
        for val, lbl in enumerate(labels):
            btn = QRadioButton(lbl)
            btn.setStyleSheet(
                "QRadioButton { font-size: 11px; color: #A0A8B4; spacing: 6px; }"
                "QRadioButton:checked { color: #E8ECF4; font-weight: 600; }"
            )
            self.button_group.addButton(btn, val)
            self.buttons[val] = btn
            choices.addWidget(btn)

        choices.addStretch()

        self.badge = QLabel("")
        self.badge.setFixedWidth(100)
        self.badge.setFixedHeight(24)
        self.badge.setAlignment(Qt.AlignCenter)
        self.badge.setStyleSheet("font-size: 10px; font-weight: 700; border-radius: 12px;")
        choices.addWidget(self.badge)

        layout.addLayout(choices)

        self.button_group.idClicked.connect(self._on_value_changed)

        # Stile base
        self.setStyleSheet(
            "CBCLItemWidget { background: #141922; border: 1px solid #1E2433; "
            "border-radius: 10px; }"
        )
        self.setFixedHeight(76)

    def set_result(self, value, confidence, flag):
        self._value = value
        self._confidence = confidence

        if flag is None and confidence > 0.85:
            self._state = "confident"
            self._set_confident(value)
        elif flag in ("low_confidence", "ambiguous", "multiple_marks") or \
                (0.0 < confidence <= 0.85 and value is not None):
            self._state = "uncertain"
            self._set_uncertain(value)
        else:
            self._state = "missing"
            self._set_missing()

    def _set_confident(self, value):
        if value is not None:
            self.buttons[value].setChecked(True)
        for btn in self.buttons.values():
            btn.setEnabled(False)

        self.badge.setText(f"OK {self._confidence:.0%}")
        self.badge.setStyleSheet(
            "background: rgba(52,211,153,0.15); color: #34D399; "
            "font-size: 10px; font-weight: 700; border-radius: 12px; padding: 2px 8px;")
        self.num_label.setStyleSheet("font-weight: 800; font-size: 13px; color: #34D399;")
        self.setStyleSheet(
            "CBCLItemWidget { background: rgba(52,211,153,0.04); "
            "border: 1px solid rgba(52,211,153,0.2); border-radius: 10px; }")

    def _set_uncertain(self, value):
        if value is not None:
            self.buttons[value].setChecked(True)
        for btn in self.buttons.values():
            btn.setEnabled(True)

        self.badge.setText("CONFERMA")
        self.badge.setStyleSheet(
            "background: rgba(251,191,36,0.15); color: #FBBF24; "
            "font-size: 10px; font-weight: 700; border-radius: 12px; padding: 2px 8px;")
        self.num_label.setStyleSheet("font-weight: 800; font-size: 13px; color: #FBBF24;")
        self.setStyleSheet(
            "CBCLItemWidget { background: rgba(251,191,36,0.04); "
            "border: 1px solid rgba(251,191,36,0.2); border-radius: 10px; }")

    def _set_missing(self):
        for btn in self.buttons.values():
            btn.setChecked(False)
            btn.setEnabled(True)

        self.badge.setText("SCEGLI")
        self.badge.setStyleSheet(
            "background: rgba(248,113,113,0.15); color: #F87171; "
            "font-size: 10px; font-weight: 700; border-radius: 12px; padding: 2px 8px;")
        self.num_label.setStyleSheet("font-weight: 800; font-size: 13px; color: #F87171;")
        self.setStyleSheet(
            "CBCLItemWidget { background: rgba(248,113,113,0.04); "
            "border: 2px solid rgba(248,113,113,0.3); border-radius: 10px; }")

    def _on_value_changed(self, id):
        self._value = id
        self.value_changed.emit(self.item_id, id)
        self.badge.setText("MANUALE")
        self.badge.setStyleSheet(
            "background: rgba(96,165,250,0.15); color: #60A5FA; "
            "font-size: 10px; font-weight: 700; border-radius: 12px; padding: 2px 8px;")
        self.num_label.setStyleSheet("font-weight: 800; font-size: 13px; color: #60A5FA;")
        self.setStyleSheet(
            "CBCLItemWidget { background: rgba(96,165,250,0.04); "
            "border: 1px solid rgba(96,165,250,0.2); border-radius: 10px; }")

    def get_value(self):
        return self._value
