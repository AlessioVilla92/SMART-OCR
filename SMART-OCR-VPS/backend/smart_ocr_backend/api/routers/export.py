"""
Export router — generate PDF report identical to Smart OCR desktop app.
"""

import io
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Body
from fastapi.responses import StreamingResponse

from smart_ocr_backend.db.models import User
from smart_ocr_backend.api.deps import get_current_user

router = APIRouter(prefix="/export", tags=["export"])

# Items to HIDE from all output (113b, 113c are disabled in desktop app)
HIDDEN_ITEMS = {'113b', '113c'}

# Item display names (113a shows as "113")
DISPLAY_ID = {'113a': '113'}

# Exact ALL_ITEMS order from scorer (excluding hidden)
def _get_visible_items():
    items = [str(i) for i in range(1, 56)]
    items += ['56a', '56b', '56c', '56d', '56e', '56f', '56g', '56h']
    items += [str(i) for i in range(57, 113)]
    items += ['113a']  # only 113a, shown as "113"
    return items

ALL_VISIBLE_ITEMS = _get_visible_items()

SYNDROME_ORDER = [
    "anxious_depressed", "withdrawn_depressed", "somatic_complaints",
    "social_problems", "thought_problems", "attention_problems",
    "rule_breaking", "aggressive_behavior",
]

SCALE_COLORS = {
    "anxious_depressed":   {"bg": "#DCEBF9", "dark": "#3D85C6", "code": "I",    "label": "Ansioso/Depresso"},
    "withdrawn_depressed": {"bg": "#D6E2F5", "dark": "#3C5A99", "code": "II",   "label": "Ritirato/Depresso"},
    "somatic_complaints":  {"bg": "#D6ECE6", "dark": "#2E8B7E", "code": "III",  "label": "Lamentele Somatiche"},
    "social_problems":     {"bg": "#FFF3CC", "dark": "#D4A017", "code": "IV",   "label": "Problemi Sociali"},
    "thought_problems":    {"bg": "#E4D7F0", "dark": "#6A3D9A", "code": "V",    "label": "Problemi del Pensiero"},
    "attention_problems":  {"bg": "#FFE0C2", "dark": "#D97F1E", "code": "VI",   "label": "Problemi di Attenzione"},
    "rule_breaking":       {"bg": "#FADADD", "dark": "#C44D7B", "code": "VII",  "label": "Comportamento Trasgressivo"},
    "aggressive_behavior": {"bg": "#F9D6D6", "dark": "#C0392B", "code": "VIII", "label": "Comportamento Aggressivo"},
    "other_problems":      {"bg": "#E8E8E8", "dark": "#6B6B6B", "code": "—",    "label": "Problemi Residui"},
}


