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
    """Verifica che tutti i 122 item siano coperti dalle scale sindromiche."""
    all_in_scales = set()
    for scale in SYNDROME_SCALES.values():
        for item in scale["items"]:
            all_in_scales.add(str(item))
    for item in OTHER_PROBLEMS["items"]:
        all_in_scales.add(str(item))

    expected = set(str(i) for i in ALL_ITEMS)
    assert all_in_scales == expected, f"Mancanti: {expected - all_in_scales}, Extra: {all_in_scales - expected}"
    print("  test_item_coverage: 122/122 item coperti")


def test_no_duplicates():
    """Verifica che nessun item appaia in piu' di una scala sindromica."""
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
    print("  test_no_duplicates: 0 duplicati")


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
    assert len(OTHER_PROBLEMS["items"]) == 19  # 16 originali + 113a/b/c
    print("  test_item_counts: conteggi corretti")


def test_broadband_sums():
    """Verifica la composizione delle scale broadband."""
    # Internalizing = I + II + III = 13 + 8 + 11 = 32 item
    int_items = sum(len(SYNDROME_SCALES[c]["items"]) for c in BROADBAND_COMPONENTS["internalizing"]["components"])
    assert int_items == 32, f"Internalizing: {int_items} != 32"

    # Externalizing = VII + VIII = 17 + 18 = 35 item
    ext_items = sum(len(SYNDROME_SCALES[c]["items"]) for c in BROADBAND_COMPONENTS["externalizing"]["components"])
    assert ext_items == 35, f"Externalizing: {ext_items} != 35"

    # Total = 122 (32 + 35 + 11 + 15 + 10 + 20 Other, che include 113a/b/c => in realta' 8+Other=103-67=...)
    # Meglio: somma tutti gli items nelle scale + other = 122
    total_in_scales = sum(len(s["items"]) for s in SYNDROME_SCALES.values()) + len(OTHER_PROBLEMS["items"])
    assert total_in_scales == 122, f"Total in scales: {total_in_scales} != 122"
    print("  test_broadband_sums: composizione corretta")


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
    print("  test_scoring_all_zeros: tutti 0 -> score 0")


def test_scoring_all_twos():
    """Con tutte risposte 2, i punteggi devono essere al massimo."""
    responses = {item: 2 for item in ALL_ITEMS}
    scorer = CBCLScorer(responses, compilatore=Compilatore.PADRE)
    profile = scorer.compute()

    assert profile.total.raw_score == 244  # 122 * 2
    assert profile.broadband["internalizing"].raw_score == 64
    assert profile.broadband["externalizing"].raw_score == 70
    for sr in profile.syndrome.values():
        assert sr.raw_score == sr.max_score
    print("  test_scoring_all_twos: tutti 2 -> score max")


def test_md_pd_same_formulas():
    """MD e PD con stesse risposte producono stessi punteggi grezzi."""
    responses = {item: (hash(str(item)) % 3) for item in ALL_ITEMS}

    profile_md = CBCLScorer(responses, compilatore=Compilatore.MADRE).compute()
    profile_pd = CBCLScorer(responses, compilatore=Compilatore.PADRE).compute()

    assert profile_md.total.raw_score == profile_pd.total.raw_score
    for key in SYNDROME_SCALES:
        assert profile_md.syndrome[key].raw_score == profile_pd.syndrome[key].raw_score
    assert profile_md.compilatore != profile_pd.compilatore
    print("  test_md_pd_same_formulas: stesse risposte -> stessi raw score")


def test_excel_column_mapping():
    """Madre usa colonna B, Padre usa colonna C."""
    responses = {1: 2, "56a": 1}

    cells_md = CBCLScorer(responses, compilatore=Compilatore.MADRE).to_excel_cells()
    cells_pd = CBCLScorer(responses, compilatore=Compilatore.PADRE).to_excel_cells()

    assert "B2" in cells_md   # item 1 -> riga 2, colonna B
    assert "B57" in cells_md  # 56a -> riga 57, colonna B
    assert "C2" in cells_pd   # item 1 -> riga 2, colonna C
    assert "C57" in cells_pd  # 56a -> riga 57, colonna C
    print("  test_excel_column_mapping: B per MD, C per PD")


def test_excel_row_mapping():
    """Verifica il mapping item -> riga Excel (caso critico: offset +8)."""
    assert item_to_excel_row(1) == 2
    assert item_to_excel_row(55) == 56
    assert item_to_excel_row("56a") == 57
    assert item_to_excel_row("56h") == 64
    assert item_to_excel_row(57) == 65
    assert item_to_excel_row(112) == 120
    assert item_to_excel_row("113a") == 121
    assert item_to_excel_row("113b") == 122
    assert item_to_excel_row("113c") == 123
    print("  test_excel_row_mapping: offset +8 post-56h corretto, 113a-c OK")


def test_validation_missing_items():
    """Verifica che la validazione segnali gli item mancanti."""
    responses = {item: 0 for item in ALL_ITEMS[:100]}  # solo 100 su 122
    scorer = CBCLScorer(responses)
    v = scorer.validate()

    assert v["n_missing"] == 22
    assert not v["is_scorable"]  # > 8 mancanti
    print("  test_validation_missing_items: segnala 22 mancanti")


def test_113_in_other():
    """Verifica che 113a/b/c siano in Other Problems."""
    other_items = [str(i) for i in OTHER_PROBLEMS["items"]]
    assert "113a" in other_items
    assert "113b" in other_items
    assert "113c" in other_items
    print("  test_113_in_other: 113a/b/c in Other Problems")


def test_total_items_count():
    """Verifica che ALL_ITEMS abbia esattamente 122 item."""
    assert len(ALL_ITEMS) == 122, f"ALL_ITEMS ha {len(ALL_ITEMS)} item, attesi 122"
    print("  test_total_items_count: 122 item totali")


def test_adapter_build_score_report():
    """Verifica che build_score_report produca report con tutte le scale."""
    from core.scorer import build_score_report

    classification_results = {}
    for item in ALL_ITEMS:
        classification_results[str(item)] = {
            "value": 1,
            "confidence": 0.95,
            "flag": None,
        }

    report = build_score_report(classification_results, session_id="test")

    assert report["total_score"] == 122  # tutti 1 * 122 items
    assert "_profile" in report

    # Verifica che ci siano scale sindromiche, DSM e broadband
    subscales = report["subscale_scores"]
    assert "anxious_depressed" in subscales
    assert "affective_problems" in subscales
    assert "internalizing" in subscales
    assert "externalizing" in subscales
    assert subscales["anxious_depressed"]["type"] == "syndrome"
    assert subscales["affective_problems"]["type"] == "dsm"
    assert subscales["internalizing"]["type"] == "broadband"

    print("  test_adapter_build_score_report: report completo con tutte le scale")


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
    test_113_in_other()
    test_total_items_count()
    test_adapter_build_score_report()
    print("\n" + "=" * 50)
    print("TUTTI I TEST SUPERATI")
    print("=" * 50)
