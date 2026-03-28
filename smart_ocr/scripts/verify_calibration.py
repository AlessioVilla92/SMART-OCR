"""
Script di verifica calibrazione griglia.
Preprocessa una foto TEST1 e sovrappone la griglia per ispezione visuale.
"""
import sys
from pathlib import Path

# Aggiungi parent al path per import moduli
sys.path.insert(0, str(Path(__file__).parent.parent))

import cv2
from core.preprocessor import preprocess_full_pipeline
from core.grid_extractor import visualize_grid_overlay


def verify(photo_path: str, page: str = "page_4", output_path: str = None):
    print(f"Preprocessing: {photo_path}")
    gray, metadata = preprocess_full_pipeline(photo_path, debug=True)
    print(f"  Dimensione originale: {metadata['original_size']}")
    print(f"  Dimensione finale: {metadata['final_size']}")
    print(f"  Deskew: {metadata['deskew_angle']:.2f}°")
    print(f"  Prospettiva corretta: {metadata['perspective_corrected']}")
    for w in metadata.get('warnings', []):
        print(f"  WARNING: {w}")

    print(f"\nSovrappongo griglia {page}...")
    overlay = visualize_grid_overlay(gray, page)

    if output_path is None:
        output_path = f"calibration_check_{page}.jpg"

    cv2.imwrite(output_path, overlay)
    print(f"Overlay salvato: {output_path}")
    print(f"Controlla visualmente che i rettangoli coincidano con le celle del questionario.")


if __name__ == "__main__":
    test_dir = Path(__file__).parent.parent.parent / "TEST1"
    photos = sorted(test_dir.glob("*.jpeg")) + sorted(test_dir.glob("*.jpg"))

    if not photos:
        print("Nessuna foto trovata in TEST1/")
        sys.exit(1)

    print(f"Trovate {len(photos)} foto in TEST1/\n")

    # Verifica page_4 con la prima foto
    verify(str(photos[0]), "page_4", "calibration_check_page4.jpg")

    if len(photos) > 1:
        print()
        verify(str(photos[1]), "page_5", "calibration_check_page5.jpg")
