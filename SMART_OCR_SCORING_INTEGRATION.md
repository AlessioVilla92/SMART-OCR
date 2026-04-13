# SMART OCR — Integrazione Modulo Scoring CBCL 6-18

> **Data:** 13 Aprile 2026  
> **Destinatario:** Claude Code  
> **Repo:** github.com/AlessioVilla92/SMART-OCR  
> **Priorità:** ALTA — Questo task sostituisce il scorer attuale con formule verificate

---

## CONTESTO

Il progetto Smart OCR è un software Python/Streamlit per la lettura automatica offline di questionari CBCL 6-18 (Child Behavior Checklist) fotografati con smartphone. Il software elabora le foto con OpenCV, classifica le risposte (0/1/2) con HOG+SVM o YOLOv8n, e poi calcola i punteggi clinici.

Il modulo di scoring attuale (`core/scorer.py` o `scorer/cbcl_scorer.py`) contiene formule **approssimate e incomplete**. Le formule corrette sono state estratte e verificate cella-per-cella dal template Excel ufficiale `CBCL_6-18.xlt` il 13/04/2026.

### Cosa devi fare

1. Sostituire il modulo scorer con il codice verificato fornito in questo documento
2. Integrare lo switch compilatore Madre/Padre nell'UI Streamlit
3. Aggiornare app.py per usare il nuovo scorer
4. Aggiungere la funzione di export verso il template Excel

---

## STRUTTURA ATTUALE DEL PROGETTO

```
smart_ocr/
├── app.py                          # Entry point Streamlit
├── config.py                       # Configurazione globale
├── core/
│   ├── preprocessor.py             # OpenCV preprocessing
│   ├── grid_extractor.py           # Estrazione celle da cbcl_grid.json
│   ├── classifier.py               # HOG + SVM classificazione
│   ├── omr_classifier.py           # Baseline pixel-counting
│   ├── photo_aligner.py            # Allineamento interattivo 4 punti
│   ├── pdf_calibrator.py           # Calibrazione da PDF
│   └── scorer.py                   # ← DA SOSTITUIRE
├── training/
│   ├── augmentor.py
│   ├── cell_generator.py
│   ├── label_tool.py
│   └── train_svm.py
├── templates/
│   └── cbcl_grid.json              # Coordinate celle (mancano 56e-56h)
├── models/
│   ├── svm_classifier.pkl
│   └── training_report.json
└── output/
```

---

## TASK 1: NUOVO MODULO SCORER

### File da creare: `scorer/cbcl_scorer.py`

Se la cartella `scorer/` non esiste, creala con `__init__.py`. Il vecchio `core/scorer.py` va mantenuto come backup (`core/scorer_old.py`) fino a validazione completa.

