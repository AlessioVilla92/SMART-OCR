"""
core/scorer.py

Adapter che mantiene l'API build_score_report() per compatibilita'
con engine.py e results_page.py, delegando il calcolo al nuovo
CBCLScorer con formule verificate.

Il vecchio modulo e' salvato in core/scorer_old.py.
"""

import json
import csv
import io
from datetime import datetime
from typing import Dict, List, Optional, Any

from scorer.cbcl_scorer import (
    CBCLScorer, CBCLProfile, Compilatore, ScaleResult,
    ALL_ITEMS as SCORED_ITEMS,
    SYNDROME_SCALES, DSM_SCALES, BROADBAND_COMPONENTS, OTHER_PROBLEMS,
)


# Lista 122 item come stringhe per compatibilita' display e form
ALL_ITEMS = [str(i) for i in SCORED_ITEMS]

# Subscale legacy (ora calcolate dal CBCLScorer)
CBCL_SUBSCALES = {}
for key, scale in SYNDROME_SCALES.items():
    CBCL_SUBSCALES[key] = scale["items"]
CBCL_SUBSCALES["other_problems"] = OTHER_PROBLEMS["items"]
for key, scale in DSM_SCALES.items():
    CBCL_SUBSCALES[key] = scale["items"]
for key, scale in BROADBAND_COMPONENTS.items():
    # Broadband: flatten component items
    items = []
    for comp_key in scale["components"]:
        items.extend(SYNDROME_SCALES[comp_key]["items"])
    CBCL_SUBSCALES[key] = items


def _extract_responses(classification_results: dict) -> dict:
    """Estrae risposte flat {item_key: 0|1|2} da classification_results."""
    responses = {}
    for item_key, result in classification_results.items():
        if isinstance(result, dict):
            val = result.get("value")
        else:
            val = result
        if val is not None:
            # Normalizza chiave: int per numeri, str per sub-item
            try:
                k = int(item_key)
            except (ValueError, TypeError):
                k = str(item_key)
            responses[k] = int(val)
    return responses


def build_score_report(
    classification_results: Dict[str, dict],
    session_id: Optional[str] = None,
    metadata: Optional[dict] = None,
    compilatore: Compilatore = Compilatore.MADRE,
    sex: Optional[str] = None,
    age: Optional[int] = None,
) -> dict:
    """
    Costruisce il report completo da risultati classificazione.
    Usa internamente CBCLScorer per calcoli verificati.

    Args:
        classification_results: output classificazione per ogni item
        session_id: identificatore sessione (NON nome paziente)
        metadata: metadati aggiuntivi
        compilatore: Compilatore.MADRE o .PADRE
        sex: "M" o "F"
        age: eta' del bambino

    Returns: report completo come dict Python (con _profile allegato)
    """
    report = {
        "session_id": session_id or f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        "timestamp": datetime.now().isoformat(),
        "metadata": metadata or {},
        "compilatore": compilatore.value,
        "items": {},
        "subscale_scores": {},
        "total_score": 0,
        "flags": [],
        "statistics": {}
    }

    # Popola items dal classification_results
    flagged_items = []
    for item_id in ALL_ITEMS:
        if item_id not in classification_results:
            report["items"][item_id] = {
                "value": None,
                "flag": "not_processed",
                "confidence": 0.0
            }
            continue

        result = classification_results[item_id]
        value = result.get("value") if isinstance(result, dict) else result
        flag = result.get("flag") if isinstance(result, dict) else None
        confidence = result.get("confidence", 0.0) if isinstance(result, dict) else 0.0

        report["items"][item_id] = {
            "value": value,
            "flag": flag,
            "confidence": round(confidence, 3) if confidence else 0.0
        }

        if flag and flag not in ("missing",):
            flagged_items.append({"item": item_id, "flag": flag})

    report["flags"] = flagged_items

    # Calcola scoring con CBCLScorer
    responses = _extract_responses(classification_results)
    scorer = CBCLScorer(
        responses=responses,
        compilatore=compilatore,
        sex=sex,
        age=age,
    )
    profile = scorer.compute()

    # Total score dal profile
    report["total_score"] = profile.total.raw_score

    # Subscale scores — include tutte le scale
    subscale_scores = {}

    # Scale sindromiche
    for key, sr in profile.syndrome.items():
        subscale_scores[key] = {
            "score": sr.raw_score,
            "max_score": sr.max_score,
            "n_items": sr.n_items,
            "items_missing": len(sr.missing_items),
            "pct": sr.pct,
            "label_it": sr.label_it,
            "type": "syndrome",
        }

    # Other problems
    subscale_scores["other_problems"] = {
        "score": profile.other.raw_score,
        "max_score": profile.other.max_score,
        "n_items": profile.other.n_items,
        "items_missing": len(profile.other.missing_items),
        "pct": profile.other.pct,
        "label_it": profile.other.label_it,
        "type": "syndrome",
    }

    # Scale broadband
    for key, sr in profile.broadband.items():
        subscale_scores[key] = {
            "score": sr.raw_score,
            "max_score": sr.max_score,
            "n_items": sr.n_items,
            "items_missing": len(sr.missing_items),
            "pct": sr.pct,
            "label_it": sr.label_it,
            "type": "broadband",
        }

    # Scale DSM
    for key, sr in profile.dsm.items():
        subscale_scores[key] = {
            "score": sr.raw_score,
            "max_score": sr.max_score,
            "n_items": sr.n_items,
            "items_missing": len(sr.missing_items),
            "pct": sr.pct,
            "label_it": sr.label_it,
            "type": "dsm",
        }

    report["subscale_scores"] = subscale_scores

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
            sum(report["items"][i].get("confidence", 0) for i in ALL_ITEMS) / max(len(ALL_ITEMS), 1), 3
        )
    }

    # Profilo completo allegato (non serializzabile in JSON direttamente)
    report["_profile"] = profile

    return report


