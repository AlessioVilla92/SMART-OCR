"""
scripts/generate_references.py

Genera immagini di riferimento grayscale A4 300DPI dal PDF CBCL.
Output: templates/cbcl_page4_ref.png e cbcl_page5_ref.png (2480x3508 px)

Requisiti: pip install PyMuPDF>=1.24.0
"""

import fitz  # PyMuPDF
from pathlib import Path


def generate_references():
    # Il PDF è nella root del progetto (un livello sopra smart_ocr/)
    project_root = Path(__file__).parent.parent.parent
    # Cbcl1.pdf ha 6 pagine (completo), cbcl.pdf ne ha solo 2
    pdf_path = project_root / "Cbcl1.pdf"

    if not pdf_path.exists():
        pdf_path = project_root / "cbcl.pdf"
    if not pdf_path.exists():
        raise FileNotFoundError(
            f"PDF CBCL non trovato in {project_root}. "
            "Servono cbcl.pdf o Cbcl1.pdf nella root del progetto."
        )

    doc = fitz.open(str(pdf_path))

    # A4 a 300 DPI: scala = 300/72 = 4.1667
    mat = fitz.Matrix(300 / 72, 300 / 72)

    pages = {
        "page_4": 3,  # indice 0-based → pagina 4 del PDF
        "page_5": 4,  # indice 0-based → pagina 5 del PDF
        "page_6": 5,  # indice 0-based → pagina 6 del PDF
    }

    templates_dir = Path(__file__).parent.parent / "templates"
    templates_dir.mkdir(exist_ok=True)

    for page_key, page_idx in pages.items():
        if page_idx >= len(doc):
            print(f"ATTENZIONE: pagina {page_idx + 1} non esiste nel PDF ({len(doc)} pagine)")
            continue

        page = doc[page_idx]
        pix = page.get_pixmap(matrix=mat, colorspace=fitz.csGRAY)

        out_path = templates_dir / f"cbcl_{page_key}_ref.png"
        pix.save(str(out_path))

        print(f"OK {out_path.name}: {pix.width}x{pix.height}")
        # Tolleranza di 2px per arrotondamento DPI
        assert abs(pix.width - 2480) <= 2 and abs(pix.height - 3508) <= 2, \
            f"Dimensioni inattese: {pix.width}x{pix.height} (atteso ~2480x3508)"

    doc.close()
    print("Riferimenti generati con successo.")


if __name__ == "__main__":
    generate_references()
