"""
Smart OCR v3.0 — App Desktop CBCL Scanner.
Entry point per l'applicazione PySide6.

Avvio: python desktop.py
"""

import sys
import os
from pathlib import Path

# Setup path
os.chdir(str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from app.main_window import MainWindow
from app.theme import apply_dark_theme, STYLESHEET_EXTRA


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Smart OCR")
    app.setOrganizationName("SmartOCR")

    # Dark theme
    apply_dark_theme(app)
    current = app.styleSheet() or ""
    app.setStyleSheet(current + STYLESHEET_EXTRA)

    # Finestra principale
    window = MainWindow()
    window.setMinimumSize(1200, 800)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
