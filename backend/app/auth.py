"""Auth dependencies — JWT-based user injection.

`current_user` is the standard dependency for any route that needs a logged-in
user. `admin_only` adds the admin-required check. `verify_token` is kept as a
backward-compat alias so old `Depends(verify_token)` references still work
while routes are migrated.
"""

from __future__ import annotations

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from .db import get_db
from .models import AppConfig, User
from .security import decode_jwt


def _get_jwt_secret(db: Session) -> str:
    cfg = db.query(AppConfig).filter(AppConfig.id == 1).first()
    return (cfg.jwt_secret if cfg else "") or ""


def current_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    """Inject the authenticated user. Raises 401 on missing/invalid token."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="missing token")
    token = authorization[7:].strip()
    secret = _get_jwt_secret(db)
    if not secret:
        raise HTTPException(status_code=503, detail="server not initialized")
    user_id = decode_jwt(token, secret)
    if user_id is None:
        raise HTTPException(status_code=401, detail="invalid or expired token")
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="user no longer exists")
    return user


def admin_only(user: User = Depends(current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="admin required")
    return user


def verify_token(user: User = Depends(current_user)) -> None:
    """Backward-compat: existing routes that used Depends(verify_token) still
    work — they'll just require a valid JWT now instead of AUTH_TOKEN."""
    return None
