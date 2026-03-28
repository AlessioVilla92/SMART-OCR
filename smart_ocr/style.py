"""
style.py

Smart OCR — Dark Glassmorphism UI Theme (2026)
Tema professionale con glassmorphism, gradient orbs, animazioni.
"""

import streamlit as st


CUSTOM_CSS = """
<style>
/* ============================================================
   SMART OCR — Dark Glassmorphism Theme 2026
   ============================================================ */

/* === FONTS === */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif !important;
    -webkit-font-smoothing: antialiased;
}

code, pre, .stCode {
    font-family: 'JetBrains Mono', monospace !important;
}

/* === BACKGROUND CON GRADIENT ORBS ANIMATI === */
.stApp {
    background: #070B14 !important;
    background-image:
        radial-gradient(ellipse 600px 600px at 10% 20%, rgba(79, 70, 229, 0.15) 0%, transparent 70%),
        radial-gradient(ellipse 500px 500px at 80% 10%, rgba(124, 58, 237, 0.12) 0%, transparent 70%),
        radial-gradient(ellipse 400px 400px at 60% 80%, rgba(236, 72, 153, 0.08) 0%, transparent 70%),
        radial-gradient(ellipse 300px 300px at 30% 70%, rgba(6, 182, 212, 0.06) 0%, transparent 70%) !important;
}

/* === HIDE STREAMLIT CHROME === */
#MainMenu, footer, header[data-testid="stHeader"] {
    visibility: hidden !important;
    height: 0 !important;
}

.stApp > header {
    background: transparent !important;
}

/* === TITOLI === */
h1 {
    background: linear-gradient(135deg, #818CF8 0%, #A78BFA 30%, #C084FC 60%, #F472B6 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    font-weight: 800;
    font-size: 2.2rem !important;
    letter-spacing: -1px;
    line-height: 1.2;
    padding-bottom: 4px;
}

h2 {
    color: #E2E8F0 !important;
    font-weight: 700;
    font-size: 1.4rem !important;
    letter-spacing: -0.3px;
    border-bottom: 2px solid rgba(124, 58, 237, 0.3);
    padding-bottom: 8px;
    margin-top: 24px !important;
}

h3 {
    color: #CBD5E1 !important;
    font-weight: 600;
    font-size: 1.1rem !important;
}

p, li, span {
    color: #B0BEC5;
}

/* === SIDEBAR — GLASS PANEL === */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, rgba(7, 11, 20, 0.95) 0%, rgba(15, 23, 42, 0.95) 100%) !important;
    border-right: 1px solid rgba(124, 58, 237, 0.15) !important;
    backdrop-filter: blur(20px);
}

section[data-testid="stSidebar"] h3,
section[data-testid="stSidebar"] .stMarkdown h3 {
    background: linear-gradient(90deg, #818CF8, #A78BFA);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    font-size: 0.75rem !important;
    text-transform: uppercase;
    letter-spacing: 2px;
    font-weight: 700;
    border-bottom: none;
    padding-bottom: 0;
}

/* === GLASSMORPHISM CARDS (Metriche) === */
[data-testid="stMetric"] {
    background: rgba(15, 23, 42, 0.6) !important;
    border: 1px solid rgba(124, 58, 237, 0.2) !important;
    border-radius: 16px !important;
    padding: 20px 16px !important;
    backdrop-filter: blur(12px) saturate(1.5) !important;
    box-shadow:
        0 4px 24px rgba(0, 0, 0, 0.3),
        inset 0 1px 0 rgba(255, 255, 255, 0.05) !important;
    transition: all 0.3s ease !important;
}

[data-testid="stMetric"]:hover {
    border-color: rgba(124, 58, 237, 0.5) !important;
    box-shadow:
        0 8px 32px rgba(79, 70, 229, 0.15),
        inset 0 1px 0 rgba(255, 255, 255, 0.08) !important;
    transform: translateY(-2px);
}

[data-testid="stMetric"] label {
    color: #64748B !important;
    font-size: 0.75rem !important;
    font-weight: 600 !important;
    text-transform: uppercase;
    letter-spacing: 1.2px;
}

[data-testid="stMetric"] [data-testid="stMetricValue"] {
    color: #F1F5F9 !important;
    font-weight: 800 !important;
    font-size: 2rem !important;
}

/* === TABS — PILL STYLE === */
.stTabs [data-baseweb="tab-list"] {
    background: rgba(15, 23, 42, 0.5) !important;
    border: 1px solid rgba(124, 58, 237, 0.15);
    border-radius: 14px;
    padding: 5px;
    gap: 4px;
    backdrop-filter: blur(10px);
}

.stTabs [data-baseweb="tab"] {
    border-radius: 10px;
    color: #64748B !important;
    font-weight: 600;
    font-size: 0.9rem;
    padding: 10px 24px;
    transition: all 0.25s ease;
}

.stTabs [data-baseweb="tab"]:hover {
    color: #CBD5E1 !important;
    background: rgba(124, 58, 237, 0.1);
}

.stTabs [aria-selected="true"] {
    background: linear-gradient(135deg, rgba(79, 70, 229, 0.3), rgba(124, 58, 237, 0.2)) !important;
    color: #F1F5F9 !important;
    box-shadow: 0 2px 12px rgba(79, 70, 229, 0.2);
}

.stTabs [data-baseweb="tab-highlight"] {
    display: none !important;
}

.stTabs [data-baseweb="tab-border"] {
    display: none !important;
}

/* === BUTTONS — GRADIENT + GLOW === */
.stButton > button {
    background: linear-gradient(135deg, #4F46E5 0%, #7C3AED 100%) !important;
    color: white !important;
    border: none !important;
    border-radius: 12px !important;
    font-weight: 600;
    font-size: 0.9rem;
    letter-spacing: 0.3px;
    padding: 10px 24px;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
    box-shadow: 0 2px 8px rgba(79, 70, 229, 0.3);
}

.stButton > button:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 6px 20px rgba(79, 70, 229, 0.5) !important;
    background: linear-gradient(135deg, #6366F1 0%, #8B5CF6 100%) !important;
}

.stButton > button:active {
    transform: translateY(0) !important;
}

/* === FILE UPLOADER — GLASS DROP ZONE === */
[data-testid="stFileUploader"] {
    background: rgba(15, 23, 42, 0.4) !important;
    border: 2px dashed rgba(124, 58, 237, 0.3) !important;
    border-radius: 16px !important;
    padding: 24px !important;
    backdrop-filter: blur(8px);
    transition: all 0.3s ease !important;
}

[data-testid="stFileUploader"]:hover {
    border-color: rgba(124, 58, 237, 0.6) !important;
    background: rgba(15, 23, 42, 0.6) !important;
    box-shadow: 0 0 30px rgba(79, 70, 229, 0.1);
}

[data-testid="stFileUploader"] small {
    color: #64748B !important;
}

/* === DATAFRAME / TABLE — GLASS === */
[data-testid="stDataFrame"] {
    border-radius: 14px !important;
    overflow: hidden !important;
    border: 1px solid rgba(124, 58, 237, 0.15) !important;
    box-shadow: 0 4px 24px rgba(0, 0, 0, 0.2);
}

/* === SELECT BOX / INPUT === */
[data-testid="stSelectbox"] > div > div,
.stNumberInput > div > div > input,
.stTextInput > div > div > input {
    background: rgba(15, 23, 42, 0.6) !important;
    border: 1px solid rgba(124, 58, 237, 0.2) !important;
    border-radius: 10px !important;
    color: #E2E8F0 !important;
    backdrop-filter: blur(8px);
    transition: border-color 0.2s;
}

[data-testid="stSelectbox"] > div > div:focus-within,
.stNumberInput > div > div > input:focus,
.stTextInput > div > div > input:focus {
    border-color: rgba(124, 58, 237, 0.6) !important;
    box-shadow: 0 0 0 2px rgba(124, 58, 237, 0.15) !important;
}

/* === SLIDER === */
.stSlider > div > div > div[role="slider"] {
    background: linear-gradient(135deg, #4F46E5, #7C3AED) !important;
    box-shadow: 0 2px 8px rgba(79, 70, 229, 0.4);
}

.stSlider > div > div > div > div {
    background: rgba(124, 58, 237, 0.3) !important;
}

/* === ALERTS — GLASS STYLE === */
[data-testid="stAlert"] {
    background: rgba(15, 23, 42, 0.5) !important;
    border-radius: 12px !important;
    backdrop-filter: blur(8px) !important;
    border: 1px solid rgba(255, 255, 255, 0.05) !important;
}

/* === PROGRESS BAR — GRADIENT ANIMATED === */
.stProgress > div > div > div {
    background: linear-gradient(90deg, #4F46E5, #7C3AED, #A78BFA, #C084FC, #EC4899) !important;
    background-size: 200% 100%;
    animation: shimmer 2s linear infinite;
    border-radius: 6px !important;
}

@keyframes shimmer {
    0% { background-position: 200% 0; }
    100% { background-position: -200% 0; }
}

/* === DOWNLOAD BUTTON === */
.stDownloadButton > button {
    background: rgba(15, 23, 42, 0.6) !important;
    border: 1px solid rgba(124, 58, 237, 0.3) !important;
    border-radius: 12px !important;
    color: #CBD5E1 !important;
    backdrop-filter: blur(8px);
    transition: all 0.3s ease;
}

.stDownloadButton > button:hover {
    background: rgba(79, 70, 229, 0.15) !important;
    border-color: rgba(124, 58, 237, 0.6) !important;
    color: #F1F5F9 !important;
    box-shadow: 0 4px 16px rgba(79, 70, 229, 0.2);
    transform: translateY(-1px);
}

/* === CHECKBOX === */
.stCheckbox label span {
    color: #94A3B8 !important;
}

/* === EXPANDER === */
.streamlit-expanderHeader {
    background: rgba(15, 23, 42, 0.4) !important;
    border-radius: 10px !important;
    border: 1px solid rgba(124, 58, 237, 0.15) !important;
}

/* === IMAGES — ROUNDED === */
[data-testid="stImage"] img {
    border-radius: 12px;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
}

/* === DIVIDER === */
hr {
    border-color: rgba(124, 58, 237, 0.15) !important;
    margin: 20px 0 !important;
}

/* === SPINNER === */
.stSpinner > div > div {
    border-top-color: #7C3AED !important;
}

/* === SUCCESS / WARNING / ERROR BANNERS === */
.stSuccess {
    background: rgba(16, 185, 129, 0.1) !important;
    border-left: 4px solid #10B981 !important;
}

.stWarning {
    background: rgba(245, 158, 11, 0.1) !important;
    border-left: 4px solid #F59E0B !important;
}

.stError {
    background: rgba(239, 68, 68, 0.1) !important;
    border-left: 4px solid #EF4444 !important;
}

/* === CUSTOM COMPONENTS === */

/* Version badge */
.version-badge {
    display: inline-block;
    background: linear-gradient(135deg, #4F46E5, #7C3AED);
    color: white;
    padding: 3px 12px;
    border-radius: 20px;
    font-size: 0.7rem;
    font-weight: 700;
    letter-spacing: 0.5px;
    box-shadow: 0 2px 8px rgba(79, 70, 229, 0.3);
    vertical-align: middle;
}

/* Status pill */
.status-pill {
    display: inline-block;
    padding: 4px 14px;
    border-radius: 20px;
    font-size: 0.78rem;
    font-weight: 600;
    letter-spacing: 0.3px;
}
.status-pill.ok { background: rgba(16, 185, 129, 0.15); color: #34D399; border: 1px solid rgba(16, 185, 129, 0.3); }
.status-pill.warn { background: rgba(245, 158, 11, 0.15); color: #FBBF24; border: 1px solid rgba(245, 158, 11, 0.3); }
.status-pill.error { background: rgba(239, 68, 68, 0.15); color: #F87171; border: 1px solid rgba(239, 68, 68, 0.3); }
.status-pill.info { background: rgba(79, 70, 229, 0.15); color: #A78BFA; border: 1px solid rgba(79, 70, 229, 0.3); }

/* Glass card */
.glass-card {
    background: rgba(15, 23, 42, 0.5);
    border: 1px solid rgba(124, 58, 237, 0.15);
    border-radius: 16px;
    padding: 24px;
    backdrop-filter: blur(12px) saturate(1.5);
    box-shadow: 0 4px 24px rgba(0, 0, 0, 0.2), inset 0 1px 0 rgba(255, 255, 255, 0.05);
    margin-bottom: 16px;
}

/* Glow text */
.glow-text {
    color: #A78BFA;
    text-shadow: 0 0 20px rgba(124, 58, 237, 0.3);
}

/* Subtle separator */
.subtle-sep {
    height: 1px;
    background: linear-gradient(90deg, transparent, rgba(124, 58, 237, 0.3), transparent);
    border: none;
    margin: 24px 0;
}

/* Scrollbar styling */
::-webkit-scrollbar {
    width: 6px;
    height: 6px;
}
::-webkit-scrollbar-track {
    background: rgba(15, 23, 42, 0.3);
}
::-webkit-scrollbar-thumb {
    background: rgba(124, 58, 237, 0.3);
    border-radius: 3px;
}
::-webkit-scrollbar-thumb:hover {
    background: rgba(124, 58, 237, 0.5);
}
</style>
"""


def inject_custom_css():
    """Inietta il CSS glassmorphism nella pagina."""
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


def render_header(title: str, subtitle: str = "", version: str = "1.0"):
    """Header con titolo gradiente e badge versione."""
    inject_custom_css()
    st.markdown(
        f"# {title} <span class='version-badge'>v{version}</span>",
        unsafe_allow_html=True
    )
    if subtitle:
        st.markdown(
            f"<p style='color:#64748B; font-size:1.05rem; margin-top:-8px; font-weight:400;'>{subtitle}</p>",
            unsafe_allow_html=True
        )
    st.markdown("<div class='subtle-sep'></div>", unsafe_allow_html=True)


def glass_card(content: str):
    """Render un blocco di contenuto in una glass card."""
    st.markdown(f"<div class='glass-card'>{content}</div>", unsafe_allow_html=True)


def status_pill(text: str, status: str = "ok"):
    """Render una pill colorata. status: ok, warn, error, info"""
    return f"<span class='status-pill {status}'>{text}</span>"
