"""Pagina Risultati — Score, subscale, export CSV/MD/PDF."""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QFileDialog,
    QGroupBox, QFrame
)
from PySide6.QtCore import Qt
import json
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from core.scorer import (
    build_score_report, report_to_csv, report_to_json,
    CBCL_SUBSCALES, ALL_ITEMS
)


class ResultsPage(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self._report = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 20, 24, 20)

        # Header
        header = QHBoxLayout()
        title = QLabel("Risultati Analisi")
        title.setStyleSheet("font-size: 20px; font-weight: 800; color: #E8ECF4;")
        header.addWidget(title)
        header.addStretch()
        layout.addLayout(header)

        # Score + Stats row
        stats_row = QHBoxLayout()
        stats_row.setSpacing(16)

        # Score card grande
        score_card = QFrame()
        score_card.setStyleSheet(
            "background: qlineargradient(x1:0, y1:0, x2:1, y2:1, "
            "stop:0 rgba(124,92,252,0.15), stop:1 rgba(185,79,255,0.08)); "
            "border: 1px solid rgba(124,92,252,0.3); border-radius: 16px; padding: 20px;"
        )
        score_layout = QVBoxLayout(score_card)
        self.score_label = QLabel("--")
        self.score_label.setObjectName("score_big")
        self.score_label.setAlignment(Qt.AlignCenter)
        score_layout.addWidget(self.score_label)
        score_desc = QLabel("SCORE TOTALE")
        score_desc.setObjectName("score_label")
        score_desc.setAlignment(Qt.AlignCenter)
        score_layout.addWidget(score_desc)
        score_card.setFixedWidth(180)
        stats_row.addWidget(score_card)

        # Stat cards
        self._stat_labels = {}
        stat_items = [
            ("items_scored", "Completati", "#34D399"),
            ("items_missing", "Mancanti", "#F87171"),
            ("items_flagged", "Con Flag", "#FBBF24"),
            ("mean_confidence", "Confidence", "#60A5FA"),
        ]
        for key, label, color in stat_items:
            card = QFrame()
            card.setStyleSheet(
                f"background-color: #141922; border: 1px solid #1E2433; "
                f"border-radius: 12px; padding: 12px;"
            )
            card_layout = QVBoxLayout(card)
            card_layout.setSpacing(4)

            val_lbl = QLabel("--")
            val_lbl.setObjectName("stat_value")
            val_lbl.setAlignment(Qt.AlignCenter)
            val_lbl.setStyleSheet(f"color: {color};")
            card_layout.addWidget(val_lbl)

            name_lbl = QLabel(label.upper())
            name_lbl.setObjectName("stat_name")
            name_lbl.setAlignment(Qt.AlignCenter)
            card_layout.addWidget(name_lbl)

            self._stat_labels[key] = val_lbl
            stats_row.addWidget(card)

        layout.addLayout(stats_row)

        # Tabella subscale
        sub_group = QGroupBox("Subscale DSM-Oriented")
        sub_layout = QVBoxLayout(sub_group)

        self.subscale_table = QTableWidget()
        self.subscale_table.setColumnCount(3)
        self.subscale_table.setHorizontalHeaderLabels(["Subscale", "Score", "Items Mancanti"])
        self.subscale_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.subscale_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.subscale_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.subscale_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.subscale_table.verticalHeader().setVisible(False)
        self.subscale_table.setAlternatingRowColors(True)
        sub_layout.addWidget(self.subscale_table)
        layout.addWidget(sub_group)

        # Export buttons
        export_row = QHBoxLayout()
        export_row.addStretch()

        for btn_text, slot in [
            ("Esporta CSV", self._export_csv),
            ("Esporta MD", self._export_md),
            ("Esporta PDF", self._export_pdf),
            ("Esporta JSON", self._export_json),
        ]:
            btn = QPushButton(btn_text)
            btn.setObjectName("export_btn")
            btn.setFixedHeight(40)
            btn.clicked.connect(slot)
            export_row.addWidget(btn)

        layout.addLayout(export_row)

    def update_results(self, report: dict):
        self._report = report
        self.score_label.setText(str(report.get("total_score", 0)))

        stats = report.get("statistics", {})
        for key, lbl in self._stat_labels.items():
            val = stats.get(key, "--")
            if key == "mean_confidence" and isinstance(val, float):
                lbl.setText(f"{val:.0%}")
            else:
                lbl.setText(str(val))

        subscales = report.get("subscale_scores", {})
        self.subscale_table.setRowCount(len(subscales))
        for row, (name, data) in enumerate(subscales.items()):
            self.subscale_table.setItem(row, 0, QTableWidgetItem(name.replace("_", " ")))
            score_item = QTableWidgetItem(str(data.get("score", 0)))
            score_item.setTextAlignment(Qt.AlignCenter)
            self.subscale_table.setItem(row, 1, score_item)
            miss_item = QTableWidgetItem(str(data.get("items_missing", 0)))
            miss_item.setTextAlignment(Qt.AlignCenter)
            self.subscale_table.setItem(row, 2, miss_item)

    def update_from_form(self, form_items: dict):
        report = build_score_report(form_items, session_id="desktop_manual")
        self.update_results(report)
        self._report = report

    def _get_export_report(self) -> dict:
        if not self._report:
            return {}
        return {k: v for k, v in self._report.items() if not k.startswith("_")}

    def _export_csv(self):
        report = self._get_export_report()
        if not report:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Salva CSV", "cbcl_results.csv", "CSV (*.csv)")
        if path:
            Path(path).write_text(report_to_csv(report), encoding="utf-8")

    def _export_json(self):
        report = self._get_export_report()
        if not report:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Salva JSON", "cbcl_results.json", "JSON (*.json)")
        if path:
            Path(path).write_text(report_to_json(report), encoding="utf-8")

    def _export_md(self):
        report = self._get_export_report()
        if not report:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Salva Markdown", "cbcl_results.md", "Markdown (*.md)")
        if not path:
            return

        lines = []
        lines.append(f"# CBCL 6-18 — Risultati")
        lines.append(f"")
        lines.append(f"**Data:** {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        lines.append(f"**Score Totale:** {report.get('total_score', 0)}")
        lines.append(f"")
        lines.append(f"## Risposte")
        lines.append(f"")
        lines.append(f"| Domanda | Valore |")
        lines.append(f"|---------|--------|")
        for item_id in ALL_ITEMS:
            val = report.get("items", {}).get(item_id, {}).get("value")
            lines.append(f"| {item_id} | {val if val is not None else '-'} |")
        lines.append(f"")
        lines.append(f"## Subscale")
        lines.append(f"")
        lines.append(f"| Subscale | Score | Mancanti |")
        lines.append(f"|----------|:-----:|:--------:|")
        for name, data in report.get("subscale_scores", {}).items():
            lines.append(f"| {name.replace('_', ' ')} | {data['score']} | {data['items_missing']} |")

        Path(path).write_text("\n".join(lines), encoding="utf-8")

    def _export_pdf(self):
        report = self._get_export_report()
        if not report:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Salva PDF", "cbcl_results.pdf", "PDF (*.pdf)")
        if not path:
            return

        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.units import mm
            from reportlab.lib import colors
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

            doc = SimpleDocTemplate(path, pagesize=A4,
                                    topMargin=20*mm, bottomMargin=20*mm,
                                    leftMargin=15*mm, rightMargin=15*mm)
            styles = getSampleStyleSheet()
            elements = []

            # Titolo
            title_style = ParagraphStyle('Title', parent=styles['Title'],
                                         fontSize=18, textColor=colors.HexColor('#333333'))
            elements.append(Paragraph("CBCL 6-18 — Risultati Analisi", title_style))
            elements.append(Spacer(1, 5*mm))

            # Info
            info_style = ParagraphStyle('Info', parent=styles['Normal'], fontSize=10)
            elements.append(Paragraph(
                f"Data: {datetime.now().strftime('%Y-%m-%d %H:%M')} | "
                f"Score Totale: <b>{report.get('total_score', 0)}</b>",
                info_style
            ))
            elements.append(Spacer(1, 8*mm))

            # Tabella subscale
            elements.append(Paragraph("Subscale DSM-Oriented", styles['Heading2']))
            sub_data = [["Subscale", "Score", "Mancanti"]]
            for name, data in report.get("subscale_scores", {}).items():
                sub_data.append([name.replace("_", " "), str(data["score"]), str(data["items_missing"])])

            sub_table = Table(sub_data, colWidths=[120*mm, 25*mm, 25*mm])
            sub_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#7C5CFC')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CCCCCC')),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F5F5F5')]),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ]))
            elements.append(sub_table)
            elements.append(Spacer(1, 8*mm))

            # Tabella items (3 colonne per risparmiare spazio)
            elements.append(Paragraph("Dettaglio Risposte", styles['Heading2']))
            items = report.get("items", {})
            item_list = [(iid, items.get(iid, {}).get("value")) for iid in ALL_ITEMS]

            # Dividi in 3 colonne
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

            doc.build(elements)

        except ImportError:
            # Fallback se reportlab non installato
            pass
