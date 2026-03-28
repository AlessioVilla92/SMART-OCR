"""Test base per il modulo preprocessor."""
import pytest
import numpy as np
import cv2
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from core.preprocessor import (
    load_image, to_grayscale, denoise, binarize_adaptive,
    deskew, normalize_resolution, enhance_contrast
)


def make_test_image(w=800, h=1000) -> np.ndarray:
    """Crea immagine di test sintetica (foglio bianco con linee)."""
    img = np.full((h, w, 3), 240, dtype=np.uint8)
    for y in range(100, h-100, 80):
        cv2.line(img, (50, y), (w-50, y), (100, 100, 100), 1)
    return img


def test_load_numpy_array():
    img = make_test_image()
    result = load_image(img)
    assert result.shape == img.shape


def test_grayscale_conversion():
    img = make_test_image()
    gray = to_grayscale(img)
    assert len(gray.shape) == 2


def test_grayscale_already_gray():
    gray = np.random.randint(0, 255, (100, 100), dtype=np.uint8)
    result = to_grayscale(gray)
    assert len(result.shape) == 2


def test_normalize_resolution():
    img = make_test_image(w=1200, h=1600)
    gray = to_grayscale(img)
    normalized = normalize_resolution(gray, target_width=2480)
    assert normalized.shape[1] == 2480


def test_deskew_no_rotation():
    img = make_test_image()
    gray = to_grayscale(img)
    result, angle = deskew(gray)
    assert abs(angle) < 5.0  # Immagine già diritta


def test_full_pipeline_synthetic():
    """Test pipeline completa su immagine sintetica."""
    from core.preprocessor import preprocess_full_pipeline
    img = make_test_image(1200, 1600)
    result, meta = preprocess_full_pipeline(img)

    assert result is not None
    assert len(result.shape) == 2
    assert 'original_size' in meta
    assert 'final_size' in meta
    assert 'warnings' in meta
