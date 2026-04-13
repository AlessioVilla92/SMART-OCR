"""
core/project_file.py

Sistema di salvataggio/caricamento progetti SmartOCR.

Formato file: .cbcl (ZIP con contenuti standard)
Struttura interna:
    project.json       — metadata (versione, data, modello)
    report.json        — report completo dall'engine
    form_values.json   — valori correnti dei 122 items (include modifiche utente)
    photos/
        page_4.jpg
        page_5.jpg
        page_6.jpg
"""

import json
import shutil
import zipfile
from pathlib import Path
from datetime import datetime
from typing import Optional

PROJECT_VERSION = "1.1"
PROJECT_EXTENSION = ".cbcl"
PROJECT_MAGIC = "SMARTOCR_CBCL"  # marker per validazione


def save_project(
    output_path: str,
    photo_paths: dict,
    report: dict,
    form_values: dict,
    mode: str = "",
    session_id: str = "",
    compilatore: str = "MD",
    child_sex: str = "",
    child_age: int = 0,
) -> bool:
    """
    Salva un progetto completo in un file .cbcl (ZIP).

    Args:
        output_path: path destinazione (aggiunge .cbcl se manca)
        photo_paths: {page_key: path_foto_originale}
        report: report completo dall'engine (items, score, subscale)
        form_values: dict {item_id: {value, confidence, flag, state}}
        mode: modello usato (svm/yolo/ensemble)
        session_id: identificatore sessione

    Returns:
        True se salvataggio OK, False altrimenti
    """
    output = Path(output_path)
    if output.suffix.lower() != PROJECT_EXTENSION:
        output = output.with_suffix(PROJECT_EXTENSION)

    # Metadata progetto
    metadata = {
        "magic": PROJECT_MAGIC,
        "version": PROJECT_VERSION,
        "app": "Smart OCR",
        "created": datetime.now().isoformat(),
        "mode": mode,
        "session_id": session_id or f"project_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        "pages": list(photo_paths.keys()),
        "compilatore": compilatore,
        "child_sex": child_sex,
        "child_age": child_age,
    }

    try:
        with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
            # 1. Metadata
            zf.writestr("project.json", json.dumps(metadata, indent=2, ensure_ascii=False))

            # 2. Report analisi (senza dati interni prefissati con _)
            clean_report = {k: v for k, v in report.items() if not k.startswith("_")} if report else {}
            zf.writestr("report.json", json.dumps(clean_report, indent=2, ensure_ascii=False))

            # 3. Valori form correnti (con le modifiche utente)
            zf.writestr("form_values.json", json.dumps(form_values, indent=2, ensure_ascii=False))

            # 3b. Profilo CBCL completo (se disponibile nel report)
            profile = report.get("_profile") if report else None
            if profile and hasattr(profile, "to_dict"):
                zf.writestr("profile.json", json.dumps(
                    profile.to_dict(), indent=2, ensure_ascii=False))

            # 4. Foto originali
            for page_key, photo_path in photo_paths.items():
                src = Path(photo_path)
                if src.exists():
                    # Estensione originale mantenuta
                    ext = src.suffix.lower() or ".jpg"
                    zf.write(src, f"photos/{page_key}{ext}")

        return True

    except (OSError, IOError, zipfile.BadZipFile) as e:
        print(f"Errore salvataggio progetto: {e}")
        return False


def load_project(project_path: str, extract_photos_to: Optional[str] = None) -> dict:
    """
    Carica un progetto da file .cbcl.

    Args:
        project_path: path al file .cbcl
        extract_photos_to: directory dove estrarre le foto (se None usa temp dir)

    Returns:
        dict con keys:
            - metadata: info progetto
            - report: report analisi originale
            - form_values: valori correnti del form
            - photo_paths: {page_key: path_estratto}

    Raises:
        FileNotFoundError, ValueError se il file non è valido
    """
    project = Path(project_path)
    if not project.exists():
        raise FileNotFoundError(f"Progetto non trovato: {project}")

    if project.suffix.lower() != PROJECT_EXTENSION:
        raise ValueError(f"Estensione non valida: {project.suffix} (attesa {PROJECT_EXTENSION})")

    # Directory di estrazione foto
    if extract_photos_to is None:
        import tempfile
        extract_dir = Path(tempfile.mkdtemp(prefix="smartocr_project_"))
    else:
        extract_dir = Path(extract_photos_to)
        extract_dir.mkdir(parents=True, exist_ok=True)

    try:
        with zipfile.ZipFile(project, 'r') as zf:
            # Valida magic/versione
            try:
                metadata_raw = zf.read("project.json").decode("utf-8")
                metadata = json.loads(metadata_raw)
            except (KeyError, json.JSONDecodeError) as e:
                raise ValueError(f"project.json mancante o corrotto: {e}")

            if metadata.get("magic") != PROJECT_MAGIC:
                raise ValueError("File non valido: magic marker errato")

            # Carica report
            try:
                report = json.loads(zf.read("report.json").decode("utf-8"))
            except KeyError:
                report = {}

            # Carica form_values
            try:
                form_values = json.loads(zf.read("form_values.json").decode("utf-8"))
            except KeyError:
                form_values = {}

            # Carica profilo CBCL (v1.1+)
            try:
                profile_data = json.loads(zf.read("profile.json").decode("utf-8"))
            except KeyError:
                profile_data = {}

            # Estrai foto
            photo_paths = {}
            for name in zf.namelist():
                if name.startswith("photos/") and not name.endswith("/"):
                    page_key = Path(name).stem  # "page_4"
                    out_path = extract_dir / Path(name).name
                    with zf.open(name) as src, open(out_path, "wb") as dst:
                        shutil.copyfileobj(src, dst)
                    photo_paths[page_key] = str(out_path)

        return {
            "metadata": metadata,
            "report": report,
            "form_values": form_values,
            "photo_paths": photo_paths,
            "profile_data": profile_data,
        }

    except zipfile.BadZipFile:
        raise ValueError("File corrotto o non è un archivio .cbcl valido")
