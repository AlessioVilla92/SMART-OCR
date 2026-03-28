"""
training/augmentor.py

Genera varianti sintetiche delle celle reali per amplificare il dataset di training.
Usa albumentations==2.0.8 (MIT license - NON aggiornare oltre questa versione).

Input:  cartelle data/raw_cells/{classe}/ con immagini reali
Output: cartelle data/synthetic/{classe}/ con N varianti per immagine

Trasformazioni applicate:
- Rotazione +/-15
- Scala 0.85-1.15
- Luminosità/contrasto +/-30%
- Sfocatura lieve (kernel 3-7px)
- Rumore gaussiano
- Distorsione prospettica lieve
- Spessore tratto (erosione/dilatazione morfologica)
"""

import cv2
import numpy as np
from pathlib import Path
import albumentations as A
from typing import Optional
import argparse


RAW_DIR = Path(__file__).parent.parent / "data" / "raw_cells"
SYNTHETIC_DIR = Path(__file__).parent.parent / "data" / "synthetic"
CLASSES = ["cerchio", "x_rossa", "vuoto"]
CELL_SIZE = (64, 64)

# Numero di varianti sintetiche per ogni immagine reale
AUGMENTATIONS_PER_IMAGE = 15


def get_augmentation_pipeline() -> A.Compose:
    """
    Pipeline di augmentazione calibrata per celle questionari CBCL.
    Ogni trasformazione simula una variabile reale (luce, mano, penna).
    """
    return A.Compose([
        # Rotazione: simula angolazione diversa del foglio o della cella
        A.Rotate(limit=15, p=0.8, border_mode=cv2.BORDER_REPLICATE),

        # Scala: simula distanza diversa della foto
        A.RandomScale(scale_limit=0.15, p=0.6),

        # Luminosità e contrasto: simula illuminazione ambiente variabile
        A.RandomBrightnessContrast(
            brightness_limit=0.3,
            contrast_limit=0.3,
            p=0.8
        ),

        # Sfocatura lieve: simula microtremito mano o autofocus imperfetto
        A.OneOf([
            A.Blur(blur_limit=3, p=0.5),
            A.GaussianBlur(blur_limit=(3, 7), p=0.5),
        ], p=0.4),

        # Rumore: simula granularità sensore fotografico
        A.GaussNoise(std_range=(0.02, 0.12), p=0.4),

        # Distorsione prospettica lieve: simula foto leggermente di sbieco
        A.Perspective(scale=(0.02, 0.05), p=0.3),

        # Ridimensionamento finale a dimensione standard
        A.Resize(height=64, width=64),
    ])


def augment_class(
    class_name: str,
    n_per_image: int = AUGMENTATIONS_PER_IMAGE,
    verbose: bool = True
) -> int:
    """
    Genera varianti sintetiche per tutte le immagini di una classe.

    Returns: numero totale immagini sintetiche generate
    """
    source_dir = RAW_DIR / class_name
    target_dir = SYNTHETIC_DIR / class_name
    target_dir.mkdir(parents=True, exist_ok=True)

    source_images = list(source_dir.glob("*.png")) + list(source_dir.glob("*.jpg"))

    if not source_images:
        print(f"⚠️  Nessuna immagine reale trovata in {source_dir}")
        return 0

    pipeline = get_augmentation_pipeline()
    generated = 0

    for img_path in source_images:
        img = cv2.imread(str(img_path), cv2.IMREAD_GRAYSCALE)
        if img is None:
            continue

        # Assicura dimensione corretta
        img = cv2.resize(img, CELL_SIZE)

        for i in range(n_per_image):
            # albumentations richiede immagine con channel dimension
            img_rgb = cv2.cvtColor(img, cv2.COLOR_GRAY2RGB)

            augmented = pipeline(image=img_rgb)
            aug_img = cv2.cvtColor(augmented["image"], cv2.COLOR_RGB2GRAY)

            # Aggiungi variante morfologica (spessore tratto)
            if i % 3 == 0:
                kernel = np.ones((2, 2), np.uint8)
                aug_img = cv2.erode(aug_img, kernel, iterations=1)  # Tratto più fino
            elif i % 3 == 1:
                kernel = np.ones((2, 2), np.uint8)
                aug_img = cv2.dilate(aug_img, kernel, iterations=1)  # Tratto più spesso

            out_name = f"{img_path.stem}_aug{i:03d}.png"
            cv2.imwrite(str(target_dir / out_name), aug_img)
            generated += 1

    if verbose:
        print(f"✅ {class_name}: {len(source_images)} reali → {generated} sintetiche")

    return generated


def run_all_augmentations(n_per_image: int = AUGMENTATIONS_PER_IMAGE):
    """Esegue augmentazione per tutte le classi."""
    print(f"\n🔄 Avvio generazione dati sintetici ({n_per_image} varianti per immagine)...")
    total = 0

    for cls in CLASSES:
        n = augment_class(cls, n_per_image)
        total += n

    print(f"\n✅ Totale immagini sintetiche generate: {total}")

    # Verifica bilanciamento classi
    print("\n📊 Distribuzione dataset:")
    for cls in CLASSES:
        real = len(list((RAW_DIR / cls).glob("*.png")))
        synth = len(list((SYNTHETIC_DIR / cls).glob("*.png")))
        print(f"   {cls}: {real} reali + {synth} sintetiche = {real + synth} totali")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=AUGMENTATIONS_PER_IMAGE,
                       help="Varianti per immagine reale")
    args = parser.parse_args()
    run_all_augmentations(args.n)
