"""
pipeline/ensemble_classifier.py

Classificatore Ensemble: combina SVM (Mode A) e YOLO (Mode B)
con soft voting e temperature scaling per calibrazione probabilita.

L'ensemble funziona cosi:
1. Entrambi i classificatori predicono la stessa cella
2. Le probabilita YOLO vengono calibrate con temperature scaling (T>1)
3. Le probabilita vengono mediate (weighted soft voting)
4. Se la confidence e bassa, si applica TTA selettivo
5. Il risultato finale e la classe con probabilita media piu alta

Se uno dei due modelli non e disponibile, degrada al singolo disponibile.
"""

import cv2
import numpy as np
from pathlib import Path
from typing import Dict, Optional, Tuple, List

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import Config


# Temperature scaling: divide i logits YOLO per T prima del softmax.
# T=1.0 = nessuna calibrazione, T>1 = probabilita piu "morbide".
# Con T=2.0, una predizione 0.99 diventa ~0.88, piu confrontabile con SVM.
YOLO_TEMPERATURE = 2.0

# Pesi per il soft voting (SVM, YOLO). Somma = 1.0.
WEIGHT_SVM = 0.45
WEIGHT_YOLO = 0.55

# Soglia sotto cui attivare TTA
TTA_CONFIDENCE_THRESHOLD = 0.90

# Soglia ambiguita ensemble
ENSEMBLE_AMBIGUITY_THRESHOLD = 0.60

# Classi binarie nell'ordine unificato
CLASS_NAMES = ["segnato", "vuoto"]


def _tta_augmentations(cell: np.ndarray) -> List[np.ndarray]:
    """
    Genera varianti per Test-Time Augmentation.
    Solo trasformazioni sicure che non alterano la semantica del mark.
    """
    h, w = cell.shape[:2]
    center = (w // 2, h // 2)
    variants = []

    # Rotazione +3 gradi
    M = cv2.getRotationMatrix2D(center, 3, 1.0)
    variants.append(cv2.warpAffine(cell, M, (w, h), borderMode=cv2.BORDER_REPLICATE))

    # Rotazione -3 gradi
    M = cv2.getRotationMatrix2D(center, -3, 1.0)
    variants.append(cv2.warpAffine(cell, M, (w, h), borderMode=cv2.BORDER_REPLICATE))

    # Flip orizzontale
    variants.append(cv2.flip(cell, 1))

    return variants


class EnsembleClassifier:
    """
    Classificatore Ensemble: SVM + YOLO con soft voting calibrato.
    Stessa interfaccia di SVMClassifier e YOLOClassifier.
    """

    def __init__(self):
        self._svm = None
        self._yolo = None
        self._active_models = []

        # Carica SVM
        if Config.svm_model_available():
            try:
                from pipeline.mode_a.svm_classifier import SVMClassifier
                self._svm = SVMClassifier()
                self._active_models.append("svm")
            except Exception as e:
                print(f"Ensemble: SVM non caricato: {e}")

        # Carica YOLO
        if Config.yolo_model_available():
            try:
                from pipeline.mode_b.yolo_classifier import YOLOClassifier
                self._yolo = YOLOClassifier()
                self._active_models.append("yolo")
            except Exception as e:
                print(f"Ensemble: YOLO non caricato: {e}")

        if not self._active_models:
            raise RuntimeError(
                "Ensemble: nessun modello disponibile. "
                "Servono almeno SVM o YOLO."
            )

        self.is_loaded = True

    @property
    def active_models(self) -> List[str]:
        return self._active_models

    def _get_svm_proba(self, cell: np.ndarray) -> Optional[np.ndarray]:
        """Ottiene probabilita SVM [segnato, vuoto]."""
        if self._svm is None:
            return None
        from core.classifier import compute_hog_features
        features = compute_hog_features(cell).reshape(1, -1)
        proba = self._svm._classifier.model.predict_proba(features)[0]
        # SVM ordine: [segnato=0, vuoto=1] — gia unificato
        return proba

    def _get_yolo_proba(self, cell: np.ndarray) -> Optional[np.ndarray]:
        """Ottiene probabilita YOLO calibrate [segnato, vuoto]."""
        if self._yolo is None:
            return None

        input_tensor = self._yolo._preprocess(cell)
        outputs = self._yolo.session.run(
            self._yolo.output_names,
            {self._yolo.input_name: input_tensor}
        )
        logits = outputs[0][0]

        # Temperature scaling: divide logits per T prima del softmax
        scaled_logits = logits / YOLO_TEMPERATURE
        proba_yolo = self._yolo._softmax(scaled_logits)

        # Rimappa da ordine YOLO a ordine unificato
        proba_unified = np.zeros(len(CLASS_NAMES))
        for yolo_idx, unified_idx in self._yolo.yolo_to_unified.items():
            proba_unified[unified_idx] = proba_yolo[yolo_idx]

        return proba_unified

    def _ensemble_proba(self, cell: np.ndarray) -> np.ndarray:
        """
        Combina probabilita SVM e YOLO con weighted soft voting.
        Returns: array [cerchio, x_rossa, vuoto] con probabilita mediate.
        """
        svm_proba = self._get_svm_proba(cell)
        yolo_proba = self._get_yolo_proba(cell)

        if svm_proba is not None and yolo_proba is not None:
            combined = WEIGHT_SVM * svm_proba + WEIGHT_YOLO * yolo_proba
        elif svm_proba is not None:
            combined = svm_proba
        else:
            combined = yolo_proba

        return combined

    def _ensemble_proba_with_tta(self, cell: np.ndarray) -> np.ndarray:
        """
        Ensemble con TTA selettivo.
        Se la confidence iniziale e bassa, applica augmentazioni e media.
        """
        proba = self._ensemble_proba(cell)
        confidence = proba.max()

        if confidence >= TTA_CONFIDENCE_THRESHOLD:
            return proba

        # TTA: media con varianti augmentate
        all_probas = [proba]
        for aug_cell in _tta_augmentations(cell):
            aug_proba = self._ensemble_proba(aug_cell)
            all_probas.append(aug_proba)

        return np.mean(all_probas, axis=0)

    def predict_cell(self, cell: np.ndarray) -> Tuple[str, float]:
        """
        Predice la classe di una cella con ensemble + TTA selettivo.
        Returns: (class_name, confidence)
        """
        proba = self._ensemble_proba_with_tta(cell)

        predicted_idx = int(np.argmax(proba))
        confidence = float(proba[predicted_idx])
        class_name = CLASS_NAMES[predicted_idx]

        if confidence < ENSEMBLE_AMBIGUITY_THRESHOLD:
            return "ambiguo", confidence

        return class_name, confidence

    def predict_item_cells(self, cells: Dict[str, np.ndarray]) -> dict:
        """
        Classifica le 3 celle (0, 1, 2) di un item.
        Stessa interfaccia di SVMClassifier e YOLOClassifier.
        """
        raw = {}
        for col_label, cell_img in cells.items():
            cls, conf = self.predict_cell(cell_img)
            raw[col_label] = (cls, conf)

        # Trova celle marcate (segnato = qualsiasi mark)
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
                value = int(marked_column)
                confidence = conf

        any_ambiguous = any(cls == "ambiguo" for cls, _ in raw.values())
        if any_ambiguous and flag is None:
            flag = "ambiguous"

        return {
            "marked_column": marked_column,
            "value": value,
            "confidence": confidence,
            "flag": flag,
            "raw_predictions": {
                col: {"class": cls, "confidence": conf}
                for col, (cls, conf) in raw.items()
            }
        }
