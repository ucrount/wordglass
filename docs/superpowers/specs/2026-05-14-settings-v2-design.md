# Settings v2 重设计 · 设计稿

**日期**: 2026-05-14
**目标**: 设置页升级为 sidebar tab 布局，加 AI 调用日志、系统日志、curl 预览、分类化的连接测试错误。所有日志为**内存 ring buffer**，重启清空。

---

## 1. 范围与约束

### 范围内
- 后端：
  - 新增 `app/log_buffer.py` —— 内存 ring buffer（AI 调用 50 条 / 系统日志 200 条），单进程内全局单例
  - `app/log.py` —— `log_event` 除了 stderr 也推到 ring buffer
  - `app/providers/openai_compat.py` —— `chat()` 和 `chat_stream()` 加 hook 录入 AI 调用记录（含 system / user / response / timing / status）
  - `app/routes/settings.py` —— 新增 endpoints：日志读取、清空、SSE 实时推流、curl 预览生成、测试错误分类
  - `app/auth.py`（如需要）—— 保持现有 token 校验
- 前端：
  - `frontend/src/views/Settings.vue` —— 整体重写为 sidebar tab 布局
  - `frontend/src/api.ts` —— 加上几个新接口的封装

### 范围外
- 持久化日志到 SQLite
- 编辑 / 删除单条日志
- 日志导出文件下载（YAGNI，要的话浏览器复制粘贴即可）
- Anthropic / Google provider 加 AI 调用记录（只 OpenAI-compat 覆盖；如未配置走其它 provider，本次不挂钩）—— 这是已知遗漏，挂钩 base.py 不优雅，留作后续
- 改动现有 reader / dashboard / library / practice 页面
- 单独的"清缓存 / 重置数据库"按钮

### 不能损坏的现有行为
- 现有的 AI provider 配置存读、保存、测试、模型列表拉取
- 现有的 auth token 流程
- Reader v3 的流式翻译 / 用法
- Dashboard 的添加单词后异步分类 / 例句补全
- ECDICT / Tatoeba 离线数据检测

---

## 2. 后端 · 内存 ring buffer

### 2.1 `app/log_buffer.py`

```python
"""Per-process in-memory ring buffers for diagnostic logs.

Two separate buffers:
  - AI_CALLS: structured records of each AI request (max 50)
  - SYSTEM_LOGS: structured events from log_event (max 200)

Single-process by design — we don't need cross-worker fanout for a single-VPS
deployment. Both are cleared on process restart (intentional: keeps the
buffers cheap, encourages diagnostic-first usage rather than archival).
"""

from __future__ import annotations

import asyncio
import threading
import time
from collections import deque
from typing import Any, AsyncIterator


_AI_LOCK = threading.Lock()
_AI_BUFFER: deque[dict[str, Any]] = deque(maxlen=50)
_AI_COUNTER = 0

_SYSLOG_LOCK = threading.Lock()
_SYSLOG_BUFFER: deque[dict[str, Any]] = deque(maxlen=200)
_SYSLOG_COUNTER = 0

# Per-process broadcast for streaming. Subscribers add an asyncio.Queue;
# push_system writes to all of them. No-op when no subscribers.
_SUBSCRIBERS: set[asyncio.Queue] = set()


def add_ai_call(record: dict[str, Any]) -> None:
    """Add one AI call record. Assigns a monotonic id."""
    global _AI_COUNTER
    with _AI_LOCK:
        _AI_COUNTER += 1
        record = {"id": _AI_COUNTER, "ts": time.time(), **record}
        _AI_BUFFER.append(record)


def get_ai_calls(limit: int = 50, kind: str | None = None) -> list[dict[str, Any]]:
    """Return AI calls newest-first, optionally filtered by kind."""
    with _AI_LOCK:
        items = list(_AI_BUFFER)
    items.reverse()
    if kind:
        items = [r for r in items if r.get("kind") == kind]
    return items[:limit]


def clear_ai_calls() -> None:
    with _AI_LOCK:
        _AI_BUFFER.clear()


def push_system(record: dict[str, Any]) -> None:
    """Append to system buffer + broadcast to streaming subscribers."""
    global _SYSLOG_COUNTER
    with _SYSLOG_LOCK:
        _SYSLOG_COUNTER += 1
        record = {"id": _SYSLOG_COUNTER, **record}
        _SYSLOG_BUFFER.append(record)
    # Broadcast (non-blocking; drop on full queue rather than block).
    for q in list(_SUBSCRIBERS):
        try:
            q.put_nowait(record)
        except asyncio.QueueFull:
            pass


def get_system_logs(limit: int = 200, event_prefix: str | None = None) -> list[dict[str, Any]]:
    with _SYSLOG_LOCK:
        items = list(_SYSLOG_BUFFER)
    items.reverse()
    if event_prefix:
        items = [r for r in items if str(r.get("event", "")).startswith(event_prefix)]
    return items[:limit]


def clear_system_logs() -> None:
    with _SYSLOG_LOCK:
        _SYSLOG_BUFFER.clear()


async def subscribe() -> AsyncIterator[dict[str, Any]]:
    """Async iterator yielding new system log records as they arrive.

    Replays the current buffer at start, then streams new entries until the
    caller cancels.
    """
    queue: asyncio.Queue = asyncio.Queue(maxsize=500)
    # Replay current contents oldest-first.
    with _SYSLOG_LOCK:
        for record in list(_SYSLOG_BUFFER):
            try:
                queue.put_nowait(record)
            except asyncio.QueueFull:
                break
    _SUBSCRIBERS.add(queue)
    try:
        while True:
            item = await queue.get()
            yield item
    finally:
        _SUBSCRIBERS.discard(queue)
```

