"""
Celery task — runs the OCR pipeline asynchronously.
"""

import json
import shutil
import time
import logging
from datetime import datetime, timezone
from pathlib import Path

import redis

from smart_ocr_backend.tasks.celery_app import celery_app
from smart_ocr_backend.settings import settings
from smart_ocr_backend.db.session import SessionLocal
from smart_ocr_backend.db.models import Job, JobStatus

logger = logging.getLogger(__name__)

_redis_client = None


def _get_redis():
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(settings.redis_url)
    return _redis_client


def _update_job(job_id: str, **kwargs):
    """Update job fields in the database."""
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if job:
            for k, v in kwargs.items():
                setattr(job, k, v)
            db.commit()
    finally:
        db.close()


@celery_app.task(name="analyse_job", bind=True)
def analyse_job(self, job_id: str):
    """
    Main pipeline task:
    1. Load uploaded images from jobs/{job_id}/
    2. Run OCREngine.process_photos()
    3. Store results in Redis with TTL
    4. Update job status in DB
    5. Cleanup uploaded images
    """
    work_dir = settings.jobs_dir / job_id
    start_time = time.time()

    def progress_cb(step: str, progress: float):
        _update_job(job_id, current_step=step, progress=progress)

    try:
        # Mark as processing
        _update_job(
            job_id,
            status=JobStatus.processing,
            started_at=datetime.now(timezone.utc),
            current_step="initializing",
            progress=0.0,
        )

        # Load job to get mode
        db = SessionLocal()
        try:
            job = db.query(Job).filter(Job.id == job_id).first()
            mode = job.mode if job else "ensemble"
        finally:
            db.close()

        # Check if this is a PDF job or photo job
        meta_path = work_dir / "meta.json"
        meta = {}
        if meta_path.exists():
            meta = json.loads(meta_path.read_text())

        from smart_ocr_backend.services.pipeline_adapter import run_pipeline, run_pdf_pipeline

        if meta.get("type") == "pdf":
            pdf_path = work_dir / "questionnaire.pdf"
            result = run_pdf_pipeline(
                pdf_path, mode,
                compilatore=meta.get("compilatore", "MD"),
                sex=meta.get("sex"),
                age=meta.get("age"),
                progress_cb=progress_cb,
            )
        else:
            result = run_pipeline(
                work_dir, mode, progress_cb,
                compilatore=meta.get("compilatore", "MD"),
                sex=meta.get("sex"),
                age=meta.get("age"),
            )

        # Store results in Redis
        r = _get_redis()
        result_key = f"smart_ocr:results:{job_id}"
        r.setex(
            result_key,
            settings.job_retention_seconds,
            json.dumps(result, ensure_ascii=False, default=str),
        )

        duration = time.time() - start_time

        _update_job(
            job_id,
            status=JobStatus.completed,
            completed_at=datetime.now(timezone.utc),
            duration_seconds=round(duration, 2),
            current_step="completed",
            progress=1.0,
        )

        logger.info(f"Job {job_id} completed in {duration:.1f}s")

    except Exception as e:
        duration = time.time() - start_time
        error_msg = str(e)[:2000]
        logger.error(f"Job {job_id} failed after {duration:.1f}s: {error_msg}")

        _update_job(
            job_id,
            status=JobStatus.failed,
            completed_at=datetime.now(timezone.utc),
            duration_seconds=round(duration, 2),
            error_message=error_msg,
            current_step="failed",
        )

    finally:
        # Cleanup uploaded images (privacy: don't keep photos on server)
        if work_dir.exists():
            try:
                shutil.rmtree(work_dir)
            except OSError:
                logger.warning(f"Failed to cleanup {work_dir}")
