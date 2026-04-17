#!/usr/bin/env bash
# Start the development server (API + Celery worker).
# Usage: bash scripts/dev_start.sh

set -e
cd "$(dirname "$0")/.."

echo "=== Smart OCR Backend — Dev Mode ==="

# Copy .env from example if not present
if [ ! -f .env ]; then
    cp .env.example .env
    echo "Created .env from .env.example — edit SECRET_KEY before production!"
fi

# Create admin user if DB is empty
python scripts/create_user.py admin admin123 --admin 2>/dev/null || true

echo ""
echo "Starting Celery worker in background..."
celery -A smart_ocr_backend.tasks.celery_app worker \
    --loglevel=info \
    --concurrency=1 \
    --pool=solo &
CELERY_PID=$!

echo "Starting FastAPI server..."
echo "API docs: http://localhost:8000/docs"
echo ""

uvicorn smart_ocr_backend.api.app:app \
    --host 0.0.0.0 \
    --port 8000 \
    --reload

# Cleanup on exit
kill $CELERY_PID 2>/dev/null