### 2.2 `app/log.py` —— 同时推入 buffer

把现有 `log_event` 改成除了 stderr 之外也调 `push_system`：

```python
# app/log.py
from __future__ import annotations

import json
import sys
import time
import uuid

from .log_buffer import push_system


def new_request_id() -> str:
    return uuid.uuid4().hex[:8]


def now_ms() -> float:
    return time.monotonic() * 1000.0


def log_event(event: str, **fields) -> None:
    payload = {"ts": time.time(), "event": event, **fields}
    try:
        line = json.dumps(payload, ensure_ascii=False, default=str)
    except Exception:
        line = f'{{"event": "{event}", "log_error": "json_fail"}}'
    print(line, file=sys.stderr, flush=True)
    try:
        push_system(payload)
    except Exception:
        # Never break the calling code because of logging
        pass
```

---

## 3. 后端 · Provider 录入 AI 调用记录

只在 `OpenAIProvider` 里做。Anthropic / Google 暂不挂钩（未在范围内，可后续抽象）。

### 3.1 `OpenAIProvider.chat()` 改写录入

`chat()` 入口录请求体，出口录响应：

```python
# 伪代码
async def chat(self, system, user, *, json_mode=False, max_tokens=None) -> str:
    from ..log_buffer import add_ai_call
    t0 = time.monotonic()
    record = {
        "kind": "chat",
        "provider": self.name,
        "model": self.model,
        "base_url": self.base_url,
        "system": system,
        "user": user,
        "json_mode": json_mode,
        "max_tokens": max_tokens,
    }
    try:
        # ... 现有 httpx 调用
        # 成功
        record["response"] = content
        record["status"] = "ok"
        record["http_status"] = resp.status_code
        record["ms"] = round((time.monotonic() - t0) * 1000, 1)
        add_ai_call(record)
        return content
    except ProviderError as e:
        record["status"] = "error"
        record["error"] = str(e)
        record["ms"] = round((time.monotonic() - t0) * 1000, 1)
        add_ai_call(record)
        raise
```

### 3.2 `OpenAIProvider.chat_stream()` 改写录入

流式版本一样录，但 response 是累加 chunks 后的完整字符串。在 generator 内累加，最后 `add_ai_call`。

