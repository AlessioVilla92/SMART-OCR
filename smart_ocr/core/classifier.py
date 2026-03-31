"""
core/classifier.py

Classificatore basato su HOG features + SVM.
In produzione carica model.pkl pre-addestrato.
NON usa AI in produzione.

Classi binarie:
    0 = "segnato" (qualsiasi marcatura: cerchio, X, tratto, annerimento, ecc.)
    1 = "vuoto"   (nessuna marcatura)
    "ambiguo" = bassa confidence, richiede revisione umana
"""

import cv2
import numpy as np
import joblib
from pathlib import Path
from typing import Tuple, Optional


MODEL_PATH = Path(__file__).parent.parent / "models" / "model.pkl"
CELL_SIZE = (64, 64)

# Soglia confidence sotto cui la cella è "ambigua"
AMBIGUITY_THRESHOLD = 0.65

# Etichette classi binarie
CLASS_LABELS = {0: "segnato", 1: "vuoto"}


def compute_hog_features(cell: np.ndarray) -> np.ndarray:
    """
    Estrae HOG (Histogram of Oriented Gradients) da una cella 64x64.

    Parametri HOG ottimizzati per simboli scritti a mano su carta:
    - winSize: deve corrispondere a CELL_SIZE
    - blockSize: 16x16 (25% della cella)
    - blockStride: 8x8 (50% di overlap tra blocchi)
    - cellSize: 8x8 (8 celle per asse -> 64 celle totali)
    - nbins: 9 (orientamenti da 0 a 180)

    Vettore output: 1764 features per cella 64x64
    """
    hog = cv2.HOGDescriptor(
        _winSize=(64, 64),
        _blockSize=(16, 16),
        _blockStride=(8, 8),
        _cellSize=(8, 8),
        _nbins=9
    )

    # Assicura dimensioni corrette
    if cell.shape != CELL_SIZE:
        cell = cv2.resize(cell, CELL_SIZE)

    features = hog.compute(cell)
    return features.flatten()


class CBCLClassifier:
    """Classificatore SVM per celle CBCL."""

    def __init__(self):
        self.model = None
        self.is_loaded = False

    def load(self, model_path: Optional[Path] = None) -> bool:
        """
        Carica il modello SVM dal file .pkl.
        Returns: True se caricato con successo, False altrimenti.
        """
        path = model_path or MODEL_PATH

        if not path.exists():
            return False

        try:
            self.model = joblib.load(path)
            self.is_loaded = True
            return True
        except Exception as e:
            print(f"Errore caricamento modello: {e}")
            return False

    def predict_cell(self, cell: np.ndarray) -> Tuple[str, float]:
        """
        Predice la classe di una singola cella.

        Returns:
            (classe, confidence)
            classe: "cerchio", "x_rossa", "vuoto", "ambiguo"
            confidence: float 0.0-1.0
        """
        if not self.is_loaded:
            raise RuntimeError("Modello non caricato. Esegui load() prima.")

        features = compute_hog_features(cell)
        features = features.reshape(1, -1)

        # SVM con probability=True restituisce probabilità per classe
        proba = self.model.predict_proba(features)[0]
        predicted_class_idx = np.argmax(proba)
        confidence = proba[predicted_class_idx]

        # Classi binarie: 0=segnato, 1=vuoto
        class_names = ["segnato", "vuoto"]
        predicted_class = class_names[predicted_class_idx]

        if confidence < AMBIGUITY_THRESHOLD:
            return "ambiguo", confidence

        return predicted_class, float(confidence)

    def predict_item_cells(
        self,
        cells: dict  # {"0": cell_64x64, "1": cell_64x64, "2": cell_64x64}
    ) -> dict:
        """
        Predice per tutte e 3 le celle di un item.

        Returns:
            {
                "marked_column": "0" | "1" | "2" | None,
                "value": 0 | 1 | 2 | None,
                "confidence": float,
                "flag": None | "ambiguous" | "missing" | "multiple_marks",
                "raw_predictions": {"0": (class, conf), "1": (class, conf), "2": (class, conf)}
            }
        """
        raw = {}
        for col_label, cell_img in cells.items():
            raw[col_label] = self.predict_cell(cell_img)

        # Trova le celle marcate (segnato = qualsiasi mark)
        marked = [
            col for col, (cls, conf) in raw.items()
            if cls == "segnato"
        ]

        flag = None
        value = None
        marked_column = None
        confidence = 0.0

        if len(marked) == 0:
            flag = "missing"
        elif len(marked) > 1:
            flag = "multiple_marks"
        else:
            marked_column = marked[0]
            cls, conf = raw[marked_column]

            if cls == "ambiguo":
                flag = "ambiguous"
            else:
                value = int(marked_column)  # La colonna 0/1/2 è il valore
                confidence = conf

        # Controlla ambiguità generale
        any_ambiguous = any(cls == "ambiguo" for cls, _ in raw.values())
        if any_ambiguous and flag is None:
            flag = "ambiguous"

        return {
            "marked_column": marked_column,
            "value": value,
            "confidence": confidence,
            "flag": flag,
            "raw_predictions": {col: {"class": cls, "confidence": conf}
                                for col, (cls, conf) in raw.items()}
        }


# Singleton per uso in produzione
_classifier_instance = None

def get_classifier() -> CBCLClassifier:
    """Ritorna istanza singleton del classificatore."""
    global _classifier_instance
    if _classifier_instance is None:
        _classifier_instance = CBCLClassifier()
        _classifier_instance.load()
    return _classifier_instance
