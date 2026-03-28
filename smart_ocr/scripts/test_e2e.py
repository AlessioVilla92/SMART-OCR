"""
Script di test end-to-end: processa foto TEST1 con pipeline completa.
Preprocessa -> Estrai celle -> Classifica con SVM -> Report.
"""
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.preprocessor import preprocess_full_pipeline
from core.grid_extractor import extract_all_cells
from core.classifier import CBCLClassifier


def test_photo(photo_path: str, page: str, classifier: CBCLClassifier):
    print(f"\n{'='*60}")
    print(f"Foto: {Path(photo_path).name}")
    print(f"Pagina: {page}")
    print(f"{'='*60}")

    # Step 1: Preprocess
    print("\n1. Preprocessing...")
    gray, meta = preprocess_full_pipeline(photo_path)
    print(f"   Dim. finale: {meta['final_size']}")
    print(f"   Prospettiva: {'corretta' if meta['perspective_corrected'] else 'non corretta'}")

    # Step 2: Extract cells
    print("\n2. Estrazione celle...")
    cells = extract_all_cells(gray, page)
    print(f"   Items estratti: {len(cells)}")

    # Step 3: Classify with SVM
    print("\n3. Classificazione SVM...")
    results = {}
    for item_id, item_cells in cells.items():
        result = classifier.predict_item_cells(item_cells)
        results[item_id] = result

    # Step 4: Summary
    scored = sum(1 for r in results.values() if r["value"] is not None)
    missing = sum(1 for r in results.values() if r["flag"] == "missing")
    ambiguous = sum(1 for r in results.values() if r["flag"] == "ambiguous")
    multiple = sum(1 for r in results.values() if r["flag"] == "multiple_marks")

    print(f"\n4. Risultati:")
    print(f"   Items totali:  {len(results)}")
    print(f"   Risposte:      {scored}")
    print(f"   Mancanti:      {missing}")
    print(f"   Ambigui:       {ambiguous}")
    print(f"   Segni multipli:{multiple}")

    if scored > 0:
        avg_conf = sum(r["confidence"] for r in results.values() if r["value"] is not None) / scored
        print(f"   Confidence media: {avg_conf:.2%}")

    # Dettaglio prime 20 risposte
    print(f"\n   Dettaglio (prime 20 risposte trovate):")
    count = 0
    for item_id, r in sorted(results.items(), key=lambda x: str(x[0]).zfill(5)):
        if count >= 20:
            break
        value = r["value"]
        conf = r["confidence"]
        flag = r["flag"] or ""
        raw = r.get("raw_predictions", {})

        # Mostra predizioni per ogni colonna
        cols_info = []
        for col in ["0", "1", "2"]:
            if col in raw:
                cls = raw[col]["class"]
                c = raw[col]["confidence"]
                cols_info.append(f"{col}:{cls[:3]}({c:.0%})")

        col_str = " | ".join(cols_info)
        status = "OK" if value is not None else flag.upper()
        val_str = str(value) if value is not None else "-"

        print(f"   Item {item_id:>4s}: val={val_str} conf={conf:.0%} [{status}] -- {col_str}")
        count += 1

    return results


def main():
    # Load classifier
    print("Caricamento modello SVM...")
    classifier = CBCLClassifier()
    if not classifier.load():
        print("ERRORE: model.pkl non trovato! Esegui prima train_svm.py")
        sys.exit(1)
    print("Modello caricato.")

    test_dir = Path(__file__).parent.parent.parent / "TEST1"
    photos = sorted(test_dir.glob("*.jpeg")) + sorted(test_dir.glob("*.jpg"))

    if not photos:
        print("Nessuna foto in TEST1/")
        sys.exit(1)

    # Page 4: prima foto (03.15.39)
    if len(photos) >= 1:
        test_photo(str(photos[0]), "page_4", classifier)

    # Page 5: terza foto (03.15.40 senza (1))
    if len(photos) >= 3:
        test_photo(str(photos[2]), "page_5", classifier)

    print(f"\n{'='*60}")
    print("TEST E2E COMPLETATO")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