```python
async def chat_stream(self, system, user, *, max_tokens=None) -> AsyncIterator[str]:
    from ..log_buffer import add_ai_call
    t0 = time.monotonic()
    accumulated = []
    first_chunk_ms = None
    record = {
        "kind": "stream",
        "provider": self.name,
        "model": self.model,
        "base_url": self.base_url,
        "system": system,
        "user": user,
        "max_tokens": max_tokens,
    }
    try:
        async with client.stream(...) as resp:
            # ... 处理 status code
            async for raw_line in resp.aiter_lines():
                # ... 解析 delta
                if delta:
                    if first_chunk_ms is None:
                        first_chunk_ms = round((time.monotonic() - t0) * 1000, 1)
                    accumulated.append(delta)
                    yield delta
        record["response"] = "".join(accumulated)
        record["status"] = "ok"
        record["chunks"] = len(accumulated)
        record["first_chunk_ms"] = first_chunk_ms
        record["ms"] = round((time.monotonic() - t0) * 1000, 1)
        add_ai_call(record)
    except ProviderError as e:
        record["status"] = "error"
        record["error"] = str(e)
        record["response"] = "".join(accumulated)
        record["ms"] = round((time.monotonic() - t0) * 1000, 1)
        add_ai_call(record)
        raise
```

注意：因为 `chat_stream` 是 `AsyncIterator[str]`，需要用 try/except + finally 处理。具体实现细节见 plan。

### 3.3 脱敏

`record` 永远不写 `api_key`。Base URL 写完整即可（不是机密）。

---

## 4. 后端 · 新增 endpoints

全部加到 `app/routes/settings.py`，prefix 是 `/api/settings`。

| Method | Path | 用途 |
|---|---|---|
| GET | `/api/settings/logs/ai?kind=&limit=` | 返回 AI 调用记录列表（newest-first） |
| POST | `/api/settings/logs/ai/clear` | 清空 AI 调用记录 |
| GET | `/api/settings/logs/system?event_prefix=&limit=` | 返回系统日志列表 |
| POST | `/api/settings/logs/system/clear` | 清空系统日志 |
| POST | `/api/settings/logs/system/stream` | SSE 实时推流系统日志（POST 与 streamSSE 工具对齐，body 留空） |
| POST | `/api/settings/curl` | 生成 curl 命令字符串 |
| POST | `/api/settings/test` | 改造现有的：返回分类错误 |

### 4.1 AI 调用记录返回示例

```json
{
  "items": [
    {
      "id": 14,
      "ts": 1715692812.4,
      "kind": "stream",
      "provider": "openai",
      "model": "deepseek-v4-flash",
      "base_url": "https://api.deepseek.com/v1",
      "system": "You are a translator...",
      "user": "It was pure serendipity that...",
      "response": "这完全是机缘巧合...",
      "status": "ok",
      "chunks": 142,
      "first_chunk_ms": 678.4,
      "ms": 3289.7
    }
  ]
}
```

### 4.2 系统日志返回示例

```json
{
  "items": [
    {
      "id": 186,
      "ts": 1715692815.7,
      "event": "translate.done",
      "rid": "a3f12b9c",
      "chunks": 142,
      "total_ms": 3289.7
    }
  ]
}
```

### 4.3 SSE 实时推流系统日志

```python
@router.post("/logs/system/stream")
async def stream_system_logs():
    from ..log_buffer import subscribe
    import json

    async def gen():
        async for rec in subscribe():
            yield f"data: {json.dumps(rec, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
```

前端用现有 `streamSSE`（POST）消费 —— body 传 `null` 即可，后端用 `await request.json()` 不需要读 body，body 留空对路由无影响。

### 4.4 curl 预览

