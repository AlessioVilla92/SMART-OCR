"""
pipeline/preprocessor.py

Wrapper condiviso: re-export del preprocessing da core.preprocessor.
Usato da entrambi i mode (A e B).
"""

from core.preprocessor import preprocess_full_pipeline, PreprocessingError

__all__ = ["preprocess_full_pipeline", "PreprocessingError"]
