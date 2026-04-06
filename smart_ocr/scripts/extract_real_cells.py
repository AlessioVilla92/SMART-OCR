"""
scripts/extract_real_cells.py

Estrae celle etichettate automaticamente da foto reali usando il baseline subtraction.
Le celle vengono salvate in data/real_cells/{segnato,vuoto}/ per il retraining.

Strategia:
1. Processa ogni foto con la pipeline v2.1 (boundary → preprocess → align)
2. Usa baseline subtraction per classificare le celle
3. Salva solo celle con classificazione ad alta confidenza
4. Applica augmentations realistiche per simulare variabilità

Uso: python scripts/extract_real_cells.py
"""

import cv2
import numpy as np
import sys
import os
from pathlib import Path
import json

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.preprocessor import preprocess_full_pipeline, load_image
from core.boundary_detector import detect_document_boundary
from core.template_aligner import TemplateAligner
from core.grid_extractor import extract_all_cells
from core.omr_classifier import classify_all_items_baseline, count_dark_pixels


def extract_cells_from_photos(photo_page_pairs, output_dir, min_confidence=0.5):
    """
    Estrae celle etichettate dalle foto reali.

    Args:
        photo_page_pairs: lista di (path_foto, page_key)
        output_dir: directory output (es. data/real_cells/)
        min_confidence: confidenza minima per accettare label
    """
    aligner = TemplateAligner()
    for pk in ['page_4', 'page_5', 'page_6']:
        try:
            aligner.load_reference(pk)
        except FileNotFoundError:
            print(f"WARNING: reference {pk} non trovato")

    segnato_dir = Path(output_dir) / "segnato"
    vuoto_dir = Path(output_dir) / "vuoto"
    segnato_dir.mkdir(parents=True, exist_ok=True)
    vuoto_dir.mkdir(parents=True, exist_ok=True)

    stats = {"total_cells": 0, "segnato": 0, "vuoto": 0, "skipped": 0}

    for photo_path, page in photo_page_pairs:
        print(f"\nProcesso: {Path(photo_path).name} -> {page}")

        img = load_image(photo_path)
        h_img, w_img = img.shape[:2]

        # Boundary detection con confidence gate
        corners = None
        try:
            c, conf, method = detect_document_boundary(img)
            margin = 5
            on_edge = any(
                pt[0] < margin or pt[1] < margin or
                pt[0] > w_img - margin or pt[1] > h_img - margin
                for pt in c
            )
            if not on_edge and conf >= 0.5:
                corners = c
        except Exception:
            pass

        warped = warp_to_a4(img, corners) if corners else img
        gray, _ = preprocess_full_pipeline(warped)

        aligned, info = aligner.align(gray, page)
        if info['aligned']:
            gray = aligned
            print(f"  Alignment: {info['method']}, matches={info['good_matches']}")
        else:
            print(f"  Alignment FALLITO, skip")
            continue

        # Estrai celle da foto e reference
        cells = extract_all_cells(gray, page)
        ref = aligner._references[page]
        ref_cells = extract_all_cells(ref, page)

        # Classifica con baseline subtraction
        results = classify_all_items_baseline(cells, ref_cells)

        for item_id, result in results.items():
            value = result.get('value')
            flag = result.get('flag')
            confidence = result.get('confidence', 0)
            deltas = result.get('deltas', {})

            if flag in ('multiple_marks', 'ambiguous'):
                stats["skipped"] += 3
                continue

            for col in ['0', '1', '2']:
                if col not in cells.get(item_id, {}):
                    continue

                cell = cells[item_id][col]
                delta = deltas.get(col, 0)
                stats["total_cells"] += 1

                # Determina label
                is_marked = (value is not None and col == str(value))

                if is_marked and delta >= 0.04:
                    # Cella marcata con buona evidenza
                    label = "segnato"
                    fname = f"{page}_{item_id}_col{col}.png"
                    cv2.imwrite(str(segnato_dir / fname), cell)
                    stats["segnato"] += 1
                elif not is_marked and delta < 0.03:
                    # Cella vuota con buona evidenza
                    label = "vuoto"
                    fname = f"{page}_{item_id}_col{col}.png"
                    cv2.imwrite(str(vuoto_dir / fname), cell)
                    stats["vuoto"] += 1
                else:
                    stats["skipped"] += 1

        scored = sum(1 for r in results.values() if r['value'] is not None)
        print(f"  Items scored: {scored}/{len(results)}")

    print(f"\n=== RISULTATI ESTRAZIONE ===")
    print(f"Celle totali:    {stats['total_cells']}")
    print(f"Segnato (label): {stats['segnato']}")
    print(f"Vuoto (label):   {stats['vuoto']}")
    print(f"Skipped:         {stats['skipped']}")

    return stats