```python
class CurlIn(BaseModel):
    provider_type: ProviderType
    base_url: str
    api_key: str = ""         # "" => use stored key
    model: str
    reveal_key: bool = False  # if True, return real key; else masked


class CurlOut(BaseModel):
    command: str


@router.post("/curl", response_model=CurlOut)
def generate_curl(payload: CurlIn, db: Session = Depends(get_db)):
    # If api_key blank, look up the saved one
    key = payload.api_key or (get_settings(db).api_key or "")
    masked = _mask_key(key) if not payload.reveal_key else key
    if payload.provider_type == "openai":
        cmd = _curl_openai(payload.base_url, masked, payload.model)
    elif payload.provider_type == "anthropic":
        cmd = _curl_anthropic(payload.base_url, masked, payload.model)
    else:
        cmd = _curl_google(payload.base_url, masked, payload.model)
    return {"command": cmd}


def _mask_key(key: str) -> str:
    if len(key) <= 12:
        return "***"
    return key[:6] + "*" * 8 + key[-4:]


def _curl_openai(base_url: str, key: str, model: str) -> str:
    body = json.dumps({"model": model, "messages": [{"role": "user", "content": "ping"}]})
    return (
        f'curl -X POST "{base_url.rstrip("/")}/chat/completions" \\\n'
        f'  -H "Authorization: Bearer {key}" \\\n'
        f'  -H "Content-Type: application/json" \\\n'
        f'  -d \'{body}\''
    )
# 类似 _curl_anthropic / _curl_google
```

### 4.5 测试错误分类

修 `/api/settings/test`，根据 `httpx` 异常类型 + HTTP 状态返回分类码：

```python
class TestResult(BaseModel):
    ok: bool
    category: str = ""    # "ok" | "dns" | "connect" | "timeout" | "auth" | "not_found" | "rate_limit" | "upstream" | "unknown"
    detail: str = ""      # 给人看的中文消息
    raw: str = ""         # 上游响应原文（截断）
    echo: str = ""        # 成功时是模型回的内容
    ms: float = 0


@router.post("/test", response_model=TestResult)
async def test_settings(payload: SettingsIn, db: Session = Depends(get_db)):
    t0 = time.monotonic()
    try:
        provider = build_provider(payload.provider_type, payload.base_url, payload.api_key, payload.model)
        text = await provider.chat("Reply with just: OK", "ping", max_tokens=10)
        ms = round((time.monotonic() - t0) * 1000, 1)
        return TestResult(ok=True, category="ok", detail=f"模型 {payload.model} 回复: {text[:80]}", echo=text[:120], ms=ms)
    except ProviderError as e:
        msg = str(e)
        ms = round((time.monotonic() - t0) * 1000, 1)
        category, detail = _classify(msg)
        return TestResult(ok=False, category=category, detail=detail, raw=msg[:400], ms=ms)
    except httpx.ConnectError as e:
        ...
    except httpx.TimeoutException:
        ...
    # 其它


def _classify(msg: str) -> tuple[str, str]:
    """从 ProviderError 的字符串（含 HTTP status + 响应体）分类。"""
    if msg.startswith("401"):
        return "auth", "API key 无效或被吊销。检查 key 是否正确、是否过期。"
    if msg.startswith("403"):
        return "auth", "API key 权限不足。可能是没开通此模型的访问。"
    if msg.startswith("404"):
        return "not_found", "模型不存在或路径错。检查 model 名字和 base_url。"
    if msg.startswith("429"):
        return "rate_limit", "请求频率超限或余额不足。"
    if msg.startswith("5"):
        return "upstream", "上游服务异常。可能是 provider 自己故障，过一会再试。"
    return "unknown", msg[:200]
```

`httpx.ConnectError` → category="dns" 或 "connect"，`httpx.TimeoutException` → "timeout"。

---

## 5. 前端 · Settings.vue 重写

### 5.1 状态

```typescript
type Tab = "ai" | "test" | "auth" | "log_ai" | "log_sys" | "offline" | "about";
const tab = ref<Tab>("ai");

// existing settings form state — 保留
const form = ref({...});

// 新状态
const curlPreview = ref("");
const curlReveal = ref(false);

const testResult = ref<TestResult | null>(null);  // 包含 category, detail, raw, ms

const aiLogs = ref<AiCallRecord[]>([]);
const aiLogsFilter = ref<"" | "chat" | "stream">("");
const expandedLog = ref<number | null>(null);  // record id

const sysLogs = ref<SystemLogRecord[]>([]);
const sysLogsFilter = ref<"" | "translate" | "usage" | "error">("");
const sysLogPaused = ref(false);
let sysLogAbort: AbortController | null = null;

const offlineStatus = ref<{ ecdict: boolean; tatoeba: boolean }>({ ecdict: false, tatoeba: false });
```

