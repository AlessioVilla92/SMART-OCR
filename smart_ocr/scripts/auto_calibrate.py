#!/usr/bin/env python3
"""
scripts/auto_calibrate.py

Calibrazione automatica della griglia CBCL da PDF digitale.
Estrae le posizioni esatte dei digit di risposta e genera cbcl_grid.json.

Uso:
    python scripts/auto_calibrate.py --pdf cbcl.pdf --page-index 1 --page-key page_4
    python scripts/auto_calibrate.py --pdf cbcl.pdf --page-index 1 --page-key page_4 --verify
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.pdf_calibrator import calibrate_from_pdf
from core.calibrator import save_calibration, TEMPLATE_PATH


def main():
    parser = argparse.ArgumentParser(
        description="Auto-calibrazione griglia CBCL da PDF digitale"
    )
    parser.add_argument("--pdf", required=True, help="Percorso al PDF CBCL")
    parser.add_argument("--page-index", type=int, default=1,
                        help="Indice pagina nel PDF (0-based, default: 1)")
    parser.add_argument("--page-key", default="page_4",
                        help="Chiave pagina in cbcl_grid.json (default: page_4)")
    parser.add_argument("--verify", action="store_true",
                        help="Genera immagine di verifica con overlay")
    parser.add_argument("--verify-output", default=None,
                        help="Percorso output immagine verifica (default: /tmp/calibration_overlay.png)")

    args = parser.parse_args()

    pdf_path = Path(args.pdf)
    if not pdf_path.exists():
        print(f"Errore: file non trovato: {pdf_path}")
        sys.exit(1)

    print(f"Calibrazione da: {pdf_path}")
    print(f"  Pagina PDF: {args.page_index + 1} (indice {args.page_index})")
    print(f"  Chiave: {args.page_key}")
    print()

    # Calibra
    page_data, layout_info = calibrate_from_pdf(
        str(pdf_path), page_index=args.page_index
    )

    # Salva
    save_calibration(args.page_key, page_data)

    # Report
    print(f"Calibrazione completata!")
    print(f"  Items rilevati: {layout_info['total_items']}")
    print(f"  Colonna SX: {len(layout_info['left_column_items'])} items "
          f"({layout_info['left_column_items'][0]}-{layout_info['left_column_items'][-1]})")
    print(f"  Colonna DX: {len(layout_info['right_column_items'])} items "
          f"({layout_info['right_column_items'][0]}-{layout_info['right_column_items'][-1]})")
    print(f"  Spaziatura colonne SX: {layout_info['col_spacing_left_pt']:.1f} pt")
    print(f"  Spaziatura colonne DX: {layout_info['col_spacing_right_pt']:.1f} pt")
    print(f"  Dimensione cella: {layout_info['cell_size_px'][0]:.0f} x "
          f"{layout_info['cell_size_px'][1]:.0f} px")
    print(f"  Salvato in: {TEMPLATE_PATH}")

    # Verifica con overlay
    if args.verify:
        verify_output = args.verify_output or "/tmp/calibration_overlay.png"
        _generate_overlay(pdf_path, args.page_index, args.page_key, verify_output)


def _generate_overlay(pdf_path, page_index, page_key, output_path):
    """Genera immagine con overlay della griglia calibrata."""
    try:
        import subprocess
        import cv2
        import numpy as np
        from core.grid_extractor import visualize_grid_overlay

        # Renderizza la pagina PDF come immagine
        with __import__('tempfile').NamedTemporaryFile(suffix='.png', delete=False) as tmp:
            tmp_path = tmp.name

        page_num = page_index + 1
        subprocess.run([
            'pdftoppm', '-png', '-f', str(page_num), '-l', str(page_num),
            '-r', '300', str(pdf_path), tmp_path.replace('.png', '')
        ], check=True)

        # pdftoppm aggiunge il numero pagina al nome
        import glob
        rendered_files = glob.glob(tmp_path.replace('.png', '') + '*.png')
        if not rendered_files:
            print("Errore: pdftoppm non ha generato il file")
            return

        rendered_path = rendered_files[0]

        # Carica e converti in grayscale
        img = cv2.imread(rendered_path)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # Genera overlay
        overlay = visualize_grid_overlay(gray, page_key)
        cv2.imwrite(output_path, overlay)
        print(f"\n  Overlay salvato: {output_path}")

        # Cleanup
        import os
        os.unlink(rendered_path)

    except Exception as e:
        print(f"\n  Errore generazione overlay: {e}")


if __name__ == "__main__":
    main()