def augment_real_cells(input_dir, output_dir, augmentations_per_image=10):
    """
    Augmenta le celle reali con trasformazioni realistiche.

    Trasformazioni specifiche per foto reali:
    - Shift leggero (±3px) — simula disallineamento
    - Rotazione (±5°) — foto non perfettamente dritta
    - Blur leggero — autofocus imperfetto
    - Rumore gaussiano — sensore camera
    - Variazione luminosita — illuminazione variabile
    """
    try:
        import albumentations as A
    except ImportError:
        print("albumentations non disponibile, skip augmentation")
        return

    transform = A.Compose([
        A.ShiftScaleRotate(
            shift_limit=0.05,     # ±3px su 64x64
            scale_limit=0.1,      # ±10% scala
            rotate_limit=5,       # ±5 gradi
            border_mode=cv2.BORDER_REPLICATE,
            p=0.8
        ),
        A.OneOf([
            A.GaussianBlur(blur_limit=(3, 5), p=1.0),
            A.MotionBlur(blur_limit=3, p=1.0),
        ], p=0.4),
        A.GaussNoise(std_range=(0.02, 0.08), p=0.3),
        A.RandomBrightnessContrast(
            brightness_limit=0.2,
            contrast_limit=0.2,
            p=0.6
        ),
        A.Perspective(scale=(0.01, 0.03), p=0.2),
    ])

    input_path = Path(input_dir)
    output_path = Path(output_dir)

    for class_name in ['segnato', 'vuoto']:
        src_dir = input_path / class_name
        dst_dir = output_path / class_name
        dst_dir.mkdir(parents=True, exist_ok=True)

        if not src_dir.exists():
            continue

        images = list(src_dir.glob("*.png"))
        print(f"\nAugmenting {class_name}: {len(images)} immagini x {augmentations_per_image} = {len(images) * augmentations_per_image}")

        for img_path in images:
            img = cv2.imread(str(img_path), cv2.IMREAD_GRAYSCALE)
            if img is None:
                continue

            # Copia originale
            cv2.imwrite(str(dst_dir / img_path.name), img)

            # Genera augmentazioni
            for i in range(augmentations_per_image):
                aug = transform(image=img)['image']
                aug_name = f"{img_path.stem}_aug{i:02d}.png"
                cv2.imwrite(str(dst_dir / aug_name), aug)

    print("\nAugmentation completata.")


def warp_to_a4(img, corners):
    """Wrapper per import circolare."""
    from core.boundary_detector import warp_to_a4 as _warp
    return _warp(img, corners)


if __name__ == "__main__":
    project_root = Path(__file__).parent.parent.parent

    # Foto di test disponibili (mappatura verificata)
    test4_dir = project_root / "test4"
    test1_dir = project_root / "TEST1"

    photo_page_pairs = []

    # test4: foto recenti (aprile 2026)
    if test4_dir.exists():
        photo_page_pairs.extend([
            (str(test4_dir / "WhatsApp Image 2026-04-03 at 13.00.26 (2).jpeg"), "page_4"),
            (str(test4_dir / "WhatsApp Image 2026-04-03 at 13.00.26 (1).jpeg"), "page_5"),
            (str(test4_dir / "WhatsApp Image 2026-04-03 at 13.00.26.jpeg"), "page_6"),
        ])

    # TEST1: foto storiche (marzo 2026)
    if test1_dir.exists():
        test1_photos = sorted(test1_dir.glob("*.jpeg"))
        # Assegnazione pagine: da verificare
        for i, photo in enumerate(test1_photos):
            page = f"page_{4 + i}" if i < 3 else "page_4"
            photo_page_pairs.append((str(photo), page))

    if not photo_page_pairs:
        print("Nessuna foto trovata in test4/ o TEST1/")
        sys.exit(1)

    print(f"Foto trovate: {len(photo_page_pairs)}")

    # Step 1: Estrai celle etichettate
    data_dir = Path(__file__).parent.parent / "data"
    real_cells_dir = data_dir / "real_cells"
    stats = extract_cells_from_photos(photo_page_pairs[:3], real_cells_dir)

    # Step 2: Augmenta
    if stats["segnato"] > 0 or stats["vuoto"] > 0:
        augmented_dir = data_dir / "real_cells_augmented"
        augment_real_cells(real_cells_dir, augmented_dir, augmentations_per_image=10)

    print("\n=== PRONTO PER RETRAINING ===")
    print("Eseguire: python training/train_svm.py")
    print("(dopo aver aggiunto real_cells_augmented a binary_generated)")
