"""Test base per il modulo classifier."""
import pytest
import numpy as np
import cv2
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from core.classifier import compute_hog_features, CBCLClassifier, CELL_SIZE


def make_test_cell(pattern: str = "empty") -> np.ndarray:
    """Crea cella di test sintetica 64x64."""
    cell = np.full(CELL_SIZE, 255, dtype=np.uint8)

    if pattern == "circle":
        cv2.circle(cell, (32, 32), 20, 0, 2)
    elif pattern == "x_mark":
        cv2.line(cell, (12, 12), (52, 52), 0, 3)
        cv2.line(cell, (52, 12), (12, 52), 0, 3)

    return cell


def test_hog_features_shape():
    cell = make_test_cell()
    features = compute_hog_features(cell)
    assert features.shape == (1764,)


def test_hog_features_deterministic():
    cell = make_test_cell("circle")
    f1 = compute_hog_features(cell)
    f2 = compute_hog_features(cell)
    np.testing.assert_array_equal(f1, f2)


def test_hog_features_different_patterns():
    empty = compute_hog_features(make_test_cell("empty"))
    circle = compute_hog_features(make_test_cell("circle"))
    x_mark = compute_hog_features(make_test_cell("x_mark"))

    # Features diverse per pattern diversi
    assert not np.allclose(empty, circle)
    assert not np.allclose(empty, x_mark)
    assert not np.allclose(circle, x_mark)


def test_classifier_no_model():
    classifier = CBCLClassifier()
    assert not classifier.is_loaded
    assert classifier.load(Path("/nonexistent/model.pkl")) is False


def test_hog_resize():
    """Test che HOG gestisca celle di dimensioni diverse."""
    small_cell = np.full((32, 32), 200, dtype=np.uint8)
    features = compute_hog_features(small_cell)
    assert features.shape == (1764,)