### 5.2 模板结构

```vue
<section class="settings">
  <header class="page-head">
    <h1>设置</h1>
    <p class="muted small">AI 配置、连接测试、调用日志和系统诊断都在这里</p>
  </header>

  <div class="settings-layout glass">
    <aside class="settings-nav">
      <div class="nav-h">配置</div>
      <button :class="{active: tab==='ai'}" @click="setTab('ai')">
        <span class="ico">⚙</span>AI Provider
      </button>
      <button :class="{active: tab==='test'}" @click="setTab('test')">
        <span class="ico">🔌</span>测试 &amp; 诊断
      </button>
      <button :class="{active: tab==='auth'}" @click="setTab('auth')">
        <span class="ico">🔒</span>访问令牌
      </button>

      <div class="nav-h">日志 &amp; 监控</div>
      <button :class="{active: tab==='log_ai'}" @click="setTab('log_ai')">
        <span class="ico">🤖</span>AI 调用记录
        <span class="nav-badge">{{ aiLogs.length }}</span>
      </button>
      <button :class="{active: tab==='log_sys'}" @click="setTab('log_sys')">
        <span class="ico">📋</span>系统日志
        <span class="nav-badge">{{ sysLogs.length }}</span>
      </button>

      <div class="nav-h">关于</div>
      <button :class="{active: tab==='offline'}" @click="setTab('offline')">
        <span class="ico">📚</span>离线数据
      </button>
      <button :class="{active: tab==='about'}" @click="setTab('about')">
        <span class="ico">ℹ</span>版本信息
      </button>
    </aside>

    <div class="settings-content">
      <AiProviderPanel v-if="tab==='ai'" ... />
      <TestPanel v-else-if="tab==='test'" ... />
      <AuthPanel v-else-if="tab==='auth'" ... />
      <AiLogsPanel v-else-if="tab==='log_ai'" ... />
      <SysLogsPanel v-else-if="tab==='log_sys'" ... />
      <OfflinePanel v-else-if="tab==='offline'" ... />
      <AboutPanel v-else-if="tab==='about'" ... />
    </div>
  </div>
</section>
```

为了避免 Settings.vue 文件太大，**每个 tab 拆成独立组件文件**（`frontend/src/components/settings/`）。这是必要的拆分，因为单文件会超过 1000+ 行难以维护。

```
frontend/src/components/settings/
  AiProviderPanel.vue
  TestPanel.vue
  AuthPanel.vue
  AiLogsPanel.vue
  SysLogsPanel.vue
  OfflinePanel.vue
  AboutPanel.vue
```

### 5.3 AiProviderPanel.vue

- 协议类型 cards（3 个：openai / anthropic / google），点击切换
- Base URL 输入框 + 快速填入预设链接
- API Key 输入框 + 显示/隐藏 toggle
- Model 输入框 + "拉取可用模型列表"按钮
- 「💾 保存」按钮固定在底部

**Tab 切换时如果有未保存改动，弹确认（或自动保存）**：本次取自动保存策略 —— 失焦或切 tab 时静默保存 form。简化 UX。

### 5.4 TestPanel.vue

- 顶部：「🧪 测试连接」按钮（用当前 form 配置）
- 结果区：根据 category 显示色（success / warn / danger），含 detail + raw（折叠的"展开原始响应"）
- 下方：curl 预览（黑底代码块）+ 「📋 复制」按钮 + 「👁 显示 key」toggle

curl 在 form 变化时自动重新生成（300ms 防抖）。

### 5.5 AuthPanel.vue

- "访问令牌" 单一输入框 + 说明 + 当前状态徽章（已设置 / 未设置）
- 「保存」按钮 + 触发同 form 的 save 逻辑

### 5.6 AiLogsPanel.vue

