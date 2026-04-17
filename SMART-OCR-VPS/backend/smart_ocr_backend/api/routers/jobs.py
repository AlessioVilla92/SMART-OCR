"""
Jobs router — create, poll, fetch results, cancel, PDF upload.
"""

import json
import uuid
import base64
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
import redis

from smart_ocr_backend.db.session import get_db
from smart_ocr_backend.db.models import User, Job, JobStatus
from smart_ocr_backend.api.deps import get_current_user
from smart_ocr_backend.settings import settings
from smart_ocr_backend.schemas.jobs import JobStatus as JobStatusSchema, JobResult

router = APIRouter(prefix="/jobs", tags=["jobs"])

_redis_client = None


def _get_redis():
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(settings.redis_url)
    return _redis_client


@router.post("/pdf-extract", status_code=200)
async def extract_pdf_pages(
    pdf_file: UploadFile = File(...),
    user: User = Depends(get_current_user),
):
    """
    Upload a PDF and extract pages as base64 images.
    Returns page thumbnails for the user to assign to page_4/5/6.
    """
    import sys
    smart_ocr_dir = str(settings.smart_ocr_dir.resolve())
    if smart_ocr_dir not in sys.path:
        sys.path.insert(0, smart_ocr_dir)

    try:
        import fitz  # PyMuPDF
    except ImportError:
        raise HTTPException(500, "PyMuPDF non installato sul server")

    content = await pdf_file.read()
    doc = fitz.open(stream=content, filetype="pdf")

    pages = []
    for i in range(len(doc)):
        pix = doc[i].get_pixmap(dpi=150)  # lower DPI for thumbnails
        img_bytes = pix.tobytes("png")
        b64 = base64.b64encode(img_bytes).decode("ascii")
        pages.append({
            "index": i,
            "width": pix.width,
            "height": pix.height,
            "thumbnail": f"data:image/png;base64,{b64}",
        })
    doc.close()

    return {"pages": pages, "total": len(pages)}


@router.post("/pdf-analyze", status_code=status.HTTP_202_ACCEPTED)
async def create_pdf_job(
    pdf_file: UploadFile = File(...),
    mode: str = Form("ensemble"),
    compilatore: str = Form("MD"),
    sex: Optional[str] = Form(None),
    age: Optional[int] = Form(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Upload a 3-page CBCL PDF for direct analysis (Mode D or specified mode).
    Pages are automatically assigned as page_4, page_5, page_6.
    """
    job_id = str(uuid.uuid4())
    job = Job(id=job_id, user_id=user.id, mode=mode)
    db.add(job)
    db.commit()

    work_dir = settings.jobs_dir / job_id
    work_dir.mkdir(parents=True, exist_ok=True)

    # Save PDF
    content = await pdf_file.read()
    pdf_path = work_dir / "questionnaire.pdf"
    pdf_path.write_bytes(content)

    # Save metadata for the task
    import json as _json
    meta = {"type": "pdf", "compilatore": compilatore, "sex": sex, "age": age}
    (work_dir / "meta.json").write_text(_json.dumps(meta))

    from smart_ocr_backend.tasks.pipeline_task import analyse_job
    analyse_job.delay(job_id)

    return {"job_id": job_id, "status": "queued"}


@router.post("", status_code=status.HTTP_202_ACCEPTED)
async def create_job(
    page_4: UploadFile = File(...),
    page_5: UploadFile = File(...),
    page_6: UploadFile = File(...),
    mode: str = Form("ensemble"),
    compilatore: str = Form("MD"),
    sex: Optional[str] = Form(None),
    age: Optional[int] = Form(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Upload 3 page images and start async OCR analysis.

    Returns job_id for polling.
    """
    if mode not in ("svm", "yolo", "ensemble"):
        raise HTTPException(400, f"Mode invalido: {mode}. Usa svm, yolo o ensemble.")

    # Create job record
    job_id = str(uuid.uuid4())
    job = Job(id=job_id, user_id=user.id, mode=mode)
    db.add(job)
    db.commit()

    # Save uploaded files
    work_dir = settings.jobs_dir / job_id
    work_dir.mkdir(parents=True, exist_ok=True)

    for page_file, page_name in [
        (page_4, "page_4"),
        (page_5, "page_5"),
        (page_6, "page_6"),
    ]:
        ext = Path(page_file.filename).suffix or ".jpg"
        dest = work_dir / f"{page_name}{ext}"
        content = await page_file.read()
        dest.write_bytes(content)

    # Save metadata
    import json as _json
    meta = {"type": "photos", "compilatore": compilatore, "sex": sex, "age": age}
    (work_dir / "meta.json").write_text(_json.dumps(meta))

    # Dispatch Celery task
    from smart_ocr_backend.tasks.pipeline_task import analyse_job
    analyse_job.delay(job_id)

    return {"job_id": job_id, "status": "queued"}


@router.get("/{job_id}", response_model=JobStatusSchema)
def get_job_status(
    job_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Poll job status and progress."""
    job = db.query(Job).filter(Job.id == job_id, Job.user_id == user.id).first()
    if not job:
        raise HTTPException(404, "Job non trovato")

    return JobStatusSchema(
        job_id=job.id,
        status=job.status.value,
        progress=job.progress,
        current_step=job.current_step,
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        duration_seconds=job.duration_seconds,
        error_message=job.error_message,
    )


@router.get("/{job_id}/results")
def get_job_results(
    job_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Fetch analysis results from Redis."""
    job = db.query(Job).filter(Job.id == job_id, Job.user_id == user.id).first()
    if not job:
        raise HTTPException(404, "Job non trovato")

    if job.status != JobStatus.completed:
        raise HTTPException(400, f"Job non completato (status={job.status.value})")

    r = _get_redis()
    result_key = f"smart_ocr:results:{job_id}"
    raw = r.get(result_key)

    if raw is None:
        raise HTTPException(
            status.HTTP_410_GONE,
            "Risultati scaduti. I risultati vengono eliminati dopo "
            f"{settings.job_retention_seconds // 60} minuti.",
        )

    result = json.loads(raw)
    result["job_id"] = job_id
    return result


@router.delete("/{job_id}")
def delete_job(
    job_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Cancel or cleanup a job."""
    job = db.query(Job).filter(Job.id == job_id, Job.user_id == user.id).first()
    if not job:
        raise HTTPException(404, "Job non trovato")

    # Delete results from Redis
    r = _get_redis()
    r.delete(f"smart_ocr:results:{job_id}")

    # Delete job record
    db.delete(job)
    db.commit()

    return {"deleted": True}
