"""
training/label_tool.py

Tool Streamlit per calibrazione griglia e labeling celle.

Uso:
    streamlit run training/label_tool.py

Tab:
1. CALIBRA GRIGLIA: carica foto, clicca 4 punti sull'immagine, salva coordinate
2. VERIFICA: overlay visuale per controllare allineamento
3. TEST OMR: testa riconoscimento automatico su foto compilata
4. ETICHETTA CELLE: labeling manuale per training SVM
"""

import streamlit as st
import cv2
import numpy as np
from pathlib import Path
from PIL import Image
import json
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.preprocessor import preprocess_full_pipeline
from core.grid_extractor import extract_all_cells, visualize_grid_overlay, TEMPLATE_PATH
from core.calibrator import (
    calculate_grid_from_anchors, save_calibration, get_calibration_status,
    estimate_cell_dimensions, estimate_col_spacing, CBCL_LAYOUT,
    calibrate_from_pdf_auto
)
from core.omr_classifier import classify_all_items_omr
from core.scorer import build_score_report, ALL_ITEMS

from streamlit_drawable_canvas import st_canvas
from style import inject_custom_css, render_header

DATA_DIR = Path(__file__).parent.parent / "data" / "raw_cells"
CLASSES = ["cerchio", "x_rossa", "vuoto", "ambiguo"]


def ensure_dirs():
    for cls in CLASSES:
        (DATA_DIR / cls).mkdir(parents=True, exist_ok=True)


def preprocess_uploaded(uploaded_file):
    """Preprocessing di un file caricato."""
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        tmp.write(uploaded_file.read())
        tmp_path = tmp.name
    uploaded_file.seek(0)
    try:
        gray, meta = preprocess_full_pipeline(tmp_path)
        return gray, meta
    except Exception as e:
        st.error(f"Errore preprocessing: {e}")
        return None, None


def gray_to_pil(gray: np.ndarray, max_width: int = 900) -> Image.Image:
    """Converte grayscale numpy in PIL Image ridimensionata per il canvas."""
    h, w = gray.shape
    scale = min(max_width / w, 1.0)
    new_w = int(w * scale)
    new_h = int(h * scale)
    resized = cv2.resize(gray, (new_w, new_h))
    return Image.fromarray(resized), scale


def get_canvas_points(canvas_result) -> list:
    """Estrae punti cliccati dal canvas drawable."""
    points = []
    if canvas_result is not None and canvas_result.json_data is not None:
        objects = canvas_result.json_data.get("objects", [])
        for obj in objects:
            if obj.get("type") == "circle":
                # Il centro del cerchio è left + radius, top + radius
                x = obj["left"] + obj.get("radius", 5)
                y = obj["top"] + obj.get("radius", 5)
                points.append((x, y))
    return points


