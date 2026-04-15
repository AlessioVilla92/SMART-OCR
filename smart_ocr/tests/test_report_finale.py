"""
test_report_finale.py — Verifica la sezione REPORT FINALE
(aree critiche con risposte = 2, raggruppate per scala).
"""

import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scorer.cbcl_scorer import Compilatore, ALL_ITEMS
from scorer.scale_colors import (
    SCALE_COLORS, ITEM_TO_SCALE, SYNDROME_ORDER,
    build_report_finale, load_italian_questions,
)
from core.scorer import ALL_ITEMS as ALL_STR, build_score_report, report_to_csv, report_to_json

PASS = 0
FAIL = 0

def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  [OK]  {name}")
    else:
        FAIL += 1
        print(f"  [!!]  {name}  -->  {detail}")


print("=" * 70)
print("TEST REPORT FINALE — Aree Critiche (risposte = 2)")
print("=" * 70)

# ─── 1. Palette colori e mapping ────────────────────────────────────
print("\n--- 1. PALETTE COLORI E MAPPING ITEM->SCALA ---")

check("9 scale colorate (8 sindromiche + Other)",
      len(SCALE_COLORS) == 9)
check("ITEM_TO_SCALE copre tutti i 122 item",
      len(ITEM_TO_SCALE) == 122)

# Ogni scala ha i campi richiesti
for key, info in SCALE_COLORS.items():
    check(f"  {key}: ha code/label/bg/dark",
          all(k in info for k in ("code", "label", "bg", "dark")))

# ─── 2. Caricamento domande IT ──────────────────────────────────────
print("\n--- 2. DOMANDE ITALIANE ---")
qs = load_italian_questions()
check("122 domande italiane caricate", len(qs) >= 120, f"caricate {len(qs)}")
check("Item 1 ha testo", bool(qs.get("1")))
check("Item 112 ha testo", bool(qs.get("112")))

# ─── 3. Build report_finale (caso completo) ─────────────────────────
print("\n--- 3. BUILD REPORT FINALE (risposte=2 sparse) ---")

critical_items = {
    "attention_problems": ["1", "4", "17", "78"],   # 4 su 10
    "aggressive_behavior": ["19", "21", "94"],       # 3 su 18
    "anxious_depressed": ["50", "52"],               # 2 su 13
    "rule_breaking": ["101"],                        # 1 su 17
}
flat_critical = [i for items in critical_items.values() for i in items]

cls = {}
for item in ALL_STR:
    if item in flat_critical:
        cls[item] = {"value": 2, "confidence": 0.95}
    elif hash(item) % 3 == 0:
        cls[item] = {"value": 1, "confidence": 0.9}
    else:
        cls[item] = {"value": 0, "confidence": 0.92}

report = build_score_report(cls, session_id="t1", compilatore=Compilatore.MADRE)
rf = build_report_finale(report)

check(f"Totale risposte critiche = 10", rf["total_critical"] == 10,
      f"got {rf['total_critical']}")
check(f"4 aree critiche identificate", len(rf["critical_areas"]) == 4,
      f"got {len(rf['critical_areas'])}")
check(f"5 aree senza critiche (9 - 4)",
      len(rf["areas_without_critical"]) == 5,
      f"got {len(rf['areas_without_critical'])}")

# Ogni area critica ha i campi richiesti
for area in rf["critical_areas"]:
    check(f"  Area {area['code']} {area['label']}: n_critical={area['n_critical']}, n_total={area['n_total']}",
          area["n_critical"] > 0 and area["n_total"] > 0)
    check(f"  Area {area['code']}: items hanno id+text",
          all("id" in it and "text" in it for it in area["items"]))
    check(f"  Area {area['code']}: colori dark+bg presenti",
          area["color_dark"] and area["color_bg"])

# Ordine: scale sindromiche prima, Other dopo
codes_found = [a["code"] for a in rf["critical_areas"]]
expected_order = ["I", "VI", "VII", "VIII"]  # da SYNDROME_ORDER
check(f"Ordine aree corretto: {codes_found}", codes_found == expected_order)

# ─── 4. Caso: nessuna risposta = 2 ──────────────────────────────────
print("\n--- 4. CASO: nessuna risposta = 2 ---")

