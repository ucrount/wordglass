# 多用户登录系统 · 设计稿

**日期**: 2026-05-14
**目标**: 把 WordGlass 从「单 token 共享」改成「多用户独立账号」—— 邀请码注册 + 用户名 / 密码登录 + JWT 会话 + 每用户独立的单词库、练习记录、AI 配置。首次访问引导设置 admin 账号；现有数据自动迁移到首个 admin。

---

## 1. 范围与约束

### 范围内
- 后端：
  - 新 `User` 表 + 新 `AppConfig` 单行表（存全局 invite_code、registration_enabled）
  - JWT 编解码工具（`PyJWT`）+ bcrypt 密码哈希（`passlib[bcrypt]`）
  - 给 `Word` / `ReviewLog` / `Setting` 加 `user_id` 外键
  - 自动迁移：首次启动检测旧 schema 时给所有现有数据填 `user_id=NULL`；首次注册的 admin 接管所有 `user_id IS NULL` 的孤儿数据
  - 新增 `app/routes/auth.py`：register / login / me / logout / setup-status
  - 新增 `app/routes/admin.py`：invite code 重置、用户列表、注册开关
  - `verify_token` 改用 JWT，返回 `User`；所有现有 route 改用 `current_user`
  - 现有 Word / Review / Settings / Stats 端点全部 user-scoped
- 前端：
  - 新增 `views/Login.vue`、`views/Register.vue`、`views/Setup.vue`（首装引导）
  - 新增 `composables/auth.ts`（当前用户、JWT 存读、登出、路由守卫辅助）
  - `router.ts`：加 `/login` `/register` `/setup`，加 `beforeEach` 守卫
  - `api.ts`：JWT 自动加 `Authorization` 头；401 → 跳 `/login`
  - `SideBar.vue`：底部加当前用户名 + 「退出」按钮
  - `components/settings/AdminPanel.vue`：admin 专属，邀请码 / 用户列表 / 注册开关
  - `Settings.vue` 加 admin tab（条件渲染）

### 范围外
- 忘记密码 / 邮件验证（用户量小，admin SSH 直接重置 DB）
- OAuth / SSO
- 多人协作 / 共享单词库（这次只做"独立"，不做"共享"）
- 用户角色多于 admin / normal 两档
- 用户头像上传
- 删除账户（admin 可禁用，但本次不做 UI）
- 密码强度提示 / zxcvbn（只做"最少 6 位"硬规则）
- AUTH_TOKEN 向后兼容（删掉旧机制，强制走 JWT）

### 不能损坏
- 现有的 Reader / Dashboard / Library / Practice / Settings 主要功能
- AI 流式翻译 / 用法面板
- 离线词典 ECDICT / Tatoeba 调用
- 暗色 / 亮色主题
- 部署脚本 `install.sh`（升级路径不能崩）

### 安全约束
- 密码绝对不存明文，bcrypt（cost=12，默认）
- JWT secret 服务启动时从 `.env` 读，没有则生成 32 字节随机串写回 `.env`
- JWT 30 天过期，支持「记住我」打勾保持；不勾就过 12 小时
- 邀请码：32 字符随机串，admin 可手动重置；存明文（不需要哈希，反正只能 admin 看）
- 注册时 username 转小写归一化，最少 3 / 最多 20 字符、`[a-z0-9_]+`
- 密码最少 6 字符（前后端都校验）
- bcrypt + JWT 都是经典方案，没自创加密

---

## 2. 后端 · schema 变更

### 2.1 新增表

```python
# app/models.py 加：

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String(20), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)  # bcrypt
    is_admin = Column(Integer, default=0, nullable=False)  # 0 / 1
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login_at = Column(DateTime, nullable=True)


class AppConfig(Base):
    """Singleton row (id=1). Stores global config that's not per-user:
    invite code, registration toggle, JWT secret.
    """

    __tablename__ = "app_config"

    id = Column(Integer, primary_key=True)
    invite_code = Column(String(64), default="")
    registration_enabled = Column(Integer, default=1)  # 0/1
    jwt_secret = Column(String(128), default="")
```

### 2.2 加 `user_id` 到现有表