- 顶部：过滤 chip（全部 / translate / usage / chat / 其它）+ 「⟳ 刷新」「🗑 清空」
- 列表：每行 `时间 | 标签+摘要 | 耗时 | status`
- 点击行展开 detail：完整 system / user / response（长内容滚动）+ timing 字段
- 点击同一行再次关闭

加载策略：进入 tab 时 fetch 一次，「⟳ 刷新」手动重新拉。无自动轮询（避免无谓请求）。

### 5.7 SysLogsPanel.vue

- 顶部：过滤 chip（全部 / translate / usage / error）+ 「⟳ 重连」「🗑 清空」
- 内容：黑底单 monospace 列表，每行一条日志（时间 + event + 字段 K=V 高亮）
- 进入 tab 时打开 SSE 流；切走或卸载时 abort
- SSE 自动 scroll-to-bottom（用户手动往上滚则不再 auto-scroll，标志位 `userScrolled`）
- 不做"暂停"——YAGNI。要看历史就滚上去；要刷新就「重连」

### 5.8 OfflinePanel.vue

- 调 `/api/words/offline-status`，显示 ECDICT / Tatoeba 是否启用，以及大致信息
- 「⟳ 刷新」

### 5.9 AboutPanel.vue

- WordGlass 版本号（硬编码或从 `package.json` 读，本次硬编码 `0.2.0`，下次大改时手动 bump）
- GitHub 链接、license
- 一句话项目介绍

---

## 6. 前端 · api.ts 新增方法

```typescript
export interface AiCallRecord {
  id: number;
  ts: number;
  kind: "chat" | "stream";
  provider: string;
  model: string;
  base_url: string;
  system: string;
  user: string;
  response: string;
  status: "ok" | "error";
  error?: string;
  http_status?: number;
  chunks?: number;
  first_chunk_ms?: number;
  ms: number;
}

export interface SystemLogRecord {
  id: number;
  ts: number;
  event: string;
  [key: string]: any;
}

export interface TestResultV2 {
  ok: boolean;
  category: string;
  detail: string;
  raw: string;
  echo: string;
  ms: number;
}

// In api object:
listAiLogs: (kind?: string, limit = 50) =>
  request<{ items: AiCallRecord[] }>(
    `/api/settings/logs/ai?limit=${limit}${kind ? `&kind=${kind}` : ""}`,
  ),
clearAiLogs: () =>
  request<{ ok: boolean }>("/api/settings/logs/ai/clear", { method: "POST" }),

listSystemLogs: (event_prefix?: string, limit = 200) =>
  request<{ items: SystemLogRecord[] }>(
    `/api/settings/logs/system?limit=${limit}${event_prefix ? `&event_prefix=${event_prefix}` : ""}`,
  ),
clearSystemLogs: () =>
  request<{ ok: boolean }>("/api/settings/logs/system/clear", { method: "POST" }),

streamSystemLogs: (onLog: (r: SystemLogRecord) => void, signal: AbortSignal) =>
  streamSSE(
    "/api/settings/logs/system/stream",
    null,  // empty body — SSE GET不带body
    (delta) => {
      try {
        const r = JSON.parse(delta);
        onLog(r);
      } catch { /* ignore */ }
    },
    () => {},
    signal,
  ),
// (注意：streamSSE 当前用 POST，需要小改支持 GET no-body —— spec 里改)

generateCurl: (payload: { provider_type: string; base_url: string; api_key: string; model: string; reveal_key: boolean }) =>
  request<{ command: string }>("/api/settings/curl", {
    method: "POST",
    body: JSON.stringify(payload),
  }),

// testSettings 改返回 TestResultV2，向后兼容（旧字段保留）
```

`streamSSE` 现在只支持 POST。新增一个支持 GET 的变体，或者让 `/logs/system/stream` 也接受 POST（保持工具同一）。**实现选 POST 路由（body 可为空）**，简单。

---

## 7. UI 视觉细节

### 7.1 layout grid

