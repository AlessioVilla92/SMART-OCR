"""
scripts/extract_cells_from_pdf.py

Estrae celle di training dal PDF ufficiale CBCL.
Il PDF non compilato contiene solo celle vuote — perfetti ground-truth per "vuoto".
Genera anche cerchio/x_rossa sintetici sovrapposti allo sfondo reale del PDF.

Uso:
    python smart_ocr/scripts/extract_cells_from_pdf.py
    python smart_ocr/scripts/extract_cells_from_pdf.py --n-synthetic 500
"""

import cv2
import numpy as np
import json
import argparse
from pathlib import Path
import sys

SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_DIR))

from core.grid_extractor import extract_cell

CELL_SIZE = 64
PDF_PAGES_DIR = PROJECT_DIR / "data" / "pdf_pages"
GRID_PATH = PROJECT_DIR / "templates" / "cbcl_grid.json"
OUTPUT_DIR = PROJECT_DIR / "data" / "pdf_cells"


def load_page_image(page_key: str, grid: dict) -> np.ndarray:
    """Carica l'immagine PNG della pagina PDF renderizzata."""
    page_idx = grid["pages"][page_key]["pdf_page_index"]
    png_path = PDF_PAGES_DIR / f"cbcl1_page_{page_idx + 1}.png"
    if not png_path.exists():
        raise FileNotFoundError(f"PNG non trovato: {png_path}")
    img = cv2.imread(str(png_path), cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise ValueError(f"Impossibile leggere: {png_path}")
    return img


def extract_vuoto_from_pdf(grid: dict) -> int:
    """Estrae tutte le celle vuote dal PDF ufficiale."""
    vuoto_dir = OUTPUT_DIR / "vuoto"
    vuoto_dir.mkdir(parents=True, exist_ok=True)

    count = 0
    for page_key, page_data in grid["pages"].items():
        img = load_page_image(page_key, grid)
        cell_w = page_data["cell_width_rel"]
        cell_h = page_data["cell_height_rel"]

        for item_id, coords in page_data["items"].items():
            row_y = coords["row_y"]
            for col_idx in range(3):
                col_key = f"col_{col_idx}_x"
                col_x = coords[col_key]

                cell = extract_cell(img, col_x, row_y, cell_w, cell_h)
                filename = f"pdf_{page_key}_{item_id}_col{col_idx}.png"
                cv2.imwrite(str(vuoto_dir / filename), cell)
                count += 1

    print(f"  Celle vuoto estratte dal PDF: {count}")
    return count


def _overlay_cerchio(bg: np.ndarray) -> np.ndarray:
    """Sovrappone un cerchio realistico su sfondo reale."""
    img = bg.copy()
    cx = CELL_SIZE // 2 + np.random.randint(-6, 7)
    cy = CELL_SIZE // 2 + np.random.randint(-6, 7)
    rx = np.random.randint(14, 26)
    ry = np.random.randint(14, 26)
    pen_color = np.random.randint(20, 80)
    thickness = np.random.choice([1, 2, 2, 3, 3])
    angle = np.random.uniform(-20, 20)

    style = np.random.choice(["full", "arc", "scribble"])
    if style == "full":
        cv2.ellipse(img, (cx, cy), (rx, ry), angle, 0, 360, int(pen_color), thickness)
    elif style == "arc":
        start = np.random.randint(0, 30)
        end = start + np.random.randint(290, 355)
        cv2.ellipse(img, (cx, cy), (rx, ry), angle, start, end, int(pen_color), thickness)
    else:
        n_pts = np.random.randint(20, 35)
        angles_arr = np.linspace(0, 2 * np.pi * np.random.uniform(0.9, 1.1), n_pts)
        pts = []
        for a in angles_arr:
            r_var = np.random.uniform(0.88, 1.12)
            px = int(cx + rx * r_var * np.cos(a + angle * np.pi / 180))
            py = int(cy + ry * r_var * np.sin(a + angle * np.pi / 180))
            pts.append([px, py])
        cv2.polylines(img, [np.array(pts, dtype=np.int32)], False, int(pen_color), thickness)

    if np.random.random() < 0.3:
        img = cv2.GaussianBlur(img, (3, 3), 0)
    return img


def _overlay_x_rossa(bg: np.ndarray) -> np.ndarray:
    """Sovrappone una X realistica su sfondo reale."""
    img = bg.copy()
    pen_color = np.random.randint(20, 80)
    thickness = np.random.choice([1, 2, 2, 3, 3, 4])
    margin = np.random.randint(6, 16)
    j = lambda: np.random.randint(-4, 5)

    style = np.random.choice(["straight", "wobbly", "thick"])
    if style in ("straight", "thick"):
        t = thickness if style == "straight" else np.random.choice([3, 4, 5])
        cv2.line(img, (margin + j(), margin + j()),
                 (CELL_SIZE - margin + j(), CELL_SIZE - margin + j()), int(pen_color), t)
        cv2.line(img, (CELL_SIZE - margin + j(), margin + j()),
                 (margin + j(), CELL_SIZE - margin + j()), int(pen_color), t)
    else:
        for _ in range(2):
            if _ == 0:
                start = (margin + j(), margin + j())
                end = (CELL_SIZE - margin + j(), CELL_SIZE - margin + j())
            else:
                start = (CELL_SIZE - margin + j(), margin + j())
                end = (margin + j(), CELL_SIZE - margin + j())
            n_pts = np.random.randint(5, 8)
            pts = []
            for i in range(n_pts):
                t_val = i / (n_pts - 1)
                px = int(start[0] + t_val * (end[0] - start[0]) + np.random.randint(-3, 4))
                py = int(start[1] + t_val * (end[1] - start[1]) + np.random.randint(-3, 4))
                pts.append([px, py])
            cv2.polylines(img, [np.array(pts)], False, int(pen_color), thickness)

    if np.random.random() < 0.3:
        img = cv2.GaussianBlur(img, (3, 3), 0)
    return img


def generate_synthetic_on_pdf_bg(grid: dict, n_per_class: int = 500) -> dict:
    """
    Genera cerchio/x_rossa sintetici usando celle vuote reali dal PDF come sfondo.
    Risultato molto piu realistico del generatore procedurale.
    """
    # Raccogli tutte le celle vuote dal PDF
    backgrounds = []
    for page_key, page_data in grid["pages"].items():
        img = load_page_image(page_key, grid)
        cell_w = page_data["cell_width_rel"]
        cell_h = page_data["cell_height_rel"]

        for item_id, coords in page_data["items"].items():
            row_y = coords["row_y"]
            for col_idx in range(3):
                col_x = coords[f"col_{col_idx}_x"]
                cell = extract_cell(img, col_x, row_y, cell_w, cell_h)
                backgrounds.append(cell)

    print(f"  Sfondi PDF reali raccolti: {len(backgrounds)}")

    stats = {}
    for class_name, overlay_fn in [("cerchio", _overlay_cerchio), ("x_rossa", _overlay_x_rossa)]:
        class_dir = OUTPUT_DIR / class_name
        class_dir.mkdir(parents=True, exist_ok=True)

        for i in range(n_per_class):
            bg = backgrounds[np.random.randint(0, len(backgrounds))].copy()
            cell = overlay_fn(bg)
            filename = f"pdfsyn_{class_name}_{i:05d}.png"
            cv2.imwrite(str(class_dir / filename), cell)

        stats[class_name] = n_per_class
        print(f"  {class_name}: {n_per_class} sintetici su sfondo PDF")

    return stats


def main():
    parser = argparse.ArgumentParser(
        description="Estrai celle training dal PDF ufficiale CBCL"
    )
    parser.add_argument("--n-synthetic", type=int, default=500,
                        help="Celle sintetiche per classe (cerchio/x_rossa)")
    args = parser.parse_args()

    if not GRID_PATH.exists():
        print("ERRORE: cbcl_grid.json non trovato. Esegui prima la calibrazione.")
        sys.exit(1)

    with open(GRID_PATH) as f:
        grid = json.load(f)

    print("=== Estrazione celle vuoto dal PDF ufficiale ===")
    n_vuoto = extract_vuoto_from_pdf(grid)

    print(f"\n=== Generazione sintetici su sfondo PDF ({args.n_synthetic}/classe) ===")
    stats = generate_synthetic_on_pdf_bg(grid, n_per_class=args.n_synthetic)

    print(f"\n=== Riepilogo ===")
    print(f"  vuoto:   {n_vuoto} (ground-truth dal PDF)")
    for cls, n in stats.items():
        print(f"  {cls}: {n} (sintetici su sfondo PDF)")
    print(f"  Output: {OUTPUT_DIR}")
    print("Fatto!")


if __name__ == "__main__":
    main()