`Word.user_id`、`ReviewLog.user_id`、`Setting.user_id` —— 全部 `ForeignKey("users.id", ondelete="CASCADE")`，nullable 在迁移期，迁移结束后 NOT NULL（但 SQLite 不支持 ALTER COLUMN，所以保持 nullable，靠应用层强制）。

`Setting` 的 PK 含义变了 —— 不再是 single-row。改 PK 为 `(id, user_id)` 太麻烦，改成：保留 `id` 自增，但 `user_id` 唯一约束。每个用户最多一行 Setting。

### 2.3 迁移逻辑 · `db.py ensure_schema()`

```python
def ensure_schema():
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())

    # existing logic ...

    # users / app_config tables — create if missing
    Base.metadata.create_all(bind=engine, tables=[
        User.__table__, AppConfig.__table__,
    ])

    # add user_id columns to existing tables (idempotent ALTER TABLE)
    for tbl in ("words", "review_logs", "settings"):
        if tbl in tables:
            cols = {c["name"] for c in inspector.get_columns(tbl)}
            if "user_id" not in cols:
                with engine.begin() as conn:
                    conn.execute(text(f"ALTER TABLE {tbl} ADD COLUMN user_id INTEGER REFERENCES users(id)"))

    # seed app_config singleton
    with SessionLocal() as db:
        cfg = db.query(AppConfig).filter(AppConfig.id == 1).first()
        if cfg is None:
            cfg = AppConfig(
                id=1,
                invite_code=_random_token(32),
                registration_enabled=1,
                jwt_secret=_random_token(64),
            )
            db.add(cfg)
            db.commit()
```

`_random_token(n)` 用 `secrets.token_urlsafe(n)`。

### 2.4 迁移孤儿数据

迁移**不在 ensure_schema** 里跑（避免启动时一头雾水做 user-creation）。流程：
1. `/api/auth/setup-status` 检查是否有 users。无 → 前端 setup 路由
2. setup 流程：用户在 `/setup` 输入 username + password → POST `/api/auth/setup`
3. 后端 `auth.setup()` —— 仅在 `users` 表空时可调用，否则 403
   - 创建 user，`is_admin=1`
   - `UPDATE words SET user_id = <new_user_id> WHERE user_id IS NULL`
   - `UPDATE review_logs SET user_id = <new_user_id> WHERE user_id IS NULL`
   - `UPDATE settings SET user_id = <new_user_id> WHERE user_id IS NULL`
   - 如果旧的 Setting 单行存在但 `user_id IS NULL`，归给 admin
   - 返回 JWT
4. setup 完成 → 跳 dashboard

---

## 3. 后端 · auth 工具

### 3.1 `app/security.py` （新文件）

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
    """Return user_id or None on invalid/expired."""
    try:
        payload = jwt.decode(token, secret, algorithms=[JWT_ALG])
        return int(payload["sub"])
    except (jwt.InvalidTokenError, KeyError, ValueError):
        return None
```

依赖：`pyjwt`、`passlib[bcrypt]` 加到 `requirements.txt`。

### 3.2 `app/auth.py` 重写

```python
"""Auth dependency — replaces old AUTH_TOKEN with JWT-based User injection."""

from __future__ import annotations

from fastapi import Depends, Header, HTTPException, status
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


# Backward-compat alias — many routes already import `verify_token`.
# Keep the symbol but make it a no-op stub. Routes get updated below.
def verify_token(user: User = Depends(current_user)) -> None:
    return None