```python
"""
scorer/cbcl_scorer.py — Smart OCR

Modulo di scoring CBCL 6-18 con le formule VERIFICATE estratte dal
template Excel ufficiale (CBCL_6-18.xlt).

Supporta compilazione Madre (MD) e Padre (PD) come profili indipendenti.

Formule verificate il 13/04/2026:
  - 0 duplicati tra scale sindromiche
  - 120/120 item coperti
  - Formule MD e PD identiche (stessa logica, dati diversi)
"""

from dataclasses import dataclass, field
from typing import Optional, Union
from enum import Enum


# ============================================================
# COMPILATORE (Madre / Padre)
# ============================================================

class Compilatore(Enum):
    MADRE = "MD"
    PADRE = "PD"


# ============================================================
# SCALE SINDROMICHE — 8 scale + Other
# Formule da: CBCL_6-18.xlt, celle F8:F16
# Verificato: 0 overlap, 120/120 item coperti
# ============================================================

SYNDROME_SCALES = {
    "anxious_depressed": {
        "code": "I",
        "label_en": "Anxious/Depressed",
        "label_it": "Ansioso/Depresso",
        "items": [14, 29, 30, 31, 32, 33, 35, 45, 50, 52, 71, 91, 112],
        # Excel: =SUM(B15,B30,B31,B32,B33,B34,B36,B46,B51,B53,B79,B99,B120)
    },
    "withdrawn_depressed": {
        "code": "II",
        "label_en": "Withdrawn/Depressed",
        "label_it": "Ritirato/Depresso",
        "items": [5, 42, 65, 69, 75, 102, 103, 111],
        # Excel: =SUM(B6,B43,B73,B77,B83,B110,B111,B119)
    },
    "somatic_complaints": {
        "code": "III",
        "label_en": "Somatic Complaints",
        "label_it": "Lamentele Somatiche",
        "items": [47, 49, 51, 54, "56a", "56b", "56c", "56d", "56e", "56f", "56g"],
        # Excel: =SUM(B48,B50,B52,B55,B57,B58,B59,B60,B61,B62,B63)
    },
    "social_problems": {
        "code": "IV",
        "label_en": "Social Problems",
        "label_it": "Problemi Sociali",
        "items": [11, 12, 25, 27, 34, 36, 38, 48, 62, 64, 79],
        # Excel: =SUM(B12,B13,B26,B28,B35,B37,B39,B49,B70,B72,B87)
    },
    "thought_problems": {
        "code": "V",
        "label_en": "Thought Problems",
        "label_it": "Problemi del Pensiero",
        "items": [9, 18, 40, 46, 58, 59, 60, 66, 70, 76, 83, 84, 85, 92, 100],
        # Excel: =SUM(B10,B19,B41,B47,B66,B67,B68,B74,B78,B84,B91,B92,B93,B100,B108)
    },
    "attention_problems": {
        "code": "VI",
        "label_en": "Attention Problems",
        "label_it": "Problemi di Attenzione",
        "items": [1, 4, 8, 10, 13, 17, 41, 61, 78, 80],
        # Excel: =SUM(B2,B5,B9,B11,B14,B18,B42,B69,B86,B88)
    },
    "rule_breaking": {
        "code": "VII",
        "label_en": "Rule-Breaking Behavior",
        "label_it": "Comportamento Trasgressivo",
        "items": [2, 26, 28, 39, 43, 63, 67, 72, 73, 81, 82, 90, 96, 99, 101, 105, 106],
        # Excel: =SUM(B3,B27,B29,B40,B44,B71,B75,B80,B81,B89,B90,B98,B104,B107,B109,B113,B114)
    },
    "aggressive_behavior": {
        "code": "VIII",
        "label_en": "Aggressive Behavior",
        "label_it": "Comportamento Aggressivo",
        "items": [3, 16, 19, 20, 21, 22, 23, 37, 57, 68, 86, 87, 88, 89, 94, 95, 97, 104],
        # Excel: =SUM(B4,B17,B20,B21,B22,B23,B24,B38,B65,B76,B94,B95,B96,B97,B102,B103,B105,B112)
    },
}

OTHER_PROBLEMS = {
    "label_en": "Other Problems",
    "label_it": "Problemi Residui",
    "items": [6, 7, 15, 24, 44, 53, 55, "56h", 74, 77, 93, 98, 107, 108, 109, 110, 113],
    # Excel: =SUM(B7,B8,B16,B25,B45,B54,B56,B64,B82,B85,B101,B106,B115,B116,B117,B118,B121)
}


# ============================================================
# SCALE BROADBAND
# Formule da: CBCL_6-18.xlt, celle F27:F30
# ============================================================

BROADBAND_COMPONENTS = {
    "internalizing": {
        "label_en": "Internalizing Problems",
        "label_it": "Problemi Internalizzanti",
        "components": ["anxious_depressed", "withdrawn_depressed", "somatic_complaints"],
        # Excel: =F8+F9+F10  →  32 item, max 64
    },
    "externalizing": {
        "label_en": "Externalizing Problems",
        "label_it": "Problemi Esternalizzanti",
        "components": ["rule_breaking", "aggressive_behavior"],
        # Excel: =F14+F15  →  35 item, max 70
    },
}


# ============================================================
# SCALE DSM-ORIENTED
# Formule da: CBCL_6-18.xlt, celle F19:F24
# Sistema parallelo: un item può stare sia in una scala
# sindromica SIA in una scala DSM (è corretto così)
# ============================================================

DSM_SCALES = {
    "affective_problems": {
        "label_en": "Affective Problems",
        "label_it": "Problemi Affettivi",
        "items": [5, 14, 18, 24, 35, 52, 54, 76, 77, 91, 100, 102, 103],
        # Excel: =SUM(B6,B15,B19,B25,B36,B53,B55,B84,B85,B99,B108,B110,B111)
    },
    "anxiety_problems": {
        "label_en": "Anxiety Problems",
        "label_it": "Problemi d'Ansia",
        "items": [11, 29, 30, 45, 50, 112],
        # Excel: =SUM(B12,B30,B31,B46,B51,B120)
    },
    "somatic_problems_dsm": {
        "label_en": "Somatic Problems (DSM)",
        "label_it": "Problemi Somatici (DSM)",
        "items": ["56a", "56b", "56c", "56d", "56e", "56f", "56g"],
        # Excel: =SUM(B57,B58,B59,B60,B61,B62,B63)
    },
    "adhd_problems": {
        "label_en": "ADHD Problems",
        "label_it": "Problemi ADHD",
        "items": [4, 8, 10, 41, 78, 93, 104],
        # Excel: =SUM(B5,B9,B11,B42,B86,B101,B112)
    },
    "oppositional_problems": {
        "label_en": "Oppositional Defiant Problems",
        "label_it": "Problemi Oppositivo-Provocatori",
        "items": [3, 22, 23, 86, 95],
        # Excel: =SUM(B4,B23,B24,B94,B103)
    },
    "conduct_problems": {
        "label_en": "Conduct Problems",
        "label_it": "Problemi della Condotta",
        "items": [15, 16, 21, 26, 28, 37, 39, 43, 57, 67, 72, 81, 82, 90, 97, 101, 106],
        # Excel: =SUM(B16,B17,B22,B27,B29,B38,B40,B44,B65,B75,B80,B89,B90,B98,B105,B109,B114)
    },
}


# ============================================================
# SOGLIE T-SCORE (dalla letteratura ASEBA)
# ============================================================

T_THRESHOLDS = {
    "syndrome": {   # Per scale sindromiche e DSM-oriented
        "normale_max": 64,      # < 65 = nella norma
        "borderline_min": 65,   # 65-69 = range borderline
        "borderline_max": 69,
        "clinico_min": 70,      # >= 70 = clinicamente significativo
    },
    "broadband": {  # Per Internalizing, Externalizing, Total Problems
        "normale_max": 59,      # < 60 = nella norma
        "borderline_min": 60,   # 60-63 = range borderline
        "borderline_max": 63,
        "clinico_min": 64,      # >= 64 = clinicamente significativo
    },
}


# ============================================================
# LISTA COMPLETA DEI 120 ITEM CBCL
# ============================================================

def all_cbcl_items() -> list:
    """Restituisce i 120 item CBCL nell'ordine corretto."""
    items = list(range(1, 56))  # 1–55
    items += ["56a", "56b", "56c", "56d", "56e", "56f", "56g", "56h"]
    items += list(range(57, 114))  # 57–113
    return items

ALL_ITEMS = all_cbcl_items()


# ============================================================
# MAPPING ITEM → RIGA EXCEL (per export nel template .xlt)
# ============================================================

def item_to_excel_row(item) -> int:
    """Converte item CBCL → riga nel template Excel.
    
    Il mapping NON è banale perché i sub-item 56a-56h occupano
    8 righe extra (57-64), sfalsando tutti gli item successivi di +8.
    
    Esempi:
        item 1  → riga 2   (item + 1)
        item 55 → riga 56  (item + 1)
        56a     → riga 57
        56h     → riga 64
        item 57 → riga 65  (item + 8)
        item 113→ riga 121 (item + 8)
    """
    sub_map = {"56a": 57, "56b": 58, "56c": 59, "56d": 60,
               "56e": 61, "56f": 62, "56g": 63, "56h": 64}
    if isinstance(item, str) and item in sub_map:
        return sub_map[item]
    n = int(item)
    return n + 1 if n <= 55 else n + 8


def excel_col_for_compilatore(compilatore) -> str:
    """Colonna B per Madre, C per Padre (come nel template .xlt)."""
    return "B" if compilatore == Compilatore.MADRE else "C"


# ============================================================
# DATACLASS RISULTATO SINGOLA SCALA
# ============================================================

@dataclass
class ScaleResult:
    key: str
    label_it: str
    label_en: str
    raw_score: int
    max_score: int
    n_items: int
    t_score: Optional[int] = None
    classification: Optional[str] = None  # "normale"/"borderline"/"clinico"
    missing_items: list = field(default_factory=list)

    @property
    def pct(self) -> float:
        """Percentuale del punteggio massimo."""
        return round(self.raw_score / self.max_score * 100, 1) if self.max_score else 0.0


# ============================================================
# DATACLASS PROFILO COMPLETO
# ============================================================

@dataclass
class CBCLProfile:
    """Profilo CBCL completo per un singolo compilatore (MD o PD)."""
    compilatore: Compilatore
    syndrome: dict       # key → ScaleResult
    broadband: dict      # key → ScaleResult
    dsm: dict            # key → ScaleResult
    other: ScaleResult
    total: ScaleResult
    validation: dict

    def to_dict(self) -> dict:
        """Serializza in dizionario per JSON export."""
        def _sr(sr: ScaleResult) -> dict:
            return {
                "label_it": sr.label_it,
                "raw_score": sr.raw_score,
                "max_score": sr.max_score,
                "n_items": sr.n_items,
                "pct": sr.pct,
                "t_score": sr.t_score,
                "classification": sr.classification,
                "missing_items": [str(i) for i in sr.missing_items],
            }
        return {
            "compilatore": self.compilatore.value,
            "syndrome_scales": {k: _sr(v) for k, v in self.syndrome.items()},
            "broadband_scales": {k: _sr(v) for k, v in self.broadband.items()},
            "dsm_scales": {k: _sr(v) for k, v in self.dsm.items()},
            "other_problems": _sr(self.other),
            "total_problems": _sr(self.total),
            "validation": self.validation,
        }

    def summary_table(self) -> list:
        """Lista di tuple (tipo, label, raw, max, pct) per tabelle Streamlit."""
        rows = []
        for sr in self.syndrome.values():
            rows.append(("Sindromica", sr.label_it, sr.raw_score, sr.max_score, sr.pct))
        rows.append(("Sindromica", self.other.label_it, self.other.raw_score, self.other.max_score, self.other.pct))
        for sr in self.broadband.values():
            rows.append(("Broadband", sr.label_it, sr.raw_score, sr.max_score, sr.pct))
        rows.append(("Broadband", self.total.label_it, self.total.raw_score, self.total.max_score, self.total.pct))
        for sr in self.dsm.values():
            rows.append(("DSM", sr.label_it, sr.raw_score, sr.max_score, sr.pct))
        return rows


# ============================================================
# MOTORE DI SCORING
# ============================================================

class CBCLScorer:
    """
    Calcola i punteggi CBCL 6-18 da un dizionario di risposte.
    Le formule sono identiche per Madre e Padre — cambia solo
    il profilo di destinazione e la colonna Excel per l'export.
    """

    def __init__(
        self,
        responses: dict,
        compilatore: Compilatore = Compilatore.MADRE,
        sex: Optional[str] = None,
        age: Optional[int] = None,
    ):
        """
        Args:
            responses: {item_key: 0|1|2}
                       chiave int per item 1-55 e 57-113
                       chiave str per "56a"-"56h"
            compilatore: Compilatore.MADRE o Compilatore.PADRE
            sex: "M" o "F" (per selezione norme T-score, se disponibili)
            age: età del bambino (per selezione norme)
        """
        self.responses = responses
        self.compilatore = compilatore
        self.sex = sex
        self.age = age

    def _sum_items(self, items: list) -> tuple:
        """Somma punteggi. Ritorna (raw_score, lista_item_mancanti)."""
        total = 0
        missing = []
        for item in items:
            val = self.responses.get(item)
            if val is None:
                missing.append(item)
            else:
                total += int(val)
        return total, missing

    def validate(self) -> dict:
        """Verifica completezza e validità delle risposte."""
        expected = set(str(i) for i in ALL_ITEMS)
        provided = set(str(k) for k in self.responses.keys())
        missing = sorted(expected - provided)
        extra = sorted(provided - expected)
        invalid = {str(k): v for k, v in self.responses.items() if v not in (0, 1, 2)}
        n_missing = len(missing)
        return {
            "total_expected": 120,
            "total_provided": 120 - n_missing,
            "n_missing": n_missing,
            "missing_items": missing,
            "extra_items": extra,
            "invalid_values": invalid,
            "is_scorable": n_missing <= 8 and len(invalid) == 0,
            "warning": (
                f"Mancano {n_missing} item — profilo non attendibile"
                if n_missing > 8 else None
            ),
        }

    def compute(self) -> CBCLProfile:
        """Calcola tutti i punteggi e restituisce un CBCLProfile completo."""

        # Scale sindromiche
        syndrome = {}
        for key, scale in SYNDROME_SCALES.items():
            raw, miss = self._sum_items(scale["items"])
            syndrome[key] = ScaleResult(
                key=key, label_it=scale["label_it"], label_en=scale["label_en"],
                raw_score=raw, max_score=len(scale["items"]) * 2,
                n_items=len(scale["items"]), missing_items=miss,
            )

        # Other Problems
        raw_other, miss_other = self._sum_items(OTHER_PROBLEMS["items"])
        other = ScaleResult(
            key="other_problems", label_it=OTHER_PROBLEMS["label_it"],
            label_en=OTHER_PROBLEMS["label_en"], raw_score=raw_other,
            max_score=len(OTHER_PROBLEMS["items"]) * 2,
            n_items=len(OTHER_PROBLEMS["items"]), missing_items=miss_other,
        )

        # Scale broadband
        broadband = {}
        for key, scale in BROADBAND_COMPONENTS.items():
            raw = sum(syndrome[c].raw_score for c in scale["components"])
            n = sum(syndrome[c].n_items for c in scale["components"])
            miss = []
            for c in scale["components"]:
                miss.extend(syndrome[c].missing_items)
            broadband[key] = ScaleResult(
                key=key, label_it=scale["label_it"], label_en=scale["label_en"],
                raw_score=raw, max_score=n * 2, n_items=n, missing_items=miss,
            )

        # Total Problems
        total_raw = sum(self.responses.get(item, 0) for item in ALL_ITEMS)
        total_miss = [item for item in ALL_ITEMS if item not in self.responses]
        total = ScaleResult(
            key="total_problems", label_it="Problemi Totali",
            label_en="Total Problems", raw_score=total_raw,
            max_score=240, n_items=120, missing_items=total_miss,
        )

        # Scale DSM
        dsm = {}
        for key, scale in DSM_SCALES.items():
            raw, miss = self._sum_items(scale["items"])
            dsm[key] = ScaleResult(
                key=key, label_it=scale["label_it"], label_en=scale["label_en"],
                raw_score=raw, max_score=len(scale["items"]) * 2,
                n_items=len(scale["items"]), missing_items=miss,
            )

        return CBCLProfile(
            compilatore=self.compilatore,
            syndrome=syndrome, broadband=broadband,
            dsm=dsm, other=other, total=total,
            validation=self.validate(),
        )

    def to_excel_cells(self) -> dict:
        """
        Genera {cella_excel: valore} per popolare il template .xlt.
        Madre → colonna B, Padre → colonna C.
        """
        col = excel_col_for_compilatore(self.compilatore)
        cells = {}
        for item, value in self.responses.items():
            row = item_to_excel_row(item)
            cells[f"{col}{row}"] = value
        return cells
```

