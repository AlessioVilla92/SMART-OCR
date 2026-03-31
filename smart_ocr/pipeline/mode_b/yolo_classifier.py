"""
pipeline/mode_b/yolo_classifier.py

Classificatore Mode B: YOLOv8n fine-tuned via ONNX Runtime.
NON richiede PyTorch o Ultralytics — solo onnxruntime e numpy.

Il modello .onnx viene generato da:
    python training/mode_b/train_yolo.py
    python training/mode_b/export_onnx.py

Classi binarie: segnato=0, vuoto=1 (mapping unificato Config.CLASSES)
ATTENZIONE: Ultralytics ordina le classi alfabeticamente durante il training.
Il mapping corretto viene letto dal training report (training_report_yolo.json).
"""

import json
import cv2
import numpy as np
from pathlib import Path
from typing import Dict, Optional, Tuple

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from config import Config

try:
    import onnxruntime as ort
except ImportError:
    ort = None


class YOLOClassifier:
    """
    Classificatore Mode B: inferenza YOLOv8n ONNX.
    Stessa interfaccia di SVMClassifier per intercambiabilita.
    """

    def __init__(self, model_path: Optional[Path] = None):
        if ort is None:
            raise ImportError(
                "onnxruntime non installato.\n"
                "Installa con: pip install onnxruntime>=1.18.0"
            )

        path = model_path or Config.YOLO_ONNX_PATH
        if not path.exists():
            raise FileNotFoundError(
                f"Modello ONNX non trovato: {path}\n"
                "Eseguire:\n"
                "  1. python training/mode_b/prepare_yolo_dataset.py\n"
                "  2. python training/mode_b/train_yolo.py\n"
                "  3. python training/mode_b/export_onnx.py"
            )

        # ONNX Runtime: usa GPU se disponibile, altrimenti CPU
        providers = ['CUDAExecutionProvider', 'CPUExecutionProvider']
        self.session = ort.InferenceSession(str(path), providers=providers)

        # Scopri nomi input/output dinamicamente
        self.input_name = self.session.get_inputs()[0].name
        self.output_names = [o.name for o in self.session.get_outputs()]
        self.input_shape = self.session.get_inputs()[0].shape

        # Carica mapping classi YOLO → unified
        self.yolo_to_unified = self._load_class_mapping()
        self.is_loaded = True

    def _load_class_mapping(self) -> Dict[int, int]:
        """
        Carica il mapping indici YOLO → indici Config.CLASSES.

        Ultralytics ordina le classi alfabeticamente:
          cerchio=0, vuoto=1, x_rossa=2

        Config.CLASSES usa:
          cerchio=0, x_rossa=1, vuoto=2

        Senza mapping, vuoto e x_rossa sarebbero invertiti!
        """
        report_path = Config.YOLO_TRAINING_REPORT_PATH
        if report_path.exists():
            try:
                with open(report_path, "r", encoding="utf-8") as f:
                    report = json.load(f)
                yolo_names = report.get("class_names", {})
                if yolo_names:
                    return self._build_class_map(yolo_names)
            except (json.JSONDecodeError, KeyError):
                pass

        # Default: assume ordine alfabetico Ultralytics
        # segnato=0 → 0, vuoto=1 → 1
        return {0: 0, 1: 1}

    def _build_class_map(self, yolo_names: dict) -> Dict[int, int]:
        """
        Costruisce mapping da indici YOLO a indici unificati Config.CLASSES.

        Args:
            yolo_names: {idx: name} dal training report (es. {"0": "cerchio", "1": "vuoto", "2": "x_rossa"})
        """
        unified_inv = Config.CLASSES_INV  # {"cerchio": 0, "x_rossa": 1, "vuoto": 2}
        mapping = {}
        for yolo_idx, name in yolo_names.items():
            yolo_idx = int(yolo_idx)
            if name in unified_inv:
                mapping[yolo_idx] = unified_inv[name]
            else:
                raise ValueError(
                    f"Classe YOLO '{name}' non trovata in Config.CLASSES: {Config.CLASSES}"
                )
        return mapping

    def _preprocess(self, cell: np.ndarray) -> np.ndarray:
        """
        Prepara cella 64x64 grayscale per inferenza ONNX.

        Replica esattamente il preprocessing di Ultralytics:
        1. Grayscale → RGB (3 canali)
        2. Resize a 64x64 (se necessario)
        3. Normalizza [0,255] → [0.0, 1.0]
        4. HWC → CHW
        5. Aggiungi batch dim → BCHW
        """
        # 1. Grayscale → RGB
        if len(cell.shape) == 2:
            cell = np.stack([cell, cell, cell], axis=-1)

        # 2. Resize
        if cell.shape[0] != 64 or cell.shape[1] != 64:
            cell = cv2.resize(cell, (64, 64), interpolation=cv2.INTER_AREA)

        # 3. Normalizza
        cell = cell.astype(np.float32) / 255.0

        # 4. HWC → CHW
        cell = np.transpose(cell, (2, 0, 1))

        # 5. Batch dimension
        cell = np.expand_dims(cell, axis=0)

        return cell

    @staticmethod
    def _softmax(x: np.ndarray) -> np.ndarray:
        """Softmax stabile numericamente."""
        e_x = np.exp(x - np.max(x))
        return e_x / e_x.sum()

    def predict_cell(self, cell: np.ndarray) -> Tuple[str, float]:
        """
        Predice la classe di una singola cella 64x64.

        Returns:
            (class_name, confidence)
            class_name: "cerchio", "x_rossa", "vuoto", "ambiguo"
            confidence: float 0.0-1.0
        """
        input_tensor = self._preprocess(cell)
        outputs = self.session.run(
            self.output_names,
            {self.input_name: input_tensor}
        )

        # Output YOLOv8 classification: shape [1, num_classes]
        logits = outputs[0][0]
        probabilities = self._softmax(logits)

        # Indice YOLO con probabilita massima
        yolo_idx = int(np.argmax(probabilities))
        confidence = float(probabilities[yolo_idx])

        # Mappa a indice unificato Config.CLASSES
        unified_idx = self.yolo_to_unified.get(yolo_idx, yolo_idx)
        class_name = Config.CLASSES.get(unified_idx, "ambiguo")

        if confidence < Config.YOLO_CONFIDENCE_THRESHOLD:
            return "ambiguo", confidence

        return class_name, confidence

    def predict_item_cells(self, cells: Dict[str, np.ndarray]) -> dict:
        """
        Classifica le 3 celle (0, 1, 2) di un item.

        Returns: stessa struttura di core/classifier.py CBCLClassifier.predict_item_cells():
        {
            "marked_column": "0"|"1"|"2"|None,
            "value": 0|1|2|None,
            "confidence": float,
            "flag": None|"ambiguous"|"missing"|"multiple_marks",
            "raw_predictions": {"0": {"class": str, "confidence": float}, ...}
        }
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

        # Controlla ambiguita generale
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


def get_yolo_classifier(model_path: Optional[Path] = None) -> YOLOClassifier:
    """Factory function per creare un YOLOClassifier."""
    return YOLOClassifier(model_path)
