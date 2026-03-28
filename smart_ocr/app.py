"""
app.py

Smart OCR — Applicazione principale Streamlit.
Avvio: streamlit run app.py

Pagine:
1. 📤 Analisi Questionario — Upload foto e analisi automatica
2. 📊 Risultati — Tabella item con valori e flag
3. 💾 Export — Download JSON e CSV
4. ⚙️  Impostazioni — Soglia ambiguità, debug mode
"""

import streamlit as st
import cv2
import numpy as np
import pandas as pd
import json
import tempfile
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))

from core.preprocessor import preprocess_full_pipeline
from core.grid_extractor import extract_all_cells, visualize_grid_overlay
from core.classifier import get_classifier
from core.omr_classifier import classify_all_items_omr
from core.scorer import build_score_report, report_to_csv, report_to_json, ALL_ITEMS
from core.calibrator import get_calibration_status
from style import inject_custom_css, render_header, glass_card, status_pill


# Configurazione pagina
st.set_page_config(
    page_title="Smart OCR — CBCL Scanner",
    page_icon="🧾",
    layout="wide",
    initial_sidebar_state="expanded"
)
inject_custom_css()


def check_ready() -> str:
    """
    Verifica che il sistema sia pronto per l'analisi.
    Returns: "svm" se modello SVM disponibile, "omr" se solo calibrazione, "none" se nulla
    """
    # Controlla calibrazione
    status = get_calibration_status()
    if not status:
        st.error(
            "⚠️ Griglia non calibrata.\n\n"
            "**Esegui prima la calibrazione:**\n"
            "`streamlit run training/label_tool.py` → tab 'Calibra Griglia'"
        )
        return "none"

    # Controlla modello SVM (opzionale)
    classifier = get_classifier()
    if classifier.is_loaded:
        return "svm"

    st.info("ℹ️ Modello SVM non trovato — uso riconoscimento OMR (pixel-counting).")
    return "omr"


def process_uploaded_image(uploaded_file, page: str, method: str, debug: bool = False) -> dict:
    """
    Processa un questionario caricato e ritorna il report completo.
    method: "svm" o "omr"
    """
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        tmp.write(uploaded_file.read())
        tmp_path = tmp.name
    uploaded_file.seek(0)

    with st.spinner("1/4 — Pre-processing immagine..."):
        gray, meta = preprocess_full_pipeline(tmp_path, debug=debug)

    if meta.get("warnings"):
        for w in meta["warnings"]:
            st.warning(f"⚠️ {w}")

    with st.spinner("2/4 — Estrazione celle griglia..."):
        cells_dict = extract_all_cells(gray, page)

    with st.spinner(f"3/4 — Classificazione celle ({method.upper()})..."):
        if method == "svm":
            classifier = get_classifier()
            classification_results = {}
            for item_id, item_cells in cells_dict.items():
                classification_results[item_id] = classifier.predict_item_cells(item_cells)
        else:
            classification_results = classify_all_items_omr(cells_dict)

    with st.spinner("4/4 — Calcolo score CBCL..."):
        report = build_score_report(
            classification_results,
            session_id=f"upload_{uploaded_file.name}"
        )

    report['_overlay'] = visualize_grid_overlay(gray, page)
    report['_preprocessed'] = gray

    return report


def render_results_table(report: dict):
    """Mostra tabella risultati con colori per flag."""

    items_data = []
    for item_id in ALL_ITEMS:
        item = report["items"].get(item_id, {})
        value = item.get("value")
        flag = item.get("flag")
        confidence = item.get("confidence", 0.0)

        # Emoji per flag
        flag_emoji = {
            None: "✅",
            "ambiguous": "⚠️",
            "missing": "❌",
            "multiple_marks": "🔴",
            "not_processed": "⬜"
        }.get(flag, "❓")

        items_data.append({
            "Item": item_id,
            "Valore": value if value is not None else "-",
            "Confidence": f"{confidence:.0%}" if confidence > 0 else "-",
            "Status": f"{flag_emoji} {flag or 'ok'}"
        })

    df = pd.DataFrame(items_data)

    # Colorazione condizionale (dark mode)
    def color_row(row):
        if "❌" in str(row["Status"]):
            return ["background-color: rgba(239, 68, 68, 0.1); color: #F87171"] * len(row)
        elif "⚠️" in str(row["Status"]):
            return ["background-color: rgba(245, 158, 11, 0.1); color: #FBBF24"] * len(row)
        elif "🔴" in str(row["Status"]):
            return ["background-color: rgba(236, 72, 153, 0.1); color: #F472B6"] * len(row)
        return ["color: #CBD5E1"] * len(row)

    styled = df.style.apply(color_row, axis=1)
    st.dataframe(styled, use_container_width=True, height=600)