---

## TASK 2: WIDGET STREAMLIT PER SWITCH MD/PD

### File da creare: `scorer/ui_widgets.py`

```python
"""
scorer/ui_widgets.py

Widget Streamlit per:
- Selezione compilatore (Madre/Padre) nella sidebar
- Visualizzazione risultati scoring
- Anagrafica bambino (sesso, età) per norme T-score
"""

import streamlit as st
import pandas as pd
from .cbcl_scorer import (
    CBCLScorer, CBCLProfile, Compilatore,
    SYNDROME_SCALES, DSM_SCALES, T_THRESHOLDS
)


def sidebar_compilatore() -> Compilatore:
    """
    Widget sidebar per selezionare chi ha compilato il questionario.
    Restituisce Compilatore.MADRE o Compilatore.PADRE.
    
    Inserire in app.py dentro il blocco sidebar:
        compilatore = sidebar_compilatore()
    """
    st.sidebar.markdown("---")
    st.sidebar.subheader("👤 Compilatore")
    
    scelta = st.sidebar.radio(
        "Questionario compilato da:",
        options=["Madre (MD)", "Padre (PD)"],
        index=0,
        help="I punteggi vengono calcolati con le stesse formule "
             "ma salvati su profili separati per il confronto clinico.",
    )
    
    compilatore = Compilatore.MADRE if "Madre" in scelta else Compilatore.PADRE
    
    emoji = "👩" if compilatore == Compilatore.MADRE else "👨"
    st.sidebar.info(f"{emoji} Profilo attivo: **{compilatore.value}**")
    
    return compilatore


def sidebar_anagrafica() -> tuple:
    """
    Widget sidebar per sesso e età del bambino.
    Necessari per selezionare il gruppo normativo T-score corretto.
    
    Restituisce (sex: str, age: int) o (None, None) se non compilati.
    
    Inserire in app.py dentro il blocco sidebar:
        sex, age = sidebar_anagrafica()
    """
    st.sidebar.markdown("---")
    st.sidebar.subheader("👶 Anagrafica bambino")
    
    sex = st.sidebar.radio(
        "Sesso:",
        options=["Maschio", "Femmina"],
        index=0,
        horizontal=True,
    )
    sex_code = "M" if sex == "Maschio" else "F"
    
    age = st.sidebar.number_input(
        "Età (anni):",
        min_value=6, max_value=18, value=10, step=1,
        help="Fascia 6-11 o 12-18 per le norme T-score",
    )
    
    fascia = "6-11" if age <= 11 else "12-18"
    st.sidebar.caption(f"Gruppo normativo: {sex_code} {fascia}")
    
    return sex_code, age


def show_results(profile: CBCLProfile):
    """
    Widget pagina principale per visualizzare i risultati.
    
    Inserire in app.py nella sezione risultati:
        profile = scorer.compute()
        show_results(profile)
    """
    emoji = "👩" if profile.compilatore == Compilatore.MADRE else "👨"
    st.header(f"{emoji} Risultati — {profile.compilatore.value}")
    
    # Validazione
    v = profile.validation
    if not v["is_scorable"]:
        st.error(f"⚠️ {v['warning']}")
    elif v["n_missing"] > 0:
        items_str = ", ".join(v["missing_items"][:10])
        st.warning(f"⚡ {v['n_missing']} item mancanti: {items_str}...")
    else:
        st.success(f"✅ Tutti i 120 item rilevati")
    
    # Metriche broadband
    col1, col2, col3 = st.columns(3)
    with col1:
        r = profile.broadband["internalizing"]
        st.metric("Internalizing", f"{r.raw_score}/{r.max_score}", f"{r.pct}%")
    with col2:
        r = profile.broadband["externalizing"]
        st.metric("Externalizing", f"{r.raw_score}/{r.max_score}", f"{r.pct}%")
    with col3:
        st.metric("Total Problems", f"{profile.total.raw_score}/{profile.total.max_score}", f"{profile.total.pct}%")
    
    # Tabella scale sindromiche
    st.subheader("📊 Scale Sindromiche")
    rows_syn = []
    for key, sr in profile.syndrome.items():
        code = SYNDROME_SCALES[key]["code"]
        rows_syn.append({
            "Scala": f"{code} — {sr.label_it}",
            "Raw": sr.raw_score,
            "Max": sr.max_score,
            "%": sr.pct,
            "Missing": len(sr.missing_items),
        })
    df_syn = pd.DataFrame(rows_syn)
    st.dataframe(df_syn, use_container_width=True, hide_index=True)
    
    # Tabella scale DSM
    st.subheader("🏥 Scale DSM-Oriented")
    rows_dsm = []
    for key, sr in profile.dsm.items():
        rows_dsm.append({
            "Scala": sr.label_it,
            "Raw": sr.raw_score,
            "Max": sr.max_score,
            "%": sr.pct,
            "Missing": len(sr.missing_items),
        })
    df_dsm = pd.DataFrame(rows_dsm)
    st.dataframe(df_dsm, use_container_width=True, hide_index=True)


def show_export_buttons(profile: CBCLProfile, session_id: str = ""):
    """
    Pulsanti di download per JSON e CSV.
    
    Inserire in app.py dopo show_results():
        show_export_buttons(profile, session_id="20260413_001")
    """
    import json
    from datetime import datetime
    
    ts = session_id or datetime.now().strftime("%Y%m%d_%H%M%S")
    comp = profile.compilatore.value
    
    col1, col2 = st.columns(2)
    
    with col1:
        json_data = json.dumps(profile.to_dict(), indent=2, ensure_ascii=False)
        st.download_button(
            "📥 Scarica JSON",
            data=json_data,
            file_name=f"cbcl_{comp}_{ts}.json",
            mime="application/json",
        )
    
    with col2:
        rows = profile.summary_table()
        df = pd.DataFrame(rows, columns=["Tipo", "Scala", "Raw", "Max", "%"])
        csv_data = df.to_csv(index=False)
        st.download_button(
            "📥 Scarica CSV",
            data=csv_data,
            file_name=f"cbcl_{comp}_{ts}.csv",
            mime="text/csv",
        )
```

