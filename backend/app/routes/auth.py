"""User registration, login, current-user, setup."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..auth import current_user
from ..db import get_db
from ..models import AppConfig, ReviewLog, Setting, User, Word
from ..security import encode_jwt, hash_password, verify_password
from ..settings_store import normalize_username

router = APIRouter(prefix="/api/auth", tags=["auth"])


class SetupStatus(BaseModel):
    needs_setup: bool
    registration_enabled: bool


class SetupIn(BaseModel):
    username: str = Field(..., min_length=3, max_length=20)
    password: str = Field(..., min_length=6, max_length=128)


class LoginIn(BaseModel):
    username: str
    password: str
    remember: bool = True


class RegisterIn(BaseModel):
    username: str = Field(..., min_length=3, max_length=20)
    password: str = Field(..., min_length=6, max_length=128)
    invite_code: str = Field(..., min_length=1)


class AuthOut(BaseModel):
    token: str
    username: str
    is_admin: bool


class MeOut(BaseModel):
    id: int
    username: str
    is_admin: bool


@router.get("/setup-status", response_model=SetupStatus)
def setup_status(db: Session = Depends(get_db)):
    has_users = db.query(User.id).first() is not None
    cfg = db.query(AppConfig).filter(AppConfig.id == 1).first()
    enabled = bool(cfg and cfg.registration_enabled)
    return SetupStatus(needs_setup=not has_users, registration_enabled=enabled)


@router.post("/setup", response_model=AuthOut)
def setup(payload: SetupIn, db: Session = Depends(get_db)):
    """First-time admin creation. Only callable when zero users exist.
    Adopts all orphan rows (user_id IS NULL) into the new admin account."""
    has_users = db.query(User.id).first() is not None
    if has_users:
        raise HTTPException(status_code=403, detail="已经完成了初始化设置")
    uname = normalize_username(payload.username)
    if not uname:
        raise HTTPException(status_code=400, detail="用户名格式不合法（3-20 位字母数字下划线）")
    admin = User(
        username=uname,
        password_hash=hash_password(payload.password),
        is_admin=1,
    )
    db.add(admin)
    db.flush()
    # Adopt orphan data
    db.query(Word).filter(Word.user_id.is_(None)).update({"user_id": admin.id})
    db.query(ReviewLog).filter(ReviewLog.user_id.is_(None)).update({"user_id": admin.id})
    db.query(Setting).filter(Setting.user_id.is_(None)).update({"user_id": admin.id})
    db.commit()
    cfg = db.query(AppConfig).filter(AppConfig.id == 1).first()
    token = encode_jwt(admin.id, cfg.jwt_secret, remember=True)
    return AuthOut(token=token, username=admin.username, is_admin=True)


@router.post("/login", response_model=AuthOut)
def login(payload: LoginIn, db: Session = Depends(get_db)):
    uname = normalize_username(payload.username)
    user = db.query(User).filter(User.username == uname).first()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    user.last_login_at = datetime.utcnow()
    db.commit()
    cfg = db.query(AppConfig).filter(AppConfig.id == 1).first()
    token = encode_jwt(user.id, cfg.jwt_secret, remember=payload.remember)
    return AuthOut(token=token, username=user.username, is_admin=bool(user.is_admin))


@router.post("/register", response_model=AuthOut)
def register(payload: RegisterIn, db: Session = Depends(get_db)):
    cfg = db.query(AppConfig).filter(AppConfig.id == 1).first()
    if not cfg or not cfg.registration_enabled:
        raise HTTPException(status_code=403, detail="管理员已关闭注册")
    if payload.invite_code != (cfg.invite_code or ""):
        raise HTTPException(status_code=403, detail="邀请码无效")
    uname = normalize_username(payload.username)
    if not uname:
        raise HTTPException(status_code=400, detail="用户名格式不合法（3-20 位字母数字下划线）")
    if db.query(User).filter(User.username == uname).first() is not None:
        raise HTTPException(status_code=409, detail="用户名已被占用")
    user = User(
        username=uname,
        password_hash=hash_password(payload.password),
        is_admin=0,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    token = encode_jwt(user.id, cfg.jwt_secret, remember=True)
    return AuthOut(token=token, username=user.username, is_admin=False)


@router.get("/me", response_model=MeOut)
def me(user: User = Depends(current_user)):
    return MeOut(id=user.id, username=user.username, is_admin=bool(user.is_admin))
