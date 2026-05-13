"""Admin-only endpoints — invite code, user list, registration toggle."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..auth import admin_only
from ..db import get_db
from ..models import AppConfig, User
from ..security import random_token

router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(admin_only)])


class InviteOut(BaseModel):
    invite_code: str
    registration_enabled: bool


class RegistrationIn(BaseModel):
    enabled: bool


class UserBrief(BaseModel):
    id: int
    username: str
    is_admin: bool
    created_at: str
    last_login_at: str | None


@router.get("/invite", response_model=InviteOut)
def get_invite(db: Session = Depends(get_db)):
    cfg = db.query(AppConfig).filter(AppConfig.id == 1).first()
    return InviteOut(
        invite_code=cfg.invite_code or "",
        registration_enabled=bool(cfg and cfg.registration_enabled),
    )


@router.post("/invite/regenerate", response_model=InviteOut)
def regenerate_invite(db: Session = Depends(get_db)):
    cfg = db.query(AppConfig).filter(AppConfig.id == 1).first()
    cfg.invite_code = random_token(24)
    db.commit()
    return InviteOut(
        invite_code=cfg.invite_code,
        registration_enabled=bool(cfg.registration_enabled),
    )


@router.put("/registration", response_model=InviteOut)
def set_registration(payload: RegistrationIn, db: Session = Depends(get_db)):
    cfg = db.query(AppConfig).filter(AppConfig.id == 1).first()
    cfg.registration_enabled = 1 if payload.enabled else 0
    db.commit()
    return InviteOut(
        invite_code=cfg.invite_code or "",
        registration_enabled=bool(cfg.registration_enabled),
    )


@router.get("/users")
def list_users(db: Session = Depends(get_db)):
    users = db.query(User).order_by(User.created_at.desc()).all()
    return {
        "items": [
            UserBrief(
                id=u.id,
                username=u.username,
                is_admin=bool(u.is_admin),
                created_at=u.created_at.isoformat() if u.created_at else "",
                last_login_at=u.last_login_at.isoformat() if u.last_login_at else None,
            ).model_dump()
            for u in users
        ]
    }
