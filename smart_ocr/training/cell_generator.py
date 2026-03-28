"""
training/cell_generator.py

Generatore di celle sintetiche realistiche per training SVM.
Crea immagini 64x64 che simulano celle CBCL marcate e vuote.

Tre classi:
  - cerchio: numero cerchiato con penna (vari stili, spessori, imperfezioni)
  - x_rossa: segno X sopra il numero (vari angoli, spessori)
  - vuoto: cella vuota con solo il numero stampato e rumore di fondo

Uso:
    python training/cell_generator.py                    # genera 500 per classe
    python training/cell_generator.py --n 1000           # genera 1000 per classe
    python training/cell_generator.py --output data/ai_cells  # cartella custom

Dopo la generazione, esegui train_svm.py per addestrare.
"""

import cv2
import numpy as np
from pathlib import Path
import argparse
from typing import Tuple


CELL_SIZE = 64
OUTPUT_DIR = Path(__file__).parent.parent / "data" / "generated"
CLASSES = ["cerchio", "x_rossa", "vuoto"]


def _random_background() -> np.ndarray:
    """Sfondo realistico: carta bianca con leggero rumore."""
    # Base: bianco/grigio chiaro con variazione
    base = np.random.randint(220, 250)
    bg = np.full((CELL_SIZE, CELL_SIZE), base, dtype=np.uint8)

    # Rumore gaussiano lieve (grana carta)
    noise = np.random.normal(0, 3, (CELL_SIZE, CELL_SIZE)).astype(np.int16)
    bg = np.clip(bg.astype(np.int16) + noise, 0, 255).astype(np.uint8)

    return bg


def _draw_printed_number(img: np.ndarray) -> np.ndarray:
    """Aggiunge un numero stampato (come nel questionario CBCL)."""
    # Numero stampato: 0, 1, o 2
    num = str(np.random.choice([0, 1, 2]))

    # Font variabile per simulare stampe diverse
    font = np.random.choice([
        cv2.FONT_HERSHEY_SIMPLEX,
        cv2.FONT_HERSHEY_DUPLEX,
    ])
    scale = np.random.uniform(0.5, 0.8)
    thickness = np.random.choice([1, 1, 2])

    # Colore: grigio chiaro (numero stampato, non scritto a mano)
    color = np.random.randint(140, 180)

    # Posizione centrata con leggero offset casuale
    text_size = cv2.getTextSize(num, font, scale, thickness)[0]
    x = (CELL_SIZE - text_size[0]) // 2 + np.random.randint(-5, 6)
    y = (CELL_SIZE + text_size[1]) // 2 + np.random.randint(-5, 6)

    cv2.putText(img, num, (x, y), font, scale, int(color), thickness)
    return img


def _add_paper_artifacts(img: np.ndarray) -> np.ndarray:
    """Aggiunge artefatti realistici: ombre, macchie, linee griglia."""
    # Possibile linea griglia (bordo cella)
    if np.random.random() < 0.4:
        color = np.random.randint(180, 210)
        thickness = 1
        side = np.random.choice(["top", "bottom", "left", "right"])
        if side == "top":
            cv2.line(img, (0, 0), (CELL_SIZE, 0), int(color), thickness)
        elif side == "bottom":
            cv2.line(img, (0, CELL_SIZE-1), (CELL_SIZE, CELL_SIZE-1), int(color), thickness)
        elif side == "left":
            cv2.line(img, (0, 0), (0, CELL_SIZE), int(color), thickness)
        elif side == "right":
            cv2.line(img, (CELL_SIZE-1, 0), (CELL_SIZE-1, CELL_SIZE), int(color), thickness)

    # Possibile ombra leggera
    if np.random.random() < 0.2:
        gradient = np.linspace(0, -15, CELL_SIZE).astype(np.int16)
        if np.random.random() < 0.5:
            img = np.clip(img.astype(np.int16) + gradient[np.newaxis, :], 0, 255).astype(np.uint8)
        else:
            img = np.clip(img.astype(np.int16) + gradient[:, np.newaxis], 0, 255).astype(np.uint8)

    return img


def generate_cerchio() -> np.ndarray:
    """
    Genera cella con cerchio disegnato a mano.
    Simula vari stili: cerchio completo, ovale, incompleto, doppio tratto.
    """
    img = _random_background()
    img = _draw_printed_number(img)

    # Centro e raggio con variazione
    cx = CELL_SIZE // 2 + np.random.randint(-6, 7)
    cy = CELL_SIZE // 2 + np.random.randint(-6, 7)
    radius_x = np.random.randint(14, 26)
    radius_y = np.random.randint(14, 26)

    # Colore penna: blu scuro o nero
    pen_color = np.random.randint(20, 80)
    thickness = np.random.choice([1, 2, 2, 3])

    # Angolo di rotazione dell'ellisse
    angle = np.random.uniform(-20, 20)

    # Stile cerchio
    style = np.random.choice(["full", "full", "full", "arc", "double"])

    if style == "full":
        cv2.ellipse(img, (cx, cy), (radius_x, radius_y), angle, 0, 360, int(pen_color), thickness)
    elif style == "arc":
        # Cerchio incompleto (80-95% dell'arco)
        start = np.random.randint(0, 40)
        end = start + np.random.randint(290, 350)
        cv2.ellipse(img, (cx, cy), (radius_x, radius_y), angle, start, end, int(pen_color), thickness)
    elif style == "double":
        # Doppio tratto (cerchio passato due volte)
        cv2.ellipse(img, (cx, cy), (radius_x, radius_y), angle, 0, 360, int(pen_color), thickness)
        offset = np.random.randint(1, 3)
        cv2.ellipse(img, (cx + offset, cy + offset), (radius_x - 1, radius_y - 1),
                     angle + 2, 0, 360, int(pen_color), max(1, thickness - 1))

    # Tratto a mano: leggera deformazione con rumore
    if np.random.random() < 0.3:
        kernel = np.ones((2, 2), np.uint8)
        if np.random.random() < 0.5:
            img = cv2.dilate(img, kernel, iterations=1)

    img = _add_paper_artifacts(img)
    return img


