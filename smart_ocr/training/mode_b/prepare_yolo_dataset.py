"""
training/mode_b/prepare_yolo_dataset.py

Converte il dataset esistente (raw_cells + synthetic + generated) in formato
YOLO classification per il fine-tuning di YOLOv8n.

Output:
    data/yolo_dataset/
    ├── train/
    │   ├── cerchio/
    │   ├── x_rossa/
    │   └── vuoto/
    ├── val/
    │   ├── cerchio/
    │   ├── x_rossa/
    │   └── vuoto/
    └── data.yaml

NON modifica i dati originali — solo lettura + copia.

Uso:
    python training/mode_b/prepare_yolo_dataset.py
    python training/mode_b/prepare_yolo_dataset.py --val-split 0.15
"""

import shutil
import random
import yaml
from pathlib import Path
from collections import defaultdict
import argparse
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config import Config


CLASSES = ["cerchio", "x_rossa", "vuoto"]
SOURCE_DIRS = [
    Config.DATA_DIR / "raw_cells",
    Config.DATA_DIR / "synthetic",
    Config.DATA_DIR / "generated",
    Config.DATA_DIR / "pdf_cells",
]


def collect_images() -> dict:
    """
    Raccoglie tutte le immagini etichettate da tutte le sorgenti.
    Returns: {class_name: [list of file paths]}
    """
    images = defaultdict(list)

    for source_dir in SOURCE_DIRS:
        if not source_dir.exists():
            print(f"  ⚠️  Directory non trovata: {source_dir}")
            continue

        for class_name in CLASSES:
            class_dir = source_dir / class_name
            if not class_dir.exists():
                continue

            for ext in ("*.png", "*.jpg", "*.jpeg"):
                for img_path in class_dir.glob(ext):
                    images[class_name].append(img_path)

    return dict(images)


def prepare_dataset(val_split: float = 0.20, seed: int = 42):
    """
    Crea dataset YOLO classification con split train/val stratificato.

    Args:
        val_split: percentuale dati per validazione (default 20%)
        seed: seed per riproducibilita
    """
    output_dir = Config.YOLO_DATASET_DIR
    print(f"\n📦 Preparazione dataset YOLO in: {output_dir}")
    print(f"   Split: train={1-val_split:.0%} / val={val_split:.0%}")
    print(f"   Seed: {seed}")

    # Raccogli immagini
    print("\n📂 Raccolta immagini...")
    images = collect_images()

    if not images:
        print("❌ Nessuna immagine trovata nelle directory sorgente:")
        for d in SOURCE_DIRS:
            print(f"   - {d}")
        return False

    # Statistiche pre-split
    print("\n📊 Immagini trovate:")
    total = 0
    for cls in CLASSES:
        n = len(images.get(cls, []))
        print(f"   {cls}: {n}")
        total += n
    print(f"   Totale: {total}")

    # Pulizia output precedente
    if output_dir.exists():
        print(f"\n🧹 Rimozione dataset precedente: {output_dir}")
        shutil.rmtree(output_dir)

    # Crea struttura directory
    for split in ("train", "val"):
        for cls in CLASSES:
            (output_dir / split / cls).mkdir(parents=True, exist_ok=True)

    # Split stratificato
    random.seed(seed)
    stats = {"train": defaultdict(int), "val": defaultdict(int)}

    for class_name in CLASSES:
        class_images = images.get(class_name, [])
        random.shuffle(class_images)

        n_val = max(1, int(len(class_images) * val_split))
        val_images = class_images[:n_val]
        train_images = class_images[n_val:]

        for img_path in train_images:
            dst = output_dir / "train" / class_name / img_path.name
            # Evita conflitti di nomi da sorgenti diverse
            if dst.exists():
                dst = output_dir / "train" / class_name / f"{img_path.parent.parent.name}_{img_path.name}"
            shutil.copy2(img_path, dst)
            stats["train"][class_name] += 1

        for img_path in val_images:
            dst = output_dir / "val" / class_name / img_path.name
            if dst.exists():
                dst = output_dir / "val" / class_name / f"{img_path.parent.parent.name}_{img_path.name}"
            shutil.copy2(img_path, dst)
            stats["val"][class_name] += 1

    # Genera data.yaml
    data_yaml = {
        "path": str(output_dir.resolve()),
        "train": "train",
        "val": "val",
        "nc": len(CLASSES),
        "names": CLASSES,
    }

    yaml_path = output_dir / "data.yaml"
    with open(yaml_path, "w", encoding="utf-8") as f:
        yaml.dump(data_yaml, f, default_flow_style=False, allow_unicode=True)

    # Report finale
    print("\n✅ Dataset creato:")
    print(f"   📁 {output_dir}")
    print(f"\n   {'Classe':<15} {'Train':>8} {'Val':>8} {'Totale':>8}")
    print(f"   {'─'*15} {'─'*8} {'─'*8} {'─'*8}")

    total_train = 0
    total_val = 0
    for cls in CLASSES:
        t = stats["train"][cls]
        v = stats["val"][cls]
        total_train += t
        total_val += v
        print(f"   {cls:<15} {t:>8} {v:>8} {t+v:>8}")

    print(f"   {'─'*15} {'─'*8} {'─'*8} {'─'*8}")
    print(f"   {'TOTALE':<15} {total_train:>8} {total_val:>8} {total_train+total_val:>8}")
    print(f"\n   data.yaml: {yaml_path}")

    # AVVISO CRITICO: ordine classi
    print("\n⚠️  ATTENZIONE — Ordine classi:")
    print(f"   data.yaml: {CLASSES}")
    print(f"   Config:    {list(Config.CLASSES.values())}")
    print("   Ultralytics potrebbe riordinare alfabeticamente.")
    print("   Verificare model.names dopo il training!")

    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Prepara dataset YOLO da celle etichettate")
    parser.add_argument("--val-split", type=float, default=0.20,
                        help="Percentuale dati per validazione (default: 0.20)")
    parser.add_argument("--seed", type=int, default=42,
                        help="Seed per riproducibilita (default: 42)")
    args = parser.parse_args()

    success = prepare_dataset(val_split=args.val_split, seed=args.seed)
    sys.exit(0 if success else 1)
