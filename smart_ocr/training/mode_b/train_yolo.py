"""
training/mode_b/train_yolo.py

Fine-tuning YOLOv8n per classificazione celle CBCL.
Richiede: ultralytics, torch con CUDA, GPU (RTX 3070 consigliata).

NOTA LICENZA: Ultralytics e AGPL-3.0.
  - Questo script gira SOLO sul PC sviluppatore durante il training.
  - Il modello addestrato (.pt e .onnx) e tuo e puoi distribuirlo.
  - Il codice Ultralytics NON va incluso nel software finale.

Uso:
    python training/mode_b/train_yolo.py
    python training/mode_b/train_yolo.py --epochs 50 --batch 32
"""

import json
import shutil
import time
from pathlib import Path
from datetime import datetime
import argparse
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config import Config

try:
    from ultralytics import YOLO
except ImportError:
    print("❌ Ultralytics non installato.")
    print("   Installa con: pip install ultralytics>=8.2.0")
    print("   Richiede anche: pip install torch torchvision")
    sys.exit(1)


def save_training_report(model, results, elapsed_seconds: float):
    """
    Salva metriche di training in training_report_yolo.json.
    Include class_names per il mapping corretto in inferenza.
    """
    report = {
        "timestamp": datetime.now().isoformat(),
        "model": "yolov8n-cls",
        "task": "classification",
        "dataset": str(Config.YOLO_DATASET_DIR),
        "training_time_seconds": round(elapsed_seconds, 1),
        "class_names": model.names,  # {0: "cerchio", 1: "vuoto", 2: "x_rossa"} o simile
        "num_classes": len(model.names),
    }

    # Aggiungi metriche dal results se disponibili
    if hasattr(results, 'results_dict') and results.results_dict:
        report["results"] = {
            k: float(v) if isinstance(v, (int, float)) else str(v)
            for k, v in results.results_dict.items()
        }

    report_path = Config.YOLO_TRAINING_REPORT_PATH
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"\n📊 Report training salvato: {report_path}")
    return report


def train_yolo(
    epochs: int = 100,
    batch: int = 64,
    imgsz: int = 64,
    patience: int = 20,
    device: str = "0",
    lr0: float = 0.001,
    dropout: float = 0.3,
):
    """
    Fine-tuning YOLOv8n-cls su dataset CBCL.
    """
    dataset_dir = Config.YOLO_DATASET_DIR
    data_yaml = dataset_dir / "data.yaml"

    if not data_yaml.exists():
        print("❌ Dataset YOLO non trovato.")
        print("   Eseguire prima: python training/mode_b/prepare_yolo_dataset.py")
        return False

    print("\n🏋️  Smart OCR — Training YOLOv8n Classification")
    print("=" * 55)
    print(f"   Dataset:   {dataset_dir}")
    print(f"   Epochs:    {epochs}")
    print(f"   Batch:     {batch}")
    print(f"   Image sz:  {imgsz}x{imgsz}")
    print(f"   Patience:  {patience}")
    print(f"   LR:        {lr0}")
    print(f"   Dropout:   {dropout}")
    print(f"   Device:    {'GPU ' + device if device != 'cpu' else 'CPU'}")

    # Carica modello pretrained ImageNet
    print("\n📥 Caricamento YOLOv8n-cls pretrained...")
    model = YOLO("yolov8n-cls.pt")

    # Training
    print("\n🚀 Avvio training...")
    start_time = time.time()

    results = model.train(
        data=str(dataset_dir),
        task="classify",
        epochs=epochs,
        imgsz=imgsz,
        batch=batch,
        device=device,
        patience=patience,
        lr0=lr0,
        lrf=0.01,              # Cosine decay
        weight_decay=0.0005,
        warmup_epochs=3,
        dropout=dropout,
        save=True,
        project=str(Config.MODELS_DIR / "yolo_training"),
        name="cbcl",
        exist_ok=True,
        pretrained=True,
        verbose=True,
    )

    elapsed = time.time() - start_time

    # Verifica ordine classi (CRITICO)
    print(f"\n📋 Classi nel modello addestrato: {model.names}")
    print(f"   Classi in Config: {Config.CLASSES}")
    if list(model.names.values()) != list(Config.CLASSES.values()):
        print("   ⚠️  ORDINE DIVERSO — il mapping verra gestito da yolo_classifier.py")

    # Copia best.pt come yolo_cbcl.pt
    best_pt = Config.MODELS_DIR / "yolo_training" / "cbcl" / "weights" / "best.pt"
    if best_pt.exists():
        shutil.copy2(best_pt, Config.YOLO_PT_PATH)
        print(f"\n✅ Modello salvato: {Config.YOLO_PT_PATH}")
        print(f"   Dimensione: {Config.YOLO_PT_PATH.stat().st_size / 1024 / 1024:.1f} MB")
    else:
        print(f"\n⚠️  best.pt non trovato in {best_pt}")
        # Cerca in path alternativi
        last_pt = Config.MODELS_DIR / "yolo_training" / "cbcl" / "weights" / "last.pt"
        if last_pt.exists():
            shutil.copy2(last_pt, Config.YOLO_PT_PATH)
            print(f"   Usato last.pt: {Config.YOLO_PT_PATH}")

    # Salva report
    report = save_training_report(model, results, elapsed)

    print(f"\n⏱️  Training completato in {elapsed/60:.1f} minuti")
    print(f"\n📌 Prossimo step: python training/mode_b/export_onnx.py")

    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fine-tuning YOLOv8n su celle CBCL")
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--batch", type=int, default=64)
    parser.add_argument("--imgsz", type=int, default=64)
    parser.add_argument("--patience", type=int, default=20)
    parser.add_argument("--device", type=str, default="0", help="GPU device o 'cpu'")
    parser.add_argument("--lr", type=float, default=0.001)
    parser.add_argument("--dropout", type=float, default=0.3)
    args = parser.parse_args()

    success = train_yolo(
        epochs=args.epochs,
        batch=args.batch,
        imgsz=args.imgsz,
        patience=args.patience,
        device=args.device,
        lr0=args.lr,
        dropout=args.dropout,
    )
    sys.exit(0 if success else 1)
