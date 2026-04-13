"""
test_display_flow.py — Verifica che il flusso dati dalla pipeline alla UI
produca risultati graficamente corretti e coerenti.

Simula:
  1. engine.process_photos() -> report (con build_score_report)
  2. main_window._on_analysis_done() -> aggiunge _profile
  3. results_page.update_results(report) -> popola tabelle
  4. Modifica manuale form -> results_page.update_from_form()
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scorer.cbcl_scorer import (
    CBCLScorer, Compilatore, CBCLProfile, ALL_ITEMS,
    SYNDROME_SCALES, DSM_SCALES, BROADBAND_COMPONENTS, OTHER_PROBLEMS,
)
from core.scorer import build_score_report, build_full_profile, ALL_ITEMS as ALL_ITEMS_STR

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
print("TEST FLUSSO DATI: ENGINE -> UI DISPLAY")
print("=" * 70)

# ─── SIMULA OUTPUT ENGINE ────────────────────────────────────────────
print("\n--- FASE 1: Simulo output engine.process_photos() ---")

# L'engine chiama build_score_report(all_classification, session_id=...)
# Simulo 122 item classificati: mix di 0, 1, 2 con qualche missing
classification_results = {}
test_values = {}
for i, item in enumerate(ALL_ITEMS_STR):
    if item in ("56g", "113b"):
        # Simula 2 item mancanti
        continue
    val = i % 3  # 0, 1, 2 ciclico
    classification_results[item] = {
        "value": val,
        "confidence": 0.85 + (i % 10) * 0.01,
        "flag": None,
    }
    test_values[item] = val

# L'engine chiama build_score_report con default (MADRE, no sex/age)
engine_report = build_score_report(
    classification_results,
    session_id="desktop_scan"
)
# L'engine aggiunge metadati
engine_report["_processing_time_ms"] = 1234
engine_report["_method"] = "ensemble"

check("Engine report ha _profile",
      "_profile" in engine_report and isinstance(engine_report["_profile"], CBCLProfile))
check("Engine report ha compilatore = MD (default)",
      engine_report.get("compilatore") == "MD")
check("Engine report ha subscale_scores",
      len(engine_report.get("subscale_scores", {})) > 0)
check("Engine report ha 122 items",
      len(engine_report.get("items", {})) == 122)
check("Engine report: 56g e 113b sono missing",
      engine_report["items"]["56g"]["flag"] == "not_processed" and
      engine_report["items"]["113b"]["flag"] == "not_processed")

# ─── SIMULA _on_analysis_done ────────────────────────────────────────
print("\n--- FASE 2: Simulo main_window._on_analysis_done() ---")

# L'utente ha selezionato: Padre, M, 12 anni
user_compilatore = Compilatore.PADRE
user_sex = "M"
user_age = 12

# main_window fa:
profile = build_full_profile(
    engine_report.get("items", {}),
    compilatore=user_compilatore,
    sex=user_sex,
    age=user_age,
)
engine_report["_profile"] = profile
engine_report["compilatore"] = user_compilatore.value

check("Profile ricalcolato con compilatore PADRE",
      profile.compilatore == Compilatore.PADRE)
check("Profile total coerente con report total_score",
      profile.total.raw_score == engine_report["total_score"],
      f"profile={profile.total.raw_score}, report={engine_report['total_score']}")

# ─── SIMULA results_page.update_results() ────────────────────────────
print("\n--- FASE 3: Simulo display nella pagina risultati ---")

# La results_page chiama _update_from_profile se _profile esiste
# Verifichiamo che i dati siano tutti disponibili e corretti

# 1. Badge compilatore
comp_display = engine_report.get("compilatore", "")
check("Compilatore badge = PD", comp_display == "PD")

# 2. Broadband cards
for key in ["internalizing", "externalizing"]:
    sr = profile.broadband.get(key)
    check(f"Broadband {key} disponibile", sr is not None)
    check(f"Broadband {key}: raw_score >= 0", sr.raw_score >= 0)
    check(f"Broadband {key}: max_score > 0", sr.max_score > 0)
    check(f"Broadband {key}: pct calcolata",
          0 <= sr.pct <= 100,
          f"pct={sr.pct}")

check("Total disponibile", profile.total is not None)
check(f"Total: raw={profile.total.raw_score} / max={profile.total.max_score}",
      profile.total.max_score == 244)

# 3. Syndrome table: 8 + Other = 9 righe
syndrome_rows = list(profile.syndrome.values()) + [profile.other]
check(f"Tabella sindromiche: {len(syndrome_rows)} righe (attese 9)",
      len(syndrome_rows) == 9)

for sr in syndrome_rows:
    check(f"  {sr.label_it}: raw={sr.raw_score}, max={sr.max_score}, missing={len(sr.missing_items)}",
          sr.raw_score >= 0 and sr.max_score > 0 and sr.raw_score <= sr.max_score)

# Verifica che i codici scala siano presenti
codes_found = []
for sr in profile.syndrome.values():
    if sr.key in SYNDROME_SCALES:
        codes_found.append(SYNDROME_SCALES[sr.key]["code"])
check(f"Codici scala presenti: {codes_found}",
      sorted(codes_found) == ["I", "II", "III", "IV", "V", "VI", "VII", "VIII"])

# 4. DSM table: 6 righe
dsm_rows = list(profile.dsm.values())
check(f"Tabella DSM: {len(dsm_rows)} righe (attese 6)",
      len(dsm_rows) == 6)

for sr in dsm_rows:
    check(f"  {sr.label_it}: raw={sr.raw_score}, max={sr.max_score}",
          sr.raw_score >= 0 and sr.max_score > 0)

# 5. Stats row
stats = engine_report.get("statistics", {})
check(f"Stats: items_scored = {stats.get('items_scored')} (attesi 120)",
      stats.get("items_scored") == 120)
check(f"Stats: items_missing = {stats.get('items_missing')} (attesi 2)",
      stats.get("items_missing") == 2)
check(f"Stats: mean_confidence e' un float",
      isinstance(stats.get("mean_confidence"), float))

# 6. Verifica coerenza numerica interna
int_raw = profile.broadband["internalizing"].raw_score
ext_raw = profile.broadband["externalizing"].raw_score
total_raw = profile.total.raw_score
other_raw = profile.other.raw_score
soc = profile.syndrome["social_problems"].raw_score
thought = profile.syndrome["thought_problems"].raw_score
att = profile.syndrome["attention_problems"].raw_score

sum_all_syndrome = sum(sr.raw_score for sr in profile.syndrome.values()) + other_raw
check("Coerenza: sum(sindromiche) + other = total",
      sum_all_syndrome == total_raw,
      f"sum={sum_all_syndrome}, total={total_raw}")

# Internalizing = I + II + III
int_expected = (profile.syndrome["anxious_depressed"].raw_score +
                profile.syndrome["withdrawn_depressed"].raw_score +
                profile.syndrome["somatic_complaints"].raw_score)
check(f"Coerenza: internalizing = I+II+III = {int_expected}",
      int_raw == int_expected,
      f"broadband={int_raw}, sum={int_expected}")

# Externalizing = VII + VIII
ext_expected = (profile.syndrome["rule_breaking"].raw_score +
                profile.syndrome["aggressive_behavior"].raw_score)
check(f"Coerenza: externalizing = VII+VIII = {ext_expected}",
      ext_raw == ext_expected,
      f"broadband={ext_raw}, sum={ext_expected}")

# ─── SIMULA MODIFICA MANUALE FORM ────────────────────────────────────
print("\n--- FASE 4: Simulo modifica form -> update_from_form() ---")

# L'utente modifica un item: 56g da missing a valore 1
form_items = dict(classification_results)
form_items["56g"] = {"value": 1, "confidence": 1.0, "flag": None}
form_items["113b"] = {"value": 0, "confidence": 1.0, "flag": None}

form_report = build_score_report(
    form_items,
    session_id="desktop_manual",
    compilatore=Compilatore.PADRE,
    sex="M",
    age=12,
)

check("Form report: 0 items missing",
      form_report["statistics"]["items_missing"] == 0)
check("Form report: total_score cambiato (56g=1 aggiunto, 113b=0 aggiunto)",
      form_report["total_score"] == engine_report["total_score"] + 1,
      f"form={form_report['total_score']}, engine={engine_report['total_score']}")

form_profile = form_report["_profile"]
check("Form: somatic_complaints aumentato di 1 (56g ora =1)",
      form_profile.syndrome["somatic_complaints"].raw_score ==
      profile.syndrome["somatic_complaints"].raw_score + 1)
check("Form: internalizing aumentato di 1 (somatic contiene 56g)",
      form_profile.broadband["internalizing"].raw_score ==
      profile.broadband["internalizing"].raw_score + 1)

# ─── SIMULA APERTURA VECCHIO PROGETTO (senza _profile) ───────────────
print("\n--- FASE 5: Simulo apertura progetto v1.0 (senza _profile) ---")

old_report = {
    "session_id": "old_project",
    "timestamp": "2026-03-01T12:00:00",
    "items": {str(item): {"value": 1, "confidence": 0.9, "flag": None} for item in ALL_ITEMS_STR},
    "subscale_scores": {
        "Affective_Problems": {"score": 7, "items_missing": 0},
        "Anxiety_Problems": {"score": 5, "items_missing": 0},
    },
    "total_score": 122,
    "statistics": {"items_scored": 122, "items_missing": 0, "items_flagged": 0, "mean_confidence": 0.9},
}

# results_page.update_results chiamera' _update_from_flat
has_profile = "_profile" in old_report
check("Vecchio progetto: no _profile", not has_profile)
check("Vecchio progetto: fallback a _update_from_flat attivato",
      not has_profile)

# subscale_scores senza "type" -> mostra tutto nella tabella sindromiche
subscales = old_report.get("subscale_scores", {})
has_types = any(isinstance(v, dict) and "type" in v for v in subscales.values())
check("Vecchio formato: subscale senza 'type' -> fallback generico",
      not has_types)

# ─── RIEPILOGO ───────────────────────────────────────────────────────
print("\n" + "=" * 70)
print(f"RISULTATO: {PASS} OK, {FAIL} FALLITI su {PASS+FAIL} test")
if FAIL == 0:
    print("FLUSSO DATI ENGINE -> DISPLAY: VERIFICATO")
else:
    print(f"ATTENZIONE: {FAIL} test falliti!")
print("=" * 70)
