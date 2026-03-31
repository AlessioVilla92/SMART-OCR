"""
pipeline/grid_extractor.py

Wrapper condiviso: re-export dell'estrazione griglia da core.grid_extractor.
Usato da entrambi i mode (A e B).
"""

from core.grid_extractor import (
    extract_all_cells,
    visualize_grid_overlay,
    extract_cell,
    load_template,
    GridExtractionError,
    CELL_SIZE,
)

__all__ = [
    "extract_all_cells",
    "visualize_grid_overlay",
    "extract_cell",
    "load_template",
    "GridExtractionError",
    "CELL_SIZE",
]
