"""Password hashing and session-bound JWT creation/verification (spec §24)."""

from datetime import datetime, timedelta, timezone
from hashlib import sha256
from uuid import uuid4

import jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Hash a plaintext password with bcrypt."""
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    """Return True if plain matches the stored bcrypt hash."""
    return pwd_context.verify(plain, hashed)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def new_token_id() -> str:
    return str(uuid4())


def token_id_hash(token_id: str) -> str:
    """Store only a one-way digest of a refresh token identifier."""
    return sha256(token_id.encode("utf-8")).hexdigest()


def create_access_token(user_id: str, role: str, session_id: str) -> str:
    """Short-lived access token bound to a revocable database session."""
    payload = {
        "sub": user_id,
        "role": role,
        "sid": session_id,
        "typ": "access",
        "iat": _now(),
        "exp": _now() + timedelta(minutes=settings.token_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_refresh_token(user_id: str, session_id: str, token_id: str) -> str:
    """Rotating refresh token bound to a revocable database session."""
    payload = {
        "sub": user_id,
        "sid": session_id,
        "jti": token_id,
        "typ": "refresh",
        "iat": _now(),
        "exp": _now() + timedelta(minutes=settings.refresh_token_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    """Decode and validate a JWT. Raises jwt.PyJWTError on any failure."""
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
