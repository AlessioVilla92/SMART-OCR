"""
Settings module — loads configuration from .env via pydantic-settings.
"""

import os
from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Paths
    base_dir: Path = Path(__file__).parent.parent
    smart_ocr_dir: Path = Path(__file__).parent.parent.parent.parent / "smart_ocr"
    jobs_dir: Path = Path(__file__).parent.parent / "data" / "jobs"

    # Database
    database_url: str = "sqlite:///./smart_ocr.db"

    # Redis
    redis_url: str = "redis://127.0.0.1:6379/0"

    # JWT
    secret_key: str = "change-me-to-a-random-64-char-string"
    jwt_algorithm: str = "HS256"
    jwt_expire_hours: int = 24

    # Celery
    celery_broker_url: str = "redis://127.0.0.1:6379/0"
    celery_result_backend: str = "redis://127.0.0.1:6379/1"

    # Job settings
    job_retention_seconds: int = 3600

    # Pipeline defaults
    default_mode: str = "ensemble"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()

# Ensure jobs directory exists
settings.jobs_dir.mkdir(parents=True, exist_ok=True)