@router.post("/pdf")
def export_pdf(
    data: dict = Body(...),
    user: User = Depends(get_current_user),
):
    """Generate PDF report identical to Smart OCR desktop app."""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm
        from reportlab.lib import colors
        from reportlab.platypus import (
            SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer,
            KeepTogether, PageBreak,
        )
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    except ImportError:
        raise HTTPException(500, "reportlab non installato sul server")

    items = data.get("items", {})
    subscales = data.get("subscale_scores", {})
    report_finale = data.get("report_finale", {})
    total_score = data.get("total_score", 0)
    comp = data.get("compilatore", "")

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            topMargin=20*mm, bottomMargin=20*mm,
                            leftMargin=15*mm, rightMargin=15*mm)
    styles = getSampleStyleSheet()
    elements = []

    # ─── TITOLO ───
    comp_label = f" — {comp}" if comp else ""
    title_style = ParagraphStyle('Title2', parent=styles['Title'],
                                 fontSize=18, textColor=colors.HexColor('#333333'))
    elements.append(Paragraph(f"CBCL 6-18 — Risultati{comp_label}", title_style))
    elements.append(Spacer(1, 5*mm))

    info_style = ParagraphStyle('Info', parent=styles['Normal'], fontSize=10)
    elements.append(Paragraph(
        f"Data: {datetime.now().strftime('%Y-%m-%d %H:%M')} | "
        f"Score Totale: <b>{total_score}</b>",
        info_style))
    elements.append(Spacer(1, 6*mm))

    # ─── TABELLA SCALE SINDROMICHE ───
    elements.append(Paragraph("Scale Sindromiche", styles['Heading2']))
    sub_data = [["Cod.", "Scala", "Raw", "Missing"]]
    row_colors_list = [colors.white]

    for key in SYNDROME_ORDER:
        sc_data = subscales.get(key, {})
        if not sc_data:
            continue
        info = SCALE_COLORS.get(key, {})
        sub_data.append([
            info.get("code", ""),
            sc_data.get("label_it", info.get("label", key)),
            str(sc_data.get("score", 0)),
            str(sc_data.get("items_missing", 0)),
        ])
        row_colors_list.append(colors.HexColor(info.get("bg", "#FFFFFF")))

    # Other row
    other = subscales.get("other_problems", {})
    if other:
        info = SCALE_COLORS["other_problems"]
        sub_data.append([
            info["code"],
            other.get("label_it", info["label"]),
            str(other.get("score", 0)),
            str(other.get("items_missing", 0)),
        ])
        row_colors_list.append(colors.HexColor(info["bg"]))

    sub_table = Table(sub_data, colWidths=[15*mm, 110*mm, 20*mm, 25*mm])
    sub_style = [
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#7C5CFC')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (0, 0), (0, -1), 'CENTER'),
        ('ALIGN', (2, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CCCCCC')),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
    ]
    for i, bg in enumerate(row_colors_list[1:], start=1):
        sub_style.append(('BACKGROUND', (0, i), (-1, i), bg))
    sub_table.setStyle(TableStyle(sub_style))
    elements.append(sub_table)
    elements.append(Spacer(1, 6*mm))

    # ─── TABELLA DSM ───
    dsm = {k: v for k, v in subscales.items()
           if isinstance(v, dict) and v.get("type") == "dsm"}
    if dsm:
        elements.append(Paragraph("Scale DSM-Oriented", styles['Heading2']))
        dsm_data = [["Scala", "Raw", "Missing"]]
        for name, sc_data in dsm.items():
            dsm_data.append([
                sc_data.get("label_it", name.replace("_", " ")),
                str(sc_data.get("score", 0)),
                str(sc_data.get("items_missing", 0)),
            ])
        dsm_table = Table(dsm_data, colWidths=[125*mm, 20*mm, 25*mm])
        dsm_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#7C5CFC')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CCCCCC')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F5F5F5')]),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ]))
        elements.append(dsm_table)
        elements.append(Spacer(1, 6*mm))

    # ─── TABELLA TOTALE ───
    elements.append(Paragraph("TOTALE", styles['Heading2']))
    bb_int = subscales.get("internalizing", {}) if isinstance(subscales.get("internalizing"), dict) else {}
    bb_ext = subscales.get("externalizing", {}) if isinstance(subscales.get("externalizing"), dict) else {}
    total_data = [
        ["Scala", "Formula", "Raw"],
        ["Internal Scala", "I + II + III", str(bb_int.get("score", 0))],
        ["External Scala", "VII + VIII", str(bb_ext.get("score", 0))],
        ["Total", "I + ... + Other", str(total_score)],
    ]
    total_table = Table(total_data, colWidths=[70*mm, 70*mm, 30*mm])
    total_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#7C5CFC')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CCCCCC')),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#F0E6FF')),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    elements.append(total_table)
    elements.append(Spacer(1, 8*mm))

    # ─── DETTAGLIO RISPOSTE (solo Item + Val, 3 colonne, NO 113b/113c) ───
    elements.append(Paragraph("Dettaglio Risposte", styles['Heading2']))
    item_list = []
    for iid in ALL_VISIBLE_ITEMS:
        display = DISPLAY_ID.get(iid, iid)
        val = items.get(iid, {}).get("value") if isinstance(items.get(iid), dict) else items.get(iid)
        item_list.append((display, val))

    third = (len(item_list) + 2) // 3
    col1 = item_list[:third]
    col2 = item_list[third:2*third]
    col3 = item_list[2*third:]

    rows = [["Item", "Val", "Item", "Val", "Item", "Val"]]
    for i in range(max(len(col1), len(col2), len(col3))):
        row = []
        for col in [col1, col2, col3]:
            if i < len(col):
                iid, val = col[i]
                row.extend([str(iid), str(val) if val is not None else "-"])
            else:
                row.extend(["", ""])
        rows.append(row)

    item_table = Table(rows, colWidths=[22*mm, 12*mm, 22*mm, 12*mm, 22*mm, 12*mm])
    item_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#7C5CFC')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('ALIGN', (1, 0), (1, -1), 'CENTER'),
        ('ALIGN', (3, 0), (3, -1), 'CENTER'),
        ('ALIGN', (5, 0), (5, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.3, colors.HexColor('#DDDDDD')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#FAFAFA')]),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]))
    elements.append(item_table)

    # ═══════════════════════════════════════════════════
    #  REPORT FINALE — Aree critiche (risposte = 2)
    # ═══════════════════════════════════════════════════
    if report_finale.get("critical_areas"):
        elements.append(PageBreak())

        header_style = ParagraphStyle(
            'RFHeader', parent=styles['Title'],
            fontSize=16, textColor=colors.HexColor('#7C5CFC'), alignment=1)
        elements.append(Paragraph("REPORT FINALE — Aree Critiche", header_style))

        subtitle_style = ParagraphStyle(
            'RFSub', parent=styles['Normal'],
            fontSize=10, alignment=1, textColor=colors.HexColor('#555555'), spaceAfter=8)
        elements.append(Paragraph(
            "Domande con risposta = 2 (problematica marcata)", subtitle_style))
        elements.append(Spacer(1, 4*mm))

        for area in report_finale["critical_areas"]:
            dark = area.get("color_dark", "#333333")
            bg = area.get("color_bg", "#F5F5F5")

            banner_text = f"<b>{area['code']} — {area['label'].upper()}</b>"
            counter_text = f"{area['n_critical']} risposte critiche su {area['n_total']} item della scala"

            area_rows = [[Paragraph(banner_text, ParagraphStyle(
                'Banner', parent=styles['Normal'], fontSize=12,
                textColor=colors.white, leading=16))]]
            area_rows.append([Paragraph(counter_text, ParagraphStyle(
                'Counter', parent=styles['Normal'], fontSize=9,
                textColor=colors.HexColor(dark), leading=12))])

            for it in area.get("items", []):
                # Skip 113b/113c from report
                if it.get("id") in HIDDEN_ITEMS:
                    continue
                item_display = DISPLAY_ID.get(it["id"], it["id"])
                line = (f"<font color='{dark}'><b>●</b></font>  "
                        f"<b>Item {item_display}</b>  —  {it.get('text', '')}")
                area_rows.append([Paragraph(line, ParagraphStyle(
                    'CritItem', parent=styles['Normal'], fontSize=9,
                    leading=12, leftIndent=8))])

            area_table = Table(area_rows, colWidths=[180*mm])
            area_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor(dark)),
                ('LEFTPADDING', (0, 0), (-1, 0), 10),
                ('TOPPADDING', (0, 0), (-1, 0), 6),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
                ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor(bg)),
                ('LEFTPADDING', (0, 1), (-1, 1), 10),
                ('TOPPADDING', (0, 1), (-1, 1), 4),
                ('BOTTOMPADDING', (0, 1), (-1, 1), 4),
                ('BACKGROUND', (0, 2), (-1, -1), colors.white),
                ('LEFTPADDING', (0, 2), (-1, -1), 10),
                ('RIGHTPADDING', (0, 2), (-1, -1), 10),
                ('TOPPADDING', (0, 2), (-1, -1), 3),
                ('BOTTOMPADDING', (0, 2), (-1, -1), 3),
                ('LINEBEFORE', (0, 1), (0, -1), 3, colors.HexColor(dark)),
                ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor(dark)),
            ]))
            elements.append(KeepTogether(area_table))
            elements.append(Spacer(1, 5*mm))

        # Aree senza criticita
        if report_finale.get("areas_without_critical"):
            elements.append(Spacer(1, 4*mm))
            no_crit = ParagraphStyle('NoCrit', parent=styles['Normal'],
                                     fontSize=9, textColor=colors.HexColor('#666666'), leading=13)
            elements.append(Paragraph("<b>Aree senza risposte critiche:</b>", no_crit))
            labels = [
                f"<font color='{a.get('color_dark', '#666')}'><b>{a['code']}</b></font> {a['label']}"
                for a in report_finale["areas_without_critical"]
            ]
            elements.append(Paragraph("  ·  ".join(labels), no_crit))

    doc.build(elements)
    buf.seek(0)

    ts_file = datetime.now().strftime("%Y%m%d_%H%M%S")
    return StreamingResponse(
        buf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="CBCL_{comp}_{ts_file}.pdf"'},
    )
