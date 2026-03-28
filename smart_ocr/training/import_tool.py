"""
training/import_tool.py

Tool per importare esempi di training da sorgenti esterne:
1. IMPORT DA CARTELLA: importa immagini già classificate da cartelle nominate per classe
2. AUTO-LABELING: carica foto CBCL compilate, estrae celle, classifica con OMR,
   e salva automaticamente nelle cartelle di training
3. IMPORT AI: accetta immagini generate da AI (DALL-E, Midjourney, ecc.)
   organizzate per classe

Uso:
    python training/import_tool.py --from-folder /path/to/labeled_cells
    python training/import_tool.py --auto-label /path/to/cbcl_photos --page page_4
    python training/import_tool.py --from-ai /path/to/ai_generated

Struttura cartella attesa per --from-folder e --from-ai:
    cartella/
    ├── cerchio/    (immagini di celle cerchiate)
    ├── x_rossa/    (immagini di celle con X)
    └── vuoto/      (immagini di celle vuote)
"""

import cv2
import numpy as np
import shutil
from pathlib import Path
import argparse
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

CELL_SIZE = (64, 64)
CLASSES = ["cerchio", "x_rossa", "vuoto"]
RAW_DIR = Path(__file__).parent.parent / "data" / "raw_cells"


def import_from_folder(source_dir: Path, resize: bool = True, verbose: bool = True) -> dict:
    """
    Importa immagini da cartelle nominate per classe.

    Args:
        source_dir: cartella con sottocartelle cerchio/, x_rossa/, vuoto/
        resize: se True, ridimensiona a 64x64
        verbose: stampa progresso

    Returns: {classe: n_importate}
    """
    stats = {}

    for class_name in CLASSES:
        src_class = source_dir / class_name
        dst_class = RAW_DIR / class_name
        dst_class.mkdir(parents=True, exist_ok=True)

        if not src_class.exists():
            if verbose:
                print(f"  ⚠️  Cartella {src_class} non trovata, skip")
            stats[class_name] = 0
            continue

        images = list(src_class.glob("*.png")) + list(src_class.glob("*.jpg")) + list(src_class.glob("*.jpeg"))
        count = 0

        for img_path in images:
            if resize:
                img = cv2.imread(str(img_path), cv2.IMREAD_GRAYSCALE)
                if img is None:
                    continue
                img = cv2.resize(img, CELL_SIZE)
                out_name = f"import_{class_name}_{img_path.stem}.png"
                cv2.imwrite(str(dst_class / out_name), img)
            else:
                shutil.copy2(str(img_path), str(dst_class / img_path.name))
            count += 1

        stats[class_name] = count
        if verbose:
            print(f"  ✅ {class_name}: {count} immagini importate")

    return stats


def auto_label_from_photos(
    photos_dir: Path,
    page: str = "page_4",
    confidence_threshold: float = 0.5,
    verbose: bool = True
) -> dict:
    """
    Auto-labeling: carica foto CBCL, estrae celle, classifica con OMR,
    e salva nelle cartelle di training.

    Solo celle con alta confidence vengono salvate (le ambigue sono scartate).

    Args:
        photos_dir: cartella con foto CBCL compilate (.jpg, .png)
        page: pagina da estrarre
        confidence_threshold: minimo confidence per accettare auto-label

    Returns: {classe: n_auto_labeled}
    """
    from core.preprocessor import preprocess_full_pipeline
    from core.grid_extractor import extract_all_cells
    from core.omr_classifier import classify_all_items_omr

    photos = list(photos_dir.glob("*.jpg")) + list(photos_dir.glob("*.jpeg")) + list(photos_dir.glob("*.png"))

    if not photos:
        print(f"  ⚠️  Nessuna foto trovata in {photos_dir}")
        return {}

    stats = {"cerchio": 0, "x_rossa": 0, "vuoto": 0, "scartate": 0}
    import time

    for photo_path in photos:
        if verbose:
            print(f"\n  📷 {photo_path.name}...")

        try:
            gray, meta = preprocess_full_pipeline(str(photo_path))
            cells = extract_all_cells(gray, page)
            results = classify_all_items_omr(cells)
        except Exception as e:
            print(f"    ❌ Errore: {e}")
            continue

        for item_id, result in results.items():
            item_cells = cells[item_id]

            if result["flag"] is not None:
                stats["scartate"] += len(item_cells)
                continue

            # Determina la classe per ogni cella
            marked_col = result.get("marked_column")
            confidence = result.get("confidence", 0)

            if confidence < confidence_threshold:
                stats["scartate"] += len(item_cells)
                continue

            for col_label, cell_img in item_cells.items():
                if col_label == marked_col:
                    # Cella marcata — classe "cerchio" (non distinguiamo cerchio da X in OMR)
                    label = "cerchio"
                else:
                    label = "vuoto"

                dst_dir = RAW_DIR / label
                dst_dir.mkdir(parents=True, exist_ok=True)

                timestamp = int(time.time() * 1000)
                filename = f"auto_{photo_path.stem}_item{item_id}_col{col_label}_{timestamp}.png"
                cv2.imwrite(str(dst_dir / filename), cell_img)
                stats[label] += 1

        if verbose:
            scored = sum(1 for r in results.values() if r["value"] is not None)
            print(f"    Processati: {len(results)} items, {scored} risposte trovate")

    return stats


