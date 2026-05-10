from fastapi import Header, HTTPException, status

from .config import settings


def verify_token(authorization: str | None = Header(default=None)) -> None:
    if not settings.AUTH_TOKEN:
        return
    expected = f"Bearer {settings.AUTH_TOKEN}"
    if authorization != expected:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid token")
