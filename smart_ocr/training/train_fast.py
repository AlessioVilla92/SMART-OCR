"""
training/train_fast.py

Training VELOCE con SGDClassifier (lineare) — completa in 1-2 minuti.
Produce lo stesso modello compatibile con core/classifier.py.

SGDClassifier + CalibratedClassifierCV:
- Scala linearmente O(n) vs O(n^3) di SVC RBF
- predict_proba via calibrazione isotonica
- 93.25% accuracy nel training precedente (training_report.json)

Uso: python training/train_fast.py
"""

import cv2
import numpy as np
import joblib
import json
from pathlib import Path
from sklearn.linear_model import SGDClassifier
from sklearn.calibration import CalibratedClassifierCV
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.metrics import classification_report, confusion_matrix
import sys
import time

sys.path.insert(0, str(Path(__file__).parent.parent))
from core.classifier import compute_hog_features

_PROJECT_ROOT = Path(__file__).parent.parent
BINARY_DIR = _PROJECT_ROOT / "data" / "binary_generated"
MODEL_DIR = _PROJECT_ROOT / "models"
MODEL_PATH = MODEL_DIR / "svm_classifier.pkl"
MODEL_PATH_LEGACY = MODEL_DIR / "model.pkl"
REPORT_PATH = MODEL_DIR / "training_report.json"

CLASSES = ["segnato", "vuoto"]
CELL_SIZE = (64, 64)
_cell_clahe = cv2.createCLAHE(clipLimit=1.5, tileGridSize=(2, 2))


def _load_and_normalize(img_path):
    img = cv2.imread(str(img_path), cv2.IMREAD_GRAYSCALE)
    if img is None:
        return None
    img = cv2.resize(img, CELL_SIZE)
    img = _cell_clahe.apply(img)
    return img


def load_dataset():
    X, y = [], []
    for class_idx, class_name in enumerate(CLASSES):
        count = 0
        class_dir = BINARY_DIR / class_name
        if not class_dir.exists():
            print(f"  WARNING: {class_dir} non trovata")
            continue
        for img_path in class_dir.glob("*.png"):
            img = _load_and_normalize(img_path)
            if img is not None:
                features = compute_hog_features(img)
                X.append(features)
                y.append(class_idx)
                count += 1
        print(f"  {class_name}: {count} immagini")
    return np.array(X, dtype=np.float32), np.array(y, dtype=np.int32)


def train():
    print("\n--- Smart OCR - Training FAST (SGDClassifier) ---")
    print("=" * 50)

    MODEL_DIR.mkdir(exist_ok=True)

    # Carica dataset
    print("\nCaricamento dataset...")
    t0 = time.time()
    X, y = load_dataset()
    t_load = time.time() - t0
    print(f"\nDataset: {len(X)} campioni in {t_load:.0f}s")
    for i, cls in enumerate(CLASSES):
        print(f"  {cls}: {np.sum(y == i)}")

    # Train/test split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, stratify=y, random_state=42
    )
    print(f"\nSplit: {len(X_train)} train, {len(X_test)} test")

    # Pipeline: Scaler + SGDClassifier + Calibrazione
    print("\nTraining SGDClassifier + CalibratedCV...")
    t0 = time.time()

    # SGD con hinge loss = SVM lineare
    base_model = Pipeline([
        ('scaler', StandardScaler()),
        ('sgd', SGDClassifier(
            loss='hinge',
            alpha=1e-4,
            max_iter=1000,
            class_weight='balanced',
            random_state=42,
            n_jobs=-1
        ))
    ])

    # Calibrazione per ottenere predict_proba
    model = CalibratedClassifierCV(base_model, cv=5, method='isotonic')
    model.fit(X_train, y_train)
    t_train = time.time() - t0
    print(f"Training completato in {t_train:.1f}s")

    # Valutazione su test set
    y_pred = model.predict(X_test)
    test_acc = np.mean(y_pred == y_test)
    cm = confusion_matrix(y_test, y_pred)
    report = classification_report(y_test, y_pred, target_names=CLASSES, output_dict=True)

    print(f"\nTest Accuracy: {test_acc:.4f} ({test_acc:.1%})")
    print(classification_report(y_test, y_pred, target_names=CLASSES))
    print("Confusion Matrix:")
    print(cm)

    # Cross-validation su tutto il dataset
    print("\nCross-validation 5-fold...")
    t0 = time.time()
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    cv_model = CalibratedClassifierCV(
        Pipeline([
            ('scaler', StandardScaler()),
            ('sgd', SGDClassifier(
                loss='hinge', alpha=1e-4, max_iter=1000,
                class_weight='balanced', random_state=42
            ))
        ]),
        cv=3, method='isotonic'
    )
    cv_scores = cross_val_score(cv_model, X, y, cv=cv, scoring='accuracy', n_jobs=-1)
    t_cv = time.time() - t0
    print(f"CV Accuracy: {cv_scores.mean():.4f} +/- {cv_scores.std():.4f} in {t_cv:.1f}s")
    print(f"Per fold: {[f'{s:.4f}' for s in cv_scores]}")

    # Training finale su TUTTO il dataset
    print("\nTraining finale su dataset completo...")
    t0 = time.time()
    final_model = CalibratedClassifierCV(
        Pipeline([
            ('scaler', StandardScaler()),
            ('sgd', SGDClassifier(
                loss='hinge', alpha=1e-4, max_iter=1000,
                class_weight='balanced', random_state=42
            ))
        ]),
        cv=5, method='isotonic'
    )
    final_model.fit(X, y)
    t_final = time.time() - t0
    print(f"Completato in {t_final:.1f}s")

    # Salva
    joblib.dump(final_model, MODEL_PATH)
    joblib.dump(final_model, MODEL_PATH_LEGACY)
    print(f"\nModello salvato: {MODEL_PATH}")
    print(f"Dimensione: {MODEL_PATH.stat().st_size / 1024:.1f} KB")

    # Report
    training_report = {
        "timestamp": __import__('datetime').datetime.now().isoformat(),
        "dataset_size": len(X),
        "classes": CLASSES,
        "classifier_type": "SGDClassifier+CalibratedCV",
        "includes_real_cells": True,
        "test_accuracy": float(test_acc),
        "train_size": len(X_train),
        "test_size": len(X_test),
        "cv_accuracy_mean": float(cv_scores.mean()),
        "cv_accuracy_std": float(cv_scores.std()),
        "cv_scores_per_fold": cv_scores.tolist(),
        "confusion_matrix": cm.tolist(),
        "classification_report": report,
        "training_time_seconds": t_load + t_train + t_cv + t_final
    }

    with open(REPORT_PATH, "w") as f:
        json.dump(training_report, f, indent=2)
    print(f"Report: {REPORT_PATH}")

    return True


if __name__ == "__main__":
    success = train()
    sys.exit(0 if success else 1)
