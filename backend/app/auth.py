from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from .db import get_db
from .settings_store import get_settings


def verify_token(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> None:
    row = get_settings(db)
    token = row.auth_token
    if not token:
        return  # auth disabled
    expected = f"Bearer {token}"
    if authorization != expected:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid token")
