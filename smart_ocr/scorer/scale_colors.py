"""
scorer/scale_colors.py

Palette colori per le 8 scale sindromiche + Other e mapping item->scala.
Utilizzato dal PDF export per visualizzazione clinica.
"""

from .cbcl_scorer import SYNDROME_SCALES, OTHER_PROBLEMS


# Palette colori per scala (hex).
# "bg" = sfondo leggero per righe/banner
# "dark" = colore intenso per risposta=2 o bordi
SCALE_COLORS = {
    "anxious_depressed":   {"bg": "#DCEBF9", "dark": "#3D85C6", "code": "I",    "label": "Ansioso/Depresso"},
    "withdrawn_depressed": {"bg": "#D6E2F5", "dark": "#3C5A99", "code": "II",   "label": "Ritirato/Depresso"},
    "somatic_complaints":  {"bg": "#D6ECE6", "dark": "#2E8B7E", "code": "III",  "label": "Lamentele Somatiche"},
    "social_problems":     {"bg": "#FFF3CC", "dark": "#D4A017", "code": "IV",   "label": "Problemi Sociali"},
    "thought_problems":    {"bg": "#E4D7F0", "dark": "#6A3D9A", "code": "V",    "label": "Problemi del Pensiero"},
    "attention_problems":  {"bg": "#FFE0C2", "dark": "#D97F1E", "code": "VI",   "label": "Problemi di Attenzione"},
    "rule_breaking":       {"bg": "#FADADD", "dark": "#C44D7B", "code": "VII",  "label": "Comportamento Trasgressivo"},
    "aggressive_behavior": {"bg": "#F9D6D6", "dark": "#C0392B", "code": "VIII", "label": "Comportamento Aggressivo"},
    "other_problems":      {"bg": "#E8E8E8", "dark": "#6B6B6B", "code": "—",    "label": "Problemi Residui"},
}


def build_item_to_scale_map() -> dict:
    """
    Mappa {item_str: scale_key} per tutti i 122 item.
    Ogni item appartiene esattamente a una scala sindromica o a Other.
    """
    m = {}
    for scale_key, scale in SYNDROME_SCALES.items():
        for item in scale["items"]:
            m[str(item)] = scale_key
    for item in OTHER_PROBLEMS["items"]:
        m[str(item)] = "other_problems"
    return m


ITEM_TO_SCALE = build_item_to_scale_map()


SYNDROME_ORDER = [
    "anxious_depressed", "withdrawn_depressed", "somatic_complaints",
    "social_problems", "thought_problems", "attention_problems",
    "rule_breaking", "aggressive_behavior",
]


def build_report_finale(report: dict) -> dict:
    """
    Costruisce la struttura del REPORT FINALE.

    Raggruppa gli item con value=2 per scala di appartenenza, con testo
    domanda italiano, contatori e liste aree senza criticita'.

    Returns:
        {
            "critical_areas": [
                {
                    "scale_key": "attention_problems",
                    "code": "VI",
                    "label": "Problemi di Attenzione",
                    "color_dark": "#D97F1E",
                    "color_bg": "#FFE0C2",
                    "n_critical": 4,
                    "n_total": 10,
                    "items": [
                        {"id": "1", "text": "Agisce in modo infantile..."},
                        ...
                    ],
                },
                ...
            ],
            "areas_without_critical": [
                {"scale_key": "...", "code": "...", "label": "...", "color_dark": "..."},
                ...
            ],
            "total_critical": 10,
        }
    """
    questions_it = load_italian_questions()

    # Raggruppa item con value=2 per scala
    by_scale = {}
    items = report.get("items", {})
    for iid, data in items.items():
        val = data.get("value") if isinstance(data, dict) else data
        if val == 2:
            scale_key = ITEM_TO_SCALE.get(str(iid), "other_problems")
            by_scale.setdefault(scale_key, []).append(str(iid))

    # Dimensioni scale
    from .cbcl_scorer import SYNDROME_SCALES, OTHER_PROBLEMS
    scale_sizes = {k: len(v["items"]) for k, v in SYNDROME_SCALES.items()}
    scale_sizes["other_problems"] = len(OTHER_PROBLEMS["items"])

    area_order = SYNDROME_ORDER + ["other_problems"]
    critical_areas = []
    for sk in area_order:
        if sk not in by_scale:
            continue
        info = SCALE_COLORS[sk]
        crits = by_scale[sk]
        critical_areas.append({
            "scale_key": sk,
            "code": info["code"],
            "label": info["label"],
            "color_dark": info["dark"],
            "color_bg": info["bg"],
            "n_critical": len(crits),
            "n_total": scale_sizes[sk],
            "items": [{"id": iid, "text": questions_it.get(iid, "")} for iid in crits],
        })

    areas_without = []
    for sk in area_order:
        if sk not in by_scale:
            info = SCALE_COLORS[sk]
            areas_without.append({
                "scale_key": sk,
                "code": info["code"],
                "label": info["label"],
                "color_dark": info["dark"],
            })

    return {
        "critical_areas": critical_areas,
        "areas_without_critical": areas_without,
        "total_critical": sum(len(v) for v in by_scale.values()),
    }


def load_italian_questions() -> dict:
    """Carica le domande CBCL in italiano da resources/cbcl_questions_it.json.

    Ritorna dict {item_str: testo_italiano}. Ritorna {} se il file manca.
    """
    import json
    from pathlib import Path
    import sys

    # Prova vari path (pacchetto, exe pyinstaller, repo)
    candidates = [
        Path(__file__).parent.parent / "resources" / "cbcl_questions_it.json",
        Path(getattr(sys, "_MEIPASS", "")) / "resources" / "cbcl_questions_it.json",
    ]
    for p in candidates:
        if p.exists():
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                # Il JSON ha struttura {"page_4": {"1": "...", ...}, "page_5": {...}, ...}
                flat = {}
                for page_data in data.values():
                    if isinstance(page_data, dict):
                        flat.update(page_data)
                return flat
            except (json.JSONDecodeError, OSError):
                continue
    return {}