# ============================================================
# TAB 1: CALIBRAZIONE
# ============================================================
def tab_calibration():
    st.header("📐 Calibrazione Griglia CBCL")

    # Stato calibrazione
    status = get_calibration_status()
    if status:
        cols = st.columns(len(status))
        for col, (page, n_items) in zip(cols, status.items()):
            col.metric(f"{page}", f"{n_items} items")

    st.markdown("---")

    # === AUTO-CALIBRAZIONE DA PDF ===
    st.subheader("Auto-calibrazione da PDF")
    st.markdown("Se hai un **PDF digitale** del questionario CBCL, puoi calibrare automaticamente.")

    pdf_file = st.file_uploader("Carica PDF CBCL", type=["pdf"], key="pdf_calib_file")
    if pdf_file:
        col_pdf1, col_pdf2 = st.columns(2)
        with col_pdf1:
            pdf_page_index = st.number_input("Pagina nel PDF (1-based)", 1, 20, 2, key="pdf_page_idx") - 1
        with col_pdf2:
            pdf_page_key = st.selectbox("Chiave pagina", ["page_4", "page_5"], key="pdf_page_key")

        if st.button("Auto-calibra da PDF", type="primary", use_container_width=True):
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                tmp.write(pdf_file.read())
                tmp_pdf_path = tmp.name
            pdf_file.seek(0)

            try:
                page_data, layout_info = calibrate_from_pdf_auto(
                    tmp_pdf_path, pdf_page_index, pdf_page_key
                )
                st.success(
                    f"Calibrazione completata! "
                    f"{layout_info['total_items']} items rilevati "
                    f"(SX: {len(layout_info['left_column_items'])}, "
                    f"DX: {len(layout_info['right_column_items'])})"
                )
                st.json(layout_info)

                # Genera overlay se possibile
                try:
                    import subprocess
                    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_img:
                        tmp_img_base = tmp_img.name.replace('.png', '')
                    subprocess.run([
                        'pdftoppm', '-png',
                        '-f', str(pdf_page_index + 1),
                        '-l', str(pdf_page_index + 1),
                        '-r', '300', tmp_pdf_path, tmp_img_base
                    ], check=True, capture_output=True)

                    import glob
                    rendered = glob.glob(tmp_img_base + '*.png')
                    if rendered:
                        img_cv = cv2.imread(rendered[0])
                        gray_cv = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
                        overlay = visualize_grid_overlay(gray_cv, pdf_page_key)
                        overlay_rgb = cv2.cvtColor(overlay, cv2.COLOR_BGR2RGB)
                        st.image(overlay_rgb, caption="Overlay calibrazione", use_container_width=True)
                except Exception:
                    pass

                st.balloons()
            except Exception as e:
                st.error(f"Errore auto-calibrazione: {e}")

    st.markdown("---")
    st.subheader("Calibrazione manuale (da foto)")

    page = st.selectbox("Pagina da calibrare", ["page_4", "page_5"])
    layout = CBCL_LAYOUT[page]
    left_items = layout["left_column"]["items"]
    right_items = layout["right_column"]["items"]

    calib_file = st.file_uploader("Carica foto questionario CBCL", type=["jpg", "jpeg", "png"], key="calib_file")

    if not calib_file:
        st.info("Carica una foto per iniziare la calibrazione.")
        return

    gray, meta = preprocess_uploaded(calib_file)
    if gray is None:
        return

    img_h, img_w = gray.shape

    if meta.get("warnings"):
        for w in meta["warnings"]:
            st.warning(w)

    # Converti per canvas
    pil_img, scale = gray_to_pil(gray, max_width=900)
    canvas_w, canvas_h = pil_img.size

    st.markdown("---")
    st.subheader("Clicca i 4 punti di ancoraggio")

    st.markdown(f"""
    Clicca **nell'ordine** sulla foto:
    1. **Primo item colonna SX** (item {left_items[0]}) — centro della cella col_0
    2. **Ultimo item colonna SX** (item {left_items[-1]}) — centro della cella col_0
    3. **Primo item colonna DX** (item {right_items[0]}) — centro della cella col_0
    4. **Ultimo item colonna DX** (item {right_items[-1]}) — centro della cella col_0

    Poi clicca un **5° punto** sulla cella col_2 dello stesso item del punto 1 (per misurare la spaziatura).
    """)

    # Canvas interattivo
    canvas_result = st_canvas(
        fill_color="rgba(255, 0, 0, 0.3)",
        stroke_width=2,
        stroke_color="#FF0000",
        background_image=pil_img,
        drawing_mode="circle",
        point_display_radius=6,
        height=canvas_h,
        width=canvas_w,
        key=f"canvas_{page}",
    )

    points = get_canvas_points(canvas_result)

    if points:
        st.write(f"**Punti selezionati: {len(points)}/5**")
        labels = [
            f"1. SX primo ({left_items[0]})",
            f"2. SX ultimo ({left_items[-1]})",
            f"3. DX primo ({right_items[0]})",
            f"4. DX ultimo ({right_items[-1]})",
            f"5. Col_2 del primo item (per spaziatura)"
        ]
        for i, pt in enumerate(points[:5]):
            label = labels[i] if i < len(labels) else f"Punto extra {i+1}"
            st.write(f"  {label}: ({pt[0]:.0f}, {pt[1]:.0f}) px canvas")

    st.markdown("---")

    # Spaziatura e dimensioni celle (con defaults intelligenti)
    est_cell_w, est_cell_h = estimate_cell_dimensions(img_w, img_h)
    est_spacing = estimate_col_spacing(img_w)

    col_a, col_b, col_c = st.columns(3)
    with col_a:
        cell_w = st.number_input("Larghezza cella (px reali)", 10, 300, int(est_cell_w), key="cw")
    with col_b:
        cell_h = st.number_input("Altezza cella (px reali)", 10, 300, int(est_cell_h), key="ch")
    with col_c:
        manual_spacing = st.number_input("Spaziatura colonne (px reali, 0=auto dai punti)", 0, 500, 0, key="sp")

    # Calcola e salva
    if len(points) >= 4:
        # Converti da coordinate canvas a coordinate immagine reale
        def to_real(pt):
            return (pt[0] / scale, pt[1] / scale)

        lt = to_real(points[0])  # left top
        lb = to_real(points[1])  # left bottom
        rt = to_real(points[2])  # right top
        rb = to_real(points[3])  # right bottom

        # Calcola spaziatura dalle coordinate
        if len(points) >= 5 and manual_spacing == 0:
            pt1_real = to_real(points[0])
            pt5_real = to_real(points[4])
            # Distanza tra col_0 e col_2 = 2 * spacing
            total_dist = abs(pt5_real[0] - pt1_real[0])
            col_spacing = total_dist / 2.0
            st.info(f"Spaziatura calcolata dai punti: {col_spacing:.1f} px")
        elif manual_spacing > 0:
            col_spacing = manual_spacing
        else:
            col_spacing = est_spacing
            st.info(f"Spaziatura stimata: {col_spacing:.1f} px (aggiungi il 5° punto per calcolo preciso)")

        # Calcola griglia
        page_data = calculate_grid_from_anchors(
            page=page,
            left_top=lt, left_bottom=lb,
            right_top=rt, right_bottom=rb,
            col_spacing=col_spacing,
            cell_width=cell_w, cell_height=cell_h,
            img_width=img_w, img_height=img_h
        )

        # Anteprima overlay
        st.subheader("Anteprima")
        save_calibration(page, page_data)
        try:
            overlay = visualize_grid_overlay(gray, page)
            overlay_pil = Image.fromarray(cv2.cvtColor(
                cv2.resize(overlay, (canvas_w, canvas_h)), cv2.COLOR_BGR2RGB
            ))
            st.image(overlay_pil, caption=f"Overlay {page} — Blu=col0, Verde=col1, Rosso=col2", use_container_width=True)
        except Exception as e:
            st.error(f"Errore overlay: {e}")

        # Salva
        if st.button("💾 Salva calibrazione", type="primary", use_container_width=True):
            path = save_calibration(page, page_data)
            st.success(f"✅ Calibrazione {page} salvata! ({len(page_data['items'])} items)")
            st.balloons()
    else:
        st.warning(f"Seleziona almeno 4 punti sulla foto (hai {len(points)}/4)")


