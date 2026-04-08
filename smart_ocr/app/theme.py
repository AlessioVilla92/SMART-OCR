"""Dark theme moderno per Smart OCR — glassmorphism inspired."""

import qdarktheme


def apply_dark_theme(app):
    """Applica dark theme base."""
    stylesheet = qdarktheme.load_stylesheet("dark")
    app.setStyleSheet(stylesheet)


COLORS = {
    "bg_primary": "#0B0F19",
    "bg_secondary": "#141922",
    "bg_card": "#1A1F2E",
    "bg_card_hover": "#222838",
    "bg_glass": "rgba(26, 31, 46, 0.85)",
    "text_primary": "#E8ECF4",
    "text_secondary": "#7B8794",
    "text_muted": "#4A5568",
    "accent": "#7C5CFC",
    "accent_light": "#9B7FFF",
    "accent_glow": "rgba(124, 92, 252, 0.25)",
    "success": "#34D399",
    "success_bg": "rgba(52, 211, 153, 0.12)",
    "warning": "#FBBF24",
    "warning_bg": "rgba(251, 191, 36, 0.12)",
    "error": "#F87171",
    "error_bg": "rgba(248, 113, 113, 0.12)",
    "info": "#60A5FA",
    "info_bg": "rgba(96, 165, 250, 0.12)",
    "border": "#2A3040",
    "border_light": "#343B4D",
    "gradient_start": "#7C5CFC",
    "gradient_end": "#B94FFF",
}

STYLESHEET_EXTRA = """
/* ── Base ── */
QMainWindow {
    background-color: #0B0F19;
}

QWidget {
    font-family: 'Segoe UI', 'Inter', sans-serif;
}

/* ── Sidebar ── */
#sidebar {
    background-color: #101420;
    border-right: 1px solid #1E2433;
    min-width: 200px;
    max-width: 200px;
}

#sidebar_logo {
    font-size: 20px;
    font-weight: 800;
    padding: 20px 0 8px;
    color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #7C5CFC, stop:1 #B94FFF);
}

#sidebar QPushButton {
    text-align: left;
    padding: 14px 20px;
    border: none;
    border-radius: 10px;
    color: #7B8794;
    font-size: 13px;
    font-weight: 500;
    margin: 2px 8px;
}

#sidebar QPushButton:hover {
    background-color: rgba(124, 92, 252, 0.08);
    color: #B0B8C4;
}

#sidebar QPushButton:checked {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 rgba(124,92,252,0.2), stop:1 rgba(185,79,255,0.1));
    color: #9B7FFF;
    font-weight: 700;
    border-left: 3px solid #7C5CFC;
}

/* ── Cards ── */
QGroupBox {
    background-color: #141922;
    border: 1px solid #1E2433;
    border-radius: 12px;
    padding: 16px;
    margin-top: 12px;
    font-size: 13px;
    font-weight: 600;
    color: #E8ECF4;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 4px 12px;
    color: #9B7FFF;
}

/* ── Scroll area ── */
#cbcl_scroll {
    background-color: #0B0F19;
    border: none;
}

QScrollBar:vertical {
    background: #0B0F19;
    width: 8px;
    border-radius: 4px;
}

QScrollBar::handle:vertical {
    background: #2A3040;
    border-radius: 4px;
    min-height: 40px;
}

QScrollBar::handle:vertical:hover {
    background: #3A4050;
}

/* ── Status bar ── */
#status_bar {
    background-color: #101420;
    border-top: 1px solid #1E2433;
    padding: 6px 16px;
    color: #7B8794;
    font-size: 11px;
}

/* ── Analyze button ── */
#analyze_btn {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #7C5CFC, stop:1 #B94FFF);
    color: white;
    font-size: 15px;
    font-weight: 700;
    padding: 14px 32px;
    border-radius: 12px;
    border: none;
    letter-spacing: 1px;
}

#analyze_btn:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #9B7FFF, stop:1 #C96FFF);
}

#analyze_btn:pressed {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #6344E0, stop:1 #A040E0);
}

#analyze_btn:disabled {
    background: #2A3040;
    color: #4A5568;
}

/* ── Export buttons ── */
#export_btn {
    background-color: #1A1F2E;
    color: #E8ECF4;
    font-size: 13px;
    font-weight: 600;
    padding: 10px 24px;
    border-radius: 10px;
    border: 1px solid #2A3040;
}

#export_btn:hover {
    background-color: #222838;
    border-color: #7C5CFC;
    color: #9B7FFF;
}

/* ── Progress bar ── */
QProgressBar {
    background-color: #141922;
    border: 1px solid #1E2433;
    border-radius: 6px;
    height: 12px;
    text-align: center;
    font-size: 9px;
    color: #7B8794;
}

QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #7C5CFC, stop:1 #B94FFF);
    border-radius: 5px;
}

/* ── ComboBox ── */
QComboBox {
    background-color: #1A1F2E;
    border: 1px solid #2A3040;
    border-radius: 8px;
    padding: 8px 12px;
    color: #E8ECF4;
    font-size: 12px;
}

QComboBox:hover {
    border-color: #7C5CFC;
}

/* ── Table ── */
QTableWidget {
    background-color: #141922;
    border: 1px solid #1E2433;
    border-radius: 8px;
    gridline-color: #1E2433;
    color: #E8ECF4;
    font-size: 12px;
}

QTableWidget::item {
    padding: 8px;
}

QHeaderView::section {
    background-color: #1A1F2E;
    color: #9B7FFF;
    font-weight: 700;
    font-size: 11px;
    border: none;
    border-bottom: 2px solid #7C5CFC;
    padding: 8px;
}

/* ── Score display ── */
#score_big {
    font-size: 56px;
    font-weight: 800;
    color: #7C5CFC;
}

#score_label {
    font-size: 14px;
    color: #7B8794;
    font-weight: 500;
}

/* ── Stat cards ── */
#stat_value {
    font-size: 22px;
    font-weight: 700;
    color: #E8ECF4;
}

#stat_name {
    font-size: 10px;
    color: #7B8794;
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 1px;
}
"""