---

## TASK 3: AGGIORNARE app.py

### Modifiche da applicare a `app.py`

Trova la sezione sidebar e aggiungi i widget. Trova la sezione dove vengono mostrati i risultati della classificazione e aggiungi il calcolo scoring.

```python
# === AGGIUNTE IN TESTA AL FILE ===
# Aggiungere agli import:
from scorer.cbcl_scorer import CBCLScorer, Compilatore, ALL_ITEMS
from scorer.ui_widgets import (
    sidebar_compilatore, sidebar_anagrafica,
    show_results, show_export_buttons,
)


# === AGGIUNTE NELLA SIDEBAR (dopo le impostazioni esistenti) ===
# Inserire dopo gli altri widget sidebar:
compilatore = sidebar_compilatore()
sex, age = sidebar_anagrafica()


# === AGGIUNTE DOPO LA CLASSIFICAZIONE OCR ===
# Dopo che la pipeline ha prodotto classification_results (dict {item: 0/1/2}),
# aggiungere:

# Adatta il formato delle risposte se necessario
# Il classificatore potrebbe restituire {"1": {"value": 0, "confidence": 0.95}, ...}
# oppure {1: 0, 2: 1, ...} — normalizza qui:
responses = {}
for item_key, result in classification_results.items():
    if isinstance(result, dict):
        val = result.get("value")
    else:
        val = result
    if val is not None:
        # Normalizza la chiave: int per numeri, str per 56a-56h
        try:
            k = int(item_key)
        except (ValueError, TypeError):
            k = str(item_key)
        responses[k] = int(val)

# Calcola i punteggi
scorer = CBCLScorer(
    responses=responses,
    compilatore=compilatore,
    sex=sex,
    age=age,
)
profile = scorer.compute()

# Mostra risultati
show_results(profile)
show_export_buttons(profile)
```

