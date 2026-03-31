"""
training/mode_b/benchmark.py

Confronto Mode A (SVM) vs Mode B (YOLO ONNX) sullo stesso dataset di test.
Misura accuracy, tempo di processing, e discrepanze tra i due mode.

Uso:
    python training/mode_b/benchmark.py
    python training/mode_b/benchmark.py --max-per-class 50
"""

import time
import cv2
import numpy as np
from pathlib import Path
from collections import defaultdict
import argparse
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config import Config


def collect_test_cells(max_per_class: int = 30) -> list:
    """Raccoglie celle di test con label nota."""
    cells = []
    classes = ["cerchio", "x_rossa", "vuoto"]

    # Usa raw_cells come ground truth (etichettate manualmente)
    source_dir = Config.DATA_DIR / "raw_cells"
    if not source_dir.exists():
        print(f"❌ Directory raw_cells non trovata: {source_dir}")
        return cells

    for class_name in classes:
        class_dir = source_dir / class_name
        if not class_dir.exists():
            continue
        for img_path in sorted(class_dir.glob("*.png"))[:max_per_class]:
            img = cv2.imread(str(img_path), cv2.IMREAD_GRAYSCALE)
            if img is not None:
                img = cv2.resize(img, (64, 64))
                cells.append((img, class_name, str(img_path)))

    return cells


def benchmark(max_per_class: int = 30):
    """Confronto Mode A vs Mode B."""

    print("\n📊 Benchmark Mode A (SVM) vs Mode B (YOLO ONNX)")
    print("=" * 55)

    # Raccogli dati test
    test_cells = collect_test_cells(max_per_class)
    if not test_cells:
        return False

    print(f"   Celle di test: {len(test_cells)}")

    results = {"svm": [], "yolo": []}
    times = {"svm": 0.0, "yolo": 0.0}

    # --- Mode A: SVM ---
    svm_available = Config.svm_model_available()
    if svm_available:
        try:
            from pipeline.mode_a.svm_classifier import SVMClassifier
            svm = SVMClassifier()

            start = time.time()
            for cell, true_class, path in test_cells:
                pred_class, pred_conf = svm.predict_cell(cell)
                results["svm"].append({
                    "true": true_class,
                    "pred": pred_class,
                    "conf": pred_conf,
                    "path": path,
                })
            times["svm"] = time.time() - start
            print(f"\n✅ Mode A (SVM): {len(results['svm'])} predizioni in {times['svm']*1000:.0f}ms")

        except Exception as e:
            print(f"\n❌ Mode A (SVM) errore: {e}")
            svm_available = False

    if not svm_available:
        print("\n⚠️  Mode A (SVM) non disponibile — skip")

    # --- Mode B: YOLO ---
    yolo_available = Config.yolo_model_available()
    if yolo_available:
        try:
            from pipeline.mode_b.yolo_classifier import YOLOClassifier
            yolo = YOLOClassifier()

            start = time.time()
            for cell, true_class, path in test_cells:
                pred_class, pred_conf = yolo.predict_cell(cell)
                results["yolo"].append({
                    "true": true_class,
                    "pred": pred_class,
                    "conf": pred_conf,
                    "path": path,
                })
            times["yolo"] = time.time() - start
            print(f"✅ Mode B (YOLO): {len(results['yolo'])} predizioni in {times['yolo']*1000:.0f}ms")

        except Exception as e:
            print(f"\n❌ Mode B (YOLO) errore: {e}")
            yolo_available = False

    if not yolo_available:
        print("⚠️  Mode B (YOLO) non disponibile — skip")

    # --- Report ---
    print("\n" + "=" * 55)
    print("📋 RISULTATI BENCHMARK")
    print("=" * 55)

    for mode_name in ("svm", "yolo"):
        mode_results = results[mode_name]
        if not mode_results:
            continue

        mode_label = "Mode A (SVM)" if mode_name == "svm" else "Mode B (YOLO)"
        correct = sum(1 for r in mode_results if r["pred"] == r["true"])
        total = len(mode_results)
        accuracy = correct / total * 100 if total > 0 else 0

        # Ambigui
        ambiguous = sum(1 for r in mode_results if r["pred"] == "ambiguo")

        # Confidence media
        mean_conf = sum(r["conf"] for r in mode_results) / total if total else 0

        # Tempo medio per cella
        ms_per_cell = (times[mode_name] / total * 1000) if total > 0 else 0

        print(f"\n   {mode_label}:")
        print(f"     Accuracy:        {correct}/{total} ({accuracy:.1f}%)")
        print(f"     Ambigui:         {ambiguous}")
        print(f"     Confidence media: {mean_conf:.3f}")
        print(f"     Tempo totale:    {times[mode_name]*1000:.0f}ms")
        print(f"     Tempo/cella:     {ms_per_cell:.1f}ms")

        # Errori per classe
        errors = defaultdict(list)
        for r in mode_results:
            if r["pred"] != r["true"] and r["pred"] != "ambiguo":
                errors[f"{r['true']} → {r['pred']}"].append(Path(r["path"]).name)

        if errors:
            print(f"     Errori:")
            for pattern, files in errors.items():
                print(f"       {pattern}: {len(files)} ({', '.join(files[:3])})")

    # --- Confronto diretto ---
    if results["svm"] and results["yolo"]:
        print(f"\n{'─' * 55}")
        print("🔀 CONFRONTO DIRETTO Mode A vs Mode B:")

        agreements = 0
        disagreements = []
        for svm_r, yolo_r in zip(results["svm"], results["yolo"]):
            if svm_r["pred"] == yolo_r["pred"]:
                agreements += 1
            else:
                disagreements.append({
                    "path": Path(svm_r["path"]).name,
                    "true": svm_r["true"],
                    "svm": f"{svm_r['pred']}({svm_r['conf']:.2f})",
                    "yolo": f"{yolo_r['pred']}({yolo_r['conf']:.2f})",
                })

        total = len(results["svm"])
        print(f"   Accordo:      {agreements}/{total} ({agreements/total*100:.1f}%)")
        print(f"   Disaccordo:   {len(disagreements)}")

        if disagreements:
            print(f"\n   Celle con predizioni diverse:")
            for d in disagreements[:10]:
                print(f"     {d['path']}: true={d['true']}, SVM={d['svm']}, YOLO={d['yolo']}")

    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Benchmark Mode A vs Mode B")
    parser.add_argument("--max-per-class", type=int, default=30,
                        help="Max celle per classe (default: 30)")
    args = parser.parse_args()

    success = benchmark(args.max_per_class)
    sys.exit(0 if success else 1)
