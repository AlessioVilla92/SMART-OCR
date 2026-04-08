# SMART OCR v3.0 — App Desktop con CBCL Digitale Interattiva
# Istruzioni Complete per Claude Code

> **Framework:** PySide6 (Qt6) — cross-platform Windows + macOS
> **Tema:** Dark theme con pyqtdarktheme
> **Packaging:** PyInstaller
> **Tutti i moduli OMR/alignment dal documento v2.1 sono inclusi**

---

## ARCHITETTURA APPLICAZIONE

```
smart_ocr/
├── main.py                         # Entry point
├── app/
│   ├── __init__.py
│   ├── main_window.py              # QMainWindow principale
│   ├── pages/
│   │   ├── __init__.py
│   │   ├── home_page.py            # Pagina caricamento foto
│   │   ├── cbcl_form_page.py       # Replica digitale CBCL interattiva
│   │   ├── results_page.py         # Riepilogo scores e subscale
│   │   └── settings_page.py        # Impostazioni modelli e soglie
│   ├── widgets/
│   │   ├── __init__.py
│   │   ├── cbcl_item_widget.py     # Widget singolo item (0/1/2 con checkbox)
│   │   ├── photo_viewer.py         # Visualizzatore foto con overlay bordi
│   │   ├── boundary_overlay.py     # Overlay bordino giallo
│   │   └── confidence_badge.py     # Badge colorato per confidence
│   ├── workers/
│   │   ├── __init__.py
│   │   └── analysis_worker.py      # QThread per processing non-blocking
│   └── theme.py                    # Dark theme e stili custom
├── core/                           # Moduli OMR (invariati da v2.1)
│   ├── boundary_detector.py
│   ├── template_aligner.py
│   ├── preprocessor.py
│   ├── grid_extractor.py
│   ├── omr_classifier.py
│   ├── classifier.py               # HOG+SVM
│   ├── scorer.py
│   └── cbcl_data.py                # Testi domande CBCL dal PDF
├── models/
├── templates/
├── training/
└── resources/
    └── cbcl_questions_it.json      # Testi 119 domande in italiano
```

---

## TECH STACK

```
# requirements.txt — AGGIORNATO per app desktop

# GUI Framework (cross-platform)
PySide6>=6.7.0                      # LGPL, Qt6 bindings ufficiali
pyqtdarktheme>=2.1.0                # MIT, dark theme flat

# Image processing (invariato)
opencv-contrib-python==4.9.0.80
numpy==1.26.4

# ML (invariato)
scikit-learn==1.8.0
joblib==1.4.0

# Boundary detection neurale
docaligner-docsaid>=1.1.0
PyTurboJPEG<2.0

# PDF rendering
PyMuPDF>=1.24.0

# Data
pandas==2.2.1
Pillow==10.3.0

# Training only
albumentations==2.0.8

# Packaging
pyinstaller>=6.6.0
```

**Perché PySide6 e non Streamlit:**
- Streamlit NON supporta checkbox cliccabili individuali in una griglia
- Streamlit NON supporta dark theme nativo
- Streamlit NON può fare packaging .exe/.app stand-alone
- PySide6 è LGPL (free), cross-platform, HiDPI nativo, PyInstaller ready

---

## LAYOUT PRINCIPALE (main_window.py)

```
┌────────────────────────────────────────────────────────┐
│  🧾 Smart OCR — CBCL Scanner                    ─ □ × │
├──────────┬─────────────────────────────────────────────┤
│          │                                             │
│  📤 Home │   [Contenuto pagina corrente]               │
│          │                                             │
│  📋 CBCL │                                             │
│          │                                             │
│  📊 Score│                                             │
│          │                                             │
│  ⚙ Opz. │                                             │
│          │                                             │
├──────────┴─────────────────────────────────────────────┤
│  Status: Pronto | Modello: SVM+OMR | Tempo: 1.8s      │
└────────────────────────────────────────────────────────┘
```

Sidebar sinistra con 4 icone navigazione. Area principale cambia per pagina.

---

## PAGINA HOME (home_page.py)

Layout in 2 colonne:

**Colonna sinistra (50%):**
- Pulsante "Carica foto" → QFileDialog per JPG/PNG
- Anteprima foto caricata con bordino giallo sovrapposto
- Info: risoluzione, confidence bordi, metodo usato
- Selezione pagina: "Pagina 4 (items 1-54)" / "Pagina 5 (items 55-112)"
- Selezione modelli: checkbox "OMR pixel", checkbox "SVM", checkbox "Entrambi"
- Pulsante "🔍 ANALIZZA" (grande, viola/accent)

