"""
core/scorer.py

Mappa i risultati della classificazione agli item CBCL.
Calcola score totali e per subscale.
Genera output JSON e CSV.

Il CBCL 6-18 ha le seguenti subscale (DSM-oriented):
- Affective Problems: items 14, 24, 56c, 56d, 56e, 56f, 56g
- Anxiety Problems: items 22, 29, 30, 31, 32, 33, 34, 35, 50, 52, 112
- Somatic Problems: items 51, 54, 56a, 56b, 56h
- ADHD Problems: items 1, 4, 8, 10, 13, 17, 41, 61, 78
- Oppositional Defiant: items 3, 22, 23, 68, 86, 95, 97
- Conduct Problems: items 2, 26, 28, 39, 43, 63, 67, 72, 73, 81, 82, 90, 96, 99, 101
"""

import json
import csv
import io
from datetime import datetime
from typing import Dict, List, Optional, Any


# Subscale CBCL 6-18 DSM-oriented
CBCL_SUBSCALES = {
    "Affective_Problems": [14, 24, "56c", "56d", "56e", "56f", "56g"],
    "Anxiety_Problems": [22, 29, 30, 31, 32, 33, 34, 35, 50, 52, 112],
    "Somatic_Problems": [51, 54, "56a", "56b", "56h"],
    "ADHD_Problems": [1, 4, 8, 10, 13, 17, 41, 61, 78],
    "Oppositional_Defiant": [3, 22, 23, 68, 86, 95, 97],
    "Conduct_Problems": [2, 26, 28, 39, 43, 63, 67, 72, 73, 81, 82, 90, 96, 99, 101],
    "Internalizing": list(range(1, 36)) + ["56a", "56b", "56c", "56d", "56e", "56f", "56g", "56h"],
    "Externalizing": list(range(86, 113)),
}

# Tutti gli item CBCL nell'ordine corretto
ALL_ITEMS = (
    [str(i) for i in range(1, 56)] +
    ["56a", "56b", "56c", "56d", "56e", "56f", "56g", "56h"] +
    [str(i) for i in range(57, 113)] +
    ["113a", "113b", "113c"]
)


def build_score_report(
    classification_results: Dict[str, dict],
    session_id: Optional[str] = None,
    metadata: Optional[dict] = None
) -> dict:
    """
    Costruisce il report completo da risultati classificazione.

    Args:
        classification_results: output di CBCLClassifier.predict_item_cells()
                                 per ogni item
        session_id: identificatore sessione (NON nome paziente)
        metadata: metadati aggiuntivi (data, operatore, ecc.)

    Returns: report completo come dict Python
    """
    report = {
        "session_id": session_id or f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        "timestamp": datetime.now().isoformat(),
        "metadata": metadata or {},
        "items": {},
        "subscale_scores": {},
        "total_score": 0,
        "flags": [],
        "statistics": {}
    }

    total = 0
    flagged_items = []

    # Processa ogni item
    for item_id in ALL_ITEMS:
        if item_id not in classification_results:
            report["items"][item_id] = {
                "value": None,
                "flag": "not_processed",
                "confidence": 0.0
            }
            continue

        result = classification_results[item_id]
        value = result.get("value")
        flag = result.get("flag")
        confidence = result.get("confidence", 0.0)

        report["items"][item_id] = {
            "value": value,
            "flag": flag,
            "confidence": round(confidence, 3)
        }

        if value is not None:
            total += value

        if flag and flag not in ("missing",):
            flagged_items.append({"item": item_id, "flag": flag})

    report["total_score"] = total
    report["flags"] = flagged_items

    # Calcola subscale
    for subscale_name, items in CBCL_SUBSCALES.items():
        subscale_total = 0
        subscale_missing = 0

        for item in items:
            item_str = str(item)
            item_data = report["items"].get(item_str, {})
            val = item_data.get("value")

            if val is not None:
                subscale_total += val
            else:
                subscale_missing += 1

        report["subscale_scores"][subscale_name] = {
            "score": subscale_total,
            "items_missing": subscale_missing
        }

    # Statistiche generali
    all_values = [
        report["items"][i]["value"]
        for i in ALL_ITEMS
        if report["items"].get(i, {}).get("value") is not None
    ]

    report["statistics"] = {
        "items_total": len(ALL_ITEMS),
        "items_scored": len(all_values),
        "items_missing": len(ALL_ITEMS) - len(all_values),
        "items_flagged": len(flagged_items),
        "items_ambiguous": sum(1 for f in flagged_items if f["flag"] == "ambiguous"),
        "mean_confidence": round(
            sum(report["items"][i].get("confidence", 0) for i in ALL_ITEMS) / len(ALL_ITEMS), 3
        )
    }

    return report


def report_to_csv(report: dict) -> str:
    """
    Converte il report in formato CSV.
    Una riga con tutti i valori degli item in ordine.
    Compatibile con Excel per scoring manuale.
    """
    output = io.StringIO()

    # Header: session_id + tutti gli item nell'ordine standard
    header = ["session_id", "timestamp"] + ALL_ITEMS + ["total_score"]
    writer = csv.writer(output)
    writer.writerow(header)

    # Valori
    row = [
        report["session_id"],
        report["timestamp"]
    ]
    for item_id in ALL_ITEMS:
        val = report["items"].get(item_id, {}).get("value", "")
        row.append("" if val is None else val)

    row.append(report["total_score"])
    writer.writerow(row)

    return output.getvalue()


def report_to_json(report: dict) -> str:
    """Converte il report in JSON formattato."""
    return json.dumps(report, indent=2, ensure_ascii=False)
