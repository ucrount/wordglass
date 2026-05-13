# 多用户登录 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** WordGlass 从「单 AUTH_TOKEN 共享」升级到「多用户 JWT 登录」—— users 表、bcrypt 密码、邀请码注册、每用户独立单词库 / 练习 / AI 设置；首次访问引导 admin 设置接管现有数据。

**Architecture:** 后端 FastAPI 加 `User` + `AppConfig` 表，给 `Word` / `ReviewLog` / `Setting` 加 `user_id` 外键；JWT (PyJWT) + bcrypt (passlib) 取代 AUTH_TOKEN；所有现有路由通过 `current_user` 依赖注入用户后过滤数据。前端加 `/login` `/register` `/setup` 路由 + auth composable + 路由守卫 + 浮字背景登录页 + sidebar 退出按钮 + admin tab。

**Tech Stack:** FastAPI + SQLAlchemy + SQLite · PyJWT · passlib[bcrypt] · Vue 3 + TypeScript + vue-router 4 · `vue-tsc -b && vite build` 验证。

**前置：** spec `docs/superpowers/specs/2026-05-14-multi-user-auth-design.md`

---

## 任务结构

```
后端（顺序，因为有 import 依赖）
T1  models.py + ensure_schema 加 User / AppConfig / user_id 列
T2  security.py（hash/verify/encode_jwt/decode_jwt/random_token）
T3  auth.py 重写（current_user / admin_only）
T4  routes/auth.py（setup-status / setup / login / register / me）
T5  routes/admin.py（invite / registration / users）
T6  words.py user-scoping
T7  review.py user-scoping
T8  stats.py user-scoping
T9  settings_store.py + routes/settings.py 改 per-user
T10 routes/translate.py + routes/words.py /usage user-scoping
T11 main.py 注册新 router + requirements.txt 加依赖

前端（T12 后大致独立）
T12 api.ts 加新方法 + types + JWT key 改名
T13 composables/auth.ts
T14 router.ts 加路由 + 守卫
T15 views/Login.vue + Register.vue + Setup.vue
T16 App.vue 条件 sidebar
T17 SideBar.vue 加用户块 + 退出
T18 components/settings/AdminPanel.vue + Settings.vue 加 tab
T19 删除 GlobalGuards.vue 旧 token 弹框逻辑

最后
T20 Build + 手动 smoke
```

后端 T6-T10 可以并行；前端 T15-T18 互相独立可并行。

---

## Task 1: models.py + ensure_schema 迁移

**Files:**
- Modify: `backend/app/models.py`
- Modify: `backend/app/db.py`

**Spec ref:** §2.1, §2.2, §2.3

- [ ] **Step 1: 在 `backend/app/models.py` 末尾追加 User 和 AppConfig 表，并给现有 Word / ReviewLog / Setting 加 user_id 列**

完整替换 `backend/app/models.py`：

```python
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from .db import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String(20), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    is_admin = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login_at = Column(DateTime, nullable=True)


class AppConfig(Base):
    """Singleton row (id=1). Global app config not tied to any user."""

    __tablename__ = "app_config"

    id = Column(Integer, primary_key=True)
    invite_code = Column(String(64), default="")
    registration_enabled = Column(Integer, default=1)
    jwt_secret = Column(String(128), default="")


class Word(Base):
    __tablename__ = "words"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=True)
    text = Column(String(100), nullable=False, index=True)
    phonetic = Column(String(120), default="")
    pos = Column(String(40), default="")
    translation = Column(Text, default="")
    category = Column(String(50), default="", index=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    mastery = Column(Integer, default=0, index=True)
    review_count = Column(Integer, default=0)
    correct_count = Column(Integer, default=0)
    next_review_at = Column(DateTime, default=datetime.utcnow, index=True)

    examples = relationship(
        "Example", back_populates="word", cascade="all, delete-orphan", order_by="Example.id"
    )
    reviews = relationship("ReviewLog", back_populates="word", cascade="all, delete-orphan")


class Example(Base):
    __tablename__ = "examples"

    id = Column(Integer, primary_key=True)
    word_id = Column(Integer, ForeignKey("words.id", ondelete="CASCADE"), index=True)
    en = Column(Text, nullable=False)
    zh = Column(Text, default="")

    word = relationship("Word", back_populates="examples")


class ReviewLog(Base):
    __tablename__ = "review_logs"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=True)
    word_id = Column(Integer, ForeignKey("words.id", ondelete="CASCADE"), index=True)
    mode = Column(String(20))
    result = Column(String(10))
    reviewed_at = Column(DateTime, default=datetime.utcnow, index=True)

    word = relationship("Word", back_populates="reviews")


class Setting(Base):
    """Per-user settings row. Each user has one row."""

    __tablename__ = "settings"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True, nullable=True)
    provider_type = Column(String(20), default="openai")
    base_url = Column(String(255), default="")
    api_key = Column(Text, default="")
    model = Column(String(100), default="")
    auth_token = Column(String(255), default="")  # deprecated; JWT replaces this
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```

**注意**：`Word.text` 原来是 `unique=True`。现在多用户下，两个用户都能加同一个词，所以**去掉 `unique=True`**，只保留 `index=True`。这是个 schema breaking change，要在 `ensure_schema()` 里处理（SQLite 无法 drop UNIQUE，建议忽略 —— 现有数据里同一个词不会跨用户冲突因为只有一个用户）。

- [ ] **Step 2: 用以下完整内容替换 `backend/app/db.py`**

```python
import secrets

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker

from .config import settings

connect_args = {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(settings.DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _add_column_if_missing(conn, table: str, column_name: str, ddl: str) -> None:
    """SQLite-safe idempotent ALTER TABLE ADD COLUMN."""
    inspector = inspect(conn)
    cols = {c["name"] for c in inspector.get_columns(table)}
    if column_name not in cols:
        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {ddl}"))


def ensure_schema():
    """Idempotent migrations: create new tables, add new columns, seed app_config."""
    # First: create all tables that are missing (Base.metadata.create_all handles this)
    Base.metadata.create_all(bind=engine)

    inspector = inspect(engine)
    tables = set(inspector.get_table_names())

    # Add columns added after initial release
    with engine.begin() as conn:
        if "words" in tables:
            _add_column_if_missing(conn, "words", "category",
                                    "category VARCHAR(50) DEFAULT ''")
            _add_column_if_missing(conn, "words", "user_id",
                                    "user_id INTEGER REFERENCES users(id)")
        if "review_logs" in tables:
            _add_column_if_missing(conn, "review_logs", "user_id",
                                    "user_id INTEGER REFERENCES users(id)")
        if "settings" in tables:
            _add_column_if_missing(conn, "settings", "user_id",
                                    "user_id INTEGER REFERENCES users(id)")

    # Seed AppConfig singleton (id=1) with random invite_code + jwt_secret
    from .models import AppConfig  # local import to avoid circular
    with SessionLocal() as db:
        cfg = db.query(AppConfig).filter(AppConfig.id == 1).first()
        if cfg is None:
            cfg = AppConfig(
                id=1,
                invite_code=secrets.token_urlsafe(24),
                registration_enabled=1,
                jwt_secret=secrets.token_urlsafe(48),
            )
            db.add(cfg)
            db.commit()
```

- [ ] **Step 3: 语法 + import 检查**

```bash
cd /Users/mm/wordglass/backend && python3 -m py_compile app/models.py app/db.py && echo "syntax ok"
```

Expected: `syntax ok`

- [ ] **Step 4: 提交**

```bash
cd /Users/mm/wordglass && git add backend/app/models.py backend/app/db.py && git commit -m "$(cat <<'EOF'
db: add User + AppConfig tables, user_id columns to words/reviews/settings

ensure_schema now creates new tables, idempotently adds user_id columns to
existing tables (SQLite-safe ALTER TABLE), and seeds the AppConfig singleton
with a random invite_code and jwt_secret on first boot. Word.text no longer
has a UNIQUE constraint — multiple users can each have their own copy of the
same word.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: security.py（hash/JWT 工具）

**Files:**
- Create: `backend/app/security.py`

**Spec ref:** §3.1

- [ ] **Step 1: 创建 `backend/app/security.py`**

```python
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
```

- [ ] **Step 2: 语法检查**（这一步要装好依赖才能 import，先只编译）

```bash
cd /Users/mm/wordglass/backend && python3 -m py_compile app/security.py && echo "syntax ok"
```

Expected: `syntax ok`

- [ ] **Step 3: 提交**

```bash
cd /Users/mm/wordglass && git add backend/app/security.py && git commit -m "$(cat <<'EOF'
security: bcrypt password hashing + PyJWT encode/decode helpers

