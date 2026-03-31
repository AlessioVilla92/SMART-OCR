"""
training/mode_b/validate_onnx.py

Verifica che il modello ONNX esportato produca risultati identici al .pt.
Confronta output di Ultralytics (.pt) con ONNX Runtime (.onnx) su celle di test.

CRITICO: senza questa validazione, errori nel preprocessing o nel mapping
classi causerebbero risultati silenziosamente sbagliati in produzione.

Uso:
    python training/mode_b/validate_onnx.py
"""

import cv2
import numpy as np
from pathlib import Path
from collections import defaultdict
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config import Config

try:
    from ultralytics import YOLO
except ImportError:
    print("❌ Ultralytics non installato (serve per il confronto .pt)")
    sys.exit(1)

try:
    import onnxruntime as ort
except ImportError:
    print("❌ onnxruntime non installato")
    sys.exit(1)


def preprocess_for_onnx(cell: np.ndarray) -> np.ndarray:
    """
    Preprocessing identico a pipeline/mode_b/yolo_classifier.py._preprocess().
    Deve replicare ESATTAMENTE quello che Ultralytics fa durante l'inferenza.
    """
    if len(cell.shape) == 2:
        cell = np.stack([cell, cell, cell], axis=-1)
    if cell.shape[0] != 64 or cell.shape[1] != 64:
        cell = cv2.resize(cell, (64, 64), interpolation=cv2.INTER_AREA)
    cell = cell.astype(np.float32) / 255.0
    cell = np.transpose(cell, (2, 0, 1))
    cell = np.expand_dims(cell, axis=0)
    return cell


def softmax(x):
    e_x = np.exp(x - np.max(x))
    return e_x / e_x.sum()


def collect_test_cells(max_per_class: int = 20) -> list:
    """Raccoglie celle di test dalle directory dati."""
    cells = []
    classes = ["cerchio", "x_rossa", "vuoto"]
    search_dirs = [
        Config.DATA_DIR / "raw_cells",
        Config.DATA_DIR / "generated",
    ]

    for class_name in classes:
        count = 0
        for source_dir in search_dirs:
            class_dir = source_dir / class_name
            if not class_dir.exists():
                continue
            for img_path in sorted(class_dir.glob("*.png"))[:max_per_class - count]:
                img = cv2.imread(str(img_path), cv2.IMREAD_GRAYSCALE)
                if img is not None:
                    img = cv2.resize(img, (64, 64))
                    cells.append((img, class_name, str(img_path)))
                    count += 1
                if count >= max_per_class:
                    break

    return cells


def validate():
    """Confronta output .pt vs .onnx su celle di test."""

    pt_path = Config.YOLO_PT_PATH
    onnx_path = Config.YOLO_ONNX_PATH

    if not pt_path.exists():
        print(f"❌ Modello .pt non trovato: {pt_path}")
        return False
    if not onnx_path.exists():
        print(f"❌ Modello .onnx non trovato: {onnx_path}")
        return False

    print("\n🔍 Validazione ONNX vs PyTorch")
    print("=" * 50)

    # Carica modelli
    pt_model = YOLO(str(pt_path))
    ort_session = ort.InferenceSession(
        str(onnx_path),
        providers=["CPUExecutionProvider"]
    )

    input_name = ort_session.get_inputs()[0].name
    output_names = [o.name for o in ort_session.get_outputs()]

    # Info modelli
    print(f"\n📋 Info modelli:")
    print(f"   PT class names:    {pt_model.names}")
    print(f"   ONNX input name:   {input_name}")
    print(f"   ONNX input shape:  {ort_session.get_inputs()[0].shape}")
    print(f"   ONNX output shape: {ort_session.get_outputs()[0].shape}")

    # Raccogli celle di test
    test_cells = collect_test_cells(max_per_class=20)
    if not test_cells:
        print("❌ Nessuna cella di test trovata")
        return False

    print(f"\n🧪 Testing su {len(test_cells)} celle...")

    matches = 0
    mismatches = 0
    max_divergence = 0.0
    divergences = []

    for cell_gray, true_class, path in test_cells:
        # Predizione .pt (Ultralytics gestisce preprocessing internamente)
        cell_rgb = cv2.cvtColor(cell_gray, cv2.COLOR_GRAY2RGB)
        pt_result = pt_model.predict(cell_rgb, imgsz=64, verbose=False)
        pt_probs = pt_result[0].probs
        pt_class_idx = int(pt_probs.top1)
        pt_conf = float(pt_probs.top1conf)

        # Predizione .onnx (preprocessing manuale)
        onnx_input = preprocess_for_onnx(cell_gray)
        onnx_output = ort_session.run(output_names, {input_name: onnx_input})
        onnx_logits = onnx_output[0][0]
        onnx_probs = softmax(onnx_logits)
        onnx_class_idx = int(np.argmax(onnx_probs))
        onnx_conf = float(onnx_probs[onnx_class_idx])

        # Confronto
        class_match = pt_class_idx == onnx_class_idx
        conf_diff = abs(pt_conf - onnx_conf)
        max_divergence = max(max_divergence, conf_diff)

        if class_match:
            matches += 1
        else:
            mismatches += 1
            divergences.append({
                "path": path,
                "true": true_class,
                "pt_class": pt_model.names[pt_class_idx],
                "pt_conf": round(pt_conf, 4),
                "onnx_class": pt_model.names.get(onnx_class_idx, f"idx_{onnx_class_idx}"),
                "onnx_conf": round(onnx_conf, 4),
            })

    # Report
    total = matches + mismatches
    match_rate = matches / total * 100 if total > 0 else 0

    print(f"\n📊 Risultati validazione:")
    print(f"   Celle testate:     {total}")
    print(f"   Match classe:      {matches}/{total} ({match_rate:.1f}%)")
    print(f"   Mismatch classe:   {mismatches}")
    print(f"   Max div. confidence: {max_divergence:.6f}")

    if divergences:
        print(f"\n⚠️  Discrepanze trovate:")
        for d in divergences[:10]:
            print(f"   {Path(d['path']).name}: "
                  f"PT={d['pt_class']}({d['pt_conf']}) vs "
                  f"ONNX={d['onnx_class']}({d['onnx_conf']})")

    if match_rate >= 99.0 and max_divergence < 0.01:
        print(f"\n✅ Validazione SUPERATA — ONNX e PT sono equivalenti")
        return True
    elif match_rate >= 95.0:
        print(f"\n⚠️  Validazione OK con warning — piccole divergenze rilevate")
        return True
    else:
        print(f"\n❌ Validazione FALLITA — ONNX e PT producono risultati diversi!")
        print("   Possibili cause:")
        print("   1. Preprocessing ONNX diverso da Ultralytics")
        print("   2. Export ONNX con opset incompatibile")
        print("   3. Problemi di precisione numerica")
        return False


if __name__ == "__main__":
    success = validate()
    sys.exit(0 if success else 1)
