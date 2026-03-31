"""
training/mode_b/export_onnx.py

Esporta il modello YOLOv8n addestrato (.pt) in formato ONNX per la distribuzione.
Il file .onnx NON richiede PyTorch o Ultralytics per l'inferenza.

Uso:
    python training/mode_b/export_onnx.py
"""

import shutil
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config import Config

try:
    from ultralytics import YOLO
except ImportError:
    print("❌ Ultralytics non installato.")
    print("   Installa con: pip install ultralytics>=8.2.0")
    sys.exit(1)


def export_onnx():
    """Esporta yolo_cbcl.pt → yolo_cbcl.onnx"""

    pt_path = Config.YOLO_PT_PATH
    if not pt_path.exists():
        print(f"❌ Modello .pt non trovato: {pt_path}")
        print("   Eseguire prima: python training/mode_b/train_yolo.py")
        return False

    print(f"\n📦 Export ONNX")
    print(f"   Input:  {pt_path}")
    print(f"   Output: {Config.YOLO_ONNX_PATH}")

    # Carica modello
    model = YOLO(str(pt_path))

    # Stampa ordine classi per verifica
    print(f"\n📋 Classi nel modello: {model.names}")

    # Export ONNX
    model.export(
        format="onnx",
        imgsz=64,
        dynamic=False,      # Shape statica per compatibilita massima
        simplify=True,       # Ottimizza il grafo ONNX
        opset=17,            # Compatibile con onnxruntime >= 1.18
    )

    # Il file .onnx viene creato accanto al .pt con stesso nome
    exported_onnx = pt_path.with_suffix(".onnx")
    if exported_onnx.exists():
        shutil.copy2(exported_onnx, Config.YOLO_ONNX_PATH)
        size_mb = Config.YOLO_ONNX_PATH.stat().st_size / 1024 / 1024
        print(f"\n✅ Modello ONNX salvato: {Config.YOLO_ONNX_PATH}")
        print(f"   Dimensione: {size_mb:.1f} MB")

        # Aggiorna report con info ONNX
        _update_report_with_onnx_info()
    else:
        print(f"\n⚠️  File .onnx non trovato dopo export: {exported_onnx}")
        return False

    print(f"\n📌 Prossimo step: python training/mode_b/validate_onnx.py")
    return True


def _update_report_with_onnx_info():
    """Aggiunge info ONNX al training report."""
    report_path = Config.YOLO_TRAINING_REPORT_PATH
    if not report_path.exists():
        return

    try:
        with open(report_path, "r", encoding="utf-8") as f:
            report = json.load(f)

        report["onnx_exported"] = True
        report["onnx_path"] = str(Config.YOLO_ONNX_PATH)
        report["onnx_size_bytes"] = Config.YOLO_ONNX_PATH.stat().st_size

        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


if __name__ == "__main__":
    success = export_onnx()
    sys.exit(0 if success else 1)
