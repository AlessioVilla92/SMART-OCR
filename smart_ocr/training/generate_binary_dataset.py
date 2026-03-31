"""
training/generate_binary_dataset.py

Genera dataset binario per classificazione SEGNATO vs VUOTO.
Include TUTTI i tipi di mark possibili nella classe "segnato":
- Cerchi (aperti, chiusi, ovali, irregolari)
- X (dritte, storte, parziali)
- Spunte/check
- Tratti di penna (diagonali, orizzontali, verticali)
- Annerimenti/colorazioni (parziali, totali)
- Puntini/macchie intenzionali
- Scarabocchi
- Quadratini pieni
- Sottolineature del numero

La classe "vuoto" include:
- Celle completamente vuote
- Celle con artefatti minimi (polvere, texture carta, ombre)
- Celle con tracce di cancellatura leggera

Uso:
    python training/generate_binary_dataset.py
    python training/generate_binary_dataset.py --n 1500
"""

import cv2
import numpy as np
from pathlib import Path
import argparse
import sys

CELL_SIZE = 64
_cell_clahe = cv2.createCLAHE(clipLimit=1.5, tileGridSize=(2, 2))

SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPT_DIR.parent
OUTPUT_DIR = PROJECT_DIR / "data" / "binary_generated"


def _paper_background() -> np.ndarray:
    """Sfondo carta realistico con variazioni."""
    base = np.random.randint(200, 248)
    bg = np.full((CELL_SIZE, CELL_SIZE), base, dtype=np.uint8)

    # Gradiente leggero (illuminazione non uniforme)
    if np.random.random() < 0.4:
        grad = np.linspace(0, np.random.randint(3, 15), CELL_SIZE).astype(np.int16)
        if np.random.random() < 0.5:
            bg = np.clip(bg.astype(np.int16) + grad[np.newaxis, :], 0, 255).astype(np.uint8)
        else:
            bg = np.clip(bg.astype(np.int16) + grad[:, np.newaxis], 0, 255).astype(np.uint8)

    # Rumore gaussiano
    noise = np.random.normal(0, np.random.uniform(1.5, 5), (CELL_SIZE, CELL_SIZE)).astype(np.int16)
    bg = np.clip(bg.astype(np.int16) + noise, 0, 255).astype(np.uint8)
    return bg


def _draw_printed_number(img: np.ndarray) -> np.ndarray:
    """Disegna il numero stampato (0, 1, o 2) come nel questionario."""
    num = str(np.random.choice([0, 1, 2]))
    font = np.random.choice([
        cv2.FONT_HERSHEY_SIMPLEX, cv2.FONT_HERSHEY_DUPLEX,
        cv2.FONT_HERSHEY_COMPLEX, cv2.FONT_HERSHEY_TRIPLEX,
    ])
    scale = np.random.uniform(0.45, 0.85)
    thickness = np.random.choice([1, 1, 2])
    color = np.random.randint(130, 195)
    text_size = cv2.getTextSize(num, font, scale, thickness)[0]
    x = (CELL_SIZE - text_size[0]) // 2 + np.random.randint(-6, 7)
    y = (CELL_SIZE + text_size[1]) // 2 + np.random.randint(-6, 7)
    cv2.putText(img, num, (x, y), font, scale, int(color), thickness)
    return img


def _add_border_artifacts(img: np.ndarray) -> np.ndarray:
    """Bordi griglia e artefatti realistici."""
    if np.random.random() < 0.4:
        color = np.random.randint(180, 220)
        t = np.random.choice([1, 1, 2])
        sides = np.random.choice(["top", "bottom", "left", "right"])
        if sides == "top":
            cv2.line(img, (0, 0), (CELL_SIZE, 0), int(color), t)
        elif sides == "bottom":
            cv2.line(img, (0, CELL_SIZE-1), (CELL_SIZE, CELL_SIZE-1), int(color), t)
        elif sides == "left":
            cv2.line(img, (0, 0), (0, CELL_SIZE), int(color), t)
        elif sides == "right":
            cv2.line(img, (CELL_SIZE-1, 0), (CELL_SIZE-1, CELL_SIZE), int(color), t)
    return img


def _random_pen_color() -> int:
    """Colore inchiostro variabile (penna nera, blu, rossa in grayscale)."""
    return np.random.randint(10, 100)


def _jitter(v=5):
    return np.random.randint(-v, v + 1)


# ============================================================
# GENERATORI CLASSE "SEGNATO"
# ============================================================

