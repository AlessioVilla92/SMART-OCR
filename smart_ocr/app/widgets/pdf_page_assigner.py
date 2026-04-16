"""
Dialog per assegnare le pagine di un PDF ai 3 slot del questionario CBCL.

Flusso:
- L'utente carica un PDF.
- Le pagine vengono renderizzate come miniature via PyMuPDF (fitz).
- Se sono esattamente 3, vengono pre-assegnate automaticamente.
- L'utente puo' riordinare trascinando le miniature tra gli slot.
- Il bottone CONFERMA si attiva solo quando tutti e 3 gli slot sono pieni.
"""

import os
import tempfile
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QWidget, QSizePolicy, QMessageBox,
)
from PySide6.QtCore import Qt, QMimeData, Signal
from PySide6.QtGui import QPixmap, QDrag, QImage

_SLOT_LABELS = [
    ("page_4", "Pagina 4\n(items 1-54)"),
    ("page_5", "Pagina 5\n(items 55-85)"),
    ("page_6", "Pagina 6\n(items 86-113)"),
]

_THUMB_W, _THUMB_H = 140, 200

_IDLE_STYLE = (
    "background: #1E293B; border: 2px dashed #334155; "
    "border-radius: 8px; color: #64748B; font-size: 10px;"
)
_HOVER_STYLE = (
    "background: rgba(124,92,252,0.12); border: 2px dashed #7C5CFC; "
    "border-radius: 8px; color: #C8B5FF; font-size: 10px;"
)
_FILLED_STYLE = (
    "background: #1E293B; border: 2px solid #34D399; "
    "border-radius: 8px;"
)


def _render_pdf_pages(pdf_path: str) -> list[QPixmap]:
    import fitz
    doc = fitz.open(pdf_path)
    pixmaps = []
    for page in doc:
        pix = page.get_pixmap(dpi=150)
        img = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format_RGB888)
        pixmaps.append(QPixmap.fromImage(img))
    doc.close()
    return pixmaps


def _save_page_as_image(pdf_path: str, page_index: int, dpi: int = 300) -> str:
    import fitz
    doc = fitz.open(pdf_path)
    page = doc[page_index]
    pix = page.get_pixmap(dpi=dpi)
    fd, tmp_path = tempfile.mkstemp(suffix=".png", prefix=f"cbcl_p{page_index}_")
    os.close(fd)
    pix.save(tmp_path)
    doc.close()
    return tmp_path


