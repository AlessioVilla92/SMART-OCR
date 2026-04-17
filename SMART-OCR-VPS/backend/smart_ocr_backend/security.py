"""
Security module — Argon2id password hashing + JWT token management.
"""

from datetime import datetime, timedelta, timezone

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from jose import jwt, JWTError

from smart_ocr_backend.settings import settings


_ph = PasswordHasher()


# ── Password hashing ─────────────────────────────────────────

def hash_password(plain: str) -> str:
    """Hash a plaintext password with Argon2id."""
    return _ph.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plaintext password against an Argon2id hash."""
    try:
        return _ph.verify(hashed, plain)
    except VerifyMismatchError:
        return False


# ── JWT tokens ────────────────────────────────────────────────

def create_access_token(subject: str, extra: dict = None) -> str:
    """Create a JWT access token with configurable expiration."""
    expire = datetime.now(timezone.utc) + timedelta(hours=settings.jwt_expire_hours)
    payload = {
        "sub": subject,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    """
    Decode and validate a JWT token.

    Returns: payload dict with 'sub' key.
    Raises: JWTError if invalid or expired.
    """
    return jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
