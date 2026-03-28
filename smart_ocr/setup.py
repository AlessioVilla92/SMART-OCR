"""
Esegui: python setup.py
Rileva l'architettura e installa le dipendenze corrette.
"""
import subprocess
import sys
import platform


def main():
    machine = platform.machine().lower()
    system = platform.system().lower()

    print(f"Sistema: {system}, Architettura: {machine}")

    if system == "darwin" and machine == "arm64":
        print("⚠️  Rilevato Apple Silicon (M1/M2/M3)")
        print("Usa conda-forge per OpenCV. Vedi README sezione 1.")
        print("Esegui: conda install -c conda-forge opencv scikit-learn numpy pillow")
        print("Poi: pip install -r requirements-arm64.txt")
    else:
        print("✅ Installazione standard (Intel Mac / Windows / Linux x86)")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])

    print("✅ Setup completato.")


if __name__ == "__main__":
    main()
