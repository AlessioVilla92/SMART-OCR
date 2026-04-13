"""
test_scorer_deep.py — Analisi completa e dettagliata del sistema di scoring.

Verifica:
  1. Copertura completa item (122/122)
  2. Zero overlap tra scale sindromiche
  3. Conteggio item per scala vs specifica ASEBA
  4. Composizione broadband (Internalizing/Externalizing)
  5. Correttezza numerica con input deterministici
  6. Coerenza tra scale sindromiche e DSM (overlap lecito)
  7. Integrita' adapter build_score_report
  8. Serializzazione profilo (to_dict / JSON)
  9. Validazione item mancanti e soglia scorabilita'
 10. Mapping Excel corretto
 11. Compilatore MD vs PD
"""

import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scorer.cbcl_scorer import (
    CBCLScorer, Compilatore, CBCLProfile, ScaleResult,
    ALL_ITEMS, SYNDROME_SCALES, DSM_SCALES, BROADBAND_COMPONENTS,
    OTHER_PROBLEMS, T_THRESHOLDS, item_to_excel_row, all_cbcl_items,
)
from core.scorer import build_score_report, build_full_profile, report_to_csv, report_to_json

PASS = 0
FAIL = 0

def check(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  [OK]  {name}")
    else:
        FAIL += 1
        print(f"  [!!]  {name}  -->  {detail}")


print("=" * 70)
print("ANALISI COMPLETA SISTEMA DI SCORING CBCL 6-18")
print("=" * 70)

# ─── 1. COPERTURA ITEM ─────────────────────────────────────────────
print("\n--- 1. COPERTURA ITEM ---")

all_in_syndrome = set()
for scale in SYNDROME_SCALES.values():
    for item in scale["items"]:
        all_in_syndrome.add(str(item))

all_in_other = set(str(i) for i in OTHER_PROBLEMS["items"])

all_in_scales = all_in_syndrome | all_in_other
expected_all = set(str(i) for i in ALL_ITEMS)

check("ALL_ITEMS ha 122 elementi", len(ALL_ITEMS) == 122, f"ha {len(ALL_ITEMS)}")
check("Sindromiche + Other coprono tutti i 122 item",
      all_in_scales == expected_all,
      f"Mancanti: {expected_all - all_in_scales}, Extra: {all_in_scales - expected_all}")
check("Nessun item extra fuori da ALL_ITEMS",
      all_in_scales - expected_all == set(),
      f"Extra: {all_in_scales - expected_all}")

# ─── 2. ZERO OVERLAP TRA SCALE SINDROMICHE ──────────────────────────
print("\n--- 2. ZERO OVERLAP SCALE SINDROMICHE ---")

seen = {}
duplicates = []
for scale_key, scale in SYNDROME_SCALES.items():
    for item in scale["items"]:
        s = str(item)
        if s in seen:
            duplicates.append(f"Item {s}: {seen[s]} E {scale_key}")
        seen[s] = scale_key
for item in OTHER_PROBLEMS["items"]:
    s = str(item)
    if s in seen:
        duplicates.append(f"Item {s}: {seen[s]} E Other")
    seen[s] = "Other"

check("Zero duplicati tra scale sindromiche + Other",
      len(duplicates) == 0,
      f"Duplicati: {duplicates}")

# ─── 3. CONTEGGIO ITEM PER SCALA ────────────────────────────────────
print("\n--- 3. CONTEGGIO ITEM PER SCALA (specifica ASEBA) ---")

expected_counts = {
    "anxious_depressed": 13,
    "withdrawn_depressed": 8,
    "somatic_complaints": 11,
    "social_problems": 11,
    "thought_problems": 15,
    "attention_problems": 10,
    "rule_breaking": 17,
    "aggressive_behavior": 18,
}
for key, expected_n in expected_counts.items():
    actual = len(SYNDROME_SCALES[key]["items"])
    check(f"  {key}: {actual} item (attesi {expected_n})",
          actual == expected_n, f"trovati {actual}")

check(f"  other_problems: {len(OTHER_PROBLEMS['items'])} item (attesi 19)",
      len(OTHER_PROBLEMS["items"]) == 19,
      f"trovati {len(OTHER_PROBLEMS['items'])}")

total_syndrome = sum(len(s["items"]) for s in SYNDROME_SCALES.values())
check(f"  Totale sindromiche: {total_syndrome} (attesi 103)",
      total_syndrome == 103, f"trovati {total_syndrome}")

dsm_counts = {
    "affective_problems": 13,
    "anxiety_problems": 6,
    "somatic_problems_dsm": 7,
    "adhd_problems": 7,
    "oppositional_problems": 5,
    "conduct_problems": 17,
}
print("\n  Scale DSM:")
for key, expected_n in dsm_counts.items():
    actual = len(DSM_SCALES[key]["items"])
    check(f"    {key}: {actual} item (attesi {expected_n})",
          actual == expected_n, f"trovati {actual}")

# ─── 4. COMPOSIZIONE BROADBAND ──────────────────────────────────────
print("\n--- 4. COMPOSIZIONE BROADBAND ---")

int_n = sum(len(SYNDROME_SCALES[c]["items"]) for c in BROADBAND_COMPONENTS["internalizing"]["components"])
ext_n = sum(len(SYNDROME_SCALES[c]["items"]) for c in BROADBAND_COMPONENTS["externalizing"]["components"])

check(f"Internalizing = I + II + III = {int_n} item (attesi 32)", int_n == 32)
check(f"Externalizing = VII + VIII = {ext_n} item (attesi 35)", ext_n == 35)
check("Internalizing composto da anxious_depressed + withdrawn_depressed + somatic_complaints",
      BROADBAND_COMPONENTS["internalizing"]["components"] ==
      ["anxious_depressed", "withdrawn_depressed", "somatic_complaints"])
check("Externalizing composto da rule_breaking + aggressive_behavior",
      BROADBAND_COMPONENTS["externalizing"]["components"] ==
      ["rule_breaking", "aggressive_behavior"])

# ─── 5. CORRETTEZZA NUMERICA ────────────────────────────────────────
print("\n--- 5. CORRETTEZZA NUMERICA ---")

# Test: tutti 0
r0 = {item: 0 for item in ALL_ITEMS}
p0 = CBCLScorer(r0).compute()
check("Tutti 0: total = 0", p0.total.raw_score == 0)
check("Tutti 0: internalizing = 0", p0.broadband["internalizing"].raw_score == 0)
check("Tutti 0: externalizing = 0", p0.broadband["externalizing"].raw_score == 0)

# Test: tutti 2
r2 = {item: 2 for item in ALL_ITEMS}
p2 = CBCLScorer(r2).compute()
check("Tutti 2: total = 244", p2.total.raw_score == 244, f"got {p2.total.raw_score}")
check("Tutti 2: internalizing = 64 (32*2)", p2.broadband["internalizing"].raw_score == 64)
check("Tutti 2: externalizing = 70 (35*2)", p2.broadband["externalizing"].raw_score == 70)
check("Tutti 2: other = 38 (19*2)", p2.other.raw_score == 38, f"got {p2.other.raw_score}")

for key in SYNDROME_SCALES:
    sr = p2.syndrome[key]
    expected_max = len(SYNDROME_SCALES[key]["items"]) * 2
    check(f"Tutti 2: {key} = {sr.raw_score} (attesi {expected_max})",
          sr.raw_score == expected_max)

# Test: tutti 1
r1 = {item: 1 for item in ALL_ITEMS}
p1 = CBCLScorer(r1).compute()
check("Tutti 1: total = 122", p1.total.raw_score == 122)
check("Tutti 1: internalizing = 32", p1.broadband["internalizing"].raw_score == 32)

# Test deterministico: solo item specifici a 2, resto 0
r_det = {item: 0 for item in ALL_ITEMS}
# Metto a 2 solo gli item di anxious_depressed
for item in SYNDROME_SCALES["anxious_depressed"]["items"]:
    r_det[item] = 2
p_det = CBCLScorer(r_det).compute()
check("Deterministico: anxious_depressed = 26 (13*2)",
      p_det.syndrome["anxious_depressed"].raw_score == 26)
check("Deterministico: withdrawn_depressed = 0",
      p_det.syndrome["withdrawn_depressed"].raw_score == 0)
check("Deterministico: total = 26",
      p_det.total.raw_score == 26)
check("Deterministico: internalizing = 26 (solo anxious contribuisce)",
      p_det.broadband["internalizing"].raw_score == 26)
check("Deterministico: externalizing = 0",
      p_det.broadband["externalizing"].raw_score == 0)

# ─── 6. OVERLAP LECITO SINDROMICHE / DSM ─────────────────────────────
print("\n--- 6. OVERLAP SINDROMICHE / DSM (sistema parallelo) ---")

dsm_items_all = set()
for scale in DSM_SCALES.values():
    for item in scale["items"]:
        dsm_items_all.add(str(item))

syn_items_all = set()
for scale in SYNDROME_SCALES.values():
    for item in scale["items"]:
        syn_items_all.add(str(item))

overlap = dsm_items_all & syn_items_all
check(f"DSM e Sindromiche condividono {len(overlap)} item (overlap lecito)",
      len(overlap) > 0,
      "Nessun overlap - potrebbe essere un errore")
check("Tutti gli item DSM sono anche in sindromiche o other",
      dsm_items_all.issubset(syn_items_all | all_in_other))

# Verifica zero overlap DENTRO le DSM
dsm_seen = {}
dsm_dupes = []
for scale_key, scale in DSM_SCALES.items():
    for item in scale["items"]:
        s = str(item)
        if s in dsm_seen:
            dsm_dupes.append(f"{s}: {dsm_seen[s]} e {scale_key}")
        dsm_seen[s] = scale_key
check("Zero duplicati DENTRO le scale DSM",
      len(dsm_dupes) == 0,
      f"Duplicati DSM: {dsm_dupes}")

# ─── 7. ADAPTER build_score_report ───────────────────────────────────
print("\n--- 7. ADAPTER build_score_report ---")

cls_results = {}
for item in ALL_ITEMS:
    cls_results[str(item)] = {"value": 1, "confidence": 0.92, "flag": None}
# Simula 2 item mancanti
del cls_results["56g"]
del cls_results["113b"]

report = build_score_report(cls_results, session_id="test_deep")
check("Report contiene _profile", "_profile" in report)
check("Report contiene compilatore", "compilatore" in report)
check("Total score = 120 (122 item a 1, meno 2 mancanti)",
      report["total_score"] == 120, f"got {report['total_score']}")

ss = report["subscale_scores"]
syn_keys = [k for k, v in ss.items() if v.get("type") == "syndrome"]
dsm_keys = [k for k, v in ss.items() if v.get("type") == "dsm"]
bb_keys = [k for k, v in ss.items() if v.get("type") == "broadband"]

check(f"Subscale sindromiche: {len(syn_keys)} (attese 9: 8 + Other)",
      len(syn_keys) == 9, f"trovate {len(syn_keys)}: {syn_keys}")
check(f"Subscale DSM: {len(dsm_keys)} (attese 6)",
      len(dsm_keys) == 6, f"trovate {len(dsm_keys)}: {dsm_keys}")
check(f"Subscale broadband: {len(bb_keys)} (attese 2)",
      len(bb_keys) == 2, f"trovate {len(bb_keys)}: {bb_keys}")

check("Somatic_complaints ha 1 missing (56g)",
      ss["somatic_complaints"]["items_missing"] == 1,
      f"got {ss['somatic_complaints']['items_missing']}")

stats = report["statistics"]
check(f"Items scored: {stats['items_scored']} (attesi 120)",
      stats["items_scored"] == 120)
check(f"Items missing: {stats['items_missing']} (attesi 2)",
      stats["items_missing"] == 2)

# ─── 8. SERIALIZZAZIONE PROFILO ──────────────────────────────────────
print("\n--- 8. SERIALIZZAZIONE PROFILO ---")

profile = report["_profile"]
d = profile.to_dict()
check("to_dict contiene compilatore", "compilatore" in d)
check("to_dict contiene syndrome_scales", "syndrome_scales" in d)
check("to_dict contiene dsm_scales", "dsm_scales" in d)
check("to_dict contiene broadband_scales", "broadband_scales" in d)
check("to_dict contiene total_problems", "total_problems" in d)
check("to_dict contiene validation", "validation" in d)

# JSON round-trip
json_str = json.dumps(d, ensure_ascii=False, indent=2)
d_back = json.loads(json_str)
check("JSON round-trip: compilatore preservato",
      d_back["compilatore"] == d["compilatore"])
check("JSON round-trip: total raw_score preservato",
      d_back["total_problems"]["raw_score"] == d["total_problems"]["raw_score"])

# report_to_json non include _profile
rj = report_to_json(report)
rj_parsed = json.loads(rj)
check("report_to_json esclude _profile",
      "_profile" not in rj_parsed)
check("report_to_json include compilatore",
      "compilatore" in rj_parsed)

# report_to_csv
csv_out = report_to_csv(report)
check("report_to_csv include header compilatore",
      "compilatore" in csv_out.split("\n")[0])
check("report_to_csv usa separatore ;",
      ";" in csv_out)

# ─── 9. VALIDAZIONE E SCORABILITA' ──────────────────────────────────
print("\n--- 9. VALIDAZIONE E SCORABILITA' ---")

# 8 mancanti: scorabile
r_8miss = {item: 0 for item in ALL_ITEMS[:114]}
v_8 = CBCLScorer(r_8miss).validate()
check(f"114 item forniti, 8 mancanti: is_scorable = True",
      v_8["is_scorable"] == True, f"got {v_8['is_scorable']}")

# 9 mancanti: non scorabile
r_9miss = {item: 0 for item in ALL_ITEMS[:113]}
v_9 = CBCLScorer(r_9miss).validate()
check(f"113 item forniti, 9 mancanti: is_scorable = False",
      v_9["is_scorable"] == False, f"got {v_9['is_scorable']}")

# Valori invalidi
r_inv = {item: 0 for item in ALL_ITEMS}
r_inv[1] = 5  # invalido
v_inv = CBCLScorer(r_inv).validate()
check("Valore invalido (5): is_scorable = False",
      v_inv["is_scorable"] == False)
check("Valore invalido segnalato in invalid_values",
      "1" in v_inv["invalid_values"])

# ─── 10. MAPPING EXCEL ──────────────────────────────────────────────
print("\n--- 10. MAPPING EXCEL ---")

excel_checks = [
    (1, 2), (55, 56),
    ("56a", 57), ("56h", 64),
    (57, 65), (112, 120),
    ("113a", 121), ("113b", 122), ("113c", 123),
]
for item, expected_row in excel_checks:
    actual = item_to_excel_row(item)
    check(f"Item {item} -> riga {actual} (attesa {expected_row})",
          actual == expected_row)

# Colonne MD/PD
cells_md = CBCLScorer({1: 2}, compilatore=Compilatore.MADRE).to_excel_cells()
cells_pd = CBCLScorer({1: 2}, compilatore=Compilatore.PADRE).to_excel_cells()
check("Madre usa colonna B", "B2" in cells_md)
check("Padre usa colonna C", "C2" in cells_pd)

# ─── 11. COMPILATORE MD vs PD ───────────────────────────────────────
print("\n--- 11. COMPILATORE MD vs PD ---")

r_test = {item: (hash(str(item)) % 3) for item in ALL_ITEMS}
p_md = CBCLScorer(r_test, compilatore=Compilatore.MADRE).compute()
p_pd = CBCLScorer(r_test, compilatore=Compilatore.PADRE).compute()

check("MD e PD: stessi raw score totali",
      p_md.total.raw_score == p_pd.total.raw_score)
check("MD e PD: compilatore diverso",
      p_md.compilatore != p_pd.compilatore)
for key in SYNDROME_SCALES:
    check(f"MD vs PD: {key} identico",
          p_md.syndrome[key].raw_score == p_pd.syndrome[key].raw_score)

# ─── 12. SOGLIE T-SCORE ─────────────────────────────────────────────
print("\n--- 12. SOGLIE T-SCORE (definizione) ---")

check("Sindromiche: normale < 65", T_THRESHOLDS["syndrome"]["normale_max"] == 64)
check("Sindromiche: borderline 65-69",
      T_THRESHOLDS["syndrome"]["borderline_min"] == 65 and
      T_THRESHOLDS["syndrome"]["borderline_max"] == 69)
check("Sindromiche: clinico >= 70", T_THRESHOLDS["syndrome"]["clinico_min"] == 70)
check("Broadband: normale < 60", T_THRESHOLDS["broadband"]["normale_max"] == 59)
check("Broadband: borderline 60-63",
      T_THRESHOLDS["broadband"]["borderline_min"] == 60 and
      T_THRESHOLDS["broadband"]["borderline_max"] == 63)
check("Broadband: clinico >= 64", T_THRESHOLDS["broadband"]["clinico_min"] == 64)

# ─── RIEPILOGO ───────────────────────────────────────────────────────
print("\n" + "=" * 70)
print(f"RISULTATO FINALE: {PASS} OK, {FAIL} FALLITI su {PASS+FAIL} test")
if FAIL == 0:
    print("SISTEMA DI SCORING: VALIDATO")
else:
    print(f"ATTENZIONE: {FAIL} test falliti — verificare!")
print("=" * 70)