# ============================================================
# TAB 2: VERIFICA
# ============================================================
def tab_verify():
    st.header("🔍 Verifica Calibrazione")

    status = get_calibration_status()
    if not status:
        st.warning("Nessuna calibrazione trovata. Vai alla tab 'Calibra Griglia'.")
        return

    verify_file = st.file_uploader("Carica foto per verificare", type=["jpg", "jpeg", "png"], key="verify_file")
    if not verify_file:
        return

    gray, meta = preprocess_uploaded(verify_file)
    if gray is None:
        return

    page = st.selectbox("Pagina", list(status.keys()), key="verify_page")

    try:
        overlay = visualize_grid_overlay(gray, page)
        overlay_rgb = cv2.cvtColor(overlay, cv2.COLOR_BGR2RGB)
        st.image(overlay_rgb, caption=f"Overlay {page}", use_container_width=True)

        # Campione celle
        cells = extract_all_cells(gray, page)
        item_ids = list(cells.keys())

        st.subheader("Campione celle estratte")
        sample = item_ids[:4] + item_ids[len(item_ids)//2:len(item_ids)//2+2] + item_ids[-2:]
        for item_id in sample:
            item_cells = cells[item_id]
            cols = st.columns([1, 1, 1, 2])
            for i, (col_label, cell_img) in enumerate(item_cells.items()):
                display = cv2.resize(cell_img, (96, 96), interpolation=cv2.INTER_NEAREST)
                cols[i].image(display, caption=f"col {col_label}", width=96)
            cols[3].markdown(f"**Item {item_id}**")
    except Exception as e:
        st.error(f"Errore: {e}")


# ============================================================
# TAB 3: TEST OMR
# ============================================================
def tab_test_omr():
    st.header("🤖 Test Riconoscimento Automatico")

    status = get_calibration_status()
    if not status:
        st.warning("Prima calibra la griglia.")
        return

    test_file = st.file_uploader("Carica foto questionario compilato", type=["jpg", "jpeg", "png"], key="test_file")
    if not test_file:
        return

    gray, meta = preprocess_uploaded(test_file)
    if gray is None:
        return

    page = st.selectbox("Pagina", list(status.keys()), key="test_page")

    if st.button("🔍 Analizza", type="primary", use_container_width=True):
        with st.spinner("Analisi in corso..."):
            cells = extract_all_cells(gray, page)
            results = classify_all_items_omr(cells)

        # Statistiche
        values = [r["value"] for r in results.values() if r["value"] is not None]
        flagged = [iid for iid, r in results.items() if r["flag"] is not None]

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Items", len(results))
        c2.metric("Risposte", len(values))
        c3.metric("Problemi", len(flagged))
        c4.metric("Score", sum(values))

        # Tabella
        import pandas as pd
        rows = []
        for item_id, r in results.items():
            emoji = {"missing": "❌", "ambiguous": "⚠️", "multiple_marks": "🔴", None: "✅"}.get(r["flag"], "❓")
            rows.append({
                "Item": item_id,
                "Risposta": r["value"] if r["value"] is not None else "-",
                "Confidence": f"{r['confidence']:.0%}",
                "col_0": f"{r['raw_counts'].get('0', 0):.1%}",
                "col_1": f"{r['raw_counts'].get('1', 0):.1%}",
                "col_2": f"{r['raw_counts'].get('2', 0):.1%}",
                "Status": f"{emoji} {r['flag'] or 'ok'}"
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, height=500)

        # Items problematici con immagini
        if flagged:
            st.subheader("⚠️ Items da verificare")
            for item_id in flagged[:10]:
                r = results[item_id]
                item_cells = cells[item_id]
                cols = st.columns([1, 1, 1, 3])
                for i, (col_label, cell_img) in enumerate(item_cells.items()):
                    display = cv2.resize(cell_img, (80, 80), interpolation=cv2.INTER_NEAREST)
                    cols[i].image(display, caption=f"col{col_label}: {r['raw_counts'].get(col_label, 0):.0%}", width=80)
                cols[3].warning(f"**Item {item_id}**: {r['flag']}")


# ============================================================
# TAB 4: LABELING
# ============================================================
def tab_labeling():
    st.header("🏷️ Etichettatura Celle")

    ensure_dirs()
    counts = {cls: len(list((DATA_DIR / cls).glob("*.png"))) for cls in CLASSES}

    col1, col2, col3, col4 = st.columns(4)
    for col, cls in zip([col1, col2, col3, col4], CLASSES):
        col.metric(cls, counts[cls])

    total = sum(counts.values())
    if total > 0:
        st.progress(min(total / 90, 1.0), text=f"{total} celle totali (minimo 90 per training: 30 per classe)")

    st.markdown("---")

    uploaded = st.file_uploader("Carica foto CBCL", type=["jpg", "jpeg", "png"], accept_multiple_files=True, key="label_files")
    if not uploaded:
        return

    status = get_calibration_status()
    page = st.selectbox("Pagina", list(status.keys()) if status else ["page_4"], key="label_page")

    file_idx = st.selectbox("Questionario", range(len(uploaded)), format_func=lambda i: uploaded[i].name)

    gray, meta = preprocess_uploaded(uploaded[file_idx])
    if gray is None:
        return

    try:
        cells_dict = extract_all_cells(gray, page)
    except Exception as e:
        st.error(f"Errore: {e}")
        return

    if 'labeled_count' not in st.session_state:
        st.session_state['labeled_count'] = 0

    item_ids = list(cells_dict.keys())
    item_idx = st.slider("Item", 0, len(item_ids) - 1, 0)
    item_id = item_ids[item_idx]

    st.subheader(f"Item {item_id}")

    cols = st.columns(3)
    for col_ui, (col_label, cell_img) in zip(cols, cells_dict[item_id].items()):
        with col_ui:
            display = cv2.resize(cell_img, (128, 128), interpolation=cv2.INTER_NEAREST)
            st.image(display, width=128, caption=f"Colonna {col_label}")
            label = st.selectbox(f"Classe", CLASSES, key=f"lbl_{item_id}_{col_label}")
            if st.button(f"💾 Salva", key=f"sv_{item_id}_{col_label}"):
                import time
                ts = int(time.time() * 1000)
                fname = f"item{item_id}_col{col_label}_{ts}.png"
                dst = DATA_DIR / label
                dst.mkdir(parents=True, exist_ok=True)
                cv2.imwrite(str(dst / fname), cell_img)
                st.session_state['labeled_count'] += 1
                st.success(f"'{label}'!")

    st.metric("Etichettate questa sessione", st.session_state['labeled_count'])


# ============================================================
# MAIN
# ============================================================
def main():
    st.set_page_config(page_title="Smart OCR — Calibrazione & Tools", page_icon="📐", layout="wide")
    inject_custom_css()
    render_header("Smart OCR — Tools", "Calibrazione, verifica e training", "1.0")

    tab1, tab2, tab3, tab4 = st.tabs(["📐 Calibra", "🔍 Verifica", "🤖 Test OMR", "🏷️ Etichetta"])

    with tab1:
        tab_calibration()
    with tab2:
        tab_verify()
    with tab3:
        tab_test_omr()
    with tab4:
        tab_labeling()


if __name__ == "__main__":
    main()