**Colonna destra (50%):**
- Dopo analisi: anteprima foto warpata con griglia sovrapposta
- Statistiche rapide: items letti, missing, ambigui
- Progress bar durante analisi

---

## PAGINA CBCL FORM (cbcl_form_page.py) — LA PIÙ IMPORTANTE

Replica digitale della CBCL con 2 colonne, identica al foglio cartaceo.
Scrollabile verticalmente. Ogni item è un widget autonomo.

### Layout pagina CBCL:

```
┌─────────────────────────────────────────────────────────┐
│  CBCL 6-18 — Pagina 4                    [Esporta CSV] │
├─────────────────────────┬───────────────────────────────┤
│                         │                               │
│  1. Agisce in modo      │  28. Infrango le regole a     │
│     infantile per la    │      casa, a scuola...        │
│     sua età             │                               │
│     [●] 0  [ ] 1  [ ] 2│      [ ] 0  [●] 1  [ ] 2     │
│                         │                               │
│  2. Beve alcolici senza │  29. Ha paura di certi        │
│     l'approvazione...   │      animali...               │
│     [●] 0  [ ] 1  [ ] 2│      [●] 0  [ ] 1  [ ] 2     │
│                         │                               │
│  3. Discute in modo     │  30. Ha paura di andare       │
│     polemico            │      a scuola                 │
│     [ ] 0  [●] 1  [ ] 2│      [●] 0  [ ] 1  [ ] 2     │
│     ⚠️ CONFIDENCE BASSA │                               │
│     ══════════════════  │                               │
│                         │                               │
│  4. Non porta a termine │  31. Ha paura di poter        │
│     le cose...          │      pensare...               │
│     [ROSSO] SCEGLI →    │      [ ] 0  [ ] 1  [●] 2     │
│     ( ) 0  ( ) 1  ( ) 2 │                               │
│                         │                               │
│  ...continua...         │  ...continua...               │
│                         │                               │
├─────────────────────────┴───────────────────────────────┤
│  Items: 54/54 completati | Ambigui: 3 | Score parz: 47 │
└─────────────────────────────────────────────────────────┘
```

### Widget singolo item (cbcl_item_widget.py):

Ogni item ha 3 stati possibili:

**STATO VERDE (confident):** Il modello ha identificato la risposta.
- Mostra testo domanda + 3 checkbox di cui una segnata con ●
- Checkbox sono READ-ONLY (non cliccabili) — l'utente vede il risultato
- Sfondo leggermente verde scuro

**STATO GIALLO (low confidence):** Il modello è incerto.
- Mostra testo + checkbox con risultato provvisorio segnato
- Badge "⚠️ Conferma" giallo
- Checkbox CLICCABILI — l'utente può cambiare
- Sfondo leggermente giallo scuro

**STATO ROSSO (missing/ambiguo):** Il modello non ha trovato risposta.
- Mostra testo + 3 radio button VUOTI
- Badge "❌ Scegli" rosso
- Radio button CLICCABILI — l'utente DEVE scegliere
- Sfondo leggermente rosso scuro
- Il numero della domanda è evidenziato in rosso

### Implementazione del widget:

