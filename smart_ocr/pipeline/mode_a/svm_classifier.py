"""
pipeline/mode_a/svm_classifier.py

Wrapper Mode A: classificatore HOG + SVM.
Delega a core.classifier.CBCLClassifier con path dal Config unificato.

Output predict_item_cells() ha la stessa struttura di core/classifier.py
cosi che scorer.py e app.py funzionino senza modifiche.
"""

from pathlib import Path
from typing import Dict, Optional
import numpy as np

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from config import Config
from core.classifier import CBCLClassifier, compute_hog_features


class SVMClassifier:
    """
    Classificatore Mode A: HOG features + SVM.
    Wrapper attorno a core.classifier.CBCLClassifier che usa Config per il path.
    """

    def __init__(self, model_path: Optional[Path] = None):
        self._classifier = CBCLClassifier()
        path = model_path or Config.get_svm_model_path()
        if not self._classifier.load(path):
            raise FileNotFoundError(
                f"Modello SVM non trovato: {path}\n"
                "Eseguire: python training/mode_a/train_svm.py"
            )

    @property
    def is_loaded(self) -> bool:
        return self._classifier.is_loaded

    def predict_cell(self, cell: np.ndarray):
        """
        Predice la classe di una singola cella 64x64.
        Returns: (class_name, confidence)
        """
        return self._classifier.predict_cell(cell)

    def predict_item_cells(self, cells: Dict[str, np.ndarray]) -> dict:
        """
        Classifica le 3 celle (0, 1, 2) di un item.

        Returns: {
            "marked_column": "0"|"1"|"2"|None,
            "value": 0|1|2|None,
            "confidence": float,
            "flag": None|"ambiguous"|"missing"|"multiple_marks",
            "raw_predictions": {"0": {"class": str, "confidence": float}, ...}
        }
        """
        return self._classifier.predict_item_cells(cells)


def get_svm_classifier(model_path: Optional[Path] = None) -> SVMClassifier:
    """Factory function per creare un SVMClassifier."""
    return SVMClassifier(model_path)
