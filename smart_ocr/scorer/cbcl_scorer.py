"""
scorer/cbcl_scorer.py — Smart OCR

Modulo di scoring CBCL 6-18 con le formule VERIFICATE estratte dal
template Excel ufficiale (CBCL_6-18.xlt).

Supporta compilazione Madre (MD) e Padre (PD) come profili indipendenti.

Formule verificate il 13/04/2026:
  - 0 duplicati tra scale sindromiche
  - 122/122 item coperti (120 standard + 113a/b/c)
  - Formule MD e PD identiche (stessa logica, dati diversi)
"""

from dataclasses import dataclass, field
from typing import Optional
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
# Verificato: 0 overlap, 122/122 item coperti
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
    "items": [6, 7, 15, 24, 44, 53, 55, "56h", 74, 77, 93, 98, 107, 108, 109, 110,
              "113a", "113b", "113c"],
    # Excel: =SUM(B7,B8,B16,B25,B45,B54,B56,B64,B82,B85,B101,B106,B115,B116,B117,B118,B122,B123,B124)
    # Item 113 decomposto in 113a/b/c (come 56 in 56a-56h)
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
        # Excel: =F8+F9+F10  ->  32 item, max 64
    },
    "externalizing": {
        "label_en": "Externalizing Problems",
        "label_it": "Problemi Esternalizzanti",
        "components": ["rule_breaking", "aggressive_behavior"],
        # Excel: =F14+F15  ->  35 item, max 70
    },
}


# ============================================================
# SCALE DSM-ORIENTED
# Formule da: CBCL_6-18.xlt, celle F19:F24
# Sistema parallelo: un item puo' stare sia in una scala
# sindromica SIA in una scala DSM (e' corretto cosi')
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
# LISTA COMPLETA DEI 122 ITEM CBCL
# ============================================================

def all_cbcl_items() -> list:
    """Restituisce i 122 item CBCL nell'ordine corretto.

    Item 56 e 113 sono decomposti nei rispettivi sub-item:
    56 -> 56a-56h, 113 -> 113a-113c.
    """
    items = list(range(1, 56))  # 1-55
    items += ["56a", "56b", "56c", "56d", "56e", "56f", "56g", "56h"]
    items += list(range(57, 113))  # 57-112
    items += ["113a", "113b", "113c"]
    return items

ALL_ITEMS = all_cbcl_items()


# ============================================================
# MAPPING ITEM -> RIGA EXCEL (per export nel template .xlt)
# ============================================================

def item_to_excel_row(item) -> int:
    """Converte item CBCL -> riga nel template Excel.

    Il mapping NON e' banale perche' i sub-item 56a-56h occupano
    8 righe extra (57-64), sfalsando tutti gli item successivi di +8.
    I sub-item 113a-113c occupano le righe 122-124.

    Esempi:
        item 1  -> riga 2   (item + 1)
        item 55 -> riga 56  (item + 1)
        56a     -> riga 57
        56h     -> riga 64
        item 57 -> riga 65  (item + 8)
        item 112-> riga 120 (item + 8)
        113a    -> riga 121
        113b    -> riga 122
        113c    -> riga 123
    """
    sub_map = {
        "56a": 57, "56b": 58, "56c": 59, "56d": 60,
        "56e": 61, "56f": 62, "56g": 63, "56h": 64,
        "113a": 121, "113b": 122, "113c": 123,
    }
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
    syndrome: dict       # key -> ScaleResult
    broadband: dict      # key -> ScaleResult
    dsm: dict            # key -> ScaleResult
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
        """Lista di tuple (tipo, label, raw, max, pct) per tabelle UI."""
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
                       chiave str per "56a"-"56h", "113a"-"113c"
            compilatore: Compilatore.MADRE o Compilatore.PADRE
            sex: "M" o "F" (per selezione norme T-score, se disponibili)
            age: eta' del bambino (per selezione norme)
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
        """Verifica completezza e validita' delle risposte."""
        expected = set(str(i) for i in ALL_ITEMS)
        provided = set(str(k) for k in self.responses.keys())
        missing = sorted(expected - provided)
        extra = sorted(provided - expected)
        invalid = {str(k): v for k, v in self.responses.items() if v not in (0, 1, 2)}
        n_missing = len(missing)
        return {
            "total_expected": 122,
            "total_provided": 122 - n_missing,
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
            max_score=244, n_items=122, missing_items=total_miss,
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
        Madre -> colonna B, Padre -> colonna C.
        """
        col = excel_col_for_compilatore(self.compilatore)
        cells = {}
        for item, value in self.responses.items():
            row = item_to_excel_row(item)
            cells[f"{col}{row}"] = value
        return cells
