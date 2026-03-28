"""
training/questionnaire_generator.py

Genera questionari CBCL compilati sintetici con calligrafie diverse.
Prende una foto reale come base, sovrappone segni a mano simulati
su celle random, e salva come nuove "foto di pazienti".

Ogni paziente sintetico ha:
- Stile di marcatura (cerchio, X, o misto)
- Spessore tratto variabile (penna fine vs penna grossa)
- Colore inchiostro (nero, blu scuro, rosso)
- Precisione (ordinato vs sbrigativo)
- Pattern di risposte casuale ma realistico

Uso:
    python training/questionnaire_generator.py --n 10
    python training/questionnaire_generator.py --n 10 --extract
"""

import cv2
import numpy as np
import json
from pathlib import Path
import argparse
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

CELL_SIZE = 64
TEMPLATE_PATH = Path(__file__).parent.parent / "templates" / "cbcl_grid.json"
OUTPUT_DIR = Path(__file__).parent.parent / "data" / "synthetic_questionnaires"


class HandwritingStyle:
    """Stile calligrafico di un paziente."""

    def __init__(self, patient_id: int):
        rng = np.random.RandomState(patient_id * 137 + 42)

        # Tipo di marcatura predominante
        self.mark_type = rng.choice(["circle", "x", "mixed"], p=[0.4, 0.4, 0.2])

        # Spessore tratto
        thickness_options = [(1, 2), (2, 3), (3, 5)]
        self.thickness_range = thickness_options[rng.choice(3, p=[0.3, 0.5, 0.2])]

        # Colore inchiostro (grayscale simulato)
        color_options = [(10, 40), (30, 70), (50, 90)]
        self.ink_color_range = color_options[rng.choice(3, p=[0.4, 0.4, 0.2])]

        # Precisione: quanto i segni sono centrati
        self.jitter = rng.choice([2, 4, 6, 8], p=[0.2, 0.4, 0.3, 0.1])

        # Velocita: cerchi completi vs incompleti
        self.completeness = rng.uniform(0.7, 1.0)

        # Pressione variabile
        self.pressure_var = rng.uniform(0.0, 0.3)

        # Probabilita di doppio tratto
        self.double_trace_prob = rng.uniform(0.0, 0.3)

    def get_thickness(self, rng):
        t = rng.randint(self.thickness_range[0], self.thickness_range[1] + 1)
        if rng.random() < self.pressure_var:
            t = max(1, t + rng.choice([-1, 1]))
        return t

    def get_ink_color(self, rng):
        return rng.randint(self.ink_color_range[0], self.ink_color_range[1])

    def get_mark_type(self, rng):
        if self.mark_type == "mixed":
            return rng.choice(["circle", "x"])
        return self.mark_type


def draw_circle_mark(img, cx, cy, cell_w, cell_h, style, rng):
    """Disegna un cerchio a mano libera."""
    thickness = style.get_thickness(rng)
    color = style.get_ink_color(rng)

    # Dimensioni ellisse
    rx = int(cell_w * rng.uniform(0.35, 0.55))
    ry = int(cell_h * rng.uniform(0.35, 0.55))
    angle = rng.uniform(-20, 20)

    # Jitter posizione
    jx = rng.randint(-style.jitter, style.jitter + 1)
    jy = rng.randint(-style.jitter, style.jitter + 1)

    # Arco (completo o parziale)
    arc_extent = int(360 * rng.uniform(style.completeness, 1.0))
    start = rng.randint(0, 360 - arc_extent) if arc_extent < 360 else 0

    cv2.ellipse(img, (cx + jx, cy + jy), (rx, ry), angle,
                start, start + arc_extent, int(color), thickness)

    # Doppio tratto
    if rng.random() < style.double_trace_prob:
        off = rng.randint(1, 3)
        cv2.ellipse(img, (cx + jx + off, cy + jy + off),
                    (rx - 1, ry - 1), angle + rng.uniform(-3, 3),
                    start, start + arc_extent, int(color),
                    max(1, thickness - 1))


