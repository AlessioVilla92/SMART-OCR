"""
Celery application — broker config and task autodiscovery.
"""

import os
import sys
from pathlib import Path

from celery import Celery

from smart_ocr_backend.settings import settings

# Ensure smart_ocr is importable for worker processes
_smart_ocr_dir = str(settings.smart_ocr_dir.resolve())
if _smart_ocr_dir not in sys.path:
    sys.path.insert(0, _smart_ocr_dir)

# Apply ARM64 thread limits before any OpenCV import
for var, default in [
    ("OPENCV_NUM_THREADS", None),
    ("OMP_NUM_THREADS", None),
    ("ORT_NUM_THREADS", None),
]:
    val = os.environ.get(var)
    if val:
        os.environ[var] = val

celery_app = Celery(
    "smart_ocr",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    # One task at a time — ML is heavy
    worker_prefetch_multiplier=1,
    # Recycle worker after 20 tasks to free leaked memory
    worker_max_tasks_per_child=20,
    # Timeout: 270s soft, 300s hard (Pi 5 ensemble can take ~90s)
    task_soft_time_limit=270,
    task_time_limit=300,
)

# Explicitly include task modules (autodiscover looks for 'tasks.py' only)
celery_app.conf.include = ["smart_ocr_backend.tasks.pipeline_task"]