def import_ai_generated(
    ai_dir: Path,
    resize: bool = True,
    verbose: bool = True
) -> dict:
    """
    Importa immagini generate da AI.
    Identico a import_from_folder ma con prefisso 'ai_' nei nomi file.

    La cartella deve avere sottocartelle: cerchio/, x_rossa/, vuoto/
    Le immagini possono essere di qualsiasi dimensione (verranno ridimensionate a 64x64).
    """
    stats = {}

    for class_name in CLASSES:
        src_class = ai_dir / class_name
        dst_class = RAW_DIR / class_name
        dst_class.mkdir(parents=True, exist_ok=True)

        if not src_class.exists():
            if verbose:
                print(f"  ⚠️  {src_class} non trovata")
            stats[class_name] = 0
            continue

        images = (list(src_class.glob("*.png")) + list(src_class.glob("*.jpg")) +
                  list(src_class.glob("*.jpeg")) + list(src_class.glob("*.webp")))
        count = 0

        for img_path in images:
            img = cv2.imread(str(img_path), cv2.IMREAD_GRAYSCALE)
            if img is None:
                # Prova con Pillow (per webp e formati non standard)
                try:
                    from PIL import Image
                    pil_img = Image.open(img_path).convert("L")
                    img = np.array(pil_img)
                except Exception:
                    continue

            if resize:
                img = cv2.resize(img, CELL_SIZE)

            out_name = f"ai_{class_name}_{img_path.stem}.png"
            cv2.imwrite(str(dst_class / out_name), img)
            count += 1

        stats[class_name] = count
        if verbose:
            print(f"  ✅ {class_name}: {count} immagini AI importate")

    return stats


def show_training_stats():
    """Mostra statistiche del dataset di training corrente."""
    print("\n📊 Dataset di training corrente:")
    print(f"   Cartella: {RAW_DIR}\n")

    total = 0
    for class_name in CLASSES + ["ambiguo"]:
        class_dir = RAW_DIR / class_name
        if class_dir.exists():
            count = len(list(class_dir.glob("*.png")))
        else:
            count = 0
        total += count

        # Conta per tipo
        gen_count = len(list(class_dir.glob("gen_*.png"))) if class_dir.exists() else 0
        auto_count = len(list(class_dir.glob("auto_*.png"))) if class_dir.exists() else 0
        ai_count = len(list(class_dir.glob("ai_*.png"))) if class_dir.exists() else 0
        import_count = len(list(class_dir.glob("import_*.png"))) if class_dir.exists() else 0
        manual_count = count - gen_count - auto_count - ai_count - import_count

        bar = "█" * min(count // 10, 40)
        print(f"   {class_name:12s}: {count:5d} {bar}")
        if count > 0:
            parts = []
            if manual_count > 0:
                parts.append(f"manual:{manual_count}")
            if gen_count > 0:
                parts.append(f"generated:{gen_count}")
            if auto_count > 0:
                parts.append(f"auto:{auto_count}")
            if ai_count > 0:
                parts.append(f"ai:{ai_count}")
            if import_count > 0:
                parts.append(f"imported:{import_count}")
            print(f"                     ({', '.join(parts)})")

    print(f"\n   Totale: {total}")

    # Check minimo per training
    min_needed = 30
    ready = all(
        len(list((RAW_DIR / cls).glob("*.png"))) >= min_needed
        for cls in CLASSES
        if (RAW_DIR / cls).exists()
    )

    if total == 0:
        print(f"\n   ❌ Dataset vuoto. Genera esempi con:")
        print(f"      python training/cell_generator.py --n 500 --merge")
    elif not ready:
        print(f"\n   ⚠️  Serve almeno {min_needed} celle per classe per il training.")
    else:
        print(f"\n   ✅ Dataset pronto per il training!")
        print(f"      python training/train_svm.py")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Import tool per training CBCL")
    parser.add_argument("--from-folder", type=str, help="Importa da cartella con sottocartelle cerchio/x_rossa/vuoto")
    parser.add_argument("--from-ai", type=str, help="Importa immagini generate da AI")
    parser.add_argument("--auto-label", type=str, help="Auto-labeling da foto CBCL compilate")
    parser.add_argument("--page", type=str, default="page_4", help="Pagina per auto-label")
    parser.add_argument("--stats", action="store_true", help="Mostra statistiche dataset")
    args = parser.parse_args()

    if args.stats or not any([args.from_folder, args.from_ai, args.auto_label]):
        show_training_stats()

    if args.from_folder:
        print(f"\n📂 Import da cartella: {args.from_folder}")
        stats = import_from_folder(Path(args.from_folder))
        print(f"\n   Totale importate: {sum(stats.values())}")

    if args.from_ai:
        print(f"\n🤖 Import AI: {args.from_ai}")
        stats = import_ai_generated(Path(args.from_ai))
        print(f"\n   Totale importate: {sum(stats.values())}")

    if args.auto_label:
        print(f"\n🏷️  Auto-labeling da foto: {args.auto_label} (pagina: {args.page})")
        stats = auto_label_from_photos(Path(args.auto_label), page=args.page)
        print(f"\n   Risultati:")
        for k, v in stats.items():
            print(f"     {k}: {v}")

    if any([args.from_folder, args.from_ai, args.auto_label]):
        print()
        show_training_stats()
