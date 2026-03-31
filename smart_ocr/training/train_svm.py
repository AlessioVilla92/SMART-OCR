"""
training/train_svm.py

Addestra il modello SVM su HOG features e lo salva come model.pkl.

Uso:
    python training/train_svm.py

Output:
    models/model.pkl          - Modello SVM addestrato
    models/training_report.json - Metriche di accuracy

Il training usa ENTRAMBI i dataset: raw_cells (reali) + synthetic.
"""

import cv2
import numpy as np
import joblib
import json
from pathlib import Path
from sklearn.svm import SVC
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.metrics import classification_report, confusion_matrix
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from core.classifier import compute_hog_features


# Percorsi (relativi al progetto, non alla cwd)
_PROJECT_ROOT = Path(__file__).parent.parent
BINARY_DIR = _PROJECT_ROOT / "data" / "binary_generated"
MODEL_DIR = _PROJECT_ROOT / "models"
MODEL_PATH = MODEL_DIR / "model.pkl"
REPORT_PATH = MODEL_DIR / "training_report.json"

CLASSES = ["segnato", "vuoto"]
CELL_SIZE = (64, 64)

# Stessa CLAHE per-cella usata in grid_extractor.py
_cell_clahe = cv2.createCLAHE(clipLimit=1.5, tileGridSize=(2, 2))

# Soglie minime per procedere al training
MIN_SAMPLES_PER_CLASS = 30
TARGET_ACCURACY = 0.88


def _load_and_normalize(img_path) -> np.ndarray:
    """Carica, ridimensiona e applica CLAHE per-cella (stessa di grid_extractor)."""
    img = cv2.imread(str(img_path), cv2.IMREAD_GRAYSCALE)
    if img is None:
        return None
    img = cv2.resize(img, CELL_SIZE)
    img = _cell_clahe.apply(img)
    return img


def load_dataset():
    """
    Carica dataset binario da binary_generated/segnato e binary_generated/vuoto.
    Le immagini hanno gia CLAHE applicata dal generatore.
    Returns: (X numpy array, y numpy array, class_names list)
    """
    X = []
    y = []

    for class_idx, class_name in enumerate(CLASSES):
        images_loaded = 0
        class_dir = BINARY_DIR / class_name
        if not class_dir.exists():
            print(f"  ATTENZIONE: {class_dir} non trovata")
            continue
        for img_path in class_dir.glob("*.png"):
            img = _load_and_normalize(img_path)
            if img is not None:
                features = compute_hog_features(img)
                X.append(features)
                y.append(class_idx)
                images_loaded += 1

        print(f"  {class_name}: {images_loaded} immagini caricate")

        if images_loaded < MIN_SAMPLES_PER_CLASS:
            print(f"  ⚠️  ATTENZIONE: {class_name} ha solo {images_loaded} immagini (minimo: {MIN_SAMPLES_PER_CLASS})")
            print(f"     Esegui: python training/augmentor.py per generare più dati")

    return np.array(X, dtype=np.float32), np.array(y, dtype=np.int32), CLASSES


def train():
    """Esegue il training completo."""
    print("\n🏋️  Smart OCR — Training SVM")
    print("=" * 50)

    MODEL_DIR.mkdir(exist_ok=True)

    # Carica dataset
    print("\n📂 Caricamento dataset...")
    X, y, class_names = load_dataset()
    print(f"\n📊 Dataset totale: {len(X)} campioni, {len(class_names)} classi")

    for i, cls in enumerate(class_names):
        count = np.sum(y == i)
        print(f"   {cls}: {count} campioni")

    if len(X) < MIN_SAMPLES_PER_CLASS * len(class_names):
        print("\n❌ Dataset insufficiente per il training affidabile.")
        print("   Esegui prima: python training/label_tool.py (etichetta almeno 30 celle per classe)")
        print("   Poi: python training/augmentor.py (genera dati sintetici)")
        return False

    # Pipeline: StandardScaler + SVM
    print("\n⚙️  Configurazione modello SVM (kernel RBF, C=10, gamma=scale)...")
    model_pipeline = Pipeline([
        ('scaler', StandardScaler()),
        ('svm', SVC(
            kernel='rbf',
            C=10.0,
            gamma='scale',
            probability=True,       # Necessario per predict_proba
            class_weight='balanced', # Gestisce squilibrio classi
            random_state=42
        ))
    ])

    # Cross-validation (5-fold stratificata)
    print("\n🔄 Cross-validation 5-fold...")
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    cv_scores = cross_val_score(model_pipeline, X, y, cv=cv, scoring='accuracy', n_jobs=-1)

    mean_acc = cv_scores.mean()
    std_acc = cv_scores.std()

    print(f"\n📈 Risultati Cross-Validation:")
    print(f"   Accuracy media: {mean_acc:.4f} ± {std_acc:.4f}")
    print(f"   Per fold: {[f'{s:.4f}' for s in cv_scores]}")

    if mean_acc < TARGET_ACCURACY:
        print(f"\n⚠️  Accuracy {mean_acc:.1%} < target {TARGET_ACCURACY:.1%}")
        print("   Suggerimenti:")
        print("   - Aggiungi più immagini reali (specialmente casi difficili)")
        print("   - Aumenta AUGMENTATIONS_PER_IMAGE in augmentor.py")
        print("   - Controlla qualità delle label (errori di etichettatura)")
    else:
        print(f"\n✅ Accuracy {mean_acc:.1%} soddisfa il target {TARGET_ACCURACY:.1%}")

    # Training finale su tutto il dataset
    print("\n💾 Training finale su dataset completo...")
    model_pipeline.fit(X, y)

    # Valutazione finale (in-sample, solo indicativa)
    y_pred = model_pipeline.predict(X)
    report = classification_report(y_pred, y, target_names=class_names, output_dict=True)
    cm = confusion_matrix(y, y_pred)

    print("\n📋 Classification Report (in-sample):")
    print(classification_report(y_pred, y, target_names=class_names))
    print("Confusion Matrix:")
    print(cm)

    # Salva modello
    joblib.dump(model_pipeline, MODEL_PATH)
    print(f"\n✅ Modello salvato: {MODEL_PATH}")
    print(f"   Dimensione file: {MODEL_PATH.stat().st_size / 1024:.1f} KB")

    # Salva report training
    training_report = {
        "timestamp": __import__('datetime').datetime.now().isoformat(),
        "dataset_size": len(X),
        "classes": class_names,
        "cv_accuracy_mean": float(mean_acc),
        "cv_accuracy_std": float(std_acc),
        "cv_scores_per_fold": cv_scores.tolist(),
        "classification_report": report,
        "confusion_matrix": cm.tolist()
    }

    with open(REPORT_PATH, "w") as f:
        json.dump(training_report, f, indent=2)

    print(f"📊 Report salvato: {REPORT_PATH}")

    return True


if __name__ == "__main__":
    success = train()
    sys.exit(0 if success else 1)