hash_password / verify_password wrap passlib's bcrypt with cost=12.
encode_jwt returns a 30-day token when remember=True, else 12h.
decode_jwt returns user_id or None on any error (invalid/expired).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: auth.py 重写（JWT 注入 User）

**Files:**
- Modify: `backend/app/auth.py`

**Spec ref:** §3.2

- [ ] **Step 1: 用以下内容完整替换 `backend/app/auth.py`**

```python
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
```

- [ ] **Step 2: 语法检查**

```bash
cd /Users/mm/wordglass/backend && python3 -m py_compile app/auth.py && echo "syntax ok"
```

Expected: `syntax ok`

- [ ] **Step 3: 提交**

```bash
cd /Users/mm/wordglass && git add backend/app/auth.py && git commit -m "$(cat <<'EOF'
auth: replace AUTH_TOKEN with JWT-backed current_user dependency

current_user decodes the Bearer JWT against the app_config.jwt_secret and
loads the User row. admin_only adds the is_admin check. verify_token kept as
an alias so existing routes keep compiling while we migrate them one by one.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: routes/auth.py（setup / login / register / me）

**Files:**
- Modify: `backend/app/settings_store.py`（加 `normalize_username`）
- Create: `backend/app/routes/auth.py`

**Spec ref:** §4.1, §4.3

- [ ] **Step 1: 在 `backend/app/settings_store.py` 顶部追加 normalize_username 函数**

把：

```python
"""Settings persistence + access. DB row is the source of truth; .env is fallback."""

from __future__ import annotations

from sqlalchemy.orm import Session

from .config import settings as env_settings
from .models import Setting
```

改成：

```python
"""Settings persistence + access. DB row is the source of truth; .env is fallback."""

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
```

- [ ] **Step 2: 创建 `backend/app/routes/auth.py`**

```python
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
```

- [ ] **Step 3: 语法检查**

```bash
cd /Users/mm/wordglass/backend && python3 -m py_compile app/settings_store.py app/routes/auth.py && echo "syntax ok"
```

Expected: `syntax ok`

- [ ] **Step 4: 提交**

```bash
cd /Users/mm/wordglass && git add backend/app/settings_store.py backend/app/routes/auth.py && git commit -m "$(cat <<'EOF'
routes/auth: setup-status, setup, login, register, me

Setup is one-shot: only callable when zero users exist; the resulting admin
adopts all orphan rows (Word/ReviewLog/Setting with user_id IS NULL). Login
returns a 30-day JWT (12h when remember=false). Register requires the
invite_code stored in app_config.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: routes/admin.py

**Files:**
- Create: `backend/app/routes/admin.py`

**Spec ref:** §4.2

- [ ] **Step 1: 创建 `backend/app/routes/admin.py`**

```python
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
```

- [ ] **Step 2: 语法检查 + 提交**

```bash
cd /Users/mm/wordglass/backend && python3 -m py_compile app/routes/admin.py && echo "syntax ok"
cd /Users/mm/wordglass && git add backend/app/routes/admin.py && git commit -m "$(cat <<'EOF'
routes/admin: invite code mgmt + registration toggle + user list

All endpoints require is_admin via the admin_only dep. Invite codes are
random_token(24) — admin can regenerate at any time.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: words.py user-scoping

**Files:**
- Modify: `backend/app/routes/words.py`

**Spec ref:** §5.1, §5.6

- [ ] **Step 1: 编辑 `backend/app/routes/words.py`**

把 `from ..auth import verify_token` 改成 `from ..auth import current_user`。

把 router 定义里的 `dependencies=[Depends(verify_token)]` 改成 `dependencies=[Depends(current_user)]`：

```python
router = APIRouter(prefix="/api/words", tags=["words"], dependencies=[Depends(current_user)])
```

实际上更彻底的做法是让每个 endpoint 显式声明 `user: User = Depends(current_user)`，因为我们需要 user.id 来过滤。**保留 router 级依赖**（确保所有路由都需要登录），**但每个 endpoint 仍要参数 `user: User = Depends(current_user)` 拿用户实例**。FastAPI 不会重复调用同一个依赖（一次请求里 `current_user` 被复用）。

修改 `/preview` 端点（GET，不写）：

```python
from ..models import Example, User, Word


@router.get("/preview")
def preview_word(
    text: str = Query(..., min_length=1, max_length=80),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    hit = lookup_ecdict(text.strip().lower())
    if hit is None:
        return {"found": False, "text": text}
    existing = db.query(Word.id).filter(
        Word.text == hit["text"], Word.user_id == user.id
    ).first()
    return {
        "found": True,
        "text": hit["text"],
        "phonetic": hit["phonetic"],
        "pos": hit["pos"],
        "translation": hit["translation"],
        "already_saved": existing is not None,
    }
```

修改 `add_word`：

```python
@router.post("", response_model=WordOut)
async def add_word(
    payload: WordCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    text = payload.text.strip().lower()
    existing = db.query(Word).filter(Word.text == text, Word.user_id == user.id).first()
    if existing:
        return existing

    local = lookup_local(text)
    if local is not None:
        word = Word(
            user_id=user.id,
            text=local["text"],
            phonetic=local["phonetic"],
            pos=local["pos"],
            translation=local["translation"],
            category="",
        )
        for ex in local["examples"]:
            word.examples.append(Example(en=ex["en"], zh=ex.get("zh", "")))
        db.add(word)
        db.commit()
        db.refresh(word)

        settings_row = get_settings(db, user.id)
        if is_configured(settings_row):
            need_category = True
            need_examples = len(word.examples) == 0
            if need_category or need_examples:
                background_tasks.add_task(
                    _enrich_word, word.id, user.id, need_category, need_examples
                )
        return word

    try:
        ai_payload = await fetch_word_payload(text, db, user.id)
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))

    word = Word(
        user_id=user.id,
        text=ai_payload.get("text", text),
        phonetic=ai_payload.get("phonetic", ""),
        pos=ai_payload.get("pos", ""),
        translation=ai_payload.get("translation", ""),
        category=ai_payload.get("category", ""),
    )
    for ex in ai_payload.get("examples", []):
        word.examples.append(Example(en=ex["en"], zh=ex.get("zh", "")))

    db.add(word)
    db.commit()
    db.refresh(word)
    return word
```

修改 `_enrich_word` 签名加 user_id 参数：

```python
async def _enrich_word(word_id: int, user_id: int, do_category: bool, do_examples: bool) -> None:
    db = SessionLocal()
    try:
        word = db.get(Word, word_id)
        if word is None or word.user_id != user_id:
            return
        if do_category and not (word.category or ""):
            cat = await categorize_word(word.text, db, user_id)
            if cat:
                word.category = cat
                db.commit()
        if do_examples and not word.examples:
            examples = await generate_examples(word.text, word.translation or "", db, user_id)
            if examples:
                for ex in examples:
                    word.examples.append(Example(en=ex["en"], zh=ex.get("zh", "")))
                db.commit()
    finally:
        db.close()
```

（`categorize_word` / `generate_examples` 在 `app/ai.py` 里也要加 user_id 参数 —— 见 Task 10。）

修改 `categories`：

```python
@router.get("/categories")
def categories(db: Session = Depends(get_db), user: User = Depends(current_user)):
    rows = (
        db.query(Word.category, func.count(Word.id))
        .filter(Word.user_id == user.id)
        .group_by(Word.category)
        .all()
    )
    counts: dict[str, int] = {cat: 0 for cat in CATEGORIES}
    counts["未分类"] = 0
    for cat, count in rows:
        key = cat or "未分类"
        counts[key] = counts.get(key, 0) + count
    return {"counts": counts, "order": ["未分类"] + CATEGORIES}
```

修改 `recategorize`：

```python
@router.post("/recategorize")
async def recategorize(db: Session = Depends(get_db), user: User = Depends(current_user)):
    uncategorized = db.query(Word).filter(
        Word.user_id == user.id,
        (Word.category == "") | (Word.category.is_(None)),
    ).all()
    if not uncategorized:
        return {"updated": 0, "total": 0}

    BATCH = 20
    updated = 0
    for i in range(0, len(uncategorized), BATCH):
        chunk = uncategorized[i : i + BATCH]
        words = [w.text for w in chunk]
        try:
            results = await categorize_words_batch(words, db, user.id)
        except RuntimeError as e:
            raise HTTPException(status_code=502, detail=str(e))
        for w in chunk:
            cat = results.get(w.text.lower())
            if cat:
                w.category = cat
                updated += 1
    db.commit()
    return {"updated": updated, "total": len(uncategorized)}
