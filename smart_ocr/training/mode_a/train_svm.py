"""
training/mode_a/train_svm.py

Redirect a training/train_svm.py (posizione originale).
Il training SVM salva il modello come models/model.pkl (path originale)
E come models/svm_classifier.pkl (nuovo path Config).
"""

import sys
from pathlib import Path

# Aggiungi path progetto
_PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

# Importa e ri-esporta il training originale
sys.path.insert(0, str(Path(__file__).parent.parent))
from train_svm import train, load_dataset

__all__ = ["train", "load_dataset"]

if __name__ == "__main__":
    success = train()
    sys.exit(0 if success else 1)