cls_no_crit = {item: {"value": 1, "confidence": 0.9} for item in ALL_STR}
report_no_crit = build_score_report(cls_no_crit, session_id="t2")
rf_no = build_report_finale(report_no_crit)

check("Nessuna critica: total_critical = 0", rf_no["total_critical"] == 0)
check("Nessuna critica: critical_areas vuoto", len(rf_no["critical_areas"]) == 0)
check("Nessuna critica: tutte 9 aree senza critiche",
      len(rf_no["areas_without_critical"]) == 9)

# ─── 5. Caso: TUTTE risposte = 2 ────────────────────────────────────
print("\n--- 5. CASO: tutte le risposte = 2 ---")

cls_all = {item: {"value": 2, "confidence": 0.95} for item in ALL_STR}
report_all = build_score_report(cls_all, session_id="t3")
rf_all = build_report_finale(report_all)

check(f"Tutte 2: total_critical = 122", rf_all["total_critical"] == 122,
      f"got {rf_all['total_critical']}")
check("Tutte 2: tutte 9 aree hanno critiche",
      len(rf_all["critical_areas"]) == 9)
check("Tutte 2: 0 aree senza critiche",
      len(rf_all["areas_without_critical"]) == 0)

# ─── 6. JSON export include report_finale ───────────────────────────
print("\n--- 6. JSON EXPORT ---")

json_out = report_to_json(report)
j = json.loads(json_out)
check("JSON: chiave 'report_finale' presente", "report_finale" in j)
check("JSON: total_critical corretto",
      j["report_finale"]["total_critical"] == 10)
check("JSON: aree critiche serializzate",
      len(j["report_finale"]["critical_areas"]) == 4)

# ─── 7. CSV export include sezione REPORT FINALE ────────────────────
print("\n--- 7. CSV EXPORT ---")

csv_out = report_to_csv(report)
check("CSV: sezione TOTALE presente", "TOTALE" in csv_out)
check("CSV: NON include colonna 'Max' nella TOTALE",
      "Max" not in csv_out.split("TOTALE")[1].split("RISPOSTE")[0])
check("CSV: sezione REPORT FINALE presente",
      "REPORT FINALE" in csv_out)
check("CSV: colonna Domanda presente", "Domanda" in csv_out)
check("CSV: item 50 (critico) presente", ";50;" in csv_out)
check("CSV: sezione AREE SENZA CRITICHE presente",
      "AREE SENZA RISPOSTE CRITICHE" in csv_out)

# ─── 8. Verifica correttezza item->scala ────────────────────────────
print("\n--- 8. CORRETTEZZA ITEM->SCALA ---")

# Item 1 = VI Attention
check("Item 1 -> attention_problems",
      ITEM_TO_SCALE["1"] == "attention_problems")
# Item 50 = I Anxious/Depressed
check("Item 50 -> anxious_depressed",
      ITEM_TO_SCALE["50"] == "anxious_depressed")
# Item 94 = VIII Aggressive
check("Item 94 -> aggressive_behavior",
      ITEM_TO_SCALE["94"] == "aggressive_behavior")
# Item 56h = Other
check("Item 56h -> other_problems",
      ITEM_TO_SCALE["56h"] == "other_problems")
# Item 113a = Other
check("Item 113a -> other_problems",
      ITEM_TO_SCALE["113a"] == "other_problems")

# ─── 9. Coerenza n_critical per area ────────────────────────────────
print("\n--- 9. COERENZA CONTATORI ---")

expected_crit = {"I": 2, "VI": 4, "VII": 1, "VIII": 3}
for area in rf["critical_areas"]:
    exp = expected_crit[area["code"]]
    check(f"  Area {area['code']}: n_critical = {exp}",
          area["n_critical"] == exp,
          f"got {area['n_critical']}")

# ─── RIEPILOGO ──────────────────────────────────────────────────────
print("\n" + "=" * 70)
print(f"RISULTATO: {PASS} OK, {FAIL} FALLITI su {PASS+FAIL} test")
if FAIL == 0:
    print("REPORT FINALE VALIDATO IN TUTTI I FORMATI")
print("=" * 70)
