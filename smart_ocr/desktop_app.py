"""
desktop_app.py

Launcher desktop per Smart OCR.
Avvia Streamlit in background e apre una finestra nativa con pywebview.

Uso diretto:   python desktop_app.py
Build .app:    streamlit-desktop-app build desktop_app.py --name "SmartOCR"
"""

import subprocess
import sys
import time
import threading
import socket
from pathlib import Path


def find_free_port():
    """Trova una porta libera."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        return s.getsockname()[1]


def wait_for_server(port, timeout=30):
    """Aspetta che il server Streamlit sia pronto."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            with socket.create_connection(("localhost", port), timeout=1):
                return True
        except (ConnectionRefusedError, socket.timeout, OSError):
            time.sleep(0.5)
    return False


def main():
    app_path = Path(__file__).parent / "app.py"
    port = find_free_port()

    # Avvia Streamlit in background
    streamlit_process = subprocess.Popen(
        [
            sys.executable, "-m", "streamlit", "run",
            str(app_path),
            f"--server.port={port}",
            "--server.headless=true",
            "--browser.gatherUsageStats=false",
            "--global.developmentMode=false",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    # Aspetta che il server sia pronto
    if not wait_for_server(port):
        print("Errore: Streamlit non si è avviato in tempo.")
        streamlit_process.kill()
        sys.exit(1)

    # Apri finestra nativa
    try:
        import webview
        window = webview.create_window(
            "Smart OCR — CBCL Scanner",
            f"http://localhost:{port}",
            width=1400,
            height=900,
            resizable=True,
            min_size=(800, 600),
        )
        webview.start()
    except ImportError:
        # Fallback: apri nel browser
        import webbrowser
        print(f"pywebview non disponibile. Apro nel browser: http://localhost:{port}")
        webbrowser.open(f"http://localhost:{port}")
        try:
            streamlit_process.wait()
        except KeyboardInterrupt:
            pass
    finally:
        streamlit_process.terminate()
        streamlit_process.wait()


if __name__ == "__main__":
    main()