```python
class CBCLItemWidget(QFrame):
    """Widget per un singolo item CBCL con 3 opzioni (0, 1, 2)."""
    
    value_changed = Signal(str, int)  # item_id, new_value
    
    def __init__(self, item_id, question_text, parent=None):
        super().__init__(parent)
        self.item_id = item_id
        self.question_text = question_text
        self._value = None
        self._confidence = 0.0
        self._state = "pending"  # pending, confident, uncertain, missing
        
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        
        # Riga 1: numero + testo domanda
        header = QHBoxLayout()
        self.num_label = QLabel(f"{self.item_id}.")
        self.num_label.setFixedWidth(30)
        self.num_label.setStyleSheet("font-weight: bold; font-size: 13px;")
        
        self.text_label = QLabel(self.question_text)
        self.text_label.setWordWrap(True)
        self.text_label.setStyleSheet("font-size: 11px;")
        
        header.addWidget(self.num_label)
        header.addWidget(self.text_label, 1)
        layout.addLayout(header)
        
        # Riga 2: 3 checkbox/radio per 0, 1, 2
        choices = QHBoxLayout()
        self.button_group = QButtonGroup(self)
        self.buttons = {}
        
        for val in [0, 1, 2]:
            btn = QRadioButton(str(val))
            btn.setStyleSheet("font-size: 13px; padding: 2px 8px;")
            self.button_group.addButton(btn, val)
            self.buttons[val] = btn
            choices.addWidget(btn)
        
        # Badge confidence
        self.badge = QLabel("")
        self.badge.setFixedWidth(120)
        self.badge.setAlignment(Qt.AlignCenter)
        choices.addWidget(self.badge)
        
        choices.addStretch()
        layout.addLayout(choices)
        
        # Connessione segnali
        self.button_group.idClicked.connect(self._on_value_changed)
        
        self.setFrameStyle(QFrame.StyledPanel)
        self.setFixedHeight(70)
    
    def set_result(self, value, confidence, flag):
        """Imposta il risultato dal modello OMR."""
        self._value = value
        self._confidence = confidence
        
        if flag is None and confidence > 0.85:
            self._state = "confident"
            self._set_confident(value)
        elif flag in ("low_confidence", "ambiguous") or (0.5 < confidence <= 0.85):
            self._state = "uncertain"
            self._set_uncertain(value)
        else:
            self._state = "missing"
            self._set_missing()
    
    def _set_confident(self, value):
        """Stato VERDE: risposta sicura, checkbox read-only."""
        self.buttons[value].setChecked(True)
        for btn in self.buttons.values():
            btn.setEnabled(False)  # Read-only
        
        self.badge.setText(f"✅ {self._confidence:.0%}")
        self.badge.setStyleSheet(
            "background: #1a3a1a; color: #4ade80; border-radius: 4px; padding: 2px;")
        self.setStyleSheet(
            "CBCLItemWidget { background: #0d1f0d; border: 1px solid #1a3a1a; border-radius: 4px; }")
    
    def _set_uncertain(self, value):
        """Stato GIALLO: risposta incerta, checkbox modificabili."""
        if value is not None:
            self.buttons[value].setChecked(True)
        for btn in self.buttons.values():
            btn.setEnabled(True)  # Cliccabili
        
        self.badge.setText(f"⚠️ Conferma")
        self.badge.setStyleSheet(
            "background: #3a2a0a; color: #fbbf24; border-radius: 4px; padding: 2px;")
        self.setStyleSheet(
            "CBCLItemWidget { background: #1f1a0d; border: 1px solid #3a2a0a; border-radius: 4px; }")
    
    def _set_missing(self):
        """Stato ROSSO: nessuna risposta, utente DEVE scegliere."""
        for btn in self.buttons.values():
            btn.setChecked(False)
            btn.setEnabled(True)
        
        self.badge.setText(f"❌ Scegli")
        self.badge.setStyleSheet(
            "background: #3a0a0a; color: #f87171; border-radius: 4px; padding: 2px;")
        self.setStyleSheet(
            "CBCLItemWidget { background: #1f0d0d; border: 2px solid #dc2626; border-radius: 4px; }")
        self.num_label.setStyleSheet(
            "font-weight: bold; font-size: 13px; color: #ef4444;")
    
    def _on_value_changed(self, id):
        self._value = id
        self.value_changed.emit(self.item_id, id)
        # Aggiorna visivamente a "confermato dall'utente"
        self.badge.setText(f"✏️ Manuale")
        self.badge.setStyleSheet(
            "background: #1a2a3a; color: #60a5fa; border-radius: 4px; padding: 2px;")
        self.setStyleSheet(
            "CBCLItemWidget { background: #0d1520; border: 1px solid #1a2a3a; border-radius: 4px; }")
    
    def get_value(self):
        return self._value
```

---

## TESTI DOMANDE CBCL — resources/cbcl_questions_it.json

Questo file va generato LEGGENDO il PDF `Cbcl_618_GENITORI.pdf` nel repository.
Contiene i testi di tutte le 119 domande in italiano.

Struttura:
```json
{
  "page_4": {
    "1": "Agisce in modo infantile per la sua età",
    "2": "Beve alcolici senza l'approvazione dei genitori",
    "3": "Discute in modo polemico",
    ...
    "56a": "Dolori (non includere mal di stomaco e mal di testa)",
    "56b": "Mal di testa",
    ...
  },
  "page_5": {
    "57": "Assale fisicamente le persone",
    ...
    "112": "Si preoccupa"
  }
}
```

**COME GENERARLO:** Il PDF `Cbcl_618_GENITORI.pdf` è nel repository come
attachment nel progetto Claude. I testi sono anche nel documento allegato
in questa conversazione (pages 4-6 del PDF). Claude Code può estrarli
dal PDF con pdfplumber o copiarli direttamente.

---