def gen_cerchio(img):
    """Cerchio attorno al numero."""
    cx = 32 + _jitter(7)
    cy = 32 + _jitter(7)
    rx = np.random.randint(13, 27)
    ry = np.random.randint(13, 27)
    color = _random_pen_color()
    t = np.random.choice([1, 2, 2, 3, 3, 4])
    angle = np.random.uniform(-20, 20)

    if np.random.random() < 0.7:
        cv2.ellipse(img, (cx, cy), (rx, ry), angle, 0, 360, color, t)
    else:
        start = np.random.randint(0, 30)
        end = start + np.random.randint(280, 355)
        cv2.ellipse(img, (cx, cy), (rx, ry), angle, start, end, color, t)
    return img


def gen_x_mark(img):
    """Segno X."""
    color = _random_pen_color()
    t = np.random.choice([1, 2, 2, 3, 3, 4, 5])
    m = np.random.randint(5, 18)
    j = _jitter
    cv2.line(img, (m+j(), m+j()), (CELL_SIZE-m+j(), CELL_SIZE-m+j()), color, t)
    cv2.line(img, (CELL_SIZE-m+j(), m+j()), (m+j(), CELL_SIZE-m+j()), color, t)
    return img


def gen_checkmark(img):
    """Spunta / check mark."""
    color = _random_pen_color()
    t = np.random.choice([2, 2, 3, 3, 4])
    # V shape
    start_x = np.random.randint(8, 20)
    mid_x = np.random.randint(25, 38)
    end_x = np.random.randint(44, 58)
    start_y = np.random.randint(20, 35)
    mid_y = np.random.randint(40, 55)
    end_y = np.random.randint(10, 25)
    cv2.line(img, (start_x, start_y), (mid_x, mid_y), color, t)
    cv2.line(img, (mid_x, mid_y), (end_x, end_y), color, t)
    return img


def gen_diagonal_stroke(img):
    """Tratto diagonale di penna."""
    color = _random_pen_color()
    t = np.random.choice([2, 3, 3, 4, 5, 6])
    if np.random.random() < 0.5:
        cv2.line(img, (8+_jitter(), 10+_jitter()), (56+_jitter(), 54+_jitter()), color, t)
    else:
        cv2.line(img, (56+_jitter(), 10+_jitter()), (8+_jitter(), 54+_jitter()), color, t)
    return img


def gen_horizontal_stroke(img):
    """Tratto orizzontale."""
    color = _random_pen_color()
    t = np.random.choice([2, 3, 4, 5])
    y = 32 + _jitter(12)
    cv2.line(img, (6+_jitter(), y), (58+_jitter(), y+_jitter(3)), color, t)
    return img


def gen_vertical_stroke(img):
    """Tratto verticale."""
    color = _random_pen_color()
    t = np.random.choice([2, 3, 4, 5])
    x = 32 + _jitter(12)
    cv2.line(img, (x, 6+_jitter()), (x+_jitter(3), 58+_jitter()), color, t)
    return img


def gen_filled_area(img):
    """Annerimento/colorazione parziale o totale."""
    color = np.random.randint(20, 90)
    fill_type = np.random.choice(["full", "partial", "scribble_fill"])

    if fill_type == "full":
        margin = np.random.randint(3, 12)
        cv2.rectangle(img, (margin, margin),
                      (CELL_SIZE-margin, CELL_SIZE-margin), color, -1)
    elif fill_type == "partial":
        x1 = np.random.randint(5, 25)
        y1 = np.random.randint(5, 25)
        x2 = np.random.randint(40, 60)
        y2 = np.random.randint(40, 60)
        cv2.rectangle(img, (x1, y1), (x2, y2), color, -1)
    else:
        # Riempimento a scarabocchio
        for _ in range(np.random.randint(8, 20)):
            y = np.random.randint(8, 56)
            t = np.random.choice([1, 2, 2, 3])
            cv2.line(img, (6+_jitter(3), y), (58+_jitter(3), y+_jitter(2)), color, t)
    return img


def gen_dot_mark(img):
    """Puntino/punto grosso intenzionale."""
    color = _random_pen_color()
    cx = 32 + _jitter(10)
    cy = 32 + _jitter(10)
    r = np.random.randint(4, 14)
    cv2.circle(img, (cx, cy), r, color, -1)
    return img


def gen_scribble(img):
    """Scarabocchio generico."""
    color = _random_pen_color()
    t = np.random.choice([1, 2, 2, 3])
    n_strokes = np.random.randint(3, 8)
    pts = []
    px, py = np.random.randint(10, 54), np.random.randint(10, 54)
    for _ in range(n_strokes):
        nx = np.clip(px + np.random.randint(-15, 16), 4, 60)
        ny = np.clip(py + np.random.randint(-15, 16), 4, 60)
        pts.append([nx, ny])
        px, py = nx, ny
    if len(pts) >= 2:
        cv2.polylines(img, [np.array(pts, dtype=np.int32)], False, color, t)
    return img