def build_full_profile(
    classification_results: dict,
    compilatore: Compilatore = Compilatore.MADRE,
    sex: Optional[str] = None,
    age: Optional[int] = None,
) -> CBCLProfile:
    """Calcola direttamente un CBCLProfile dai risultati classificazione."""
    responses = _extract_responses(classification_results)
    scorer = CBCLScorer(
        responses=responses,
        compilatore=compilatore,
        sex=sex,
        age=age,
    )
    return scorer.compute()


def report_to_csv(report: dict) -> str:
    """
    Converte il report in formato CSV con sezioni:
      1. TOTALE (Internal, External, Total — senza colonna Max)
      2. RISPOSTE (valori di tutti gli item)
      3. REPORT FINALE (aree critiche con risposta=2)
    Separatore ';' per compatibilità Excel IT.
    """
    output = io.StringIO()
    writer = csv.writer(output, delimiter=";")

    subscales = report.get("subscale_scores", {})
    bb_int = subscales.get("internalizing", {}) if isinstance(subscales.get("internalizing"), dict) else {}
    bb_ext = subscales.get("externalizing", {}) if isinstance(subscales.get("externalizing"), dict) else {}

    # Sezione TOTALE (senza Max)
    writer.writerow(["TOTALE"])
    writer.writerow(["Scala", "Formula", "Raw"])
    writer.writerow(["Internal Scala", "I + II + III", bb_int.get("score", 0)])
    writer.writerow(["External Scala", "VII + VIII", bb_ext.get("score", 0)])
    writer.writerow(["Total", "I + ... + Other", report.get("total_score", 0)])
    writer.writerow([])

    # Sezione Items
    writer.writerow(["RISPOSTE"])
    header = ["session_id", "timestamp", "compilatore"] + ALL_ITEMS + ["total_score"]
    writer.writerow(header)
    row = [
        report["session_id"],
        report["timestamp"],
        report.get("compilatore", "MD"),
    ]
    for item_id in ALL_ITEMS:
        val = report["items"].get(item_id, {}).get("value", "")
        row.append("" if val is None else val)
    row.append(report["total_score"])
    writer.writerow(row)
    writer.writerow([])

    # Sezione REPORT FINALE (aree critiche)
    try:
        from scorer.scale_colors import build_report_finale
        rf = build_report_finale(report)
        writer.writerow(["REPORT FINALE - AREE CRITICHE (risposte = 2)"])
        writer.writerow([f"Totale risposte critiche: {rf['total_critical']}"])
        writer.writerow([])
        writer.writerow(["Cod.", "Area", "N.Critiche", "N.Totale", "Item", "Domanda"])
        for area in rf["critical_areas"]:
            for item in area["items"]:
                writer.writerow([
                    area["code"],
                    area["label"],
                    area["n_critical"],
                    area["n_total"],
                    item["id"],
                    item["text"],
                ])
        if rf["areas_without_critical"]:
            writer.writerow([])
            writer.writerow(["AREE SENZA RISPOSTE CRITICHE"])
            for a in rf["areas_without_critical"]:
                writer.writerow([a["code"], a["label"]])
    except ImportError:
        pass

    return output.getvalue()


def report_to_json(report: dict) -> str:
    """Converte il report in JSON formattato (esclude _profile non serializzabile).
    Include la sezione 'report_finale' con le aree critiche (risposte=2)."""
    clean = {k: v for k, v in report.items() if not k.startswith("_")}
    try:
        from scorer.scale_colors import build_report_finale
        clean["report_finale"] = build_report_finale(report)
    except ImportError:
        pass
    return json.dumps(clean, indent=2, ensure_ascii=False)