---

## TASK 4: EXPORT VERSO TEMPLATE EXCEL

### File da creare: `scorer/excel_export.py`

Questo modulo prende le risposte OCR e le scrive nelle celle corrette del template `.xlt`, così il clinico può aprirlo in Excel e avere le formule già calcolate.

```python
"""
scorer/excel_export.py

Popola il template Excel CBCL_6-18.xlt con le risposte OCR.
Le formule già presenti nel template calcolano automaticamente
i punteggi sindromici, broadband e DSM.
"""

import shutil
from pathlib import Path
from openpyxl import load_workbook
from .cbcl_scorer import CBCLScorer, Compilatore, item_to_excel_row, ALL_ITEMS


def export_to_excel(
    responses: dict,
    compilatore: Compilatore,
    template_path: str = "templates/CBCL_6-18.xlt",
    output_path: str = None,
    child_name: str = "",
    child_dob: str = "",
    test_date: str = "",
) -> str:
    """
    Copia il template e lo popola con le risposte OCR.
    
    Args:
        responses: {item: 0/1/2} — risposte OCR
        compilatore: MADRE o PADRE
        template_path: percorso del template .xlt
        output_path: percorso output (auto-generato se None)
        child_name: nome del bambino (opzionale, per cella E3)
        child_dob: data nascita (opzionale, per cella E4)
        test_date: data test (opzionale, per cella E5)
    
    Returns:
        Percorso del file Excel generato.
    """
    from datetime import datetime
    
    template = Path(template_path)
    if not template.exists():
        raise FileNotFoundError(f"Template non trovato: {template_path}")
    
    if output_path is None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        comp = compilatore.value
        output_path = f"output/CBCL_{comp}_{ts}.xlsx"
    
    # Copia template
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(template, out)
    
    # Apri e popola
    wb = load_workbook(str(out))
    ws = wb["Foglio1"]
    
    # Colonna dati: B per Madre, C per Padre
    col_idx = 2 if compilatore == Compilatore.MADRE else 3
    
    # Scrivi risposte
    for item in ALL_ITEMS:
        val = responses.get(item)
        if val is not None:
            row = item_to_excel_row(item)
            ws.cell(row=row, column=col_idx, value=int(val))
    
    # Scrivi metadati (opzionali)
    if child_name:
        ws["E3"] = child_name
    if child_dob:
        ws["E4"] = child_dob
    if test_date:
        ws["E5"] = test_date
    
    wb.save(str(out))
    return str(out)
```