## WORKER THREAD (analysis_worker.py)

L'analisi è pesante (~2s) e DEVE girare su un QThread separato
per non bloccare la UI.

```python
class AnalysisWorker(QThread):
    """Thread separato per l'analisi OMR."""
    
    progress = Signal(str, int)           # fase_nome, percentuale
    boundary_detected = Signal(object, float, str)  # corners, conf, method
    alignment_done = Signal(object, dict)  # aligned_img, info
    item_result = Signal(str, dict)       # item_id, result_dict
    finished = Signal(dict)               # report completo
    error = Signal(str)                   # messaggio errore
    
    def __init__(self, photo_path, page_key, use_svm, use_omr):
        super().__init__()
        self.photo_path = photo_path
        self.page_key = page_key
        self.use_svm = use_svm
        self.use_omr = use_omr
    
    def run(self):
        try:
            # Fase 1: Boundary detection
            self.progress.emit("Rilevamento bordi...", 10)
            img = cv2.imread(self.photo_path)
            corners, conf, method = detect_document_boundary(img)
            self.boundary_detected.emit(corners, conf, method)
            
            # Fase 2: Warp
            self.progress.emit("Correzione prospettiva...", 25)
            warped = warp_to_a4(img, corners)
            
            # Fase 3: Preprocess
            self.progress.emit("Pre-processing...", 40)
            gray, meta = preprocess_full_pipeline(warped)
            
            # Fase 4: SIFT Alignment
            self.progress.emit("Allineamento template...", 55)
            aligner = TemplateAligner()
            aligner.load_reference(self.page_key)
            aligned, align_info = aligner.align(gray, self.page_key)
            self.alignment_done.emit(aligned, align_info)
            
            # Fase 5: Grid extraction
            self.progress.emit("Estrazione celle...", 70)
            cells = extract_all_cells(aligned, self.page_key)
            
            # Fase 6: Mark reading
            self.progress.emit("Lettura risposte...", 80)
            results = {}
            
            if self.use_omr:
                omr_results = classify_all_items_omr(cells)
                results = omr_results
            
            if self.use_svm:
                classifier = get_classifier()
                if classifier.is_loaded:
                    for item_id, item_cells in cells.items():
                        svm_result = classifier.predict_item_cells(item_cells)
                        if self.use_omr:
                            # Ensemble: media confidence
                            omr_r = results.get(item_id, {})
                            if omr_r.get('value') == svm_result.get('value'):
                                # Concordano → boost confidence
                                svm_result['confidence'] = min(1.0,
                                    (omr_r.get('confidence', 0) + svm_result.get('confidence', 0)) / 2 * 1.3)
                            else:
                                # Discordano → prendi quello con confidence più alta
                                if svm_result.get('confidence', 0) > omr_r.get('confidence', 0):
                                    results[item_id] = svm_result
                                # altrimenti tieni OMR
                        else:
                            results[item_id] = svm_result
                        
                        self.item_result.emit(item_id, results.get(item_id, svm_result))
            
            # Fase 7: Score
            self.progress.emit("Calcolo score...", 95)
            report = build_score_report(results)
            
            self.progress.emit("Completato!", 100)
            self.finished.emit(report)
            
        except Exception as e:
            self.error.emit(str(e))
```

---

## DARK THEME (theme.py)

```python
"""Dark theme per Smart OCR — basato su pyqtdarktheme + custom."""

import qdarktheme
from PySide6.QtGui import QPalette, QColor

def apply_dark_theme(app):
    """Applica dark theme Material-inspired."""
    qdarktheme.setup_theme(
        theme="dark",
        custom_colors={
            "primary": "#818CF8",      # Indaco — accent principale
            "primary>button.hoverBackground": "#6366F1",
        },
        corner_shape="rounded",
    )

# Colori applicazione
COLORS = {
    "bg_primary": "#0F172A",       # Sfondo principale (slate-900)
    "bg_secondary": "#1E293B",     # Sfondo card (slate-800)
    "bg_hover": "#334155",         # Hover (slate-700)
    "text_primary": "#F1F5F9",     # Testo principale (slate-100)
    "text_secondary": "#94A3B8",   # Testo secondario (slate-400)
    "accent": "#818CF8",           # Accent (indigo-400)
    "success": "#4ADE80",          # Verde (green-400)
    "warning": "#FBBF24",          # Giallo (amber-400)
    "error": "#F87171",            # Rosso (red-400)
    "info": "#60A5FA",             # Blu (blue-400)
    "border": "#334155",           # Bordi (slate-700)
}

STYLESHEET_EXTRA = """
QMainWindow {
    background-color: #0F172A;
}

/* Sidebar */
#sidebar {
    background-color: #1E293B;
    border-right: 1px solid #334155;
    min-width: 180px;
    max-width: 180px;
}

#sidebar QPushButton {
    text-align: left;
    padding: 12px 16px;
    border: none;
    border-radius: 8px;
    color: #94A3B8;
    font-size: 13px;
}

#sidebar QPushButton:checked {
    background-color: #1E1B4B;
    color: #818CF8;
    font-weight: bold;
}

/* CBCL Form */
#cbcl_scroll {
    background-color: #0F172A;
}

/* Status bar */
#status_bar {
    background-color: #1E293B;
    border-top: 1px solid #334155;
    padding: 4px 12px;
    color: #94A3B8;
    font-size: 11px;
}

/* Pulsante analizza */
#analyze_btn {
    background-color: #6366F1;
    color: white;
    font-size: 15px;
    font-weight: bold;
    padding: 12px 24px;
    border-radius: 8px;
    border: none;
}

#analyze_btn:hover {
    background-color: #818CF8;
}

#analyze_btn:pressed {
    background-color: #4F46E5;
}
"""
```