```

旧代码用 `Depends(verify_token)` 的 route，本次改为 `Depends(current_user)` 拿 `User` 实例。

---

## 4. 后端 · auth 路由

### 4.1 `app/routes/auth.py`（新文件）

```python
"""User registration, login, current-user, setup."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..auth import current_user
from ..db import get_db
from ..models import AppConfig, Setting, User, Word, ReviewLog
from ..security import encode_jwt, hash_password, verify_password
from ..settings_store import normalize_username

router = APIRouter(prefix="/api/auth", tags=["auth"])


class SetupStatus(BaseModel):
    needs_setup: bool   # True if zero users; client should route to /setup
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
    """First-time admin creation. Only callable when zero users exist."""
    has_users = db.query(User.id).first() is not None
    if has_users:
        raise HTTPException(status_code=403, detail="已经完成了初始化设置")
    uname = normalize_username(payload.username)
    if not uname:
        raise HTTPException(status_code=400, detail="用户名格式不合法")
    admin = User(
        username=uname,
        password_hash=hash_password(payload.password),
        is_admin=1,
    )
    db.add(admin)
    db.flush()  # get id
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
        raise HTTPException(status_code=400, detail="用户名格式不合法")
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

### 4.2 `app/routes/admin.py`（新文件）

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
    return {"items": [
        UserBrief(
            id=u.id,
            username=u.username,
            is_admin=bool(u.is_admin),
            created_at=u.created_at.isoformat() if u.created_at else "",
            last_login_at=u.last_login_at.isoformat() if u.last_login_at else None,
        ).model_dump()
        for u in users
    ]}
```

### 4.3 `app/settings_store.py` 加 username 归一化

```python
import re

_USERNAME_RE = re.compile(r"^[a-z0-9_]{3,20}$")


def normalize_username(raw: str) -> str:
    """Lowercase + trim. Returns '' if format invalid."""
    s = (raw or "").strip().lower()
    return s if _USERNAME_RE.match(s) else ""
```

---

## 5. 后端 · 现有路由 user-scoping

每个查 / 改 `Word` / `ReviewLog` / `Setting` 的地方都要加 `current_user` 依赖并过滤。

### 5.1 `words.py` 改动

- `add_word`：`Word(user_id=user.id, ...)`，`db.query(Word).filter(Word.text==text, Word.user_id==user.id)`
- `list_words` / `get_word` / `delete_word`：全部 `.filter(Word.user_id == user.id)`
- `recategorize`：同上
- `categories`：同上
- `preview_word`：保留 ECDICT 查询不变；`already_saved` 改成 `.filter(Word.text==..., Word.user_id==user.id)`
- `usage`：不需要 user 关联，但用户得登录 → 加 `current_user` 依赖

### 5.2 `review.py` 改动

- 全部 `current_user` 依赖；`Word.user_id == user.id` 过滤
- `ReviewLog(user_id=user.id, ...)`

### 5.3 `stats.py` 改动

- `stats`、`heatmap` 全部按 user 过滤

### 5.4 `settings.py` 改动 + `settings_store.py`

- `get_settings(db, user_id)` —— 改成按 user_id 取行；不存在则 lazy-create 一行
- 移除 `auth_token` 相关逻辑（JWT 取代）—— 整列保留作为废弃字段，新代码不读不写
- `is_configured(row)` 检查不变
- 现有 settings endpoints 全部加 `current_user`
- `update_settings` 加 `user_id` 参数

### 5.5 `translate.py` 改动

- `translate_stream` / `translate` 改用 `current_user`，settings 用 `get_settings(db, user.id)`

### 5.6 `routes/words.py` 的 `/usage` 同上

每个 AI 调用现在用当前用户的 settings。

---

## 6. 后端 · 主入口

### 6.1 `main.py` 注册新路由

```python
from .routes import auth, admin, review, settings, stats, translate, words

app.include_router(auth.router)
app.include_router(admin.router)
# ... 其余不变
```

### 6.2 requirements 新增

```
pyjwt==2.9.0
passlib[bcrypt]==1.7.4
bcrypt==4.2.0   # 显式钉以避免 passlib 与新 bcrypt 4.x 报 warning
```

`deploy/install.sh` 跑 `pip install -r requirements.txt` 自动装。

---

## 7. 前端 · 路由 + 守卫

### 7.1 `composables/auth.ts`（新文件）

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
      return raw ? JSON.parse(raw) as CurrentUser : null;
    } catch { return null; }
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

### 7.2 `api.ts` 改 JWT 发送 + 401 跳转

```typescript
// 把现有 getToken / setToken 换成读 wordglass.jwt
const TOKEN_KEY = "wordglass.jwt";  // 注意：从旧 wordglass.token 改名了
export function getToken(): string { return localStorage.getItem(TOKEN_KEY) ?? ""; }
export function setToken(t: string) { localStorage.setItem(TOKEN_KEY, t); }

// request() 内部：401 时 dispatch 'wordglass:unauth' 事件 + 清 token
// （由 router 守卫 / App.vue 监听并 redirect /login）
```

### 7.3 `router.ts` 加路由 + 守卫

```typescript
import { useAuth } from "./composables/auth";
import { api } from "./api";

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

router.beforeEach(async (to) => {
  const auth = useAuth();
  // Public routes always allowed
  if (to.meta.public) return true;
  // Check setup status before anything else (only once)
  try {
    const s = await api.setupStatus();
    if (s.needs_setup) return { name: "setup" };
  } catch { /* network down — continue, will 401 below */ }
  // Auth-required route: redirect to login if no token
  if (to.meta.auth && !auth.isAuthed.value) {
    return { name: "login", query: { next: to.fullPath } };
  }
  return true;
});
```

### 7.4 `App.vue` 改

`SideBar` 只在 `isAuthed` 时显示；登录/注册/setup 页面是 full-screen 不需要 sidebar。

```vue
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
```

`no-sidebar` 样式：`margin-left: 0`；`full-page`：取消 `max-width: 1500px` / `padding`。

---

## 8. 前端 · Login / Register / Setup 页面

### 8.1 共用 layout — 「浮字背景」

三个页面共用一个 `AuthLayout`（不抽组件，直接复制 ~30 行 CSS 三遍，避免引入新组件抽象）—— 居中玻璃卡 + 背景 4 个 italic 衬线英文单词浮动。

每个页面输入字段不同，按钮文案不同，下方链接切换。

### 8.2 `Login.vue`

```vue
<script setup lang="ts">
import { ref, onMounted } from "vue";
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
    const r = await api.login({ username: username.value, password: password.value, remember: remember.value });
    setSession(r.token, { id: 0, username: r.username, is_admin: r.is_admin });
    // Fetch full /me to get id
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
  // If already setup needs and no users exist, jump to setup
  try {
    const s = await api.setupStatus();
    if (s.needs_setup) router.replace({ name: "setup" });
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
```

样式：`.auth-page` 全屏，浮字背景同 mockup，`.auth-card` 玻璃卡居中 max-width 380px。

### 8.3 `Register.vue`

同样布局，多一个邀请码输入。提交成功后 setSession + replace dashboard。

### 8.4 `Setup.vue`

「首次使用 · 设置管理员账号」标题，无邀请码（首装），有"再次输入密码"。提交成功后 setSession + replace dashboard。挂载时调 `/setup-status`，如果不需要 setup 则跳 login。

---

## 9. 前端 · SideBar 改动

底部加：
- 当前用户名（带 👤 图标）
- 「退出」按钮

```vue
<div class="user-block">
  <span class="user-icon">👤</span>
  <div class="user-info">
    <div class="username">{{ user?.username }}</div>
    <button class="logout-btn" @click="logout">退出</button>
  </div>
</div>
```

`logout()` 清 session + `router.replace({ name: "login" })`。

---

## 10. 前端 · AdminPanel + Settings tab

### 10.1 `Settings.vue` 加 admin tab（条件）

```typescript
const isAdmin = computed(() => /* useAuth().isAdmin */);
const tabs = computed(() => [
  // 现有...
  { group: "管理", items: isAdmin.value ? [
    { id: "admin" as const, icon: "👑", label: "管理员" },
  ] : [] },
  // ...
]);
```

### 10.2 `components/settings/AdminPanel.vue`

- 邀请码：当前值 + 「📋 复制」 + 「🔁 重新生成」
- 注册开关：toggle
- 用户列表：表格 username / admin badge / 注册时间 / 最后登录

---

## 11. API 客户端新增

```typescript
// api.ts 加：
setupStatus: () => request<{ needs_setup: boolean; registration_enabled: boolean }>("/api/auth/setup-status"),
setup: (payload: { username: string; password: string }) =>
  request<{ token: string; username: string; is_admin: boolean }>(
    "/api/auth/setup", { method: "POST", body: JSON.stringify(payload) }
  ),
login: (payload: { username: string; password: string; remember: boolean }) => /* ... */,
register: (payload: { username: string; password: string; invite_code: string }) => /* ... */,
me: () => request<{ id: number; username: string; is_admin: boolean }>("/api/auth/me"),

// admin
getInvite: () => request<{ invite_code: string; registration_enabled: boolean }>("/api/admin/invite"),
regenerateInvite: () => request<{ invite_code: string; registration_enabled: boolean }>(
  "/api/admin/invite/regenerate", { method: "POST" }
),
setRegistration: (enabled: boolean) => request(
  "/api/admin/registration", { method: "PUT", body: JSON.stringify({ enabled }) }
),
listUsers: () => request<{ items: any[] }>("/api/admin/users"),
```

---

## 12. 错误处理

- 401 → `clearSession()` + dispatch `wordglass:unauth` 事件 + 路由跳 `/login?next=<现在的路径>`
- 注册：邀请码错 / 用户名重复 / 注册关闭 → 友好红字
- 登录：用户名密码错 → 红字
- Setup：用户已存在（被人抢先访问过）→ 红字 + 跳 login

---

## 13. 部署 / 升级

### 13.1 现有 VPS 升级路径

跑 `install.sh`：
1. `git pull` 拉新代码
2. `pip install -r requirements.txt` 装 `pyjwt` / `bcrypt`
3. 启服务 → `ensure_schema()` 自动加 user_id 列、建 users/app_config 表、生成 jwt_secret + invite_code
4. 浏览器访问 → 检测 `needs_setup=true` → 跳 `/setup`
5. 用户填管理员账号 → 现有所有 Word / Setting 数据归到他名下 → 进 dashboard
6. AUTH_TOKEN 旧机制无人调用（旧前端代码不会再走），新前端用 JWT

### 13.2 删除老逻辑

- 后端：`Setting.auth_token` 列保留但不再读写
- 前端：移除 `GlobalGuards.vue` 的 token 弹框流程（现在 401 自动跳登录）

### 13.3 README 更新

主 README 加一节"账号 & 注册"，写明邀请码在管理员的设置页里。

---

## 14. 验收

- 全新 VPS（无任何 db）→ 访问 → 跳 `/setup` → 创建 admin → 进 dashboard → 现有功能都正常
- 已有 wordglass.db（前 v3 数据）的 VPS → 升级跑 install.sh → 访问 → 跳 `/setup` → admin 创建后能看到所有旧单词
- 登录后刷新 → 仍然登录（JWT 在 localStorage）
- 「记住我」未勾 → 12 小时后过期跳登录
- 注册需要邀请码，错码报"邀请码无效"
- 注册关闭后访问 `/register` → 报"管理员已关闭注册"
- 普通用户不能访问 `/api/admin/*`（403）
- 普通用户登录后看不到 Settings 的「管理员」tab
- 多人登录同时使用 → 数据互不干扰（A 看不到 B 的单词）
- 切换账号：A 退出 → B 登录 → 看到的是 B 的单词库
- `npm run build` 通过；`python3 -m py_compile` 通过

---

## 15. 实施顺序（plan 细化）

1. 后端 schema + security 工具（User、AppConfig、JWT、bcrypt）
2. 后端 auth.py 重写 + 新 routes auth.py
3. 后端 admin.py
4. 后端现有 route 全部 user-scoping（words/review/stats/settings/translate）
5. requirements 更新 + ensure_schema 迁移
6. 前端 api.ts JWT + 新方法
7. 前端 composables/auth.ts
8. 前端 router 守卫
9. 前端 Login / Register / Setup 页面
10. 前端 App.vue / SideBar 条件渲染 + 退出按钮
11. 前端 AdminPanel
12. 跑 build + 手动 smoke
13. README + deploy/README 更新

---

## 16. 不做（明确）

- 不做忘记密码 / 邮件
- 不做 OAuth
- 不做团队共享单词库
- 不做用户头像 / 个人资料编辑
- 不做账号删除 UI（保留 admin 数据库手动操作）
- 不做后端 `pytest` 测试（项目现状没测试基建，保持一致）
- 不做 AUTH_TOKEN 向后兼容（删干净，UI 调过来都用 JWT）