---

## TASK 5: AGGIORNARE cbcl_grid.json

Il template attuale manca dei sub-item **56e, 56f, 56g, 56h**. Questi sono necessari per il calcolo corretto delle scale Somatic Complaints (III) e Other Problems.

### Azione richiesta

Apri `templates/cbcl_grid.json` e aggiungi le coordinate per gli item mancanti. Sono nella stessa pagina degli altri sub-item 56 (pagina 5 del questionario, `page_5` nel JSON). La struttura di ogni item è:

```json
"56e": {
    "row_y": <coordinata_y_relativa>,
    "cells": {
        "0": {"x": <x_centro_cella_0>, "width": <larghezza>},
        "1": {"x": <x_centro_cella_1>, "width": <larghezza>},
        "2": {"x": <x_centro_cella_2>, "width": <larghezza>}
    }
}
```

Le coordinate y si ricavano dal pattern degli altri sub-item 56a-56d già presenti. I sub-item sono equidistanziati verticalmente. Calcola lo spacing e prosegui la sequenza.

---

## TASK 6: FILE `scorer/__init__.py`

```python
"""
Modulo scoring CBCL 6-18 per Smart OCR.

Uso:
    from scorer.cbcl_scorer import CBCLScorer, Compilatore
    from scorer.ui_widgets import sidebar_compilatore, show_results
"""

from .cbcl_scorer import (
    CBCLScorer,
    CBCLProfile,
    Compilatore,
    ScaleResult,
    ALL_ITEMS,
    SYNDROME_SCALES,
    DSM_SCALES,
    BROADBAND_COMPONENTS,
    OTHER_PROBLEMS,
    T_THRESHOLDS,
    all_cbcl_items,
    item_to_excel_row,
)
```

---

## TASK 7: TEST DEL NUOVO SCORER

### File da creare: `tests/test_scorer.py`