---

## ENTRY POINT (main.py)

```python
import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from app.main_window import MainWindow
from app.theme import apply_dark_theme, STYLESHEET_EXTRA

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Smart OCR")
    app.setOrganizationName("SmartOCR")
    
    # Dark theme
    apply_dark_theme(app)
    app.setStyleSheet(app.styleSheet() + STYLESHEET_EXTRA)
    
    # Finestra principale
    window = MainWindow()
    window.setMinimumSize(1200, 800)
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
```

---

## PAGINA RISULTATI (results_page.py)

Dopo che l'utente ha confermato/corretto tutti gli item sulla pagina CBCL,
la pagina risultati mostra:

1. **Score totale** in grande
2. **Tabella subscale** CBCL DSM-oriented con score per subscala
3. **Grafico a barre** delle subscale (QChart o matplotlib embed)
4. **Pulsanti export:** CSV, JSON, PDF report
5. **Riepilogo:** items totali, automatici, corretti manualmente, missing

---

## PACKAGING

### Windows:
```bash
pyinstaller --name "SmartOCR" --onedir --windowed \
  --add-data "templates;templates" \
  --add-data "models;models" \
  --add-data "resources;resources" \
  --collect-all PySide6 \
  --collect-all qdarktheme \
  main.py
```

### macOS:
```bash
pyinstaller --name "SmartOCR" --onedir --windowed \
  --add-data "templates:templates" \
  --add-data "models:models" \
  --add-data "resources:resources" \
  --collect-all PySide6 \
  --collect-all qdarktheme \
  --osx-bundle-identifier "com.smartocr.cbcl" \
  main.py
```

---

## ORDINE IMPLEMENTAZIONE PER CLAUDE CODE

1. `pip install PySide6 pyqtdarktheme` e verifica funzionamento
2. Creare `resources/cbcl_questions_it.json` estraendo testi dal PDF
3. Creare `app/theme.py` con dark theme
4. Creare `app/widgets/cbcl_item_widget.py` (widget singolo item)
5. Creare `app/pages/cbcl_form_page.py` (griglia 2 colonne scrollabile)
6. Creare `app/widgets/photo_viewer.py` (anteprima con bordi gialli)
7. Creare `app/workers/analysis_worker.py` (QThread processing)
8. Creare `app/pages/home_page.py` (upload + analisi)
9. Creare `app/pages/results_page.py` (scores + export)
10. Creare `app/main_window.py` (sidebar + stacked pages)
11. Creare `main.py` (entry point)
12. Integrare tutti i moduli core/ (boundary_detector, template_aligner, ecc.)
13. Test end-to-end su foto reali
14. PyInstaller build

**CRITICO:** I moduli `core/` descritti nel documento v2.1
(boundary_detector.py, template_aligner.py, preprocessor.py aggiornato,
omr_classifier.py aggiornato) devono essere implementati PRIMA della UI.
La UI li chiama attraverso il AnalysisWorker.

---

## NOTA FINALE

Questo documento combina:
- **v2.1**: Pipeline OMR completa (boundary → SIFT → ECC → reading)
- **v3.0**: UI desktop PySide6 con CBCL digitale interattiva

Claude Code deve implementare PRIMA i moduli core (v2.1 steps 1-8),
POI la UI (v3.0). Testare i core modules con uno script CLI prima
di collegare la UI.
