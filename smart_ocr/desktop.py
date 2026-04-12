"""
Smart OCR v3.5 — App Desktop CBCL Scanner.
Entry point per l'applicazione PySide6.

Avvio: python desktop.py
"""

import sys
import os
from pathlib import Path

# Setup path: gestisce sia esecuzione standalone (Python) sia bundle PyInstaller.
# In bundle PyInstaller, sys._MEIPASS punta alla cartella _internal con i dati.
if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
    APP_DIR = Path(sys._MEIPASS)
else:
    APP_DIR = Path(__file__).parent

os.chdir(str(APP_DIR))
sys.path.insert(0, str(APP_DIR))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from app.main_window import MainWindow
from app.theme import apply_dark_theme, STYLESHEET_EXTRA


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Smart OCR")
    app.setOrganizationName("Tivanio")

    # Icona applicazione
    icon_path = Path(__file__).parent / "resources" / "icons" / "app_icon.ico"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    # Dark theme
    apply_dark_theme(app)
    current = app.styleSheet() or ""
    app.setStyleSheet(current + STYLESHEET_EXTRA)

    # Finestra principale
    window = MainWindow()
    window.setMinimumSize(1200, 800)
    if icon_path.exists():
        window.setWindowIcon(QIcon(str(icon_path)))
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