def main():
    # Sidebar
    with st.sidebar:
        st.markdown(
            "<div style='text-align:center; padding: 16px 0 8px;'>"
            "<span style='font-size:2rem;'>🧾</span><br>"
            "<span style='font-size:1.1rem; font-weight:700; "
            "background: linear-gradient(135deg, #818CF8, #C084FC); "
            "-webkit-background-clip: text; -webkit-text-fill-color: transparent;'>"
            "Smart OCR</span>"
            "</div>",
            unsafe_allow_html=True
        )
        st.markdown("<div class='subtle-sep'></div>", unsafe_allow_html=True)

        st.markdown("### Impostazioni")
        debug_mode = st.checkbox("Modalità debug", False)

        st.markdown("<div class='subtle-sep'></div>", unsafe_allow_html=True)
        st.markdown("### Stato sistema")

        calib_status = get_calibration_status()
        if calib_status:
            for pg, n in calib_status.items():
                st.markdown(status_pill(f"📐 {pg}: {n} items", "ok"), unsafe_allow_html=True)
        else:
            st.markdown(status_pill("📐 Non calibrato", "warn"), unsafe_allow_html=True)

        classifier = get_classifier()
        if classifier.is_loaded:
            st.markdown(status_pill("🧠 SVM attivo", "ok"), unsafe_allow_html=True)
        else:
            st.markdown(status_pill("🤖 Modalità OMR", "info"), unsafe_allow_html=True)

        st.markdown("<div class='subtle-sep'></div>", unsafe_allow_html=True)
        st.markdown(
            "<div style='text-align:center; color:#475569; font-size:0.7rem; padding-top:8px;'>"
            "Smart OCR v1.0<br>CBCL 6-18 Scanner"
            "</div>",
            unsafe_allow_html=True
        )

    # Titolo
    render_header("Smart OCR", "Lettura automatica questionari CBCL 6-18 da foto smartphone", "1.0")

    # Tab principali
    tab_upload, tab_results, tab_export = st.tabs([
        "📤 Analisi", "📊 Risultati", "💾 Export"
    ])

    with tab_upload:
        method = check_ready()
        if method == "none":
            return

        st.header("Carica foto questionario")

        # Selezione pagina
        page = st.selectbox("Pagina del questionario", list(calib_status.keys()) if calib_status else ["page_4"])

        col_left, col_right = st.columns([1, 1])

        with col_left:
            uploaded = st.file_uploader(
                "Foto del questionario CBCL compilato",
                type=["jpg", "jpeg", "png"],
                help="Foto da smartphone. Tieni il foglio su superficie piana con buona illuminazione."
            )

            if uploaded:
                st.image(uploaded, caption="Foto originale", use_container_width=True)

        with col_right:
            if uploaded:
                st.info(f"Metodo: **{method.upper()}** {'(pixel-counting)' if method == 'omr' else '(machine learning)'}")
                if st.button("🔍 Analizza Questionario", type="primary", use_container_width=True):
                    try:
                        report = process_uploaded_image(uploaded, page, method, debug=debug_mode)
                        st.session_state['current_report'] = report

                        stats = report["statistics"]
                        c1, c2, c3, c4 = st.columns(4)
                        c1.metric("📝 Score Totale", report["total_score"])
                        c2.metric("✅ Item Completati", stats["items_scored"])
                        c3.metric("❌ Item Mancanti", stats["items_missing"])
                        c4.metric("⚠️ Ambigui", stats["items_ambiguous"])

                        if debug_mode and '_overlay' in report:
                            st.image(report['_overlay'], caption="Overlay griglia rilevata", use_container_width=True)

                        st.success("✅ Analisi completata! Vai alla tab 'Risultati'")

                    except Exception as e:
                        st.error(f"❌ Errore durante l'analisi: {e}")
                        if debug_mode:
                            import traceback
                            st.code(traceback.format_exc())

    with tab_results:
        if 'current_report' not in st.session_state:
            st.info("Carica e analizza un questionario nella tab '📤 Analisi'")
            return

        report = st.session_state['current_report']

        st.header("Risultati Analisi")

        # Score subscale
        st.subheader("Score per Subscala")
        subscale_data = []
        for name, data in report["subscale_scores"].items():
            subscale_data.append({
                "Subscala": name.replace("_", " "),
                "Score": data["score"],
                "Item Mancanti": data["items_missing"]
            })
        st.dataframe(pd.DataFrame(subscale_data), use_container_width=True)

        # Tabella item completa
        st.subheader("Dettaglio Item")
        render_results_table(report)

        # Avviso per item che richiedono revisione
        flags = report.get("flags", [])
        if flags:
            st.subheader("⚠️ Item che richiedono revisione manuale")
            for f in flags:
                st.warning(f"Item {f['item']}: {f['flag']}")

    with tab_export:
        if 'current_report' not in st.session_state:
            st.info("Analizza prima un questionario")
            return

        report = st.session_state['current_report']
        # Rimuovi dati immagine prima dell'export
        export_report = {k: v for k, v in report.items() if not k.startswith('_')}

        st.header("Export Risultati")

        col1, col2 = st.columns(2)

        with col1:
            st.subheader("📄 Export JSON")
            json_str = report_to_json(export_report)
            st.download_button(
                "⬇️ Scarica JSON",
                data=json_str,
                file_name=f"{export_report['session_id']}.json",
                mime="application/json",
                use_container_width=True
            )

        with col2:
            st.subheader("📊 Export CSV")
            csv_str = report_to_csv(export_report)
            st.download_button(
                "⬇️ Scarica CSV",
                data=csv_str,
                file_name=f"{export_report['session_id']}.csv",
                mime="text/csv",
                use_container_width=True
            )


if __name__ == "__main__":
    main()