```

修改 `list_words`：

```python
@router.get("", response_model=list[WordBrief])
def list_words(
    q: str | None = Query(default=None),
    category: str | None = Query(default=None),
    mastery: int | None = Query(default=None, ge=0, le=5),
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    query = db.query(Word).filter(Word.user_id == user.id)
    if q:
        like = f"%{q.lower()}%"
        query = query.filter(func.lower(Word.text).like(like) | Word.translation.like(f"%{q}%"))
    if category is not None:
        if category == "未分类":
            query = query.filter((Word.category == "") | (Word.category.is_(None)))
        else:
            query = query.filter(Word.category == category)
    if mastery is not None:
        query = query.filter(Word.mastery == mastery)
    return query.order_by(desc(Word.created_at)).offset(offset).limit(limit).all()
```

修改 `get_word`：

```python
@router.get("/{word_id}", response_model=WordOut)
def get_word(word_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    w = db.get(Word, word_id)
    if not w or w.user_id != user.id:
        raise HTTPException(status_code=404, detail="word not found")
    return w
```

修改 `delete_word`：

```python
@router.delete("/{word_id}")
def delete_word(word_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    w = db.get(Word, word_id)
    if not w or w.user_id != user.id:
        raise HTTPException(status_code=404, detail="word not found")
    db.delete(w)
    db.commit()
    return {"ok": True}
```

修改 `word_usage_stream`：

```python
@router.post("/usage")
async def word_usage_stream(
    payload: UsageIn,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    row = get_settings(db, user.id)
    if not is_configured(row):
        raise HTTPException(status_code=502, detail="AI 未配置，无法生成用法解释。在右上角 ⚙ 设置中配一个 AI provider 再试。")
    # rest unchanged
```

`offline_status` 不需要 user 过滤（全局只读），保留 router 级 current_user 依赖即可。

- [ ] **Step 2: 语法检查 + 提交**

```bash
cd /Users/mm/wordglass/backend && python3 -m py_compile app/routes/words.py && echo "syntax ok"
cd /Users/mm/wordglass && git add backend/app/routes/words.py && git commit -m "$(cat <<'EOF'
routes/words: scope all queries/inserts to current_user

Word.user_id is now required on insert and filter on every read/update/delete.
_enrich_word background task carries user_id explicitly. ai.categorize_word /
generate_examples / fetch_word_payload signatures updated to take user_id —
those are implemented in Task 10.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: review.py user-scoping

**Files:**
- Modify: `backend/app/routes/review.py`

**Spec ref:** §5.2

- [ ] **Step 1: 用以下内容完整替换 `backend/app/routes/review.py`**

```python
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import current_user
from ..db import get_db
from ..models import ReviewLog, User, Word
from ..review import apply_review
from ..schemas import ReviewIn, WordOut

router = APIRouter(prefix="/api/review", tags=["review"], dependencies=[Depends(current_user)])


@router.get("/due", response_model=list[WordOut])
def due_words(
    limit: int = 50,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    now = datetime.utcnow()
    return (
        db.query(Word)
        .filter(Word.user_id == user.id, Word.next_review_at <= now)
        .order_by(Word.next_review_at.asc())
        .limit(limit)
        .all()
    )


@router.post("")
def submit_review(
    payload: ReviewIn,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    word = db.get(Word, payload.word_id)
    if not word or word.user_id != user.id:
        raise HTTPException(status_code=404, detail="word not found")

    new_mastery, next_at = apply_review(word.mastery, payload.result)
    word.mastery = new_mastery
    word.next_review_at = next_at
    word.review_count += 1
    if payload.result in {"good", "easy"}:
        word.correct_count += 1

    db.add(ReviewLog(user_id=user.id, word_id=word.id, mode=payload.mode, result=payload.result))
    db.commit()
    db.refresh(word)
    return {
        "ok": True,
        "mastery": word.mastery,
        "next_review_at": word.next_review_at.isoformat(),
    }
```

- [ ] **Step 2: 语法检查 + 提交**

```bash
cd /Users/mm/wordglass/backend && python3 -m py_compile app/routes/review.py && echo "syntax ok"
cd /Users/mm/wordglass && git add backend/app/routes/review.py && git commit -m "$(cat <<'EOF'
routes/review: scope due-queue + submit-review to current_user

ReviewLog rows carry user_id; due/submit endpoints filter by Word.user_id ==
user.id so users only see and review their own words.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: stats.py user-scoping

**Files:**
- Modify: `backend/app/routes/stats.py`

**Spec ref:** §5.3

- [ ] **Step 1: 用以下内容完整替换 `backend/app/routes/stats.py`**

```python
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import Date, cast, func
from sqlalchemy.orm import Session

from ..auth import current_user
from ..db import get_db
from ..models import ReviewLog, User, Word
from ..schemas import StatsOut

router = APIRouter(prefix="/api/stats", tags=["stats"], dependencies=[Depends(current_user)])


@router.get("", response_model=StatsOut)
def stats(db: Session = Depends(get_db), user: User = Depends(current_user)):
    now = datetime.utcnow()
    week_ago = now - timedelta(days=7)
    base = db.query(Word).filter(Word.user_id == user.id)
    total = base.count()
    due = base.filter(Word.next_review_at <= now).count()
    mastered = base.filter(Word.mastery >= 5).count()
    week = base.filter(Word.created_at >= week_ago).count()
    return StatsOut(total=total, due_today=due, mastered=mastered, added_this_week=week)


@router.get("/heatmap")
def heatmap(
    days: int = Query(default=35, ge=7, le=180),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    """Daily activity (adds + reviews) for the heatmap calendar widget."""
    since = datetime.utcnow() - timedelta(days=days)

    reviews = (
        db.query(cast(ReviewLog.reviewed_at, Date), func.count())
        .filter(ReviewLog.user_id == user.id, ReviewLog.reviewed_at >= since)
        .group_by(cast(ReviewLog.reviewed_at, Date))
        .all()
    )
    adds = (
        db.query(cast(Word.created_at, Date), func.count())
        .filter(Word.user_id == user.id, Word.created_at >= since)
        .group_by(cast(Word.created_at, Date))
        .all()
    )

    by_day: dict[str, int] = {}
    for d, c in reviews:
        by_day[str(d)] = by_day.get(str(d), 0) + c
    for d, c in adds:
        by_day[str(d)] = by_day.get(str(d), 0) + c

    return {"days": by_day, "since": since.date().isoformat()}
```

- [ ] **Step 2: 语法检查 + 提交**

```bash
cd /Users/mm/wordglass/backend && python3 -m py_compile app/routes/stats.py && echo "syntax ok"
cd /Users/mm/wordglass && git add backend/app/routes/stats.py && git commit -m "stats: per-user counts and heatmap

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 9: settings_store.py + settings.py 改 per-user

**Files:**
- Modify: `backend/app/settings_store.py`
- Modify: `backend/app/routes/settings.py`

**Spec ref:** §5.4

- [ ] **Step 1: 改 `settings_store.py` 让 `get_settings` 按 user_id 取行**

```python
"""Settings persistence + access. Per-user: each user has one Setting row."""

from __future__ import annotations

import re

from sqlalchemy.orm import Session

from .config import settings as env_settings
from .models import Setting


_USERNAME_RE = re.compile(r"^[a-z0-9_]{3,20}$")


def normalize_username(raw: str) -> str:
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
```

- [ ] **Step 2: 改 `routes/settings.py` 所有 endpoint 加 `current_user` + 用 user.id 调用**

把 `from ..auth import verify_token` 改 `from ..auth import current_user`；
router 级 `dependencies=[Depends(verify_token)]` 改成 `dependencies=[Depends(current_user)]`；
每个 endpoint 加 `user: User = Depends(current_user)`，调 `get_settings(db, user.id)` / `update_settings(db, user.id, ...)`。

`/test` 和 `/curl` 端点已经接受 SettingsIn 作为 input，逻辑内部 fallback 也要换：`row = get_settings(db, user.id)`。

`from ..models import User` 加 import。

具体：每个引用 `get_settings(db)` 的地方改成 `get_settings(db, user.id)`；引用 `update_settings(db, ...)` 改成 `update_settings(db, user.id, ...)`。

`logs/ai`、`logs/system` 等日志端点：日志是全局的（不分用户），不需要 user 过滤，但仍然要 `current_user` 依赖（router 级已经覆盖）。

- [ ] **Step 3: 语法检查 + 提交**

```bash
cd /Users/mm/wordglass/backend && python3 -m py_compile app/settings_store.py app/routes/settings.py && echo "syntax ok"
cd /Users/mm/wordglass && git add backend/app/settings_store.py backend/app/routes/settings.py && git commit -m "settings: per-user AI config

get_settings / update_settings now take user_id; each user has their own
provider/base_url/key/model row.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 10: translate.py + ai.py user-scoping

**Files:**
- Modify: `backend/app/routes/translate.py`
- Modify: `backend/app/ai.py`

**Spec ref:** §5.5

- [ ] **Step 1: `ai.py` 改签名**

把所有读 settings 的函数加 user_id 参数：

`lookup_local(word)` — 不改（纯本地 ECDICT 查询，无 AI）
`fetch_word_payload(word, db)` → `fetch_word_payload(word, db, user_id)` → `get_settings(db, user_id)`
`categorize_word(word, db)` → `categorize_word(word, db, user_id)`
`generate_examples(word, translation, db)` → `(word, translation, db, user_id)`
`categorize_words_batch(words, db)` → `(words, db, user_id)`

具体修改：每个函数体内的 `get_settings(db)` 改 `get_settings(db, user_id)`。

- [ ] **Step 2: `translate.py` 改 endpoint 用 current_user**

```python
from ..auth import current_user
from ..models import User

# router 改成
router = APIRouter(prefix="/api/translate", tags=["translate"], dependencies=[Depends(current_user)])

# translate / translate_stream 加 user 参数
@router.post("", response_model=TranslateOut)
async def translate(payload: TranslateIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    row = get_settings(db, user.id)
    # 其余不变
    ...


@router.post("/stream")
async def translate_stream(payload: TranslateIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    row = get_settings(db, user.id)
    # 其余不变
    ...
```

- [ ] **Step 3: 语法检查 + 提交**

```bash
cd /Users/mm/wordglass/backend && python3 -m py_compile app/routes/translate.py app/ai.py && echo "syntax ok"
cd /Users/mm/wordglass && git add backend/app/routes/translate.py backend/app/ai.py && git commit -m "translate + ai: pick provider from per-user settings

All AI helpers now take user_id so they can resolve the correct settings row.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 11: main.py + requirements.txt

**Files:**
- Modify: `backend/app/main.py`
- Modify: `backend/requirements.txt`

**Spec ref:** §6

- [ ] **Step 1: 用以下内容完整替换 `backend/app/main.py`**

```python
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .db import Base, engine, ensure_schema
from .routes import admin, auth, review, settings, stats, translate, words


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    ensure_schema()
    yield


app = FastAPI(title="WordGlass API", version="0.4.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(words.router)
app.include_router(review.router)
app.include_router(stats.router)
app.include_router(settings.router)
app.include_router(translate.router)


@app.get("/api/health")
def health():
    return {"ok": True}
```

- [ ] **Step 2: 修改 `backend/requirements.txt` 追加依赖**

读文件，在末尾追加：

```
pyjwt==2.9.0
passlib[bcrypt]==1.7.4
bcrypt==4.2.0
```

- [ ] **Step 3: 验证 import**

```bash
cd /Users/mm/wordglass/backend && python3 -m py_compile app/main.py && echo "syntax ok"
```

Expected: `syntax ok`

- [ ] **Step 4: 提交**

```bash
cd /Users/mm/wordglass && git add backend/app/main.py backend/requirements.txt && git commit -m "main: register auth + admin routers; deps: pyjwt + passlib[bcrypt]

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 12: 前端 api.ts JWT key + 新方法

**Files:**
- Modify: `frontend/src/api.ts`

**Spec ref:** §11, §7.2

- [ ] **Step 1: 改 token key 名 + 401 触发跳转**

把：

```typescript
const TOKEN_KEY = "wordglass.token";
```

改成：

```typescript
const TOKEN_KEY = "wordglass.jwt";
```

把 `request<T>` 函数里 401 处理改成 dispatch `wordglass:unauth` 事件（已经有 `wordglass:api-error` 通用事件，我们再 dispatch 一个专门的）：

把：

```typescript
    if (typeof window !== "undefined") {
      window.dispatchEvent(
        new CustomEvent("wordglass:api-error", { detail: { status: resp.status, message: detail } })
      );
    }
    throw new ApiError(detail, resp.status);
```

改成：

```typescript
    if (typeof window !== "undefined") {
      window.dispatchEvent(
        new CustomEvent("wordglass:api-error", { detail: { status: resp.status, message: detail } })
      );
      if (resp.status === 401) {
        window.dispatchEvent(new CustomEvent("wordglass:unauth"));
      }
    }
    throw new ApiError(detail, resp.status);
```

- [ ] **Step 2: 在文件末尾的 `export const api = { ... }` 内追加 auth + admin 方法（在最后一个方法后、`};` 前）**

```typescript

  // ── Auth (v0.4) ──────────────────────────────────────────────
  setupStatus: () =>
    request<{ needs_setup: boolean; registration_enabled: boolean }>("/api/auth/setup-status"),

  setup: (username: string, password: string) =>
    request<{ token: string; username: string; is_admin: boolean }>(
      "/api/auth/setup",
      { method: "POST", body: JSON.stringify({ username, password }) },
    ),

  login: (username: string, password: string, remember: boolean) =>
    request<{ token: string; username: string; is_admin: boolean }>(
      "/api/auth/login",
      { method: "POST", body: JSON.stringify({ username, password, remember }) },
    ),

  register: (username: string, password: string, invite_code: string) =>
    request<{ token: string; username: string; is_admin: boolean }>(
      "/api/auth/register",
      { method: "POST", body: JSON.stringify({ username, password, invite_code }) },
    ),

  me: () =>
    request<{ id: number; username: string; is_admin: boolean }>("/api/auth/me"),

  // ── Admin (v0.4) ─────────────────────────────────────────────
  getInvite: () =>
    request<{ invite_code: string; registration_enabled: boolean }>("/api/admin/invite"),

  regenerateInvite: () =>
    request<{ invite_code: string; registration_enabled: boolean }>(
      "/api/admin/invite/regenerate",
      { method: "POST" },
    ),

  setRegistration: (enabled: boolean) =>
    request<{ invite_code: string; registration_enabled: boolean }>(
      "/api/admin/registration",
      { method: "PUT", body: JSON.stringify({ enabled }) },
    ),

  listUsers: () =>
    request<{ items: Array<{ id: number; username: string; is_admin: boolean; created_at: string; last_login_at: string | null }> }>(
      "/api/admin/users",
    ),
```

- [ ] **Step 3: 跑 build**

```bash
cd /Users/mm/wordglass/frontend && npm run build 2>&1 | tail -3
```

Expected: 通过。

- [ ] **Step 4: 提交**

```bash
cd /Users/mm/wordglass && git add frontend/src/api.ts && git commit -m "api: rename token key to wordglass.jwt; add auth + admin methods

401 responses now dispatch wordglass:unauth so the router/guard can redirect
to /login without each caller handling it.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 13: composables/auth.ts

**Files:**
- Create: `frontend/src/composables/auth.ts`

**Spec ref:** §7.1

- [ ] **Step 1: 创建文件**

```typescript
import { computed, ref } from "vue";

const TOKEN_KEY = "wordglass.jwt";
const USER_KEY = "wordglass.user";

export interface CurrentUser {
  id: number;
  username: string;
  is_admin: boolean;
}

const _token = ref<string>(localStorage.getItem(TOKEN_KEY) || "");
const _user = ref<CurrentUser | null>(
  (() => {
    try {
      const raw = localStorage.getItem(USER_KEY);
      return raw ? (JSON.parse(raw) as CurrentUser) : null;
    } catch {
      return null;
    }
  })(),
);

export function useAuth() {
  return {
    token: computed(() => _token.value),
    user: computed(() => _user.value),
    isAuthed: computed(() => !!_token.value && !!_user.value),
    isAdmin: computed(() => !!_user.value?.is_admin),
    setSession(token: string, user: CurrentUser) {
      _token.value = token;
      _user.value = user;
      localStorage.setItem(TOKEN_KEY, token);
      localStorage.setItem(USER_KEY, JSON.stringify(user));
    },
    clearSession() {
      _token.value = "";
      _user.value = null;
      localStorage.removeItem(TOKEN_KEY);
      localStorage.removeItem(USER_KEY);
    },
  };
}
```

- [ ] **Step 2: 跑 build + 提交**

```bash
cd /Users/mm/wordglass/frontend && npm run build 2>&1 | tail -3
cd /Users/mm/wordglass && git add frontend/src/composables/auth.ts && git commit -m "composables/auth: useAuth() with token/user reactive state + localStorage persistence

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 14: router.ts 加路由 + 守卫

**Files:**
- Modify: `frontend/src/router.ts`

**Spec ref:** §7.3

- [ ] **Step 1: 用以下内容完整替换 `frontend/src/router.ts`**

```typescript
import { createRouter, createWebHistory } from "vue-router";

import { api } from "./api";
import { useAuth } from "./composables/auth";

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/", name: "dashboard", component: () => import("./views/Dashboard.vue"), meta: { auth: true } },
    { path: "/reader", name: "reader", component: () => import("./views/Reader.vue"), meta: { auth: true } },
    { path: "/library", name: "library", component: () => import("./views/Library.vue"), meta: { auth: true } },
    { path: "/practice", name: "practice", component: () => import("./views/Practice.vue"), meta: { auth: true } },
    { path: "/settings", name: "settings", component: () => import("./views/Settings.vue"), meta: { auth: true } },
    { path: "/login", name: "login", component: () => import("./views/Login.vue"), meta: { public: true } },
    { path: "/register", name: "register", component: () => import("./views/Register.vue"), meta: { public: true } },
    { path: "/setup", name: "setup", component: () => import("./views/Setup.vue"), meta: { public: true } },
  ],
});

let setupCache: { needs_setup: boolean; registration_enabled: boolean } | null = null;
async function checkSetup() {
  if (setupCache !== null) return setupCache;
  try {
    setupCache = await api.setupStatus();
  } catch {
    setupCache = { needs_setup: false, registration_enabled: true };
  }
  return setupCache;
}

router.beforeEach(async (to) => {
  // Public routes always allowed
  if (to.meta.public) {
    // But: if user lands on /login or /register while setup is needed, redirect to /setup
    const s = await checkSetup();
    if (s.needs_setup && to.name !== "setup") {
      return { name: "setup" };
    }
    return true;
  }

  // Auth-required route
  const auth = useAuth();
  const s = await checkSetup();
  if (s.needs_setup) {
    return { name: "setup" };
  }
  if (!auth.isAuthed.value) {
    return { name: "login", query: { next: to.fullPath } };
  }
  return true;
});

// React to global 401 events (dispatched by api.ts) — clear session + go to login
window.addEventListener("wordglass:unauth", () => {
  const auth = useAuth();
  auth.clearSession();
  setupCache = null;
  if (router.currentRoute.value.name !== "login" && router.currentRoute.value.name !== "setup") {
    router.replace({ name: "login", query: { next: router.currentRoute.value.fullPath } });
  }
});
```

- [ ] **Step 2: build + 提交**

```bash
cd /Users/mm/wordglass/frontend && npm run build 2>&1 | tail -3
cd /Users/mm/wordglass && git add frontend/src/router.ts && git commit -m "router: auth + setup guard, redirect to /login on 401

Routes flagged meta.public bypass the guard. checkSetup() short-circuits all
routing to /setup if the server has zero users. 'wordglass:unauth' window
event (dispatched by api.ts on 401) clears the session and redirects.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 15: Login.vue + Register.vue + Setup.vue

**Files:**
- Create: `frontend/src/views/Login.vue`
- Create: `frontend/src/views/Register.vue`
- Create: `frontend/src/views/Setup.vue`

**Spec ref:** §8

三个页面共享 layout，CSS 复制三遍（避免抽组件）。

- [ ] **Step 1: 创建 `Login.vue`**

```vue
<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRoute, useRouter, RouterLink } from "vue-router";
import { api } from "../api";
import { useAuth } from "../composables/auth";

const route = useRoute();
const router = useRouter();
const { setSession } = useAuth();

const username = ref("");
const password = ref("");
const remember = ref(true);
const loading = ref(false);
const error = ref("");

async function submit() {
  if (!username.value || !password.value) return;
  loading.value = true;
  error.value = "";
  try {
    const r = await api.login(username.value, password.value, remember.value);
    setSession(r.token, { id: 0, username: r.username, is_admin: r.is_admin });
    try {
      const me = await api.me();
      setSession(r.token, me);
    } catch { /* keep partial */ }
    const next = (route.query.next as string) || "/";
    router.replace(next);
  } catch (e: any) {
    error.value = e.message || "登录失败";
  } finally {
    loading.value = false;
  }
}

onMounted(async () => {
  try {
    const s = await api.setupStatus();
    if (s.needs_setup) router.replace({ name: "setup" });
  } catch { /* network — stay */ }
});
</script>

<template>
  <div class="auth-page">
    <div class="floating-bg">
      <span class="w w1">serendipity</span>
      <span class="w w2">epiphany</span>
      <span class="w w3">resilience</span>
      <span class="w w4">solitude</span>
    </div>
    <div class="auth-card glass-strong">
      <div class="brand-row">
        <span class="brand-dot" />
        <span class="brand-name">WordGlass</span>
      </div>
      <p class="brand-tagline">回到你的英文书。</p>
      <h2 class="form-h">登录</h2>
      <form @submit.prevent="submit">
        <div class="field">
          <label>用户名</label>
          <input v-model="username" class="input" autocomplete="username" autofocus />
        </div>
        <div class="field">
          <label>密码</label>
          <input v-model="password" class="input" type="password" autocomplete="current-password" />
        </div>
        <label class="remember">
          <input type="checkbox" v-model="remember" /> 记住我（30 天）
        </label>
        <div v-if="error" class="error">{{ error }}</div>
        <button type="submit" class="btn btn-primary auth-btn" :disabled="loading">
          {{ loading ? "登录中…" : "登 录" }}
        </button>
      </form>
      <p class="switch-mode">
        没账号？<RouterLink to="/register" class="link">注册（需邀请码）</RouterLink>
      </p>
    </div>
  </div>
</template>

<style scoped>
.auth-page {
  position: relative;
  min-height: 100vh;
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 32px;
}

.floating-bg {
  position: absolute;
  inset: 0;
  pointer-events: none;
  overflow: hidden;
  z-index: 0;
}
.floating-bg .w {
  position: absolute;
  font-family: var(--font-serif);
  font-style: italic;
  color: color-mix(in srgb, var(--brand) 12%, transparent);
  font-weight: 700;
  user-select: none;
}
.floating-bg .w1 { top: 8%; left: 5%; transform: rotate(-8deg); font-size: 64px; }
.floating-bg .w2 { top: 62%; left: 48%; font-size: 82px; }
.floating-bg .w3 { top: 26%; right: 4%; font-size: 54px; transform: rotate(6deg); color: color-mix(in srgb, var(--accent) 16%, transparent); }
.floating-bg .w4 { bottom: 8%; left: 10%; font-size: 48px; color: color-mix(in srgb, var(--accent) 14%, transparent); transform: rotate(-4deg); }

.auth-card {
  position: relative;
  z-index: 2;
  width: 100%;
  max-width: 380px;
  padding: 36px 36px 30px;
}

.brand-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 4px;
}
.brand-dot {
  width: 22px;
  height: 28px;
  border-radius: 3px;
  background: linear-gradient(180deg, var(--brand) 0%, var(--accent) 100%);
  box-shadow: 0 2px 6px rgba(50, 60, 40, 0.25);
  position: relative;
  flex-shrink: 0;
}
.brand-dot::after {
  content: "";
  position: absolute;
  left: 4px;
  right: 4px;
  top: 5px;
  height: 1px;
  background: rgba(255, 255, 255, 0.45);
  box-shadow: 0 4px 0 rgba(255, 255, 255, 0.30), 0 8px 0 rgba(255, 255, 255, 0.20);
}
.brand-name {
  font-family: var(--font-serif);
  font-size: 22px;
  font-weight: 700;
}

.brand-tagline {
  font-size: 12px;
  color: var(--text-secondary);
  margin: 4px 0 22px;
}

.form-h {
  font-family: var(--font-serif);
  font-size: 24px;
  font-weight: 700;
  margin: 0 0 18px;
}

.field {
  margin-bottom: 12px;
}
.field label {
  display: block;
  font-size: 11px;
  font-weight: 600;
  color: var(--text-secondary);
  margin-bottom: 4px;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

.remember {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--text-secondary);
  cursor: pointer;
  margin: 6px 0 14px;
}

.auth-btn {
  width: 100%;
  margin-top: 8px;
}

.error {
  color: var(--danger);
  font-size: 12.5px;
  padding: 8px 12px;
  border-radius: 8px;
  background: color-mix(in srgb, var(--danger) 10%, transparent);
  margin: 4px 0 8px;
}

.switch-mode {
  text-align: center;
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: 14px;
}
.link {
  color: var(--brand);
  text-decoration: none;
  font-weight: 600;
}
.link:hover { text-decoration: underline; }
</style>
```

- [ ] **Step 2: 创建 `Register.vue`** — 同样 layout，多 invite_code 字段

```vue
<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRouter, RouterLink } from "vue-router";
import { api } from "../api";
import { useAuth } from "../composables/auth";

const router = useRouter();
const { setSession } = useAuth();

const username = ref("");
const password = ref("");
const inviteCode = ref("");
const loading = ref(false);
const error = ref("");
const registrationEnabled = ref(true);

async function submit() {
  if (!username.value || !password.value || !inviteCode.value) return;
  loading.value = true;
  error.value = "";
  try {
    const r = await api.register(username.value, password.value, inviteCode.value);
    setSession(r.token, { id: 0, username: r.username, is_admin: r.is_admin });
    try {
      const me = await api.me();
      setSession(r.token, me);
    } catch { /* keep partial */ }
    router.replace("/");
  } catch (e: any) {
    error.value = e.message || "注册失败";
  } finally {
    loading.value = false;
  }
}

onMounted(async () => {
  try {
    const s = await api.setupStatus();
    if (s.needs_setup) {
      router.replace({ name: "setup" });
      return;
    }
    registrationEnabled.value = s.registration_enabled;
    if (!s.registration_enabled) {
      error.value = "管理员已关闭注册。请联系管理员获取账号。";
    }
  } catch { /* network */ }
});
</script>

<template>
  <div class="auth-page">
    <div class="floating-bg">
      <span class="w w1">serendipity</span>
      <span class="w w2">epiphany</span>
      <span class="w w3">resilience</span>
      <span class="w w4">solitude</span>
    </div>
    <div class="auth-card glass-strong">
      <div class="brand-row">
        <span class="brand-dot" />
        <span class="brand-name">WordGlass</span>
      </div>
      <p class="brand-tagline">建一个属于你的英文书。</p>
      <h2 class="form-h">注册</h2>
      <form @submit.prevent="submit">
        <div class="field">
          <label>用户名</label>
          <input v-model="username" class="input" autocomplete="username" autofocus
                 placeholder="3-20 位字母数字下划线" />
        </div>
        <div class="field">
          <label>密码</label>
          <input v-model="password" class="input" type="password" autocomplete="new-password"
                 placeholder="至少 6 位" />
        </div>
        <div class="field">
          <label>邀请码</label>
          <input v-model="inviteCode" class="input" type="text" placeholder="向管理员获取" />
        </div>
        <div v-if="error" class="error">{{ error }}</div>
        <button type="submit" class="btn btn-primary auth-btn"
                :disabled="loading || !registrationEnabled">
          {{ loading ? "注册中…" : "创 建 账 号" }}
        </button>
      </form>
      <p class="switch-mode">
        已有账号？<RouterLink to="/login" class="link">直接登录</RouterLink>
      </p>
    </div>
  </div>
</template>

<style scoped>
.auth-page {
  position: relative;
  min-height: 100vh;
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 32px;
}
.floating-bg {
  position: absolute;
  inset: 0;
  pointer-events: none;
  overflow: hidden;
  z-index: 0;
}
.floating-bg .w {
  position: absolute;
  font-family: var(--font-serif);
  font-style: italic;
  color: color-mix(in srgb, var(--brand) 12%, transparent);
  font-weight: 700;
  user-select: none;
}
.floating-bg .w1 { top: 8%; left: 5%; transform: rotate(-8deg); font-size: 64px; }
.floating-bg .w2 { top: 62%; left: 48%; font-size: 82px; }
.floating-bg .w3 { top: 26%; right: 4%; font-size: 54px; transform: rotate(6deg); color: color-mix(in srgb, var(--accent) 16%, transparent); }
.floating-bg .w4 { bottom: 8%; left: 10%; font-size: 48px; color: color-mix(in srgb, var(--accent) 14%, transparent); transform: rotate(-4deg); }

.auth-card { position: relative; z-index: 2; width: 100%; max-width: 380px; padding: 36px 36px 30px; }
.brand-row { display: flex; align-items: center; gap: 10px; margin-bottom: 4px; }
.brand-dot {
  width: 22px; height: 28px; border-radius: 3px;
  background: linear-gradient(180deg, var(--brand) 0%, var(--accent) 100%);
  box-shadow: 0 2px 6px rgba(50, 60, 40, 0.25);
  position: relative; flex-shrink: 0;
}
.brand-dot::after {
  content: ""; position: absolute; left: 4px; right: 4px; top: 5px; height: 1px;
  background: rgba(255, 255, 255, 0.45);
  box-shadow: 0 4px 0 rgba(255, 255, 255, 0.30), 0 8px 0 rgba(255, 255, 255, 0.20);
}
.brand-name { font-family: var(--font-serif); font-size: 22px; font-weight: 700; }
.brand-tagline { font-size: 12px; color: var(--text-secondary); margin: 4px 0 22px; }
.form-h { font-family: var(--font-serif); font-size: 24px; font-weight: 700; margin: 0 0 18px; }
.field { margin-bottom: 12px; }
.field label { display: block; font-size: 11px; font-weight: 600; color: var(--text-secondary); margin-bottom: 4px; letter-spacing: 0.04em; text-transform: uppercase; }
.auth-btn { width: 100%; margin-top: 8px; }
.error { color: var(--danger); font-size: 12.5px; padding: 8px 12px; border-radius: 8px; background: color-mix(in srgb, var(--danger) 10%, transparent); margin: 4px 0 8px; }
.switch-mode { text-align: center; font-size: 12px; color: var(--text-secondary); margin-top: 14px; }
.link { color: var(--brand); text-decoration: none; font-weight: 600; }
.link:hover { text-decoration: underline; }
</style>
```

- [ ] **Step 3: 创建 `Setup.vue`** — 首装管理员

```vue
<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { api } from "../api";
import { useAuth } from "../composables/auth";

const router = useRouter();
const { setSession } = useAuth();

const username = ref("");
const password = ref("");
const password2 = ref("");
const loading = ref(false);
const error = ref("");

async function submit() {
  if (!username.value || !password.value) return;
  if (password.value !== password2.value) {
    error.value = "两次输入的密码不一致";
    return;
  }
  loading.value = true;
  error.value = "";
  try {
    const r = await api.setup(username.value, password.value);
    setSession(r.token, { id: 0, username: r.username, is_admin: r.is_admin });
    try {
      const me = await api.me();
      setSession(r.token, me);
    } catch { /* keep partial */ }
    router.replace("/");
  } catch (e: any) {
    error.value = e.message || "初始化失败";
  } finally {
    loading.value = false;
  }
}

onMounted(async () => {
  try {
    const s = await api.setupStatus();
    if (!s.needs_setup) {
      router.replace({ name: "login" });
    }
  } catch { /* network */ }
});
</script>

<template>
  <div class="auth-page">
    <div class="floating-bg">
      <span class="w w1">serendipity</span>
      <span class="w w2">epiphany</span>
      <span class="w w3">resilience</span>
      <span class="w w4">solitude</span>
    </div>
    <div class="auth-card glass-strong">
      <div class="brand-row">
        <span class="brand-dot" />
        <span class="brand-name">WordGlass</span>
      </div>
      <p class="brand-tagline">首次使用 · 创建管理员账号</p>
      <h2 class="form-h">👑 初始化</h2>
      <p class="muted small intro">
        这是首次访问，请创建管理员账号。之后所有现有数据（如果有）会归到这个账号下。
      </p>
      <form @submit.prevent="submit">
        <div class="field">
          <label>管理员用户名</label>
          <input v-model="username" class="input" autocomplete="username" autofocus
                 placeholder="3-20 位字母数字下划线" />
        </div>
        <div class="field">
          <label>密码</label>
          <input v-model="password" class="input" type="password" autocomplete="new-password"
                 placeholder="至少 6 位" />
        </div>
        <div class="field">
          <label>再次输入密码</label>
          <input v-model="password2" class="input" type="password" autocomplete="new-password" />
        </div>
        <div v-if="error" class="error">{{ error }}</div>
        <button type="submit" class="btn btn-primary auth-btn" :disabled="loading">
          {{ loading ? "创建中…" : "完成初始化" }}
        </button>
      </form>
    </div>
  </div>
</template>

<style scoped>
.auth-page {
  position: relative;
  min-height: 100vh;
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 32px;
}
.floating-bg {
  position: absolute;
  inset: 0;
  pointer-events: none;
  overflow: hidden;
  z-index: 0;
}
.floating-bg .w {
  position: absolute;
  font-family: var(--font-serif);
  font-style: italic;
  color: color-mix(in srgb, var(--brand) 12%, transparent);
  font-weight: 700;
  user-select: none;
}
.floating-bg .w1 { top: 8%; left: 5%; transform: rotate(-8deg); font-size: 64px; }
.floating-bg .w2 { top: 62%; left: 48%; font-size: 82px; }
.floating-bg .w3 { top: 26%; right: 4%; font-size: 54px; transform: rotate(6deg); color: color-mix(in srgb, var(--accent) 16%, transparent); }
.floating-bg .w4 { bottom: 8%; left: 10%; font-size: 48px; color: color-mix(in srgb, var(--accent) 14%, transparent); transform: rotate(-4deg); }

.auth-card { position: relative; z-index: 2; width: 100%; max-width: 420px; padding: 36px 36px 30px; }
.brand-row { display: flex; align-items: center; gap: 10px; margin-bottom: 4px; }
.brand-dot {
  width: 22px; height: 28px; border-radius: 3px;
  background: linear-gradient(180deg, var(--brand) 0%, var(--accent) 100%);
  box-shadow: 0 2px 6px rgba(50, 60, 40, 0.25);
  position: relative; flex-shrink: 0;
}
.brand-dot::after {
  content: ""; position: absolute; left: 4px; right: 4px; top: 5px; height: 1px;
  background: rgba(255, 255, 255, 0.45);
  box-shadow: 0 4px 0 rgba(255, 255, 255, 0.30), 0 8px 0 rgba(255, 255, 255, 0.20);
}
.brand-name { font-family: var(--font-serif); font-size: 22px; font-weight: 700; }
.brand-tagline { font-size: 12px; color: var(--text-secondary); margin: 4px 0 22px; }
.form-h { font-family: var(--font-serif); font-size: 24px; font-weight: 700; margin: 0 0 8px; }
.intro { margin: 0 0 16px; font-size: 12px; color: var(--text-secondary); line-height: 1.55; }
.muted { color: var(--text-secondary); }
.small { font-size: 12px; }
.field { margin-bottom: 12px; }
.field label { display: block; font-size: 11px; font-weight: 600; color: var(--text-secondary); margin-bottom: 4px; letter-spacing: 0.04em; text-transform: uppercase; }
.auth-btn { width: 100%; margin-top: 8px; }
.error { color: var(--danger); font-size: 12.5px; padding: 8px 12px; border-radius: 8px; background: color-mix(in srgb, var(--danger) 10%, transparent); margin: 4px 0 8px; }
</style>
```

- [ ] **Step 4: build + 提交**

```bash
cd /Users/mm/wordglass/frontend && npm run build 2>&1 | tail -3
cd /Users/mm/wordglass && git add frontend/src/views/Login.vue frontend/src/views/Register.vue frontend/src/views/Setup.vue && git commit -m "views: Login / Register / Setup pages (floating-words layout)

Three auth pages share the same centered glass-card on italic-serif floating
words background. Setup is one-shot — only reachable when zero users exist.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 16: App.vue 条件 sidebar

**Files:**
- Modify: `frontend/src/App.vue`

**Spec ref:** §7.4

- [ ] **Step 1: 用以下完整内容替换 `frontend/src/App.vue`**

```vue
<script setup lang="ts">
import GlobalGuards from "./components/GlobalGuards.vue";
import SideBar from "./components/SideBar.vue";
import { useAuth } from "./composables/auth";

const { isAuthed } = useAuth();
</script>

<template>
  <div class="app-shell">
    <SideBar v-if="isAuthed" />
    <main class="main" :class="{ 'no-sidebar': !isAuthed }">
      <div class="main-inner" :class="{ 'full-page': !isAuthed }">
        <GlobalGuards v-if="isAuthed" />
        <RouterView v-slot="{ Component }">
          <Transition name="fade" mode="out-in">
            <component :is="Component" />
          </Transition>
        </RouterView>
      </div>
    </main>
  </div>
</template>

<style>
.app-shell {
  min-height: 100vh;
  display: flex;
}

.main {
  flex: 1;
  margin-left: 220px;
  min-width: 0;
  min-height: 100vh;
}

.main.no-sidebar {
  margin-left: 0;
}

.main-inner {
  max-width: 1500px;
  margin: 0 auto;
  padding: 28px 32px 40px;
}

.main-inner.full-page {
  max-width: none;
  padding: 0;
}

@media (max-width: 860px) {
  .main { margin-left: 0; }
  .main-inner { padding: 72px 20px 40px; }
  .main-inner.full-page { padding: 0; }
}
</style>
```

- [ ] **Step 2: build + 提交**

```bash
cd /Users/mm/wordglass/frontend && npm run build 2>&1 | tail -3
cd /Users/mm/wordglass && git add frontend/src/App.vue && git commit -m "App.vue: hide sidebar + GlobalGuards on auth pages

Auth pages (/login /register /setup) become full-screen with the floating-
words background, no sidebar, no padding.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 17: SideBar.vue 加用户块 + 退出

**Files:**
- Modify: `frontend/src/components/SideBar.vue`

**Spec ref:** §9

- [ ] **Step 1: 在 SideBar.vue 顶部 script 引入 auth**

读现有 SideBar.vue 后，在 `<script setup>` 顶部加：

```typescript
import { useAuth } from "../composables/auth";
import { useRouter } from "vue-router";
const { user, clearSession } = useAuth();
const router = useRouter();
function logout() {
  clearSession();
  router.replace({ name: "login" });
}
```

- [ ] **Step 2: 在 `.footer` 区块（主题切换按钮所在的容器）**之上加用户块

在主题切换按钮 `<button class="theme-btn"...>` 之前插入：

```vue
<div v-if="user" class="user-block">
  <span class="user-icon">👤</span>
  <div class="user-info">
    <div class="username">{{ user.username }}</div>
    <button class="logout-btn" @click="logout">退出</button>
  </div>
</div>
```

并在 `<style scoped>` 末尾追加：

```css
.user-block {
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 8px 12px;
  border-bottom: 1px solid var(--hairline);
  margin-bottom: 4px;
}
.user-icon { font-size: 16px; opacity: 0.7; }
.user-info { display: flex; flex-direction: column; gap: 2px; min-width: 0; flex: 1; }
.username {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.logout-btn {
  appearance: none;
  background: transparent;
  border: none;
  padding: 0;
  font: inherit;
  font-size: 11px;
  color: var(--text-tertiary);
  cursor: pointer;
  text-align: left;
}
.logout-btn:hover { color: var(--danger); }
```

- [ ] **Step 3: build + 提交**

```bash
cd /Users/mm/wordglass/frontend && npm run build 2>&1 | tail -3
cd /Users/mm/wordglass && git add frontend/src/components/SideBar.vue && git commit -m "SideBar: show current username + 退出 button

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 18: AdminPanel + Settings 加 admin tab

**Files:**
- Create: `frontend/src/components/settings/AdminPanel.vue`
- Modify: `frontend/src/views/Settings.vue`

**Spec ref:** §10

- [ ] **Step 1: 创建 `AdminPanel.vue`**

```vue
<script setup lang="ts">
import { onMounted, ref } from "vue";
import { api } from "../../api";

interface UserRow {
  id: number;
  username: string;
  is_admin: boolean;
  created_at: string;
  last_login_at: string | null;
}

const inviteCode = ref("");
const registrationEnabled = ref(true);
const users = ref<UserRow[]>([]);
const loading = ref(false);
const error = ref("");
const copied = ref(false);

async function reload() {
  loading.value = true;
  error.value = "";
  try {
    const inv = await api.getInvite();
    inviteCode.value = inv.invite_code;
    registrationEnabled.value = inv.registration_enabled;
    const { items } = await api.listUsers();
    users.value = items;
  } catch (e: any) {
    error.value = e.message || "加载失败";
  } finally {
    loading.value = false;
  }
}

async function regenerate() {
  if (!confirm("重新生成邀请码会让旧的失效，确定？")) return;
  try {
    const inv = await api.regenerateInvite();
    inviteCode.value = inv.invite_code;
  } catch (e: any) {
    error.value = e.message || "重新生成失败";
  }
}

async function toggleRegistration() {
  try {
    const inv = await api.setRegistration(!registrationEnabled.value);
    registrationEnabled.value = inv.registration_enabled;
  } catch (e: any) {
    error.value = e.message || "切换失败";
  }
}

async function copyInvite() {
  try {
    await navigator.clipboard.writeText(inviteCode.value);
    copied.value = true;
    setTimeout(() => { copied.value = false; }, 1600);
  } catch { /* ignore */ }
}

function fmtDate(s: string | null) {
  if (!s) return "—";
  try {
    return new Date(s).toLocaleString("zh-CN", { hour12: false });
  } catch { return s; }
}

onMounted(reload);
</script>

<template>
  <div>
    <header class="panel-head">
      <h2>👑 管理员</h2>
      <button class="chip" @click="reload" :disabled="loading">⟳ 刷新</button>
    </header>

    <div v-if="error" class="error">{{ error }}</div>

    <section class="row">
      <label>邀请码</label>
      <div class="invite-box">
        <code class="invite-code">{{ inviteCode || "（未生成）" }}</code>
        <button class="chip" @click="copyInvite">{{ copied ? "✓ 已复制" : "📋 复制" }}</button>
        <button class="chip warn" @click="regenerate">🔁 重新生成</button>
      </div>
      <div class="help">把这串给要注册的朋友。重新生成会让旧码立刻失效。</div>
    </section>

    <section class="row">
      <label>开放注册</label>
      <label class="toggle">
        <input type="checkbox" :checked="registrationEnabled" @change="toggleRegistration" />
        <span>{{ registrationEnabled ? "已开启 · 持邀请码的人可注册" : "已关闭 · 任何人都不能注册" }}</span>
      </label>
    </section>

    <hr class="divider" />

    <h3>用户列表（{{ users.length }} 个）</h3>
    <table class="users">
      <thead>
        <tr><th>用户名</th><th>角色</th><th>注册时间</th><th>最近登录</th></tr>
      </thead>
      <tbody>
        <tr v-for="u in users" :key="u.id">
          <td><strong>{{ u.username }}</strong></td>
          <td>
            <span class="role" :class="{ admin: u.is_admin }">
              {{ u.is_admin ? "👑 admin" : "普通" }}
            </span>
          </td>
          <td>{{ fmtDate(u.created_at) }}</td>
          <td>{{ fmtDate(u.last_login_at) }}</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<style scoped>
.panel-head {
  display: flex; align-items: baseline; justify-content: space-between;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--hairline);
  margin-bottom: 16px;
}
.panel-head h2 {
  font-family: var(--font-serif); font-size: 18px; font-weight: 700; margin: 0;
}

.chip {
  appearance: none;
  border: 1px solid var(--hairline);
  background: var(--glass-bg-dim);
  padding: 3px 11px;
  border-radius: 999px;
  cursor: pointer;
  font-size: 11.5px;
  color: var(--text-secondary);
}
.chip:hover { color: var(--text-primary); }
.chip.warn:hover { background: color-mix(in srgb, var(--warn) 10%, transparent); color: var(--warn); }

.row { display: flex; flex-direction: column; gap: 6px; margin-bottom: 16px; }
.row > label { font-size: 12px; font-weight: 600; color: var(--text-secondary); }
.help { font-size: 11.5px; color: var(--text-tertiary); }

.invite-box {
  display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
  padding: 10px 12px;
  background: var(--glass-bg-dim);
  border: 1px solid var(--hairline);
  border-radius: var(--radius-md);
}
.invite-code {
  font-family: var(--font-mono);
  font-size: 13px;
  color: var(--brand);
  flex: 1;
  word-break: break-all;
}

.toggle {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  font-size: 12.5px;
  color: var(--text-primary);
}

.divider { border: none; border-top: 1px solid var(--hairline); margin: 18px 0; }

h3 { font-size: 13.5px; margin: 0 0 8px; font-weight: 700; }

.users {
  width: 100%;
  border-collapse: collapse;
  font-size: 12.5px;
  background: var(--glass-bg-dim);
  border: 1px solid var(--hairline);
  border-radius: var(--radius-md);
  overflow: hidden;
}
.users th, .users td {
  padding: 8px 12px;
  text-align: left;
  border-bottom: 1px solid var(--hairline);
}
.users th {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--text-secondary);
  background: var(--glass-bg);
}
.users tr:last-child td { border-bottom: none; }

.role { font-size: 11px; padding: 1px 7px; border-radius: 4px; background: var(--glass-bg-dim); color: var(--text-secondary); }
.role.admin {
  background: color-mix(in srgb, var(--brand) 18%, transparent);
  color: var(--brand);
  font-weight: 600;
}

.error { color: var(--danger); font-size: 12px; padding: 8px 0; }
</style>
```

- [ ] **Step 2: 改 `Settings.vue` 加 admin tab（条件）**

打开 Settings.vue。导入 `AdminPanel` 和 `useAuth`：

```typescript
import AdminPanel from "../components/settings/AdminPanel.vue";
import { useAuth } from "../composables/auth";

const { isAdmin } = useAuth();
```

把 Tab 类型加 `"admin"`：

```typescript
type Tab = "ai" | "test" | "auth" | "log_ai" | "log_sys" | "offline" | "about" | "admin";
```

`loadTab()` 里 valid 数组加 `"admin"`。

把 tabs computed 加管理员组（在「关于」组之前）：

```typescript
const tabs = computed(() => [
  // ... 现有
  { group: "日志 & 监控", items: [/* ... */]},
  ...(isAdmin.value ? [{
    group: "管理",
    items: [{ id: "admin" as const, icon: "👑", label: "管理员" }],
  }] : []),
  { group: "关于", items: [/* ... */]},
]);
```

模板里在 `<AboutPanel v-else-if="tab === 'about'" />` 之前加：

```vue
<AdminPanel v-else-if="tab === 'admin'" />
```

- [ ] **Step 3: build + 提交**

```bash
cd /Users/mm/wordglass/frontend && npm run build 2>&1 | tail -3
cd /Users/mm/wordglass && git add frontend/src/components/settings/AdminPanel.vue frontend/src/views/Settings.vue && git commit -m "settings: AdminPanel + admin tab (conditional)

Admin-only tab shows the invite code (with copy + regenerate), the
registration toggle, and the user list.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 19: 删除 GlobalGuards 旧 token 弹框

**Files:**
- Modify: `frontend/src/components/GlobalGuards.vue`

**Spec ref:** §13.2

- [ ] **Step 1: 用以下内容完整替换 `GlobalGuards.vue`**

只保留 AI 未配置提醒，移除 token 弹框（现在 401 直接跳 /login）。

```vue
<script setup lang="ts">
import { onMounted, ref } from "vue";
import { RouterLink, useRoute } from "vue-router";
import { api } from "../api";

const aiConfigured = ref<boolean | null>(null);
const route = useRoute();

async function checkConfig() {
  try {
    const s = await api.getSettings();
    aiConfigured.value = s.configured;
  } catch {
    aiConfigured.value = false;
  }
}

onMounted(checkConfig);
</script>

<template>
  <Transition name="fade">
    <div
      v-if="aiConfigured === false && route.name !== 'settings'"
      class="banner glass-strong"
    >
      <div>
        <strong>👋 还差一步</strong> · AI 服务还没配置，去
        <RouterLink to="/settings" class="link">设置</RouterLink>
        填一下，就能开始添加单词了。
      </div>
    </div>
  </Transition>
</template>

<style scoped>
.banner {
  position: sticky;
  top: 80px;
  z-index: 40;
  padding: 12px 18px;
  border-radius: var(--radius-md);
  margin: 8px 0 20px;
  font-size: 14px;
}
.banner .link {
  color: var(--accent);
  font-weight: 600;
  text-decoration: none;
}
.banner .link:hover { text-decoration: underline; }
</style>
```

- [ ] **Step 2: build + 提交**

```bash
cd /Users/mm/wordglass/frontend && npm run build 2>&1 | tail -3
cd /Users/mm/wordglass && git add frontend/src/components/GlobalGuards.vue && git commit -m "GlobalGuards: drop AUTH_TOKEN modal; 401 now redirects to /login via router

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 20: Build + smoke

**Files:** 无（验证）

**Spec ref:** §14

- [ ] **Step 1: 全量 build**

```bash
cd /Users/mm/wordglass/frontend && npm run build 2>&1 | tail -5
```

Expected: 通过。

- [ ] **Step 2: 安装新后端依赖（如要本地跑）**

```bash
cd /Users/mm/wordglass/backend && source .venv/bin/activate && pip install pyjwt passlib[bcrypt] bcrypt
```

- [ ] **Step 3: 启 dev**

后端：
```bash
cd /Users/mm/wordglass/backend && source .venv/bin/activate && uvicorn app.main:app --reload --port 8000
```

前端：
```bash
cd /Users/mm/wordglass/frontend && npm run dev
```

- [ ] **Step 4: 手动 smoke**

打开浏览器 http://127.0.0.1:5173。第一次访问应跳 `/setup`。

| 检查 | 期望 |
|---|---|
| 访问 / | 跳 `/setup`（首次） |
| 填管理员账号 + 密码 | 创建成功，跳 dashboard。所有现有单词都在（如果原来本地有数据） |
| 退出（侧栏底部） | 跳 `/login`，本地 token 清掉 |
| 重新登录 | 进 dashboard，单词都在 |
| 切到 `/settings` → 管理员 tab | 看到邀请码 + 用户列表（只有自己）+ 注册开关 |
| 复制邀请码 → 退出 → /register | 填用户名 + 密码 + 邀请码 → 注册成功进 dashboard |
| 用新用户加单词 | 加入成功；切回 admin 看不到新用户的词 |
| 注册一个普通用户 → 它能访问 settings 但看不到「管理员」tab | ✓ |
| 手动改 localStorage 把 jwt 设为乱字符 → 刷新页面 | 跳 /login |
| 切到 reader 试翻译 | 普通用户用自己的 AI 配置；admin 用自己的 |

- [ ] **Step 5: 关 dev，不提交（QA 不改代码）**

---

## 完成

20 个 task 完成后：
- 后端有 User + AppConfig 表，所有数据 user-scoped
- JWT 取代 AUTH_TOKEN
- 前端有 /login /register /setup 三个 auth 页面（浮字背景）
- 路由守卫拦截未登录
- 管理员有专属 tab 管邀请码 + 用户

后续 README 更新 + push 在另外的步骤里做。
