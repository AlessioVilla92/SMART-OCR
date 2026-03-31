"""
pipeline/mode_a/hog_extractor.py

Re-export delle HOG features da core.classifier.
"""

from core.classifier import compute_hog_features

__all__ = ["compute_hog_features"]
