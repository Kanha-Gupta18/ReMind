"""Password hashing and JWT creation/verification (spec §24).

Tokens are stateless JWTs:
  - access token  (~30 min)  carries sub, role, patient scope (pid)
  - refresh token (7 days)   carries sub + typ="refresh", used to mint new pairs

Secrets come from settings.jwt_secret (keep out of the repo, see .env).
"""

from datetime import datetime, timedelta, timezone

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


def create_access_token(user_id: str, role: str, patient_id: str | None) -> str:
    """Access token identifying the user and their patient scope."""
    payload = {
        "sub": user_id,
        "role": role,
        "pid": patient_id,
        "typ": "access",
        "iat": _now(),
        "exp": _now() + timedelta(minutes=settings.token_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_refresh_token(user_id: str) -> str:
    """Long-lived token used only to mint new access/refresh pairs."""
    payload = {
        "sub": user_id,
        "typ": "refresh",
        "iat": _now(),
        "exp": _now() + timedelta(minutes=settings.refresh_token_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    """Decode and validate a JWT. Raises jwt.PyJWTError on any failure."""
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