def draw_x_mark(img, cx, cy, cell_w, cell_h, style, rng):
    """Disegna una X a mano libera."""
    thickness = style.get_thickness(rng)
    color = style.get_ink_color(rng)

    # Margini
    mx = int(cell_w * rng.uniform(0.15, 0.35))
    my = int(cell_h * rng.uniform(0.15, 0.35))

    j = lambda: rng.randint(-style.jitter, style.jitter + 1)

    # Due linee della X
    x1, y1 = cx - mx + j(), cy - my + j()
    x2, y2 = cx + mx + j(), cy + my + j()
    x3, y3 = cx + mx + j(), cy - my + j()
    x4, y4 = cx - mx + j(), cy + my + j()

    cv2.line(img, (x1, y1), (x2, y2), int(color), thickness)
    cv2.line(img, (x3, y3), (x4, y4), int(color), thickness)

    # Doppio tratto
    if rng.random() < style.double_trace_prob:
        cv2.line(img, (x1 + 1, y1 + 1), (x2 + 1, y2 + 1),
                 int(color), max(1, thickness - 1))


def generate_responses(n_items, rng):
    """Genera risposte realistiche per un paziente CBCL."""
    responses = {}
    for i in range(n_items):
        # Distribuzione realistica CBCL: ~50% rispondono 0, ~30% rispondono 1, ~20% rispondono 2
        r = rng.choice([0, 1, 2, -1], p=[0.45, 0.25, 0.20, 0.10])
        # -1 = non risponde (lascia vuoto)
        if r >= 0:
            responses[i] = r
    return responses


def generate_questionnaire(
    base_image: np.ndarray,
    page: str,
    patient_id: int,
    template: dict
) -> tuple:
    """
    Genera un questionario compilato sintetico.

    Returns: (immagine_con_segni, risposte_dict)
    """
    rng = np.random.RandomState(patient_id * 7919 + 31)
    style = HandwritingStyle(patient_id)

    img = base_image.copy()
    h, w = img.shape[:2]

    page_data = template["pages"][page]
    items = page_data["items"]
    cell_w_rel = page_data["cell_width_rel"]
    cell_h_rel = page_data["cell_height_rel"]

    cell_w_px = int(cell_w_rel * w)
    cell_h_px = int(cell_h_rel * h)

    # Genera risposte
    item_ids = list(items.keys())
    responses = generate_responses(len(item_ids), rng)

    ground_truth = {}

    for idx, item_id in enumerate(item_ids):
        coords = items[item_id]
        row_y = coords["row_y"]

        if idx not in responses:
            ground_truth[item_id] = None  # Non risposto
            continue

        answer = responses[idx]  # 0, 1, o 2
        col_key = f"col_{answer}_x"

        if col_key not in coords:
            continue

        # Centro della cella da marcare
        cx = int(coords[col_key] * w)
        cy = int(row_y * h)

        # Disegna il segno
        mark_type = style.get_mark_type(rng)
        if mark_type == "circle":
            draw_circle_mark(img, cx, cy, cell_w_px, cell_h_px, style, rng)
        else:
            draw_x_mark(img, cx, cy, cell_w_px, cell_h_px, style, rng)

        ground_truth[item_id] = int(answer)

    # Aggiungi rumore fotografico globale
    noise_level = rng.uniform(2, 8)
    noise = rng.normal(0, noise_level, img.shape).astype(np.int16)
    img = np.clip(img.astype(np.int16) + noise, 0, 255).astype(np.uint8)

    # Leggera variazione di luminosita
    brightness = rng.randint(-15, 16)
    img = np.clip(img.astype(np.int16) + brightness, 0, 255).astype(np.uint8)

    return img, ground_truth


