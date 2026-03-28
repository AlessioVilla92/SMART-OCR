"""
training/cell_generator_v2.py

Generatore avanzato di celle sintetiche v2.
Aggiunge varianti piu realistiche rispetto al generatore base:
- Cerchi con tratto spesso/sottile, aperti, ovali, sovrapposti al numero
- X con angoli variabili, tratti interrotti, pressione variabile
- Celle vuote con artefatti realistici (ombre, pieghe, macchie inchiostro)
- Sfondo con texture carta variabile
- Numeri stampati con posizioni e font piu vari

Uso:
    python training/cell_generator_v2.py --n 800
    python training/cell_generator_v2.py --n 800 --merge
"""

import cv2
import numpy as np
from pathlib import Path
import argparse

CELL_SIZE = 64
OUTPUT_DIR = Path(__file__).parent.parent / "data" / "generated"
CLASSES = ["cerchio", "x_rossa", "vuoto"]


def _paper_background() -> np.ndarray:
    """Sfondo carta con texture variabile."""
    style = np.random.choice(["uniform", "gradient", "spotted", "lined"])

    base = np.random.randint(210, 248)
    bg = np.full((CELL_SIZE, CELL_SIZE), base, dtype=np.uint8)

    if style == "gradient":
        direction = np.random.choice(["h", "v", "diag"])
        grad = np.linspace(0, np.random.randint(5, 20), CELL_SIZE).astype(np.int16)
        if direction == "h":
            bg = np.clip(bg.astype(np.int16) + grad[np.newaxis, :], 0, 255).astype(np.uint8)
        elif direction == "v":
            bg = np.clip(bg.astype(np.int16) + grad[:, np.newaxis], 0, 255).astype(np.uint8)
        else:
            for i in range(CELL_SIZE):
                bg[i] = np.clip(bg[i].astype(np.int16) + int(grad[i] * 0.7), 0, 255).astype(np.uint8)
    elif style == "spotted":
        for _ in range(np.random.randint(3, 10)):
            cx = np.random.randint(0, CELL_SIZE)
            cy = np.random.randint(0, CELL_SIZE)
            r = np.random.randint(3, 12)
            val = np.random.randint(-10, 10)
            cv2.circle(bg, (cx, cy), r, int(np.clip(base + val, 0, 255)), -1)
    elif style == "lined":
        if np.random.random() < 0.5:
            y_line = np.random.randint(10, CELL_SIZE - 10)
            color = np.random.randint(190, 220)
            cv2.line(bg, (0, y_line), (CELL_SIZE, y_line), int(color), 1)

    # Rumore gaussiano
    noise = np.random.normal(0, np.random.uniform(2, 6), (CELL_SIZE, CELL_SIZE)).astype(np.int16)
    bg = np.clip(bg.astype(np.int16) + noise, 0, 255).astype(np.uint8)

    return bg


def _draw_number(img: np.ndarray) -> np.ndarray:
    """Numero stampato con maggiore variabilita."""
    num = str(np.random.choice([0, 1, 2]))

    font = np.random.choice([
        cv2.FONT_HERSHEY_SIMPLEX,
        cv2.FONT_HERSHEY_DUPLEX,
        cv2.FONT_HERSHEY_COMPLEX,
        cv2.FONT_HERSHEY_TRIPLEX,
    ])
    scale = np.random.uniform(0.4, 0.9)
    thickness = np.random.choice([1, 1, 2, 2])

    # Colore: da grigio chiaro a medio (stampa sbiadita vs nitida)
    color = np.random.randint(120, 190)

    text_size = cv2.getTextSize(num, font, scale, thickness)[0]
    x = (CELL_SIZE - text_size[0]) // 2 + np.random.randint(-8, 9)
    y = (CELL_SIZE + text_size[1]) // 2 + np.random.randint(-8, 9)

    cv2.putText(img, num, (x, y), font, scale, int(color), thickness)
    return img