```css
.settings-layout {
  display: grid;
  grid-template-columns: 200px 1fr;
  gap: 0;
  min-height: 540px;
  padding: 0;             /* 整个卡片背景，左 nav 不需要内 padding */
  overflow: hidden;       /* 圆角不漏内容 */
}
.settings-nav {
  padding: 18px 12px;
  border-right: 1px solid var(--hairline);
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.settings-content {
  padding: 22px 28px;
  min-width: 0;
  overflow-y: auto;
}
```

### 7.2 nav button 样式

复用现有侧栏的 nav-item 风格（左侧 3px brand 标尺、brand-soft 背景）。

### 7.3 curl 黑底代码块

```css
.curl-block {
  background: #1d2017;
  color: #cbd6b8;
  border-radius: 10px;
  padding: 14px 16px;
  font-family: var(--font-mono);
  font-size: 12px;
  line-height: 1.6;
  position: relative;
  overflow-x: auto;
}
.curl-key { color: #d8b483; }
.curl-str { color: #a3c98a; }
.curl-actions {
  position: absolute; top: 8px; right: 8px;
  display: flex; gap: 6px;
}
```

### 7.4 日志行

参考 mockup —— 4 列 grid（时间 / 标签 + 摘要 / 耗时 / 状态）。展开后 detail 用黑底 monospace 块。

### 7.5 暗色

所有颜色用 token；黑底 code block 在暗色下仍是黑（保持一致），与玻璃卡反差。

### 7.6 移动端 `<860px`

侧 nav 折成顶 tab bar（水平滚动），内容区铺满。

---

## 8. 错误处理

- AI 调用录入失败 → 不影响业务（已有 try/except 包裹）
- ring buffer 已满 → deque(maxlen) 自动丢弃最旧的
- SSE 客户端断 → 后端 finally 清理 subscriber
- 测试连接超时 → category = "timeout"，detail "请求超时（>10s），检查 base_url 是否可达 / VPS 出口"

---

## 9. 性能

- AI 调用 50 条最大占用 ~250KB 内存（每条平均 5KB）
- 系统日志 200 条最大占用 ~80KB
- SSE 推流：subscribe 时一次性 replay 历史（200 条），之后每条都广播；500 上限队列防止单个慢客户端拖累其它
- 测试连接：超时 10s（不要等太久）

---

## 10. 验收

- 进设置页默认在「AI Provider」tab
- 改 form 字段 → 切到「测试」tab → 立刻看到对应的 curl 命令
- 点测试 → 显示分类化结果（DNS 失败 / 401 / 200 等）
- 切到「AI 调用记录」tab → 看到刚才的测试调用 + 之前的 translate / usage 流式调用
- 点单行 → 看到完整 system + user + response + timing
- 切到「系统日志」tab → 自动开始 SSE 推流；在 reader 页面做翻译 → 这里实时滚出日志
- 「暂停」按钮 → 推流不中断但 UI 不 append
- 切方向 / 关闭 tab → 系统日志的 SSE 自动 abort
- 暗色 / 亮色都正常
- `npm run build` 通过；后端 `python3 -m py_compile` 通过

---

## 11. 实施顺序（plan 细化）

1. 后端 `app/log_buffer.py` + `app/log.py` 联动
2. 后端 OpenAIProvider `chat` / `chat_stream` 录入 AI 调用
3. 后端 `app/routes/settings.py` 新增日志/curl/test 端点
4. 前端 `api.ts` 新增 6 个方法 + 类型
5. 前端 `frontend/src/components/settings/` 新建 7 个 panel 组件
6. 前端 `Settings.vue` 重写为壳（nav + 路由到 panel）
7. 前端样式补完（curl 块、log 行、SSE 推流等）
8. 跑 build + 手动 smoke

---

## 12. 不做（明确）

- 不引入 vuex / pinia（form 状态本地化在 Settings.vue 或 panel 内）
- 不引入 markdown 渲染器（用 `<pre>`）
- 不持久化任何日志
- 不挂钩 Anthropic / Google provider 录入（后续再加）
- 不导出日志为 json / csv 文件
- 不改 reader / dashboard / library / practice