def main():
    parser = argparse.ArgumentParser(description="Genera questionari CBCL sintetici")
    parser.add_argument("--n", type=int, default=10, help="Numero pazienti da generare")
    parser.add_argument("--page", type=str, default="both", help="page_4, page_5, o both")
    parser.add_argument("--extract", action="store_true", help="Estrai celle e fai auto-labeling")
    args = parser.parse_args()

    # Carica template
    with open(TEMPLATE_PATH) as f:
        template = json.load(f)

    # Carica foto base (preprocessata) per ciascuna pagina
    from core.preprocessor import preprocess_full_pipeline

    test_dir = Path(__file__).parent.parent.parent / "TEST1"
    photos = sorted(test_dir.glob("*.jpeg")) + sorted(test_dir.glob("*.jpg"))

    if not photos:
        print("ERRORE: Nessuna foto in TEST1/")
        sys.exit(1)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    pages = []
    if args.page in ("page_4", "both"):
        pages.append(("page_4", str(photos[0])))
    if args.page in ("page_5", "both"):
        pages.append(("page_5", str(photos[2] if len(photos) >= 3 else photos[-1])))

    all_questionnaires = []

    for page, photo_path in pages:
        print(f"\nPreprocessing base: {Path(photo_path).name} ({page})...")
        base_gray, _ = preprocess_full_pipeline(photo_path)

        for patient_id in range(1, args.n + 1):
            style = HandwritingStyle(patient_id)
            print(f"  Paziente {patient_id:2d}: "
                  f"stile={style.mark_type}, "
                  f"spessore={style.thickness_range}, "
                  f"precisione=jitter{style.jitter}")

            img, ground_truth = generate_questionnaire(
                base_gray, page, patient_id, template
            )

            # Salva questionario
            fname = f"synthetic_patient{patient_id:02d}_{page}.jpg"
            fpath = OUTPUT_DIR / fname
            cv2.imwrite(str(fpath), img)

            # Salva ground truth
            gt_fname = f"synthetic_patient{patient_id:02d}_{page}_gt.json"
            with open(OUTPUT_DIR / gt_fname, "w") as f:
                json.dump(ground_truth, f, indent=2)

            all_questionnaires.append((fpath, page, ground_truth))

            # Conta risposte
            answered = sum(1 for v in ground_truth.values() if v is not None)
            total = len(ground_truth)
            print(f"           risposte: {answered}/{total}")

    print(f"\nGenerati {len(all_questionnaires)} questionari in {OUTPUT_DIR}")

    if args.extract:
        print("\nEstrazione celle con auto-labeling...")
        extract_cells_from_synthetic(all_questionnaires, template)


def extract_cells_from_synthetic(questionnaires, template):
    """Estrae celle dai questionari sintetici usando il ground truth."""
    from core.grid_extractor import extract_all_cells
    import time

    raw_dir = Path(__file__).parent.parent / "data" / "raw_cells"
    stats = {"cerchio": 0, "x_rossa": 0, "vuoto": 0}

    for fpath, page, ground_truth in questionnaires:
        img = cv2.imread(str(fpath), cv2.IMREAD_GRAYSCALE)
        if img is None:
            continue

        cells = extract_all_cells(img, page)

        for item_id, item_cells in cells.items():
            gt_value = ground_truth.get(item_id)

            for col_label, cell_img in item_cells.items():
                col_int = int(col_label)

                if gt_value is None:
                    # Item non risposto -> tutte le celle sono vuote
                    label = "vuoto"
                elif col_int == gt_value:
                    # Cella marcata
                    label = "cerchio"  # Usiamo cerchio come label generica per "marcato"
                else:
                    label = "vuoto"

                dst_dir = raw_dir / label
                dst_dir.mkdir(parents=True, exist_ok=True)

                timestamp = int(time.time() * 1000)
                fname = f"synth_{fpath.stem}_item{item_id}_col{col_label}_{timestamp}.png"
                cv2.imwrite(str(dst_dir / fname), cell_img)
                stats[label] += 1

    print(f"\nCelle estratte:")
    for label, count in stats.items():
        print(f"  {label}: {count}")
    print(f"  Totale: {sum(stats.values())}")


if __name__ == "__main__":
    main()