def _add_artifacts(img: np.ndarray, intensity: str = "medium") -> np.ndarray:
    """Artefatti: bordi griglia, ombre, macchie."""
    # Bordi cella (linee griglia)
    if np.random.random() < 0.5:
        color = np.random.randint(175, 215)
        thickness = np.random.choice([1, 1, 2])
        sides = np.random.choice(["top", "bottom", "left", "right", "multi"],
                                  p=[0.2, 0.2, 0.15, 0.15, 0.3])
        if sides == "multi":
            for s in np.random.choice(["top", "bottom", "left", "right"],
                                       size=np.random.randint(2, 4), replace=False):
                _draw_border(img, s, int(color), thickness)
        else:
            _draw_border(img, sides, int(color), thickness)

    # Ombra
    if np.random.random() < 0.25:
        grad_len = np.random.randint(10, 25)
        gradient = np.linspace(0, -grad_len, CELL_SIZE).astype(np.int16)
        if np.random.random() < 0.5:
            img = np.clip(img.astype(np.int16) + gradient[np.newaxis, :], 0, 255).astype(np.uint8)
        else:
            img = np.clip(img.astype(np.int16) + gradient[:, np.newaxis], 0, 255).astype(np.uint8)

    # Macchie di inchiostro (piccole)
    if intensity in ("medium", "high") and np.random.random() < 0.15:
        for _ in range(np.random.randint(1, 3)):
            px = np.random.randint(5, CELL_SIZE - 5)
            py = np.random.randint(5, CELL_SIZE - 5)
            r = np.random.randint(1, 4)
            c = np.random.randint(100, 180)
            cv2.circle(img, (px, py), r, int(c), -1)

    return img


def _draw_border(img, side, color, thickness):
    if side == "top":
        cv2.line(img, (0, 0), (CELL_SIZE, 0), color, thickness)
    elif side == "bottom":
        cv2.line(img, (0, CELL_SIZE - 1), (CELL_SIZE, CELL_SIZE - 1), color, thickness)
    elif side == "left":
        cv2.line(img, (0, 0), (0, CELL_SIZE), color, thickness)
    elif side == "right":
        cv2.line(img, (CELL_SIZE - 1, 0), (CELL_SIZE - 1, CELL_SIZE), color, thickness)


def generate_cerchio() -> np.ndarray:
    """Cerchio con varianti avanzate."""
    img = _paper_background()
    img = _draw_number(img)

    cx = CELL_SIZE // 2 + np.random.randint(-8, 9)
    cy = CELL_SIZE // 2 + np.random.randint(-8, 9)
    rx = np.random.randint(12, 28)
    ry = np.random.randint(12, 28)

    pen_color = np.random.randint(15, 90)
    thickness = np.random.choice([1, 1, 2, 2, 3, 3, 4])
    angle = np.random.uniform(-25, 25)

    style = np.random.choice([
        "full", "full", "arc_big", "arc_small",
        "double", "scribble", "thick_partial", "oval_flat"
    ])

    if style == "full":
        cv2.ellipse(img, (cx, cy), (rx, ry), angle, 0, 360, int(pen_color), thickness)
    elif style == "arc_big":
        start = np.random.randint(0, 30)
        end = start + np.random.randint(300, 350)
        cv2.ellipse(img, (cx, cy), (rx, ry), angle, start, end, int(pen_color), thickness)
    elif style == "arc_small":
        start = np.random.randint(0, 60)
        end = start + np.random.randint(240, 310)
        cv2.ellipse(img, (cx, cy), (rx, ry), angle, start, end, int(pen_color), thickness)
    elif style == "double":
        cv2.ellipse(img, (cx, cy), (rx, ry), angle, 0, 360, int(pen_color), thickness)
        off = np.random.randint(1, 4)
        cv2.ellipse(img, (cx + off, cy + off), (rx - 2, ry - 2),
                     angle + np.random.uniform(-5, 5), 0, 360,
                     int(pen_color), max(1, thickness - 1))
    elif style == "scribble":
        # Cerchio disegnato con polyline irregolare
        n_pts = np.random.randint(20, 40)
        angles = np.linspace(0, 2 * np.pi * np.random.uniform(0.85, 1.1), n_pts)
        pts = []
        for a in angles:
            r_var = np.random.uniform(0.85, 1.15)
            px = int(cx + rx * r_var * np.cos(a + angle * np.pi / 180))
            py = int(cy + ry * r_var * np.sin(a + angle * np.pi / 180))
            pts.append([px, py])
        pts = np.array(pts, dtype=np.int32)
        cv2.polylines(img, [pts], False, int(pen_color), thickness)
    elif style == "thick_partial":
        t = np.random.choice([3, 4, 5])
        start = np.random.randint(0, 50)
        end = start + np.random.randint(270, 340)
        cv2.ellipse(img, (cx, cy), (rx, ry), angle, start, end, int(pen_color), t)
    elif style == "oval_flat":
        rx2 = np.random.randint(18, 28)
        ry2 = np.random.randint(8, 14)
        cv2.ellipse(img, (cx, cy), (rx2, ry2), angle, 0, 360, int(pen_color), thickness)

    # Blur leggero per simulare foto
    if np.random.random() < 0.3:
        k = np.random.choice([3, 3, 5])
        img = cv2.GaussianBlur(img, (k, k), 0)

    img = _add_artifacts(img)
    return img