def gen_underline(img):
    """Sottolineatura del numero."""
    color = _random_pen_color()
    t = np.random.choice([2, 3, 4])
    y = np.random.randint(38, 52)
    cv2.line(img, (10+_jitter(), y), (54+_jitter(), y+_jitter(2)), color, t)
    return img


def gen_cross_plus(img):
    """Segno a croce (+)."""
    color = _random_pen_color()
    t = np.random.choice([2, 3, 3, 4])
    mid = 32
    m = np.random.randint(8, 16)
    cv2.line(img, (mid+_jitter(), m+_jitter()), (mid+_jitter(), CELL_SIZE-m+_jitter()), color, t)
    cv2.line(img, (m+_jitter(), mid+_jitter()), (CELL_SIZE-m+_jitter(), mid+_jitter()), color, t)
    return img


def gen_double_stroke(img):
    """Doppio tratto (due linee parallele)."""
    color = _random_pen_color()
    t = np.random.choice([2, 3])
    offset = np.random.randint(4, 10)
    m = np.random.randint(8, 15)
    cv2.line(img, (m, m), (CELL_SIZE-m, CELL_SIZE-m), color, t)
    cv2.line(img, (m+offset, m), (CELL_SIZE-m+offset, CELL_SIZE-m), color, t)
    return img


# Lista pesata di generatori segnato
SEGNATO_GENERATORS = [
    (gen_cerchio, 3.0),       # Piu comune
    (gen_x_mark, 3.0),        # Piu comune
    (gen_checkmark, 2.0),
    (gen_diagonal_stroke, 2.0),
    (gen_horizontal_stroke, 1.0),
    (gen_vertical_stroke, 0.5),
    (gen_filled_area, 2.0),
    (gen_dot_mark, 1.5),
    (gen_scribble, 1.5),
    (gen_underline, 1.0),
    (gen_cross_plus, 1.0),
    (gen_double_stroke, 0.5),
]


# ============================================================
# GENERATORI CLASSE "VUOTO"
# ============================================================

def gen_vuoto_clean(img):
    """Cella completamente vuota."""
    return img


def gen_vuoto_dust(img):
    """Cella con polvere/puntini casuali."""
    for _ in range(np.random.randint(1, 4)):
        px = np.random.randint(3, 61)
        py = np.random.randint(3, 61)
        r = np.random.choice([1, 1, 1, 2])
        c = np.random.randint(160, 220)
        cv2.circle(img, (px, py), r, int(c), -1)
    return img


def gen_vuoto_shadow(img):
    """Cella con ombra leggera."""
    grad = np.linspace(0, np.random.randint(10, 25), CELL_SIZE).astype(np.int16)
    if np.random.random() < 0.5:
        img = np.clip(img.astype(np.int16) - grad[np.newaxis, :], 0, 255).astype(np.uint8)
    else:
        img = np.clip(img.astype(np.int16) - grad[:, np.newaxis], 0, 255).astype(np.uint8)
    return img


def gen_vuoto_erasure(img):
    """Cella con traccia di cancellatura leggera."""
    cx = np.random.randint(15, 50)
    cy = np.random.randint(15, 50)
    r = np.random.randint(8, 18)
    mask = np.zeros((CELL_SIZE, CELL_SIZE), dtype=np.float32)
    cv2.circle(mask, (cx, cy), r, 1.0, -1)
    mask = cv2.GaussianBlur(mask, (11, 11), 0)
    img = np.clip(img.astype(np.float32) - mask * np.random.uniform(5, 18), 0, 255).astype(np.uint8)
    return img


def gen_vuoto_border_bleed(img):
    """Cella con residuo bordo della cella adiacente."""
    if np.random.random() < 0.5:
        y = np.random.choice([0, 1, CELL_SIZE-2, CELL_SIZE-1])
        x1 = np.random.randint(0, 20)
        x2 = x1 + np.random.randint(5, 20)
        c = np.random.randint(140, 195)
        cv2.line(img, (x1, y), (x2, y), int(c), 1)
    else:
        x = np.random.choice([0, 1, CELL_SIZE-2, CELL_SIZE-1])
        y1 = np.random.randint(0, 20)
        y2 = y1 + np.random.randint(5, 20)
        c = np.random.randint(140, 195)
        cv2.line(img, (x, y1), (x, y2), int(c), 1)
    return img


