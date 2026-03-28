"""
run.py — Wrapper per packaging con PyInstaller.
Avvia l'app Streamlit come applicazione desktop.
"""
import subprocess
import sys
from pathlib import Path


def main():
    app_path = Path(__file__).parent / "app.py"

    subprocess.run([
        sys.executable, "-m", "streamlit", "run",
        str(app_path),
        "--global.developmentMode=false",
        "--server.headless=true",
        "--server.port=8501",
        "--browser.gatherUsageStats=false"
    ])


if __name__ == "__main__":
    main()