def generate_x_rossa() -> np.ndarray:
    """X con varianti avanzate."""
    img = _paper_background()
    img = _draw_number(img)

    pen_color = np.random.randint(15, 90)
    thickness = np.random.choice([1, 2, 2, 3, 3, 4, 5])
    margin = np.random.randint(4, 18)

    style = np.random.choice([
        "straight", "straight", "wobbly", "asymmetric",
        "thick", "partial", "cross"
    ])

    j = lambda: np.random.randint(-5, 6)

    if style in ("straight", "thick"):
        t = thickness if style == "straight" else np.random.choice([4, 5, 6])
        cv2.line(img, (margin + j(), margin + j()),
                 (CELL_SIZE - margin + j(), CELL_SIZE - margin + j()), int(pen_color), t)
        cv2.line(img, (CELL_SIZE - margin + j(), margin + j()),
                 (margin + j(), CELL_SIZE - margin + j()), int(pen_color), t)
    elif style == "wobbly":
        # X con linee ondulate (polyline)
        for _ in range(2):
            if _ == 0:
                start = (margin + j(), margin + j())
                end = (CELL_SIZE - margin + j(), CELL_SIZE - margin + j())
            else:
                start = (CELL_SIZE - margin + j(), margin + j())
                end = (margin + j(), CELL_SIZE - margin + j())
            n_pts = np.random.randint(5, 10)
            pts = []
            for i in range(n_pts):
                t_val = i / (n_pts - 1)
                px = int(start[0] + t_val * (end[0] - start[0]) + np.random.randint(-3, 4))
                py = int(start[1] + t_val * (end[1] - start[1]) + np.random.randint(-3, 4))
                pts.append([px, py])
            cv2.polylines(img, [np.array(pts)], False, int(pen_color), thickness)
    elif style == "asymmetric":
        # Una linea piu lunga dell'altra
        cv2.line(img, (margin - 2 + j(), margin - 2 + j()),
                 (CELL_SIZE - margin + 2 + j(), CELL_SIZE - margin + 2 + j()),
                 int(pen_color), thickness)
        short_margin = margin + np.random.randint(4, 10)
        cv2.line(img, (CELL_SIZE - short_margin + j(), short_margin + j()),
                 (short_margin + j(), CELL_SIZE - short_margin + j()),
                 int(pen_color), max(1, thickness - 1))
    elif style == "partial":
        # Una linea della X incompleta
        cv2.line(img, (margin + j(), margin + j()),
                 (CELL_SIZE - margin + j(), CELL_SIZE - margin + j()), int(pen_color), thickness)
        # Seconda linea solo parziale
        mid_x = CELL_SIZE // 2
        mid_y = CELL_SIZE // 2
        if np.random.random() < 0.5:
            cv2.line(img, (CELL_SIZE - margin + j(), margin + j()),
                     (mid_x + j(), mid_y + j()), int(pen_color), thickness)
        else:
            cv2.line(img, (mid_x + j(), mid_y + j()),
                     (margin + j(), CELL_SIZE - margin + j()), int(pen_color), thickness)
    elif style == "cross":
        # Croce (+) invece di X
        mid = CELL_SIZE // 2
        cv2.line(img, (mid + j(), margin + j()),
                 (mid + j(), CELL_SIZE - margin + j()), int(pen_color), thickness)
        cv2.line(img, (margin + j(), mid + j()),
                 (CELL_SIZE - margin + j(), mid + j()), int(pen_color), thickness)

    # Secondo tratto sovrapposto (pressione variabile)
    if np.random.random() < 0.25:
        cv2.line(img, (margin + j(), margin + j()),
                 (CELL_SIZE - margin + j(), CELL_SIZE - margin + j()),
                 int(pen_color + 20), max(1, thickness - 1))

    if np.random.random() < 0.3:
        k = np.random.choice([3, 3, 5])
        img = cv2.GaussianBlur(img, (k, k), 0)

    img = _add_artifacts(img)
    return img