def generate_x_rossa() -> np.ndarray:
    """
    Genera cella con segno X.
    Simula vari stili: X netta, X storta, X con tratti di penna variabili.
    """
    img = _random_background()
    img = _draw_printed_number(img)

    # Colore penna
    pen_color = np.random.randint(20, 80)
    thickness = np.random.choice([2, 2, 3, 3, 4])

    # Margini variabili
    margin = np.random.randint(6, 16)

    # Punti con variazione (simula mano imprecisa)
    jitter = lambda: np.random.randint(-4, 5)

    x1, y1 = margin + jitter(), margin + jitter()
    x2, y2 = CELL_SIZE - margin + jitter(), CELL_SIZE - margin + jitter()
    x3, y3 = CELL_SIZE - margin + jitter(), margin + jitter()
    x4, y4 = margin + jitter(), CELL_SIZE - margin + jitter()

    # Prima linea della X
    cv2.line(img, (x1, y1), (x2, y2), int(pen_color), thickness)
    # Seconda linea della X
    cv2.line(img, (x3, y3), (x4, y4), int(pen_color), thickness)

    # Variante: a volte una linea è più marcata
    if np.random.random() < 0.3:
        cv2.line(img, (x1 + 1, y1 + 1), (x2 + 1, y2 + 1), int(pen_color), max(1, thickness - 1))

    img = _add_paper_artifacts(img)
    return img


def generate_vuoto() -> np.ndarray:
    """
    Genera cella vuota.
    Solo il numero stampato + rumore di fondo, nessun segno a mano.
    """
    img = _random_background()
    img = _draw_printed_number(img)

    # A volte piccoli artefatti (ma MAI un segno intenzionale)
    if np.random.random() < 0.15:
        # Piccolo punto (polvere/macchia)
        px = np.random.randint(5, CELL_SIZE - 5)
        py = np.random.randint(5, CELL_SIZE - 5)
        cv2.circle(img, (px, py), np.random.randint(1, 3), np.random.randint(150, 200), -1)

    img = _add_paper_artifacts(img)
    return img


# Mappa classe -> funzione generatrice
GENERATORS = {
    "cerchio": generate_cerchio,
    "x_rossa": generate_x_rossa,
    "vuoto": generate_vuoto,
}


def generate_dataset(
    n_per_class: int = 500,
    output_dir: Path = OUTPUT_DIR,
    verbose: bool = True
) -> dict:
    """
    Genera un dataset completo di celle sintetiche.

    Args:
        n_per_class: numero di immagini per classe
        output_dir: cartella di output
        verbose: stampa progresso

    Returns: {classe: n_generati}
    """
    stats = {}

    for class_name, generator_fn in GENERATORS.items():
        class_dir = output_dir / class_name
        class_dir.mkdir(parents=True, exist_ok=True)

        for i in range(n_per_class):
            cell = generator_fn()
            filename = f"gen_{class_name}_{i:05d}.png"
            cv2.imwrite(str(class_dir / filename), cell)

        stats[class_name] = n_per_class

        if verbose:
            print(f"  ✅ {class_name}: {n_per_class} celle generate in {class_dir}")

    return stats


def merge_into_training(source_dir: Path = OUTPUT_DIR):
    """
    Copia le celle generate nelle cartelle di training (data/raw_cells/).
    Questo le rende disponibili per augmentor.py e train_svm.py.
    """
    import shutil

    raw_dir = Path(__file__).parent.parent / "data" / "raw_cells"

    total = 0
    for class_name in CLASSES:
        src = source_dir / class_name
        dst = raw_dir / class_name
        dst.mkdir(parents=True, exist_ok=True)

        if not src.exists():
            continue

        for img_path in src.glob("*.png"):
            shutil.copy2(str(img_path), str(dst / img_path.name))
            total += 1

    print(f"  ✅ Copiate {total} celle in {raw_dir}")
    return total


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Genera celle sintetiche per training CBCL")
    parser.add_argument("--n", type=int, default=500, help="Celle per classe (default: 500)")
    parser.add_argument("--output", type=str, default=None, help="Cartella output")
    parser.add_argument("--merge", action="store_true", help="Copia anche in data/raw_cells/")
    args = parser.parse_args()

    output = Path(args.output) if args.output else OUTPUT_DIR

    print(f"\n🎨 Generazione celle sintetiche ({args.n} per classe)...")
    print(f"   Output: {output}\n")

    stats = generate_dataset(n_per_class=args.n, output_dir=output)

    print(f"\n📊 Riepilogo:")
    for cls, n in stats.items():
        print(f"   {cls}: {n}")
    print(f"   Totale: {sum(stats.values())}")

    if args.merge:
        print(f"\n📦 Merge in data/raw_cells/...")
        merge_into_training(output)

    print(f"\n✅ Fatto! Prossimi passi:")
    print(f"   1. python training/augmentor.py    (genera varianti)")
    print(f"   2. python training/train_svm.py    (addestra modello)")