class _DraggableThumb(QLabel):
    """Miniatura di pagina PDF trascinabile."""

    def __init__(self, page_index: int, pixmap: QPixmap, parent=None):
        super().__init__(parent)
        self.page_index = page_index
        self._full_pixmap = pixmap
        scaled = pixmap.scaled(_THUMB_W, _THUMB_H, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.setPixmap(scaled)
        self.setFixedSize(_THUMB_W, _THUMB_H)
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet(
            "background: #141922; border: 1.5px solid #334155; border-radius: 6px;"
        )
        self.setCursor(Qt.OpenHandCursor)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.setCursor(Qt.ClosedHandCursor)

    def mouseMoveEvent(self, event):
        if not (event.buttons() & Qt.LeftButton):
            return
        drag = QDrag(self)
        mime = QMimeData()
        mime.setText(str(self.page_index))
        drag.setMimeData(mime)
        scaled = self._full_pixmap.scaled(80, 110, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        drag.setPixmap(scaled)
        drag.exec(Qt.MoveAction)
        self.setCursor(Qt.OpenHandCursor)


class _AssignSlot(QLabel):
    """Slot di destinazione per una pagina PDF. Accetta drag & drop."""

    page_assigned = Signal(str, int)    # (slot_key, page_index)
    page_removed = Signal(str)          # (slot_key)

    def __init__(self, slot_key: str, label_text: str, parent=None):
        super().__init__(parent)
        self.slot_key = slot_key
        self._label_text = label_text
        self._assigned_index = None
        self._assigned_pixmap = None
        self.setFixedSize(_THUMB_W + 20, _THUMB_H + 40)
        self.setAlignment(Qt.AlignCenter)
        self.setAcceptDrops(True)
        self._show_empty()

    def _show_empty(self):
        self.setText(f"{self._label_text}\n\nTrascina qui")
        self.setStyleSheet(_IDLE_STYLE)
        self._assigned_index = None
        self._assigned_pixmap = None

    def assign(self, page_index: int, pixmap: QPixmap):
        self._assigned_index = page_index
        self._assigned_pixmap = pixmap
        scaled = pixmap.scaled(_THUMB_W, _THUMB_H, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.setPixmap(scaled)
        self.setStyleSheet(_FILLED_STYLE)

    def get_assigned_index(self):
        return self._assigned_index

    def clear_slot(self):
        self.clear()
        self._show_empty()
        self.page_removed.emit(self.slot_key)

    def dragEnterEvent(self, event):
        if event.mimeData().hasText():
            event.acceptProposedAction()
            self.setStyleSheet(_HOVER_STYLE)

    def dragLeaveEvent(self, event):
        if self._assigned_index is not None:
            self.setStyleSheet(_FILLED_STYLE)
        else:
            self.setStyleSheet(_IDLE_STYLE)

    def dropEvent(self, event):
        page_idx = int(event.mimeData().text())
        event.acceptProposedAction()
        self.page_assigned.emit(self.slot_key, page_idx)

    def mouseDoubleClickEvent(self, event):
        if self._assigned_index is not None:
            self.clear_slot()


class PdfPageAssigner(QDialog):
    """Dialog modale: assegna pagine PDF agli slot Pagina 4/5/6."""

    def __init__(self, pdf_path: str, parent=None):
        super().__init__(parent)
        self.pdf_path = pdf_path
        self._page_pixmaps: list[QPixmap] = []
        self._slots: dict[str, _AssignSlot] = {}
        self._thumbs: list[_DraggableThumb] = []
        self._result: dict[str, int] = {}
        self.setWindowTitle("Assegna pagine PDF")
        self.setMinimumSize(700, 520)
        self.setStyleSheet("background: #0F1219; color: #E8ECF4;")
        self._load_pdf()
        self._setup_ui()
        if len(self._page_pixmaps) == 3:
            self._auto_assign()

    def _load_pdf(self):
        try:
            self._page_pixmaps = _render_pdf_pages(self.pdf_path)
        except Exception as e:
            QMessageBox.critical(self, "Errore PDF", f"Impossibile leggere il PDF:\n{e}")

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        n = len(self._page_pixmaps)
        info = QLabel(
            f"PDF caricato: {Path(self.pdf_path).name}  —  {n} pagin{'a' if n == 1 else 'e'} trovate\n"
            "Trascina le pagine negli slot corrispondenti. Doppio click su uno slot per svuotarlo."
        )
        info.setStyleSheet("font-size: 12px; color: #94A3B8; padding: 8px;")
        info.setWordWrap(True)
        layout.addWidget(info)

        # --- Pagine disponibili (scrollabile per PDF con molte pagine) ---
        avail_label = QLabel("Pagine disponibili")
        avail_label.setStyleSheet("font-size: 13px; font-weight: bold; color: #7C5CFC;")
        layout.addWidget(avail_label)

        scroll = QScrollArea()
        scroll.setFixedHeight(_THUMB_H + 40)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        avail_container = QWidget()
        self._avail_layout = QHBoxLayout(avail_container)
        self._avail_layout.setSpacing(12)
        self._avail_layout.setContentsMargins(8, 4, 8, 4)

        for i, pxm in enumerate(self._page_pixmaps):
            thumb = _DraggableThumb(i, pxm)
            self._thumbs.append(thumb)
            self._avail_layout.addWidget(thumb)

        self._avail_layout.addStretch()
        scroll.setWidget(avail_container)
        layout.addWidget(scroll)

        # --- Slot di assegnazione ---
        assign_label = QLabel("Assegnazione (trascina qui)")
        assign_label.setStyleSheet("font-size: 13px; font-weight: bold; color: #34D399;")
        layout.addWidget(assign_label)

        slots_row = QHBoxLayout()
        slots_row.setSpacing(20)
        for slot_key, label_text in _SLOT_LABELS:
            slot = _AssignSlot(slot_key, label_text)
            slot.page_assigned.connect(self._on_page_assigned)
            slot.page_removed.connect(self._on_page_removed)
            self._slots[slot_key] = slot

            col = QVBoxLayout()
            col.setAlignment(Qt.AlignCenter)
            title = QLabel(label_text.replace("\n", " "))
            title.setAlignment(Qt.AlignCenter)
            title.setStyleSheet("font-size: 11px; color: #94A3B8; font-weight: bold;")
            col.addWidget(title)
            col.addWidget(slot)
            slots_row.addLayout(col)

        layout.addLayout(slots_row)

        # --- Bottoni ---
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        cancel_btn = QPushButton("Annulla")
        cancel_btn.setFixedSize(120, 40)
        cancel_btn.setStyleSheet(
            "QPushButton { background: transparent; color: #94A3B8; border: 1.5px solid #334155; "
            "border-radius: 8px; font-size: 13px; }"
            "QPushButton:hover { border-color: #64748B; color: #E8ECF4; }"
        )
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        self._confirm_btn = QPushButton("CONFERMA")
        self._confirm_btn.setFixedSize(160, 40)
        self._confirm_btn.setEnabled(False)
        self._confirm_btn.setStyleSheet(
            "QPushButton { background: #34D399; color: #0F1219; border-radius: 8px; "
            "font-size: 14px; font-weight: 800; }"
            "QPushButton:hover { background: #6EE7B7; }"
            "QPushButton:disabled { background: #1E293B; color: #4A5568; }"
        )
        self._confirm_btn.clicked.connect(self._confirm)
        btn_row.addWidget(self._confirm_btn)

        layout.addLayout(btn_row)

    def _on_page_assigned(self, slot_key: str, page_index: int):
        for sk, slot in self._slots.items():
            if sk != slot_key and slot.get_assigned_index() == page_index:
                slot.clear_slot()

        self._slots[slot_key].assign(page_index, self._page_pixmaps[page_index])
        self._update_thumb_visibility()
        self._update_confirm()

    def _on_page_removed(self, slot_key: str):
        self._update_thumb_visibility()
        self._update_confirm()

    def _update_thumb_visibility(self):
        assigned = {s.get_assigned_index() for s in self._slots.values() if s.get_assigned_index() is not None}
        for thumb in self._thumbs:
            thumb.setVisible(thumb.page_index not in assigned)

    def _update_confirm(self):
        all_filled = all(s.get_assigned_index() is not None for s in self._slots.values())
        self._confirm_btn.setEnabled(all_filled)

    def _auto_assign(self):
        for i, (slot_key, _) in enumerate(_SLOT_LABELS):
            self._slots[slot_key].assign(i, self._page_pixmaps[i])
        self._update_thumb_visibility()
        self._update_confirm()

    def _confirm(self):
        self._result = {}
        for slot_key, slot in self._slots.items():
            self._result[slot_key] = slot.get_assigned_index()
        self.accept()

    def get_result(self) -> dict[str, int]:
        return self._result

    def get_image_paths(self) -> dict[str, str]:
        paths = {}
        for slot_key, page_index in self._result.items():
            paths[slot_key] = _save_page_as_image(self.pdf_path, page_index)
        return paths
