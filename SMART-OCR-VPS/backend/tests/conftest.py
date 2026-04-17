"""
Test configuration and fixtures.
"""

import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Ensure backend is importable
sys.path.insert(0, str(Path(__file__).parent.parent))

from smart_ocr_backend.db.session import Base, get_db
from smart_ocr_backend.db.models import User, UserRole
from smart_ocr_backend.security import hash_password


# In-memory SQLite for tests — StaticPool ensures all connections
# share the same underlying database (otherwise each connection
# gets its own empty in-memory DB).
TEST_ENGINE = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSession = sessionmaker(autocommit=False, autoflush=False, bind=TEST_ENGINE)


def override_get_db():
    db = TestSession()
    try:
        yield db
    finally:
        db.close()


def _create_test_app() -> FastAPI:
    """Create a test app WITHOUT lifespan (no real DB init)."""
    app = FastAPI(title="Smart OCR API Test")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    from smart_ocr_backend.api.routers import health, auth, jobs, scoring
    app.include_router(health.router, prefix="/api/v1")
    app.include_router(auth.router, prefix="/api/v1")
    app.include_router(jobs.router, prefix="/api/v1")
    app.include_router(scoring.router, prefix="/api/v1")

    app.dependency_overrides[get_db] = override_get_db
    return app


@pytest.fixture(autouse=True, scope="session")
def setup_db():
    """Create tables and seed test user once for all tests."""
    Base.metadata.create_all(bind=TEST_ENGINE)

    db = TestSession()
    user = User(
        username="testuser",
        password_hash=hash_password("testpass"),
        role=UserRole.clinician,
    )
    db.add(user)
    db.commit()
    db.close()

    yield

    Base.metadata.drop_all(bind=TEST_ENGINE)


@pytest.fixture()
def client():
    """TestClient for the test FastAPI app."""
    app = _create_test_app()
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def auth_token(client):
    """Get a JWT token for the test user."""
    resp = client.post(
        "/api/v1/auth/login",
        data={"username": "testuser", "password": "testpass"},
    )
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    return resp.json()["access_token"]


@pytest.fixture()
def auth_headers(auth_token):
    """Authorization headers with Bearer token."""
    return {"Authorization": f"Bearer {auth_token}"}
