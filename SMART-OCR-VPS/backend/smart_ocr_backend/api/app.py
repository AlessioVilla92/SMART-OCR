"""
FastAPI application factory.
Serves the React SPA frontend + REST API.
"""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from smart_ocr_backend.db.init_db import init_db

# Path to the built frontend (Vite output)
FRONTEND_DIR = Path(__file__).parent.parent.parent.parent / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: initialize database. Shutdown: nothing special."""
    init_db()
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="Smart OCR API",
        version="6.1.0",
        description="REST API per analisi OCR questionari CBCL 6-18",
        lifespan=lifespan,
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register API routers
    from smart_ocr_backend.api.routers import health, auth, jobs, scoring, export

    app.include_router(health.router, prefix="/api/v1")
    app.include_router(auth.router, prefix="/api/v1")
    app.include_router(jobs.router, prefix="/api/v1")
    app.include_router(scoring.router, prefix="/api/v1")
    app.include_router(export.router, prefix="/api/v1")

    # Serve frontend static files if the build directory exists
    if FRONTEND_DIR.exists():
        # Mount assets directory for JS/CSS bundles
        assets_dir = FRONTEND_DIR / "assets"
        if assets_dir.exists():
            app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

        # Serve static files (manifest, icons, etc.)
        @app.get("/manifest.json")
        async def manifest():
            return FileResponse(FRONTEND_DIR / "manifest.json")

        # SPA catch-all: serve index.html for all non-API routes
        @app.get("/{full_path:path}")
        async def serve_spa(request: Request, full_path: str):
            # If the file exists in dist/, serve it directly
            file_path = FRONTEND_DIR / full_path
            if full_path and file_path.is_file():
                return FileResponse(file_path)
            # Otherwise serve index.html (SPA routing)
            return FileResponse(FRONTEND_DIR / "index.html")

    return app


app = create_app()
