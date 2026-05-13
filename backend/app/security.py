"""Password hashing + JWT encoding/decoding."""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

import jwt
from passlib.hash import bcrypt

JWT_ALG = "HS256"


def hash_password(plain: str) -> str:
    return bcrypt.using(rounds=12).hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.verify(plain, hashed)
    except (ValueError, TypeError):
        return False


def random_token(nbytes: int = 32) -> str:
    return secrets.token_urlsafe(nbytes)


def encode_jwt(user_id: int, secret: str, remember: bool = False) -> str:
    """Issue JWT. Long-lived (30d) if remember=True else 12h."""
    ttl = timedelta(days=30) if remember else timedelta(hours=12)
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": int(now.timestamp()),
        "exp": int((now + ttl).timestamp()),
    }
    return jwt.encode(payload, secret, algorithm=JWT_ALG)


def decode_jwt(token: str, secret: str) -> int | None:
    """Return user_id or None on invalid/expired token."""
    try:
        payload = jwt.decode(token, secret, algorithms=[JWT_ALG])
        return int(payload["sub"])
    except (jwt.InvalidTokenError, KeyError, ValueError):
        return None
