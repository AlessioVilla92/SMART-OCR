"""
training/shared/augmentor.py

Re-export da training/augmentor.py.
Condiviso tra Mode A e Mode B.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from augmentor import (
    get_augmentation_pipeline,
    augment_class,
    run_all_augmentations,
    RAW_DIR,
    SYNTHETIC_DIR,
    CLASSES,
    CELL_SIZE,
    AUGMENTATIONS_PER_IMAGE,
)

__all__ = [
    "get_augmentation_pipeline",
    "augment_class",
    "run_all_augmentations",
    "RAW_DIR",
    "SYNTHETIC_DIR",
    "CLASSES",
    "CELL_SIZE",
    "AUGMENTATIONS_PER_IMAGE",
]
