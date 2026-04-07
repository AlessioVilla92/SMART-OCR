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

from config import Config, ClassificationMode
from core.preprocessor import preprocess_full_pipeline, load_image
from core.boundary_detector import detect_document_boundary, warp_to_a4, draw_boundary_overlay
from core.template_aligner import TemplateAligner
from core.grid_extractor import extract_all_cells, visualize_grid_overlay
from core.classifier import get_classifier
from core.omr_classifier import classify_all_items_omr, classify_all_items_baseline
from core.scorer import build_score_report, report_to_csv, report_to_json, ALL_ITEMS
from core.calibrator import get_calibration_status
from style import inject_custom_css, render_header, glass_card, status_pill


@st.cache_resource
def get_aligner():
    """Singleton TemplateAligner con reference cached."""
    aligner = TemplateAligner()
    try:
        aligner.load_reference("page_4")
        aligner.load_reference("page_5")
        aligner.load_reference("page_6")
    except FileNotFoundError:
        pass  # Reference non generate, alignment disabilitato
    return aligner


# Configurazione pagina
st.set_page_config(
    page_title="Smart OCR — CBCL Scanner",
    page_icon="🧾",
    layout="wide",
    initial_sidebar_state="expanded"
)
inject_custom_css()


def check_ready(selected_mode: ClassificationMode = ClassificationMode.MODE_A_SVM) -> str:
    """
    Verifica che il sistema sia pronto per l'analisi.
    Returns: "svm", "yolo", "omr", "pdf", o "none"
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

    # Mode D: PDF digitale
    if selected_mode == ClassificationMode.MODE_D_PDF:
        st.success("PDF mode attivo: OMR ottimizzato per PDF digitali (no preprocessing fotografico)")
        return "pdf"

    # Mode C: Ensemble (SVM + YOLO + TTA)
    if selected_mode == ClassificationMode.MODE_C_ENSEMBLE:
        if Config.svm_model_available() or Config.yolo_model_available():
            try:
                from pipeline.ensemble_classifier import EnsembleClassifier
                ens = EnsembleClassifier()
                models = ", ".join(ens.active_models)
                st.success(f"Ensemble attivo con: {models}")
                return "ensemble"
            except Exception as e:
                st.warning(f"⚠️ Errore caricamento Ensemble: {e}\nFallback a Mode A...")
        else:
            st.warning("⚠️ Nessun modello disponibile per Ensemble. Fallback a OMR.")

    # Mode B: YOLO ONNX
    if selected_mode == ClassificationMode.MODE_B_YOLO:
        if Config.yolo_model_available():
            try:
                from pipeline.mode_b.yolo_classifier import YOLOClassifier
                _test = YOLOClassifier()
                return "yolo"
            except Exception as e:
                st.warning(f"⚠️ Errore caricamento YOLO: {e}")
        else:
            st.warning(
                "⚠️ Modello YOLO ONNX non trovato.\n\n"
                "**Per addestrare il modello AI:**\n"
                "1. `python training/mode_b/prepare_yolo_dataset.py`\n"
                "2. `python training/mode_b/train_yolo.py`\n"
                "3. `python training/mode_b/export_onnx.py`\n\n"
                "Fallback a Mode A (SVM)..."
            )

    # Mode A: SVM (o fallback da Mode B)
    classifier = get_classifier()
    if classifier.is_loaded:
        return "svm"

    st.info("ℹ️ Modello SVM non trovato — uso riconoscimento OMR (pixel-counting).")
    return "omr"


def process_uploaded_image(uploaded_file, page: str, method: str, debug: bool = False) -> dict:
    """
    Processa un questionario caricato e ritorna il report completo.
    method: "svm", "yolo", "ensemble", "omr", o "pdf"

    Pipeline v2.1 (5 fasi per foto):
    1. Boundary detection + overlay giallo
    2. Perspective correction A4
    3. Preprocessing (shadow removal + denoise + CLAHE)
    4. SIFT+ECC alignment al template PDF
    5. Classificazione celle
    """
    from core.omr_classifier import classify_all_items_pdf

    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        tmp.write(uploaded_file.read())
        tmp_path = tmp.name
    uploaded_file.seek(0)

    if method == "pdf":
        # PDF mode: preprocessing leggero (solo resize, no prospettiva/deskew)
        with st.spinner("1/3 — Caricamento immagine (PDF mode)..."):
            img = cv2.imread(tmp_path)
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
            gray = cv2.resize(gray, (2480, 3508), interpolation=cv2.INTER_AREA)
            meta = {"pdf_mode": True}
    else:
        # FASE 1: Boundary detection
        with st.spinner("1/5 — Rilevamento bordi documento..."):
            img = load_image(tmp_path)
            corners = None
            try:
                corners, conf, det_method = detect_document_boundary(img)
                # Verifica qualità: scarta se corners sui bordi immagine o confidence bassa
                h_img, w_img = img.shape[:2]
                margin = 5
                on_edge = any(
                    c[0] < margin or c[1] < margin or
                    c[0] > w_img - margin or c[1] > h_img - margin
                    for c in corners
                )
                if on_edge or conf < 0.5:
                    if debug:
                        st.info(f"Boundary {det_method} scartato (conf={conf:.0%}, on_edge={on_edge}). Skip perspective correction.")
                    corners = None
                else:
                    overlay = draw_boundary_overlay(img, corners)
                    st.image(cv2.cvtColor(overlay, cv2.COLOR_BGR2RGB),
                             caption=f"Bordi: {det_method} (conf={conf:.0%})",
                             use_container_width=True)
            except Exception as e:
                if debug:
                    st.warning(f"Boundary detection fallito: {e}")

        # FASE 2: Perspective correction A4
        with st.spinner("2/5 — Correzione prospettiva..."):
            if corners is not None:
                warped = warp_to_a4(img, corners)
            else:
                warped = img

        # FASE 3: Preprocessing (shadow removal + denoise + CLAHE)
        with st.spinner("3/5 — Pre-processing immagine..."):
            gray, meta = preprocess_full_pipeline(warped, debug=debug)

        # FASE 4: SIFT+ECC alignment al template
        with st.spinner("4/5 — Allineamento al template..."):
            aligner = get_aligner()
            aligned, align_info = aligner.align(gray, page)
            if align_info.get("aligned"):
                gray = aligned
                if debug:
                    st.json(align_info)
            elif debug:
                st.info(f"Alignment non riuscito: {align_info}")

    if meta.get("warnings"):
        for w in meta["warnings"]:
            st.warning(f"Warning: {w}")

    # FASE 5: Estrazione celle e classificazione
    step = "2/3" if method == "pdf" else "5/5"
    with st.spinner(f"{step} — Estrazione e classificazione celle ({method.upper()})..."):
        cells_dict = extract_all_cells(gray, page)

        if method == "pdf":
            classification_results = classify_all_items_pdf(
                cells_dict,
                empty_threshold=Config.PDF_EMPTY_THRESHOLD,
                min_ratio=Config.PDF_MIN_RATIO,
                ambiguity_gap=Config.PDF_AMBIGUITY_GAP
            )
        elif method == "ensemble":
            from pipeline.ensemble_classifier import EnsembleClassifier
            ens_clf = EnsembleClassifier()
            classification_results = {}
            for item_id, item_cells in cells_dict.items():
                classification_results[item_id] = ens_clf.predict_item_cells(item_cells)
        elif method == "svm":
            classifier = get_classifier()
            classification_results = {}
            for item_id, item_cells in cells_dict.items():
                classification_results[item_id] = classifier.predict_item_cells(item_cells)
        elif method == "yolo":
            from pipeline.mode_b.yolo_classifier import YOLOClassifier
            yolo_clf = YOLOClassifier()
            classification_results = {}
            for item_id, item_cells in cells_dict.items():
                classification_results[item_id] = yolo_clf.predict_item_cells(item_cells)
        else:
            classification_results = classify_all_items_omr(cells_dict)

        # Strategia combinata: YOLO + Baseline fallback per massima copertura
        # Se alignment riuscito e reference disponibile, usa baseline per recuperare
        # items che il metodo primario ha flaggato come missing/multiple_marks
        aligner_ref = get_aligner()
        if align_info.get("aligned") and page in aligner_ref._references:
            ref_img = aligner_ref._references[page]
            ref_cells = extract_all_cells(ref_img, page)
            baseline_results = classify_all_items_baseline(cells_dict, ref_cells)

            for item_id, primary in classification_results.items():
                fallback = baseline_results.get(item_id, {})
                pv = primary.get("value")
                pf = primary.get("flag")
                fv = fallback.get("value")
                ff = fallback.get("flag")

                # Se il metodo primario ha fallito, usa baseline come fallback
                if pv is None or pf in ("missing", "multiple_marks", "ambiguous"):
                    if fv is not None and ff in (None, "low_confidence", "multiple_marks"):
                        classification_results[item_id] = fallback

    report = build_score_report(
        classification_results,
        session_id=f"upload_{uploaded_file.name}"
    )

    report['_overlay'] = visualize_grid_overlay(gray, page)
    report['_preprocessed'] = gray

    if debug and '_overlay' in report:
        st.image(report['_overlay'], caption="Griglia sovrapposta dopo alignment",
                 use_container_width=True)

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

        # Toggle Mode A / Mode B
        st.markdown("### Modalità Riconoscimento")
        mode_choice = st.radio(
            "Motore di classificazione",
            [
                "A — Classico (HOG + SVM)",
                "B — AI (YOLOv8n ONNX)",
                "C — Ensemble (SVM + YOLO + TTA)",
                "D — PDF digitale (OMR ottimizzato)"
            ],
            index=2,
            help=(
                "Mode A: robusto, no GPU. Mode B: AI fine-tuned. "
                "Mode C: ensemble di entrambi con TTA, massima accuratezza. "
                "Mode D: per PDF digitali (no preprocessing fotografico, OMR winner-takes-all)."
            )
        )
        if "D" in mode_choice:
            selected_mode = ClassificationMode.MODE_D_PDF
        elif "C" in mode_choice:
            selected_mode = ClassificationMode.MODE_C_ENSEMBLE
        elif "B" in mode_choice:
            selected_mode = ClassificationMode.MODE_B_YOLO
        else:
            selected_mode = ClassificationMode.MODE_A_SVM

        st.markdown("<div class='subtle-sep'></div>", unsafe_allow_html=True)
        st.markdown("### Stato sistema")

        calib_status = get_calibration_status()
        if calib_status:
            for pg, n in calib_status.items():
                st.markdown(status_pill(f"📐 {pg}: {n} items", "ok"), unsafe_allow_html=True)
        else:
            st.markdown(status_pill("📐 Non calibrato", "warn"), unsafe_allow_html=True)

        # Stato modelli — entrambi
        svm_ok = Config.svm_model_available()
        yolo_ok = Config.yolo_model_available()

        if svm_ok:
            st.markdown(status_pill("🧠 SVM (Mode A) disponibile", "ok"), unsafe_allow_html=True)
        else:
            st.markdown(status_pill("🧠 SVM (Mode A) non trovato", "warn"), unsafe_allow_html=True)

        if yolo_ok:
            st.markdown(status_pill("🤖 YOLO ONNX (Mode B) disponibile", "ok"), unsafe_allow_html=True)
        else:
            st.markdown(status_pill("🤖 YOLO ONNX (Mode B) non trovato", "info"), unsafe_allow_html=True)

        # Fallback OMR se nessun modello
        if not svm_ok and not yolo_ok:
            st.markdown(status_pill("📊 Fallback: OMR pixel-counting", "info"), unsafe_allow_html=True)

        st.markdown("<div class='subtle-sep'></div>", unsafe_allow_html=True)
        st.markdown(
            "<div style='text-align:center; color:#475569; font-size:0.7rem; padding-top:8px;'>"
            "Smart OCR v2.1<br>CBCL 6-18 Scanner"
            "</div>",
            unsafe_allow_html=True
        )

    # Titolo
    render_header("Smart OCR", "Lettura automatica questionari CBCL 6-18 da foto smartphone", "2.1")

    # Tab principali
    tab_upload, tab_results, tab_export = st.tabs([
        "📤 Analisi", "📊 Risultati", "💾 Export"
    ])

    with tab_upload:
        method = check_ready(selected_mode)
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
                method_desc = {
                    "svm": "(HOG + SVM — Mode A)",
                    "yolo": "(YOLOv8n ONNX — Mode B)",
                    "omr": "(pixel-counting — fallback)"
                }.get(method, "")
                st.info(f"Metodo: **{method.upper()}** {method_desc}")
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

                        st.success("Analisi completata! Vai alla tab 'Risultati'")

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