def generate_vuoto() -> np.ndarray:
    """Cella vuota con artefatti realistici."""
    img = _paper_background()
    img = _draw_number(img)

    # Artefatti piu frequenti nelle celle vuote
    artifact_type = np.random.choice([
        "clean", "clean", "clean",
        "dust", "smudge", "partial_line", "fingerprint"
    ])

    if artifact_type == "dust":
        for _ in range(np.random.randint(1, 5)):
            px = np.random.randint(3, CELL_SIZE - 3)
            py = np.random.randint(3, CELL_SIZE - 3)
            r = np.random.randint(1, 3)
            c = np.random.randint(150, 210)
            cv2.circle(img, (px, py), r, int(c), -1)
    elif artifact_type == "smudge":
        sx = np.random.randint(10, CELL_SIZE - 10)
        sy = np.random.randint(10, CELL_SIZE - 10)
        sw = np.random.randint(5, 15)
        sh = np.random.randint(3, 8)
        overlay = img[sy:sy + sh, sx:sx + sw].astype(np.int16) - np.random.randint(5, 15)
        img[sy:sy + sh, sx:sx + sw] = np.clip(overlay, 0, 255).astype(np.uint8)
    elif artifact_type == "partial_line":
        # Frammento di linea (dal bordo di un segno nella cella adiacente)
        if np.random.random() < 0.5:
            y = np.random.choice([0, 1, 2, CELL_SIZE - 3, CELL_SIZE - 2, CELL_SIZE - 1])
            x1 = np.random.randint(0, CELL_SIZE // 3)
            x2 = x1 + np.random.randint(5, 20)
            c = np.random.randint(120, 180)
            cv2.line(img, (x1, y), (x2, y), int(c), 1)
        else:
            x = np.random.choice([0, 1, 2, CELL_SIZE - 3, CELL_SIZE - 2, CELL_SIZE - 1])
            y1 = np.random.randint(0, CELL_SIZE // 3)
            y2 = y1 + np.random.randint(5, 20)
            c = np.random.randint(120, 180)
            cv2.line(img, (x, y1), (x, y2), int(c), 1)
    elif artifact_type == "fingerprint":
        # Alone leggero (impronta dito)
        cx = np.random.randint(15, CELL_SIZE - 15)
        cy = np.random.randint(15, CELL_SIZE - 15)
        r = np.random.randint(8, 20)
        mask = np.zeros((CELL_SIZE, CELL_SIZE), dtype=np.float32)
        cv2.circle(mask, (cx, cy), r, 1.0, -1)
        mask = cv2.GaussianBlur(mask, (11, 11), 0)
        img = np.clip(img.astype(np.float32) - mask * np.random.uniform(5, 15), 0, 255).astype(np.uint8)

    img = _add_artifacts(img, intensity="high")
    return img


GENERATORS = {
    "cerchio": generate_cerchio,
    "x_rossa": generate_x_rossa,
    "vuoto": generate_vuoto,
}


def generate_dataset(n_per_class: int = 800, output_dir: Path = OUTPUT_DIR) -> dict:
    stats = {}
    for class_name, gen_fn in GENERATORS.items():
        class_dir = output_dir / class_name
        class_dir.mkdir(parents=True, exist_ok=True)

        for i in range(n_per_class):
            cell = gen_fn()
            filename = f"genv2_{class_name}_{i:05d}.png"
            cv2.imwrite(str(class_dir / filename), cell)

        stats[class_name] = n_per_class
        print(f"  {class_name}: {n_per_class} celle v2 generate")

    return stats


def merge_into_training(source_dir: Path = OUTPUT_DIR):
    import shutil
    raw_dir = Path(__file__).parent.parent / "data" / "raw_cells"
    total = 0
    for class_name in CLASSES:
        src = source_dir / class_name
        dst = raw_dir / class_name
        dst.mkdir(parents=True, exist_ok=True)
        if not src.exists():
            continue
        for img_path in src.glob("genv2_*.png"):
            shutil.copy2(str(img_path), str(dst / img_path.name))
            total += 1
    print(f"  Copiate {total} celle v2 in {raw_dir}")
    return total


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Genera celle sintetiche v2 (avanzate)")
    parser.add_argument("--n", type=int, default=800, help="Celle per classe")
    parser.add_argument("--output", type=str, default=None)
    parser.add_argument("--merge", action="store_true")
    args = parser.parse_args()

    output = Path(args.output) if args.output else OUTPUT_DIR

    print(f"Generazione celle sintetiche v2 ({args.n} per classe)...")
    stats = generate_dataset(n_per_class=args.n, output_dir=output)

    total = sum(stats.values())
    print(f"Totale: {total}")

    if args.merge:
        print("Merge in data/raw_cells/...")
        merge_into_training(output)

    print("Fatto!")
