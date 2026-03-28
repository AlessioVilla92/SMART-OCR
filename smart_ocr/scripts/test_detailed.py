"""
Test dettagliato: per ogni domanda mostra quale quadratino (0, 1, 2) e segnato.
Formato output:
  Domanda  1: [X] [ ] [ ]  -> risposta = 0  (conf: 95%)
  Domanda  2: [ ] [X] [ ]  -> risposta = 1  (conf: 88%)
  Domanda  3: [ ] [ ] [ ]  -> MANCANTE
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.preprocessor import preprocess_full_pipeline
from core.grid_extractor import extract_all_cells
from core.classifier import CBCLClassifier


def analyze_photo(photo_path: str, page: str, classifier: CBCLClassifier):
    print(f"\n{'='*70}")
    print(f"  FOTO: {Path(photo_path).name}")
    print(f"  PAGINA: {page}")
    print(f"{'='*70}")

    gray, meta = preprocess_full_pipeline(photo_path)
    cells = extract_all_cells(gray, page)

    print(f"\n  {'Domanda':>10s}   0    1    2    Risposta")
    print(f"  {'-'*55}")

    scored = 0
    total = 0

    # Ordina items in modo naturale
    def sort_key(item_id):
        # Gestisci sub-items come 56a, 56b, ecc.
        base = ""
        suffix = ""
        for c in item_id:
            if c.isdigit():
                base += c
            else:
                suffix += c
        return (int(base) if base else 0, suffix)

    for item_id in sorted(cells.keys(), key=sort_key):
        total += 1
        item_cells = cells[item_id]
        result = classifier.predict_item_cells(item_cells)

        # Costruisci visualizzazione quadratini
        raw = result.get("raw_predictions", {})
        boxes = []
        for col in ["0", "1", "2"]:
            if col in raw:
                cls = raw[col]["class"]
                conf = raw[col]["confidence"]
                if cls in ("cerchio", "x_rossa"):
                    boxes.append(f"[X]")
                elif cls == "ambiguo":
                    boxes.append(f"[?]")
                else:
                    boxes.append(f"[ ]")
            else:
                boxes.append(f"   ")

        box_str = "  ".join(boxes)

        # Risultato
        value = result["value"]
        flag = result["flag"]
        confidence = result["confidence"]

        if value is not None:
            scored += 1
            resp_str = f"-> risposta = {value}  (conf: {confidence:.0%})"
        elif flag == "missing":
            resp_str = "-> MANCANTE"
        elif flag == "multiple_marks":
            resp_str = "-> SEGNI MULTIPLI"
        elif flag == "ambiguous":
            resp_str = "-> AMBIGUO"
        else:
            resp_str = f"-> {flag}"

        print(f"  {item_id:>10s}   {box_str}    {resp_str}")

    print(f"\n  {'-'*55}")
    print(f"  Totale domande: {total}")
    print(f"  Risposte trovate: {scored}/{total} ({scored/total*100:.0f}%)")
    print(f"  Mancanti: {sum(1 for r in [classifier.predict_item_cells(cells[i]) for i in cells] if r['flag'] == 'missing')}")


def main():
    print("Caricamento modello SVM...")
    classifier = CBCLClassifier()
    if not classifier.load():
        print("ERRORE: model.pkl non trovato!")
        sys.exit(1)
    print("Modello caricato.\n")

    test_dir = Path(__file__).parent.parent.parent / "TEST1"
    photos = sorted(test_dir.glob("*.jpeg")) + sorted(test_dir.glob("*.jpg"))

    if not photos:
        print("Nessuna foto in TEST1/")
        sys.exit(1)

    # Page 4: prima foto
    analyze_photo(str(photos[0]), "page_4", classifier)

    # Page 5: terza foto
    if len(photos) >= 3:
        analyze_photo(str(photos[2]), "page_5", classifier)


if __name__ == "__main__":
    main()