```python
"""
tests/test_scorer.py

Test di verifica per il modulo scoring CBCL.
Verifica che le formule producano risultati corretti
e che il conteggio item sia completo.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scorer.cbcl_scorer import (
    CBCLScorer, Compilatore, ALL_ITEMS,
    SYNDROME_SCALES, DSM_SCALES, BROADBAND_COMPONENTS, OTHER_PROBLEMS,
    item_to_excel_row,
)


def test_item_coverage():
    """Verifica che tutti i 120 item siano coperti dalle scale sindromiche."""
    all_in_scales = set()
    for scale in SYNDROME_SCALES.values():
        for item in scale["items"]:
            all_in_scales.add(str(item))
    for item in OTHER_PROBLEMS["items"]:
        all_in_scales.add(str(item))
    
    expected = set(str(i) for i in ALL_ITEMS)
    assert all_in_scales == expected, f"Mancanti: {expected - all_in_scales}, Extra: {all_in_scales - expected}"
    print("✓ test_item_coverage: 120/120 item coperti")


def test_no_duplicates():
    """Verifica che nessun item appaia in più di una scala sindromica."""
    seen = {}
    for scale_key, scale in SYNDROME_SCALES.items():
        for item in scale["items"]:
            s = str(item)
            assert s not in seen, f"Item {s} duplicato: {seen[s]} e {scale_key}"
            seen[s] = scale_key
    for item in OTHER_PROBLEMS["items"]:
        s = str(item)
        assert s not in seen, f"Item {s} duplicato: {seen[s]} e Other"
        seen[s] = "Other"
    print("✓ test_no_duplicates: 0 duplicati")


def test_item_counts():
    """Verifica il numero di item per scala."""
    expected = {
        "anxious_depressed": 13,
        "withdrawn_depressed": 8,
        "somatic_complaints": 11,
        "social_problems": 11,
        "thought_problems": 15,
        "attention_problems": 10,
        "rule_breaking": 17,
        "aggressive_behavior": 18,
    }
    for key, count in expected.items():
        actual = len(SYNDROME_SCALES[key]["items"])
        assert actual == count, f"{key}: attesi {count}, trovati {actual}"
    assert len(OTHER_PROBLEMS["items"]) == 17
    print("✓ test_item_counts: conteggi corretti")


def test_broadband_sums():
    """Verifica la composizione delle scale broadband."""
    # Internalizing = I + II + III = 13 + 8 + 11 = 32 item
    int_items = sum(len(SYNDROME_SCALES[c]["items"]) for c in BROADBAND_COMPONENTS["internalizing"]["components"])
    assert int_items == 32, f"Internalizing: {int_items} != 32"
    
    # Externalizing = VII + VIII = 17 + 18 = 35 item
    ext_items = sum(len(SYNDROME_SCALES[c]["items"]) for c in BROADBAND_COMPONENTS["externalizing"]["components"])
    assert ext_items == 35, f"Externalizing: {ext_items} != 35"
    
    # Total = 120
    assert int_items + ext_items + 11 + 15 + 10 + 17 == 120  # +IV+V+VI+Other
    print("✓ test_broadband_sums: composizione corretta")


def test_scoring_all_zeros():
    """Con tutte risposte 0, tutti i punteggi devono essere 0."""
    responses = {item: 0 for item in ALL_ITEMS}
    scorer = CBCLScorer(responses, compilatore=Compilatore.MADRE)
    profile = scorer.compute()
    
    assert profile.total.raw_score == 0
    for sr in profile.syndrome.values():
        assert sr.raw_score == 0
    for sr in profile.broadband.values():
        assert sr.raw_score == 0
    print("✓ test_scoring_all_zeros: tutti 0 → score 0")


def test_scoring_all_twos():
    """Con tutte risposte 2, i punteggi devono essere al massimo."""
    responses = {item: 2 for item in ALL_ITEMS}
    scorer = CBCLScorer(responses, compilatore=Compilatore.PADRE)
    profile = scorer.compute()
    
    assert profile.total.raw_score == 240
    assert profile.broadband["internalizing"].raw_score == 64
    assert profile.broadband["externalizing"].raw_score == 70
    for sr in profile.syndrome.values():
        assert sr.raw_score == sr.max_score
    print("✓ test_scoring_all_twos: tutti 2 → score max")


def test_md_pd_same_formulas():
    """MD e PD con stesse risposte producono stessi punteggi grezzi."""
    responses = {item: (hash(str(item)) % 3) for item in ALL_ITEMS}
    
    profile_md = CBCLScorer(responses, compilatore=Compilatore.MADRE).compute()
    profile_pd = CBCLScorer(responses, compilatore=Compilatore.PADRE).compute()
    
    assert profile_md.total.raw_score == profile_pd.total.raw_score
    for key in SYNDROME_SCALES:
        assert profile_md.syndrome[key].raw_score == profile_pd.syndrome[key].raw_score
    assert profile_md.compilatore != profile_pd.compilatore
    print("✓ test_md_pd_same_formulas: stesse risposte → stessi raw score")


def test_excel_column_mapping():
    """Madre usa colonna B, Padre usa colonna C."""
    responses = {1: 2, "56a": 1}
    
    cells_md = CBCLScorer(responses, compilatore=Compilatore.MADRE).to_excel_cells()
    cells_pd = CBCLScorer(responses, compilatore=Compilatore.PADRE).to_excel_cells()
    
    assert "B2" in cells_md   # item 1 → riga 2, colonna B
    assert "B57" in cells_md  # 56a → riga 57, colonna B
    assert "C2" in cells_pd   # item 1 → riga 2, colonna C
    assert "C57" in cells_pd  # 56a → riga 57, colonna C
    print("✓ test_excel_column_mapping: B per MD, C per PD")


def test_excel_row_mapping():
    """Verifica il mapping item → riga Excel (caso critico: offset +8)."""
    assert item_to_excel_row(1) == 2
    assert item_to_excel_row(55) == 56
    assert item_to_excel_row("56a") == 57
    assert item_to_excel_row("56h") == 64
    assert item_to_excel_row(57) == 65
    assert item_to_excel_row(113) == 121
    print("✓ test_excel_row_mapping: offset +8 post-56h corretto")


def test_validation_missing_items():
    """Verifica che la validazione segnali gli item mancanti."""
    responses = {item: 0 for item in ALL_ITEMS[:100]}  # solo 100 su 120
    scorer = CBCLScorer(responses)
    v = scorer.validate()
    
    assert v["n_missing"] == 20
    assert not v["is_scorable"]  # > 8 mancanti
    print("✓ test_validation_missing_items: segnala 20 mancanti")


if __name__ == "__main__":
    test_item_coverage()
    test_no_duplicates()
    test_item_counts()
    test_broadband_sums()
    test_scoring_all_zeros()
    test_scoring_all_twos()
    test_md_pd_same_formulas()
    test_excel_column_mapping()
    test_excel_row_mapping()
    test_validation_missing_items()
    print("\n" + "=" * 50)
    print("TUTTI I TEST SUPERATI ✓")
    print("=" * 50)
```

---

## RIEPILOGO CHECKLIST PER CLAUDE CODE

Esegui i task nell'ordine indicato e spunta ogni passaggio:

- [ ] **Task 1**: Creare `scorer/cbcl_scorer.py` con il codice fornito
- [ ] **Task 2**: Creare `scorer/ui_widgets.py` con i widget Streamlit
- [ ] **Task 3**: Aggiornare `app.py` con import e integrazione scorer + switch MD/PD
- [ ] **Task 4**: Creare `scorer/excel_export.py` per export nel template .xlt
- [ ] **Task 5**: Aggiornare `cbcl_grid.json` aggiungendo item 56e, 56f, 56g, 56h
- [ ] **Task 6**: Creare `scorer/__init__.py`
- [ ] **Task 7**: Creare `tests/test_scorer.py` ed eseguire tutti i test
- [ ] **Backup**: Rinominare il vecchio `core/scorer.py` in `core/scorer_old.py`
- [ ] **Dipendenza**: Assicurarsi che `openpyxl` sia nel `requirements.txt` (serve per l'export Excel)
- [ ] **Verifica finale**: Avviare `streamlit run app.py` e confermare che lo switch MD/PD è visibile nella sidebar

### Errori da NON fare

1. NON modificare le liste di item nelle formule — sono state verificate cella-per-cella dal template Excel
2. NON confondere il sistema sindromico con il sistema DSM — sono due sistemi paralleli, gli item possono apparire in entrambi
3. NON dimenticare che l'item 56 ha 8 sub-item (56a-56h) che sfalsano di +8 tutte le righe Excel successive
4. NON mettere i dati del paziente nei log — il logger deve essere anonimizzato

---

## APPENDICE: TABELLA COMPLETA ITEM → SCALA

Per riferimento rapido durante il debug. Ogni riga mostra a quale scala sindromica appartiene l'item.

```
Item  Scala sindromica             | Item  Scala sindromica
───── ─────────────────────────────┼───── ─────────────────────────────
1     VI  Attention Problems       | 57    VIII Aggressive Behavior
2     VII Rule-Breaking            | 58    V    Thought Problems
3     VIII Aggressive Behavior     | 59    V    Thought Problems
4     VI  Attention Problems       | 60    V    Thought Problems
5     II  Withdrawn/Depressed      | 61    VI   Attention Problems
6     Other                        | 62    IV   Social Problems
7     Other                        | 63    VII  Rule-Breaking
8     VI  Attention Problems       | 64    IV   Social Problems
9     V   Thought Problems         | 65    II   Withdrawn/Depressed
10    VI  Attention Problems       | 66    V    Thought Problems
11    IV  Social Problems          | 67    VII  Rule-Breaking
12    IV  Social Problems          | 68    VIII Aggressive Behavior
13    VI  Attention Problems       | 69    II   Withdrawn/Depressed
14    I   Anxious/Depressed        | 70    V    Thought Problems
15    Other                        | 71    I    Anxious/Depressed
16    VIII Aggressive Behavior     | 72    VII  Rule-Breaking
17    VI  Attention Problems       | 73    VII  Rule-Breaking
18    V   Thought Problems         | 74    Other
19    VIII Aggressive Behavior     | 75    II   Withdrawn/Depressed
20    VIII Aggressive Behavior     | 76    V    Thought Problems
21    VIII Aggressive Behavior     | 77    Other
22    VIII Aggressive Behavior     | 78    VI   Attention Problems
23    VIII Aggressive Behavior     | 79    IV   Social Problems
24    Other                        | 80    VI   Attention Problems
25    IV  Social Problems          | 81    VII  Rule-Breaking
26    VII Rule-Breaking            | 82    VII  Rule-Breaking
27    IV  Social Problems          | 83    V    Thought Problems
28    VII Rule-Breaking            | 84    V    Thought Problems
29    I   Anxious/Depressed        | 85    V    Thought Problems
30    I   Anxious/Depressed        | 86    VIII Aggressive Behavior
31    I   Anxious/Depressed        | 87    VIII Aggressive Behavior
32    I   Anxious/Depressed        | 88    VIII Aggressive Behavior
33    I   Anxious/Depressed        | 89    VIII Aggressive Behavior
34    IV  Social Problems          | 90    VII  Rule-Breaking
35    I   Anxious/Depressed        | 91    I    Anxious/Depressed
36    IV  Social Problems          | 92    V    Thought Problems
37    VIII Aggressive Behavior     | 93    Other
38    IV  Social Problems          | 94    VIII Aggressive Behavior
39    VII Rule-Breaking            | 95    VIII Aggressive Behavior
40    V   Thought Problems         | 96    VII  Rule-Breaking
41    VI  Attention Problems       | 97    VIII Aggressive Behavior
42    II  Withdrawn/Depressed      | 98    Other
43    VII Rule-Breaking            | 99    VII  Rule-Breaking
44    Other                        | 100   V    Thought Problems
45    I   Anxious/Depressed        | 101   VII  Rule-Breaking
46    V   Thought Problems         | 102   II   Withdrawn/Depressed
47    III Somatic Complaints       | 103   II   Withdrawn/Depressed
48    IV  Social Problems          | 104   VIII Aggressive Behavior
49    III Somatic Complaints       | 105   VII  Rule-Breaking
50    I   Anxious/Depressed        | 106   VII  Rule-Breaking
51    III Somatic Complaints       | 107   Other
52    I   Anxious/Depressed        | 108   Other
53    Other                        | 109   Other
54    III Somatic Complaints       | 110   Other
55    Other                        | 111   II   Withdrawn/Depressed
56a   III Somatic Complaints       | 112   I    Anxious/Depressed
56b   III Somatic Complaints       | 113   Other
56c   III Somatic Complaints       |
56d   III Somatic Complaints       |
56e   III Somatic Complaints       |
56f   III Somatic Complaints       |
56g   III Somatic Complaints       |
56h   Other                        |
```

---

*Fine documento — CBCL Scoring Integration Guide v2.0*
