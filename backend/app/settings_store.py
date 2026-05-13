"""Settings persistence + access. Per-user: each user has one Setting row."""

from __future__ import annotations

import re

from sqlalchemy.orm import Session

from .config import settings as env_settings
from .models import Setting


_USERNAME_RE = re.compile(r"^[a-z0-9_]{3,20}$")


def normalize_username(raw: str) -> str:
    """Lowercase + trim. Returns '' if format invalid."""
    s = (raw or "").strip().lower()
    return s if _USERNAME_RE.match(s) else ""


def _ensure_row(db: Session, user_id: int) -> Setting:
    row = db.query(Setting).filter(Setting.user_id == user_id).first()
    if row is None:
        # Seed from .env once for this user (mostly useful for admin's first row)
        env_url = env_settings.AI_BASE_URL or ""
        provider = "openai"
        if "anthropic" in env_url:
            provider = "anthropic"
        elif "generativelanguage" in env_url or "google" in env_url:
            provider = "google"
        row = Setting(
            user_id=user_id,
            provider_type=provider,
            base_url=env_url,
            api_key=env_settings.AI_API_KEY or "",
            model=env_settings.AI_MODEL or "",
            auth_token="",  # deprecated
        )
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


def get_settings(db: Session, user_id: int) -> Setting:
    return _ensure_row(db, user_id)


def is_configured(row: Setting) -> bool:
    return bool(row.provider_type and row.base_url and row.api_key and row.model)


def update_settings(
    db: Session,
    user_id: int,
    *,
    provider_type: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
    model: str | None = None,
    auth_token: str | None = None,
) -> Setting:
    row = _ensure_row(db, user_id)
    if provider_type is not None:
        row.provider_type = provider_type.lower().strip()
    if base_url is not None:
        row.base_url = base_url.strip().rstrip("/")
    if api_key is not None and api_key != "":
        row.api_key = api_key
    if model is not None:
        row.model = model.strip()
    if auth_token is not None:
        row.auth_token = auth_token  # kept for compat; not used
    db.commit()
    db.refresh(row)
    return row


def mask_key(key: str) -> str:
    if not key:
        return ""
    if len(key) <= 8:
        return "•" * len(key)
    return f"{key[:4]}…{key[-4:]}"
