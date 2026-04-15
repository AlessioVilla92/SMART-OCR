"""Pagina Risultati — Score broadband, scale sindromiche, DSM, export."""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QFileDialog,
    QGroupBox, QFrame, QScrollArea
)
from PySide6.QtCore import Qt
import json
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from core.scorer import (
    build_score_report, report_to_csv, report_to_json,
    CBCL_SUBSCALES, ALL_ITEMS, build_full_profile
)
from scorer.cbcl_scorer import Compilatore, CBCLProfile, SYNDROME_SCALES, DSM_SCALES


class ResultsPage(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self._report = None
        self._setup_ui()

    def _setup_ui(self):
        # Scroll area per contenuto lungo
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 20, 24, 20)

        # Header + compilatore badge
        header = QHBoxLayout()
        title = QLabel("Risultati Analisi")
        title.setStyleSheet("font-size: 20px; font-weight: 800; color: #E8ECF4;")
        header.addWidget(title)

        self.compilatore_badge = QLabel("")
        self.compilatore_badge.setStyleSheet(
            "font-size: 12px; font-weight: 700; color: #C8B5FF; "
            "background: rgba(124,92,252,0.18); border: 1px solid rgba(124,92,252,0.35); "
            "border-radius: 8px; padding: 4px 12px;"
        )
        self.compilatore_badge.setVisible(False)
        header.addWidget(self.compilatore_badge)

        header.addStretch()
        layout.addLayout(header)

        # === BROADBAND CARDS (Internalizing, Externalizing, Total) ===
        broadband_row = QHBoxLayout()
        broadband_row.setSpacing(12)

        card_gradient = (
            "background: qlineargradient(x1:0, y1:0, x2:1, y2:1, "
            "stop:0 rgba(124,92,252,0.15), stop:1 rgba(185,79,255,0.08)); "
            "border: 1px solid rgba(124,92,252,0.3); border-radius: 16px; padding: 16px;"
        )

        self._broadband_labels = {}
        broadband_items = [
            ("internalizing", "INTERNALIZING", "#60A5FA"),
            ("externalizing", "EXTERNALIZING", "#F87171"),
            ("total", "TOTALE", "#C8B5FF"),
        ]
        for key, label, color in broadband_items:
            card = QFrame()
            card.setStyleSheet(card_gradient)
            card_layout = QVBoxLayout(card)
            card_layout.setSpacing(4)

            val_lbl = QLabel("--")
            val_lbl.setAlignment(Qt.AlignCenter)
            val_lbl.setStyleSheet(f"font-size: 28px; font-weight: 900; color: {color};")
            card_layout.addWidget(val_lbl)

            pct_lbl = QLabel("")
            pct_lbl.setAlignment(Qt.AlignCenter)
            pct_lbl.setStyleSheet("font-size: 11px; font-weight: 600; color: #A0A8B4;")
            card_layout.addWidget(pct_lbl)

            name_lbl = QLabel(label)
            name_lbl.setAlignment(Qt.AlignCenter)
            name_lbl.setStyleSheet(
                "font-size: 9px; font-weight: 800; color: #8B95A7; "
                "letter-spacing: 1.5px; padding-top: 4px;"
            )
            card_layout.addWidget(name_lbl)

            self._broadband_labels[key] = (val_lbl, pct_lbl)
            broadband_row.addWidget(card)

        layout.addLayout(broadband_row)

        # Stats row (sotto broadband)
        stats_row = QHBoxLayout()
        stats_row.setSpacing(12)

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
                "background-color: #141922; border: 1px solid #1E2433; "
                "border-radius: 12px; padding: 10px;"
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

        # === TABELLA SCALE SINDROMICHE ===
        syn_group = QGroupBox("Scale Sindromiche")
        syn_layout = QVBoxLayout(syn_group)

        self.syndrome_table = QTableWidget()
        self.syndrome_table.setColumnCount(5)
        self.syndrome_table.setHorizontalHeaderLabels(["Cod.", "Scala", "Raw", "Max", "Missing"])
        self.syndrome_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        for col in [0, 2, 3, 4]:
            self.syndrome_table.horizontalHeader().setSectionResizeMode(col, QHeaderView.ResizeToContents)
        self.syndrome_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.syndrome_table.verticalHeader().setVisible(False)
        self.syndrome_table.setAlternatingRowColors(True)
        syn_layout.addWidget(self.syndrome_table)
        layout.addWidget(syn_group)

        # === TABELLA SCALE DSM ===
        dsm_group = QGroupBox("Scale DSM-Oriented")
        dsm_layout = QVBoxLayout(dsm_group)

        self.dsm_table = QTableWidget()
        self.dsm_table.setColumnCount(4)
        self.dsm_table.setHorizontalHeaderLabels(["Scala", "Raw", "Max", "Missing"])
        self.dsm_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        for col in [1, 2, 3]:
            self.dsm_table.horizontalHeader().setSectionResizeMode(col, QHeaderView.ResizeToContents)
        self.dsm_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.dsm_table.verticalHeader().setVisible(False)
        self.dsm_table.setAlternatingRowColors(True)
        dsm_layout.addWidget(self.dsm_table)
        layout.addWidget(dsm_group)

        # === SEZIONE TOTALE (riepilogo broadband come da template Excel) ===
        total_group = QGroupBox("TOTALE")
        total_group.setStyleSheet(
            "QGroupBox { font-size: 14px; font-weight: 800; color: #C8B5FF; "
            "border: 2px solid rgba(124,92,252,0.4); border-radius: 10px; "
            "margin-top: 12px; padding-top: 16px; }"
            "QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 6px; }"
        )
        total_layout = QVBoxLayout(total_group)

        self.total_table = QTableWidget()
        self.total_table.setColumnCount(4)
        self.total_table.setHorizontalHeaderLabels(["Scala", "Formula", "Raw", "Max"])
        self.total_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.total_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.total_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.total_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.total_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.total_table.verticalHeader().setVisible(False)
        self.total_table.setAlternatingRowColors(True)
        self.total_table.setFixedHeight(140)
        total_layout.addWidget(self.total_table)
        layout.addWidget(total_group)

        # Export buttons
        export_row = QHBoxLayout()
        export_row.addStretch()

        for btn_text, slot in [
            ("Esporta CSV", self._export_csv),
            ("Esporta MD", self._export_md),
            ("Esporta PDF", self._export_pdf),
            ("Esporta JSON", self._export_json),
            ("Esporta Excel", self._export_excel),
        ]:
            btn = QPushButton(btn_text)
            btn.setObjectName("export_btn")
            btn.setFixedHeight(40)
            btn.clicked.connect(slot)
            export_row.addWidget(btn)

        layout.addLayout(export_row)

        scroll.setWidget(container)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    def update_results(self, report: dict):
        self._report = report

        # Compilatore badge
        comp = report.get("compilatore", "")
        if comp:
            label = "Madre (MD)" if comp == "MD" else "Padre (PD)"
            self.compilatore_badge.setText(label)
            self.compilatore_badge.setVisible(True)
        else:
            self.compilatore_badge.setVisible(False)

        # Profile ricco (se disponibile)
        profile = report.get("_profile")

        if profile and isinstance(profile, CBCLProfile):
            self._update_from_profile(profile, report)
        else:
            self._update_from_flat(report)

    def _update_from_profile(self, profile: CBCLProfile, report: dict):
        """Aggiorna UI con CBCLProfile completo."""

        # Broadband cards
        for key in ["internalizing", "externalizing"]:
            sr = profile.broadband.get(key)
            if sr:
                val_lbl, pct_lbl = self._broadband_labels[key]
                val_lbl.setText(f"{sr.raw_score}/{sr.max_score}")
                pct_lbl.setText(f"{sr.pct}%")

        # Total
        val_lbl, pct_lbl = self._broadband_labels["total"]
        val_lbl.setText(f"{profile.total.raw_score}/{profile.total.max_score}")
        pct_lbl.setText(f"{profile.total.pct}%")

        # Statistics
        stats = report.get("statistics", {})
        for key, lbl in self._stat_labels.items():
            val = stats.get(key, "--")
            if key == "mean_confidence" and isinstance(val, float):
                lbl.setText(f"{val:.0%}")
            else:
                lbl.setText(str(val))

        # Syndrome table (8 scales + Other)
        rows = list(profile.syndrome.values()) + [profile.other]
        self.syndrome_table.setRowCount(len(rows))
        for i, sr in enumerate(rows):
            code = ""
            if sr.key in SYNDROME_SCALES:
                code = SYNDROME_SCALES[sr.key]["code"]
            self.syndrome_table.setItem(i, 0, QTableWidgetItem(code))
            self.syndrome_table.setItem(i, 1, QTableWidgetItem(sr.label_it))
            raw_item = QTableWidgetItem(str(sr.raw_score))
            raw_item.setTextAlignment(Qt.AlignCenter)
            self.syndrome_table.setItem(i, 2, raw_item)
            max_item = QTableWidgetItem(str(sr.max_score))
            max_item.setTextAlignment(Qt.AlignCenter)
            self.syndrome_table.setItem(i, 3, max_item)
            miss_item = QTableWidgetItem(str(len(sr.missing_items)))
            miss_item.setTextAlignment(Qt.AlignCenter)
            self.syndrome_table.setItem(i, 4, miss_item)

        # DSM table (6 scales)
        dsm_rows = list(profile.dsm.values())
        self.dsm_table.setRowCount(len(dsm_rows))
        for i, sr in enumerate(dsm_rows):
            self.dsm_table.setItem(i, 0, QTableWidgetItem(sr.label_it))
            raw_item = QTableWidgetItem(str(sr.raw_score))
            raw_item.setTextAlignment(Qt.AlignCenter)
            self.dsm_table.setItem(i, 1, raw_item)
            max_item = QTableWidgetItem(str(sr.max_score))
            max_item.setTextAlignment(Qt.AlignCenter)
            self.dsm_table.setItem(i, 2, max_item)
            miss_item = QTableWidgetItem(str(len(sr.missing_items)))
            miss_item.setTextAlignment(Qt.AlignCenter)
            self.dsm_table.setItem(i, 3, miss_item)

        # Tabella TOTALE (3 righe: Internalizing / Externalizing / Total)
        total_rows = [
            ("Internal Scala", "I + II + III",
             profile.broadband["internalizing"].raw_score,
             profile.broadband["internalizing"].max_score),
            ("External Scala", "VII + VIII",
             profile.broadband["externalizing"].raw_score,
             profile.broadband["externalizing"].max_score),
            ("Total", "I + ... + Other",
             profile.total.raw_score,
             profile.total.max_score),
        ]
        self.total_table.setRowCount(3)
        for i, (scala, formula, raw, mx) in enumerate(total_rows):
            scala_item = QTableWidgetItem(scala)
            if i == 2:
                from PySide6.QtGui import QFont
                f = QFont()
                f.setBold(True)
                scala_item.setFont(f)
            self.total_table.setItem(i, 0, scala_item)
            formula_item = QTableWidgetItem(formula)
            formula_item.setTextAlignment(Qt.AlignCenter)
            self.total_table.setItem(i, 1, formula_item)
            raw_item = QTableWidgetItem(str(raw))
            raw_item.setTextAlignment(Qt.AlignCenter)
            if i == 2:
                from PySide6.QtGui import QFont
                f = QFont()
                f.setBold(True)
                raw_item.setFont(f)
            self.total_table.setItem(i, 2, raw_item)
            max_item = QTableWidgetItem(str(mx))
            max_item.setTextAlignment(Qt.AlignCenter)
            self.total_table.setItem(i, 3, max_item)

    def _update_from_flat(self, report: dict):
        """Fallback: aggiorna UI dal report flat (vecchi progetti senza _profile)."""
        total = report.get("total_score", 0)
        val_lbl, pct_lbl = self._broadband_labels["total"]
        val_lbl.setText(str(total))
        pct_lbl.setText("")

        # Svuota broadband non disponibili
        for key in ["internalizing", "externalizing"]:
            val_lbl, pct_lbl = self._broadband_labels[key]
            val_lbl.setText("--")
            pct_lbl.setText("")

        # Statistics
        stats = report.get("statistics", {})
        for key, lbl in self._stat_labels.items():
            val = stats.get(key, "--")
            if key == "mean_confidence" and isinstance(val, float):
                lbl.setText(f"{val:.0%}")
            else:
                lbl.setText(str(val))

        # Tutte le subscale nella tabella sindromica
        subscales = report.get("subscale_scores", {})
        syndrome_rows = [(k, v) for k, v in subscales.items()
                         if isinstance(v, dict) and v.get("type") in ("syndrome", None)]
        dsm_rows = [(k, v) for k, v in subscales.items()
                    if isinstance(v, dict) and v.get("type") == "dsm"]

        if not syndrome_rows and not dsm_rows:
            # Vecchio formato senza type: mostra tutto nel sindromiche
            syndrome_rows = list(subscales.items())

        self.syndrome_table.setRowCount(len(syndrome_rows))
        for i, (name, data) in enumerate(syndrome_rows):
            self.syndrome_table.setItem(i, 0, QTableWidgetItem(""))
            self.syndrome_table.setItem(i, 1, QTableWidgetItem(
                data.get("label_it", name.replace("_", " "))))
            raw_item = QTableWidgetItem(str(data.get("score", 0)))
            raw_item.setTextAlignment(Qt.AlignCenter)
            self.syndrome_table.setItem(i, 2, raw_item)
            max_item = QTableWidgetItem(str(data.get("max_score", "")))
            max_item.setTextAlignment(Qt.AlignCenter)
            self.syndrome_table.setItem(i, 3, max_item)
            miss_item = QTableWidgetItem(str(data.get("items_missing", 0)))
            miss_item.setTextAlignment(Qt.AlignCenter)
            self.syndrome_table.setItem(i, 4, miss_item)

        self.dsm_table.setRowCount(len(dsm_rows))
        for i, (name, data) in enumerate(dsm_rows):
            self.dsm_table.setItem(i, 0, QTableWidgetItem(
                data.get("label_it", name.replace("_", " "))))
            raw_item = QTableWidgetItem(str(data.get("score", 0)))
            raw_item.setTextAlignment(Qt.AlignCenter)
            self.dsm_table.setItem(i, 1, raw_item)
            max_item = QTableWidgetItem(str(data.get("max_score", "")))
            max_item.setTextAlignment(Qt.AlignCenter)
            self.dsm_table.setItem(i, 2, max_item)
            miss_item = QTableWidgetItem(str(data.get("items_missing", 0)))
            miss_item.setTextAlignment(Qt.AlignCenter)
            self.dsm_table.setItem(i, 3, miss_item)

        # Tabella TOTALE dal flat (se presente nei subscale_scores)
        total_rows_flat = []
        bb_int = subscales.get("internalizing")
        bb_ext = subscales.get("externalizing")
        if isinstance(bb_int, dict):
            total_rows_flat.append(("Internal Scala", "I + II + III",
                                    bb_int.get("score", 0), bb_int.get("max_score", 64)))
        if isinstance(bb_ext, dict):
            total_rows_flat.append(("External Scala", "VII + VIII",
                                    bb_ext.get("score", 0), bb_ext.get("max_score", 70)))
        total_rows_flat.append(("Total", "I + ... + Other",
                                report.get("total_score", 0), 244))
        self.total_table.setRowCount(len(total_rows_flat))
        for i, (scala, formula, raw, mx) in enumerate(total_rows_flat):
            self.total_table.setItem(i, 0, QTableWidgetItem(scala))
            formula_item = QTableWidgetItem(formula)
            formula_item.setTextAlignment(Qt.AlignCenter)
            self.total_table.setItem(i, 1, formula_item)
            raw_item = QTableWidgetItem(str(raw))
            raw_item.setTextAlignment(Qt.AlignCenter)
            self.total_table.setItem(i, 2, raw_item)
            max_item = QTableWidgetItem(str(mx))
            max_item.setTextAlignment(Qt.AlignCenter)
            self.total_table.setItem(i, 3, max_item)

    def update_from_form(self, form_items: dict,
                         compilatore: Compilatore = Compilatore.MADRE,
                         sex: str = None, age: int = None):
        report = build_score_report(
            form_items, session_id="desktop_manual",
            compilatore=compilatore, sex=sex, age=age,
        )
        self.update_results(report)
        self._report = report

    def reset(self):
        """Azzera i risultati al loro stato iniziale."""
        self._report = None
        for key in self._broadband_labels:
            val_lbl, pct_lbl = self._broadband_labels[key]
            val_lbl.setText("--")
            pct_lbl.setText("")
        for lbl in self._stat_labels.values():
            lbl.setText("--")
        self.syndrome_table.setRowCount(0)
        self.dsm_table.setRowCount(0)
        self.total_table.setRowCount(0)
        self.compilatore_badge.setVisible(False)

    def _get_export_report(self) -> dict:
        if not self._report:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(
                self, "Nessun dato",
                "Nessun risultato disponibile.\nEsegui prima un'analisi nella pagina Upload."
            )
            return {}
        return {k: v for k, v in self._report.items() if not k.startswith("_")}

    def _safe_write(self, path: str, content: str):
        """Scrive file con gestione errori."""
        from PySide6.QtWidgets import QMessageBox
        try:
            Path(path).write_text(content, encoding="utf-8")
            QMessageBox.information(self, "Esportato", f"File salvato:\n{path}")
        except (IOError, OSError) as e:
            QMessageBox.warning(self, "Errore esportazione", f"Impossibile salvare:\n{e}")

    def _export_csv(self):
        report = self._get_export_report()
        if not report:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Salva CSV", "cbcl_results.csv", "CSV (*.csv)")
        if path:
            self._safe_write(path, report_to_csv(report))

    def _export_json(self):
        report = self._get_export_report()
        if not report:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Salva JSON", "cbcl_results.json", "JSON (*.json)")
        if path:
            self._safe_write(path, report_to_json(report))

    def _export_excel(self):
        """Export nel template Excel CBCL_6-18.xlt."""
        if not self._report:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Nessun dato", "Nessun risultato disponibile.")
            return

        path, _ = QFileDialog.getSaveFileName(
            self, "Salva Excel", "cbcl_results.xlsx", "Excel (*.xlsx)")
        if not path:
            return

        try:
            from scorer.excel_export import export_to_excel
            from scorer.cbcl_scorer import Compilatore

            comp_val = self._report.get("compilatore", "MD")
            compilatore = Compilatore.MADRE if comp_val == "MD" else Compilatore.PADRE

            # Estrai risposte flat
            responses = {}
            for item_id, item_data in self._report.get("items", {}).items():
                val = item_data.get("value") if isinstance(item_data, dict) else item_data
                if val is not None:
                    try:
                        k = int(item_id)
                    except (ValueError, TypeError):
                        k = str(item_id)
                    responses[k] = int(val)

            result_path = export_to_excel(
                responses=responses,
                compilatore=compilatore,
                output_path=path,
            )
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(self, "Esportato", f"Excel salvato:\n{result_path}")

        except FileNotFoundError as e:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Template mancante",
                                f"Template Excel non trovato:\n{e}")
        except ImportError:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Modulo mancante",
                                "Esportazione Excel richiede 'openpyxl'.\n\n"
                                "Installa con: pip install openpyxl")
        except Exception as e:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Errore Excel", f"Errore generazione Excel:\n{e}")

    def _export_md(self):
        report = self._get_export_report()
        if not report:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Salva Markdown", "cbcl_results.md", "Markdown (*.md)")
        if not path:
            return

        lines = []
        comp = report.get("compilatore", "")
        comp_label = f" ({comp})" if comp else ""
        lines.append(f"# CBCL 6-18 — Risultati{comp_label}")
        lines.append(f"")
        lines.append(f"**Data:** {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        lines.append(f"**Score Totale:** {report.get('total_score', 0)}")
        lines.append(f"")

        # Broadband
        subscales = report.get("subscale_scores", {})
        broadband = {k: v for k, v in subscales.items()
                     if isinstance(v, dict) and v.get("type") == "broadband"}
        if broadband:
            lines.append(f"## Broadband")
            lines.append(f"| Scala | Score | Max | % |")
            lines.append(f"|-------|:-----:|:---:|:-:|")
            for name, data in broadband.items():
                lines.append(f"| {data.get('label_it', name)} | "
                             f"{data.get('score', 0)} | {data.get('max_score', '')} | "
                             f"{data.get('pct', '')} |")
            lines.append(f"")

        # TOTALE (riepilogo come da template Excel) — senza Max
        lines.append(f"## TOTALE")
        lines.append(f"| Scala | Formula | Raw |")
        lines.append(f"|-------|---------|:---:|")
        bb_int = subscales.get("internalizing", {}) if isinstance(subscales.get("internalizing"), dict) else {}
        bb_ext = subscales.get("externalizing", {}) if isinstance(subscales.get("externalizing"), dict) else {}
        lines.append(f"| Internal Scala | I + II + III | {bb_int.get('score', 0)} |")
        lines.append(f"| External Scala | VII + VIII | {bb_ext.get('score', 0)} |")
        lines.append(f"| **Total** | **I + ... + Other** | **{report.get('total_score', 0)}** |")
        lines.append(f"")

        # Sindromiche — senza Max
        syndrome = {k: v for k, v in subscales.items()
                    if isinstance(v, dict) and v.get("type") in ("syndrome", None)
                    and k not in broadband}
        if syndrome:
            lines.append(f"## Scale Sindromiche")
            lines.append(f"| Scala | Score | Missing |")
            lines.append(f"|-------|:-----:|:-------:|")
            for name, data in syndrome.items():
                lines.append(f"| {data.get('label_it', name.replace('_', ' '))} | "
                             f"{data.get('score', 0)} | {data.get('items_missing', 0)} |")
            lines.append(f"")

        # DSM — senza Max
        dsm = {k: v for k, v in subscales.items()
               if isinstance(v, dict) and v.get("type") == "dsm"}
        if dsm:
            lines.append(f"## Scale DSM-Oriented")
            lines.append(f"| Scala | Score | Missing |")
            lines.append(f"|-------|:-----:|:-------:|")
            for name, data in dsm.items():
                lines.append(f"| {data.get('label_it', name.replace('_', ' '))} | "
                             f"{data.get('score', 0)} | {data.get('items_missing', 0)} |")
            lines.append(f"")

        # Risposte
        lines.append(f"## Risposte")
        lines.append(f"")
        lines.append(f"| Domanda | Valore |")
        lines.append(f"|---------|--------|")
        for item_id in ALL_ITEMS:
            val = report.get("items", {}).get(item_id, {}).get("value")
            lines.append(f"| {item_id} | {val if val is not None else '-'} |")
        lines.append(f"")

        # ───────────────────────────────────────────
        # REPORT FINALE — Aree Critiche
        # ───────────────────────────────────────────
        from scorer.scale_colors import build_report_finale
        rf = build_report_finale(report)

        lines.append(f"---")
        lines.append(f"")
        lines.append(f"# REPORT FINALE — Aree Critiche")
        lines.append(f"")
        lines.append(f"_Domande con risposta = 2 (problematica marcata)_")
        lines.append(f"")
        lines.append(f"**Totale risposte critiche: {rf['total_critical']}**")
        lines.append(f"")

        for area in rf["critical_areas"]:
            lines.append(f"## {area['code']} — {area['label']}")
            lines.append(f"")
            lines.append(f"_{area['n_critical']} risposte critiche su "
                         f"{area['n_total']} item della scala_")
            lines.append(f"")
            for item in area["items"]:
                lines.append(f"- **Item {item['id']}** — {item['text']}")
            lines.append(f"")

        if rf["areas_without_critical"]:
            lines.append(f"### Aree senza risposte critiche")
            lines.append(f"")
            lines.append(", ".join(
                f"**{a['code']}** {a['label']}"
                for a in rf["areas_without_critical"]
            ))

        self._safe_write(path, "\n".join(lines))

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
            from reportlab.platypus import (
                SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer,
                KeepTogether, PageBreak,
            )
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from scorer.scale_colors import SCALE_COLORS, ITEM_TO_SCALE, load_italian_questions
            from scorer.cbcl_scorer import SYNDROME_SCALES, OTHER_PROBLEMS

            doc = SimpleDocTemplate(path, pagesize=A4,
                                    topMargin=20*mm, bottomMargin=20*mm,
                                    leftMargin=15*mm, rightMargin=15*mm)
            styles = getSampleStyleSheet()
            elements = []

            # Titolo
            comp = report.get("compilatore", "")
            comp_label = f" — {comp}" if comp else ""
            title_style = ParagraphStyle('Title', parent=styles['Title'],
                                         fontSize=18, textColor=colors.HexColor('#333333'))
            elements.append(Paragraph(f"CBCL 6-18 — Risultati{comp_label}", title_style))
            elements.append(Spacer(1, 5*mm))

            # Info
            info_style = ParagraphStyle('Info', parent=styles['Normal'], fontSize=10)
            elements.append(Paragraph(
                f"Data: {datetime.now().strftime('%Y-%m-%d %H:%M')} | "
                f"Score Totale: <b>{report.get('total_score', 0)}</b>",
                info_style
            ))
            elements.append(Spacer(1, 6*mm))

            subscales = report.get("subscale_scores", {})

            # Ordine scale sindromiche da visualizzare
            syndrome_order = [
                "anxious_depressed", "withdrawn_depressed", "somatic_complaints",
                "social_problems", "thought_problems", "attention_problems",
                "rule_breaking", "aggressive_behavior",
            ]

            # ─── TABELLA SCALE SINDROMICHE (senza Max, con badge colore) ───
            elements.append(Paragraph("Scale Sindromiche", styles['Heading2']))
            sub_data = [["Cod.", "Scala", "Raw", "Missing"]]
            row_colors = [colors.white]  # riga header
            for key in syndrome_order:
                data = subscales.get(key, {})
                if not data:
                    continue
                info = SCALE_COLORS.get(key, {})
                sub_data.append([
                    info.get("code", ""),
                    data.get("label_it", info.get("label", key)),
                    str(data.get("score", 0)),
                    str(data.get("items_missing", 0)),
                ])
                row_colors.append(colors.HexColor(info.get("bg", "#FFFFFF")))
            # Riga Other
            other_data = subscales.get("other_problems", {})
            if other_data:
                info = SCALE_COLORS["other_problems"]
                sub_data.append([
                    info["code"],
                    other_data.get("label_it", info["label"]),
                    str(other_data.get("score", 0)),
                    str(other_data.get("items_missing", 0)),
                ])
                row_colors.append(colors.HexColor(info["bg"]))

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
            # Sfondi per singola riga (colore scala)
            for i, bg in enumerate(row_colors[1:], start=1):
                sub_style.append(('BACKGROUND', (0, i), (-1, i), bg))
            sub_table.setStyle(TableStyle(sub_style))
            elements.append(sub_table)
            elements.append(Spacer(1, 6*mm))

            # ─── TABELLA DSM (senza Max) ───
            dsm = {k: v for k, v in subscales.items()
                   if isinstance(v, dict) and v.get("type") == "dsm"}
            if dsm:
                elements.append(Paragraph("Scale DSM-Oriented", styles['Heading2']))
                dsm_data = [["Scala", "Raw", "Missing"]]
                for name, data in dsm.items():
                    dsm_data.append([
                        data.get("label_it", name.replace("_", " ")),
                        str(data.get("score", 0)),
                        str(data.get("items_missing", 0)),
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

            # ─── TABELLA TOTALE (senza Max) ───
            elements.append(Paragraph("TOTALE", styles['Heading2']))
            bb_int = subscales.get("internalizing", {}) if isinstance(subscales.get("internalizing"), dict) else {}
            bb_ext = subscales.get("externalizing", {}) if isinstance(subscales.get("externalizing"), dict) else {}
            total_data = [
                ["Scala", "Formula", "Raw"],
                ["Internal Scala", "I + II + III", str(bb_int.get("score", 0))],
                ["External Scala", "VII + VIII", str(bb_ext.get("score", 0))],
                ["Total", "I + ... + Other", str(report.get("total_score", 0))],
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

            # ─── DETTAGLIO RISPOSTE (neutro, 3 colonne) ───
            elements.append(Paragraph("Dettaglio Risposte", styles['Heading2']))
            items = report.get("items", {})
            item_list = [(iid, items.get(iid, {}).get("value")) for iid in ALL_ITEMS]

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
            elements.append(PageBreak())

            header_style = ParagraphStyle(
                'ReportFinalHeader', parent=styles['Title'],
                fontSize=16, textColor=colors.HexColor('#7C5CFC'),
                alignment=1,  # center
            )
            elements.append(Paragraph("REPORT FINALE — Aree Critiche", header_style))
            subtitle_style = ParagraphStyle(
                'ReportFinalSub', parent=styles['Normal'],
                fontSize=10, alignment=1, textColor=colors.HexColor('#555555'),
                spaceAfter=8,
            )
            elements.append(Paragraph(
                "Domande con risposta = 2 (problematica marcata)", subtitle_style))
            elements.append(Spacer(1, 4*mm))

            from scorer.scale_colors import build_report_finale
            rf = build_report_finale(report)

            for area in rf["critical_areas"]:
                banner_text = f"<b>{area['code']} — {area['label'].upper()}</b>"
                counter_text = f"{area['n_critical']} risposte critiche su {area['n_total']} item della scala"

                area_rows = [[Paragraph(banner_text, ParagraphStyle(
                    'Banner', parent=styles['Normal'], fontSize=12,
                    textColor=colors.white, leading=16,
                ))]]
                area_rows.append([Paragraph(counter_text, ParagraphStyle(
                    'Counter', parent=styles['Normal'], fontSize=9,
                    textColor=colors.HexColor(area['color_dark']), leading=12,
                ))])
                for item in area["items"]:
                    line = f"<font color='{area['color_dark']}'><b>●</b></font>  " \
                           f"<b>Item {item['id']}</b>  —  {item['text']}"
                    area_rows.append([Paragraph(line, ParagraphStyle(
                        'CriticalItem', parent=styles['Normal'], fontSize=9,
                        leading=12, leftIndent=8,
                    ))])

                area_table = Table(area_rows, colWidths=[180*mm])
                area_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor(area['color_dark'])),
                    ('LEFTPADDING', (0, 0), (-1, 0), 10),
                    ('TOPPADDING', (0, 0), (-1, 0), 6),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
                    ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor(area['color_bg'])),
                    ('LEFTPADDING', (0, 1), (-1, 1), 10),
                    ('TOPPADDING', (0, 1), (-1, 1), 4),
                    ('BOTTOMPADDING', (0, 1), (-1, 1), 4),
                    ('BACKGROUND', (0, 2), (-1, -1), colors.white),
                    ('LEFTPADDING', (0, 2), (-1, -1), 10),
                    ('RIGHTPADDING', (0, 2), (-1, -1), 10),
                    ('TOPPADDING', (0, 2), (-1, -1), 3),
                    ('BOTTOMPADDING', (0, 2), (-1, -1), 3),
                    ('LINEBEFORE', (0, 1), (0, -1), 3, colors.HexColor(area['color_dark'])),
                    ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor(area['color_dark'])),
                ]))
                elements.append(KeepTogether(area_table))
                elements.append(Spacer(1, 5*mm))

            # Aree senza criticita'
            if rf["areas_without_critical"]:
                elements.append(Spacer(1, 4*mm))
                no_crit_style = ParagraphStyle(
                    'NoCrit', parent=styles['Normal'], fontSize=9,
                    textColor=colors.HexColor('#666666'), leading=13,
                )
                elements.append(Paragraph(
                    "<b>Aree senza risposte critiche:</b>", no_crit_style))
                labels = [
                    f"<font color='{a['color_dark']}'><b>{a['code']}</b></font> {a['label']}"
                    for a in rf["areas_without_critical"]
                ]
                elements.append(Paragraph("  ·  ".join(labels), no_crit_style))

            doc.build(elements)

            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(self, "Esportato", f"PDF salvato:\n{path}")

        except ImportError:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(
                self, "Modulo mancante",
                "Esportazione PDF richiede 'reportlab'.\n\n"
                "Installa con: pip install reportlab"
            )
        except Exception as e:
            from PySide6.QtWidgets import QMessageBox
            import traceback
            QMessageBox.warning(self, "Errore PDF",
                                f"Errore generazione PDF:\n{e}\n\n{traceback.format_exc()[:500]}")