VUOTO_GENERATORS = [
    (gen_vuoto_clean, 4.0),
    (gen_vuoto_dust, 2.0),
    (gen_vuoto_shadow, 2.0),
    (gen_vuoto_erasure, 1.5),
    (gen_vuoto_border_bleed, 1.0),
]


def _weighted_choice(generators):
    """Sceglie un generatore in base ai pesi."""
    fns, weights = zip(*generators)
    weights = np.array(weights, dtype=np.float64)
    weights /= weights.sum()
    idx = np.random.choice(len(fns), p=weights)
    return fns[idx]


def generate_cell(class_name: str) -> np.ndarray:
    """Genera una singola cella per la classe specificata."""
    img = _paper_background()
    img = _draw_printed_number(img)

    if class_name == "segnato":
        gen_fn = _weighted_choice(SEGNATO_GENERATORS)
        img = gen_fn(img)
    else:
        gen_fn = _weighted_choice(VUOTO_GENERATORS)
        img = gen_fn(img)

    img = _add_border_artifacts(img)

    # Blur leggero opzionale (simula foto)
    if np.random.random() < 0.25:
        k = np.random.choice([3, 3, 5])
        img = cv2.GaussianBlur(img, (k, k), 0)

    # Applica CLAHE per-cella (coerente con grid_extractor)
    img = _cell_clahe.apply(img)

    return img


def generate_dataset(n_per_class: int = 1500):
    """Genera dataset binario completo."""
    print(f"Generazione dataset binario ({n_per_class} per classe)...")

    for class_name in ["segnato", "vuoto"]:
        class_dir = OUTPUT_DIR / class_name
        class_dir.mkdir(parents=True, exist_ok=True)

        for i in range(n_per_class):
            cell = generate_cell(class_name)
            filename = f"bingen_{class_name}_{i:05d}.png"
            cv2.imwrite(str(class_dir / filename), cell)

        print(f"  {class_name}: {n_per_class} celle generate")

    # Converti anche i dati esistenti cerchio/x_rossa → segnato
    print("\nConversione dati esistenti → binario...")
    _convert_existing_to_binary()

    print(f"\nOutput: {OUTPUT_DIR}")


def _convert_existing_to_binary():
    """
    Copia i dati esistenti nelle categorie binarie:
    - cerchio + x_rossa → segnato
    - vuoto → vuoto
    """
    import shutil
    data_dir = PROJECT_DIR / "data"
    sources = ["raw_cells", "synthetic", "generated", "pdf_cells"]

    segnato_dir = OUTPUT_DIR / "segnato"
    vuoto_dir = OUTPUT_DIR / "vuoto"
    segnato_dir.mkdir(parents=True, exist_ok=True)
    vuoto_dir.mkdir(parents=True, exist_ok=True)

    counts = {"segnato": 0, "vuoto": 0}

    for src in sources:
        src_dir = data_dir / src
        if not src_dir.exists():
            continue

        # cerchio → segnato
        for cls in ["cerchio", "x_rossa"]:
            cls_dir = src_dir / cls
            if not cls_dir.exists():
                continue
            for img_path in cls_dir.glob("*.png"):
                # Applica CLAHE per coerenza
                img = cv2.imread(str(img_path), cv2.IMREAD_GRAYSCALE)
                if img is None:
                    continue
                img = cv2.resize(img, (CELL_SIZE, CELL_SIZE))
                img = _cell_clahe.apply(img)
                dst = segnato_dir / f"{src}_{cls}_{img_path.name}"
                cv2.imwrite(str(dst), img)
                counts["segnato"] += 1

        # vuoto → vuoto
        vuoto_cls = src_dir / "vuoto"
        if vuoto_cls.exists():
            for img_path in vuoto_cls.glob("*.png"):
                img = cv2.imread(str(img_path), cv2.IMREAD_GRAYSCALE)
                if img is None:
                    continue
                img = cv2.resize(img, (CELL_SIZE, CELL_SIZE))
                img = _cell_clahe.apply(img)
                dst = vuoto_dir / f"{src}_vuoto_{img_path.name}"
                cv2.imwrite(str(dst), img)
                counts["vuoto"] += 1

    print(f"  Convertiti: segnato={counts['segnato']}, vuoto={counts['vuoto']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Genera dataset binario segnato/vuoto")
    parser.add_argument("--n", type=int, default=1500, help="Celle generate per classe")
    args = parser.parse_args()

    generate_dataset(n_per_class=args.n)
    print("Fatto!")
