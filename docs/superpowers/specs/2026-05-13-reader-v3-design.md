# Reader v3 重设计 · 设计稿

**日期**: 2026-05-13
**目标**: 在现有 Reader v2 基础上加四件事：
1. 译文流式输出（按字到达）—— 主要为了提升感知速度
2. 点单词后右边新增 AI 用法 + 记忆方法面板（流式，自动触发）
3. 点单词自动 TTS 朗读 + 单词卡 🔊 按钮重播
4. 修"原文点击不了"bug —— 用显式「✏️ 编辑」按钮替代"点空白进编辑"，底部面板固定高度防止内容跳动

---

## 1. 范围与约束

### 范围内
- `backend/app/providers/base.py` —— `Provider` 加可选 `chat_stream` 方法（默认非流式 fallback）
- `backend/app/providers/openai_compat.py` —— 实现真正的 SSE 流式
- `backend/app/routes/translate.py` —— 新增 `POST /api/translate/stream` 流式端点；原 `POST /api/translate` 保留（向后兼容）
- `backend/app/routes/words.py` —— 新增 `POST /api/words/usage` 流式端点（用法+记忆法）
- `frontend/src/api.ts` —— `translateTextStream` 和 `wordUsageStream` 两个流式封装
- `frontend/src/views/Reader.vue` —— UI 重新布局：底部两等列、显式编辑按钮、TTS 集成、流式渲染
- `frontend/src/composables/tts.ts` —— 现有，直接复用，零改动

### 范围外
- Anthropic / Google providers 的真正流式实现（只在 OpenAI-compat 上做，其余落 fallback：调 chat() 拿到完整结果一次性 yield）
- 翻译结果缓存
- 用法面板的多语言切换
- 把 Reader.vue 拆成多个子组件（保持单文件，文件大小可接受 ~700-800 行）
- 修改 Dashboard / Library / Practice / Settings

### 不能损坏的现有行为
- 自动翻译（粘贴 / 停顿 1.2s 触发）—— 切到流式版本
- 方向 toggle（英→中 / 中→英）—— 完全保留
- 单词加入单词库 → Dashboard 同步
- localStorage 持久化（原文、译文、方向）
- 暗色 / 亮色主题
- 移动端响应式（≤1000px 单列堆叠）
- AI 未配置时友好报错

---

## 2. 后端 · Provider 抽象加流式

### 2.1 `Provider` 基类

```python
# backend/app/providers/base.py
from typing import AsyncIterator

class Provider(abc.ABC):
    # ... 现有方法保留

    async def chat_stream(
        self,
        system: str,
        user: str,
        *,
        max_tokens: int | None = None,
    ) -> AsyncIterator[str]:
        """Stream the assistant text as it arrives. Yields token chunks (1 to N
        characters each — provider-dependent).

        Default fallback: call self.chat() and yield the entire result once.
        Subclasses with native streaming should override.
        """
        full = await self.chat(system, user, max_tokens=max_tokens)
        yield full
```

### 2.2 `OpenAIProvider.chat_stream`

```python
# backend/app/providers/openai_compat.py
import json
from typing import AsyncIterator

class OpenAIProvider(Provider):
    # ... existing chat() unchanged

    async def chat_stream(
        self,
        system: str,
        user: str,
        *,
        max_tokens: int | None = None,
    ) -> AsyncIterator[str]:
        url = f"{self.base_url}/chat/completions"
        body: dict[str, Any] = {
            "model": self.model,
            "temperature": 0.4,
            "stream": True,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        if max_tokens is not None:
            body["max_tokens"] = max_tokens

        client = _client()
        async with client.stream("POST", url, headers=self._headers(), json=body) as resp:
            if resp.status_code >= 400:
                text = (await resp.aread()).decode("utf-8", errors="replace")
                raise ProviderError(f"{resp.status_code}: {text[:300]}")
            async for raw_line in resp.aiter_lines():
                if not raw_line or not raw_line.startswith("data:"):
                    continue
                payload = raw_line[5:].strip()
                if payload == "[DONE]":
                    return
                try:
                    obj = json.loads(payload)
                    delta = obj.get("choices", [{}])[0].get("delta", {}).get("content")
                except (json.JSONDecodeError, KeyError, IndexError):
                    continue
                if delta:
                    yield delta
```

httpx 的 `client.stream()` 会自动迭代 SSE 帧。OpenAI / DeepSeek / Groq / Ollama 都遵循同样的格式。

### 2.3 兼容性

- `Provider.chat_stream` 默认 fallback 让 Anthropic / Google 不至于报 `NotImplementedError`
- 旧 `chat()` 完全保留 —— ai.py 里的分类、补例句、原 `/api/translate` 都不动

---

## 3. 后端 · 翻译流式端点

新增 `POST /api/translate/stream`，旧 `POST /api/translate` 保留（向后兼容 + ai.py 等可能调用）。

```python
# backend/app/routes/translate.py
from fastapi.responses import StreamingResponse

@router.post("/stream")
async def translate_stream(payload: TranslateIn, db: Session = Depends(get_db)):
    row = get_settings(db)
    if not is_configured(row):
        raise HTTPException(
            status_code=502,
            detail="AI 未配置，无法翻译整段文本。在右上角 ⚙ 设置中配一个 AI provider 再试。",
        )
    system = SYSTEM_TO_EN if payload.target_lang == "en" else SYSTEM_TO_ZH

    async def gen():
        try:
            provider = build_provider(row.provider_type, row.base_url, row.api_key, row.model)
            async for chunk in provider.chat_stream(system, payload.text, max_tokens=2000):
                # SSE format: each event is `data: <json>\n\n`
                yield f"data: {json.dumps({'delta': chunk})}\n\n"
            yield "data: [DONE]\n\n"
        except ProviderError as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")
```

注意：
- 路径是 `/api/translate/stream`（router prefix `/api/translate` + `/stream`）
- SSE：每行 `data: <json>\n\n`，最后 `data: [DONE]\n\n`
- 错误以 `data: {"error": "..."}` 输出，前端读到 error 字段后中止并显示

---

## 4. 后端 · 用法 + 记忆法端点

新增 `POST /api/words/usage` 流式端点，使用 `【用法】` / `【记忆方法】` 段落分隔符让前端可解析渲染。

```python
# backend/app/routes/words.py
import json
from fastapi.responses import StreamingResponse

USAGE_SYSTEM = (
    "You are an English vocabulary teacher writing for Chinese learners. "
    "For the given English word or phrase, write a concise Chinese explanation "
    "with TWO sections in this exact format (Chinese only, no English explanations):\n\n"
    "【用法】\n"
    "1-2 sentences (40-80 Chinese characters): nuance, common usage scenarios, "
    "frequent collocations. Use 例 to introduce 1-2 short collocation examples in English.\n\n"
    "【记忆方法】\n"
    "1-2 sentences (30-60 Chinese characters): mnemonic tricks — etymology, "
    "association with similar-sounding Chinese, breakdown of word parts, or memorable image.\n\n"
    "Output ONLY the two sections with their markers. No greeting, no closing."
)


class UsageIn(BaseModel):
    text: str = Field(..., min_length=1, max_length=80)


@router.post("/usage")
async def word_usage_stream(payload: UsageIn, db: Session = Depends(get_db)):
    row = get_settings(db)
    if not is_configured(row):
        raise HTTPException(
            status_code=502,
            detail="AI 未配置，无法生成用法解释。在右上角 ⚙ 设置中配一个 AI provider 再试。",
        )

    async def gen():
        try:
            provider = build_provider(row.provider_type, row.base_url, row.api_key, row.model)
            async for chunk in provider.chat_stream(
                USAGE_SYSTEM, payload.text.strip(), max_tokens=500
            ):
                yield f"data: {json.dumps({'delta': chunk})}\n\n"
            yield "data: [DONE]\n\n"
        except ProviderError as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")
```

`/api/words/usage` 路径（router prefix `/api/words` + `/usage`）。

---

## 5. 前端 · api.ts 流式封装

```typescript
// 通用的 SSE 读取器，用于 translate 和 usage
async function streamSSE(
  path: string,
  body: any,
  onDelta: (text: string) => void,
  onError: (msg: string) => void,
  signal?: AbortSignal,
): Promise<void> {
  const headers = new Headers({ "Content-Type": "application/json" });
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);

  try {
    const resp = await fetch(path, {
      method: "POST",
      headers,
      body: JSON.stringify(body),
      signal,
    });
    if (!resp.ok) {
      let detail = `${resp.status}`;
      try { detail = (await resp.json()).detail ?? detail; } catch { detail = await resp.text(); }
      onError(detail);
      return;
    }
    if (!resp.body) {
      onError("流式响应不可读");
      return;
    }

    const reader = resp.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buffer = "";
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let idx;
      while ((idx = buffer.indexOf("\n\n")) >= 0) {
        const rawEvent = buffer.slice(0, idx).trim();
        buffer = buffer.slice(idx + 2);
        if (!rawEvent.startsWith("data:")) continue;
        const payload = rawEvent.slice(5).trim();
        if (payload === "[DONE]") return;
        try {
          const obj = JSON.parse(payload);
          if (obj.error) { onError(obj.error); return; }
          if (typeof obj.delta === "string") onDelta(obj.delta);
        } catch { /* malformed chunk — ignore */ }
      }
    }
  } catch (e: any) {
    // AbortError = user cancelled (switched direction / picked another word). Silent.
    if (e?.name === "AbortError") return;
    onError(e?.message || "网络错误");
  }
}

export const api = {
  // ... 现有方法保留

  translateTextStream: (
    text: string,
    target_lang: "zh" | "en",
    onDelta: (t: string) => void,
    onError: (m: string) => void,
    signal?: AbortSignal,
  ) => streamSSE("/api/translate/stream", { text, target_lang }, onDelta, onError, signal),

  wordUsageStream: (
    text: string,
    onDelta: (t: string) => void,
    onError: (m: string) => void,
    signal?: AbortSignal,
  ) => streamSSE("/api/words/usage", { text }, onDelta, onError, signal),
};
```

`getToken()` 已存在；`signal` 用于在用户切换方向 / 重新选词时取消上一个进行中的请求。**streamSSE 内部消化 AbortError**，调用方不需要 try/catch，错误统一走 onError 回调。

---

## 6. 前端 · Reader.vue 改动

### 6.1 新增状态

```typescript
const usage = ref<{
  loading: boolean;
  text: string;        // full accumulated text
  error: string;
} | null>(null);

let translateAbort: AbortController | null = null;
let usageAbort: AbortController | null = null;
```

`usage` 在用户点击单词后立即创建（loading 状态），AI 流回来的字符累加到 `usage.text`。前端把 `usage.text` 按 `【用法】` / `【记忆方法】` 分段渲染。

### 6.2 doTranslate 改用流式

```typescript
async function doTranslate() {
  cancelDebounce();
  const text = sourceText.value.trim();
  if (!text || loading.value) return;
  if (translateAbort) translateAbort.abort();
  translateAbort = new AbortController();

  const textareaFocused = document.activeElement === textareaRef.value;
  const targetLang = direction.value === "en-to-zh" ? "zh" : "en";
  loading.value = true;
  error.value = "";
  setTarget("");  // clear before streaming

  let accumulated = "";
  try {
    await api.translateTextStream(
      text, targetLang,
      (delta) => { accumulated += delta; setTarget(accumulated); },
      (msg) => { error.value = msg; },
      translateAbort.signal,
    );
    lastTranslatedText = text;
    if (sourceText.value.trim() === text && !textareaFocused) {
      mode.value = "read";
    }
  } catch (e: any) {
    if (e.name !== "AbortError") error.value = e.message || "翻译失败";
  } finally {
    loading.value = false;
    if (sourceText.value.trim() && sourceText.value.trim() !== lastTranslatedText.trim()) {
      scheduleTranslate(false);
    }
  }
}
```

### 6.3 点单词流程：TTS + preview + 流式用法

```typescript
import { isSpeechSupported, speak } from "../composables/tts";
const ttsSupported = isSpeechSupported();

async function onWordClick(event: MouseEvent, word: string) {
  if (direction.value !== "en-to-zh") return;
  event.stopPropagation();

  // 1. 立刻设 selected loading 态、立刻播音（无网络等待）
  selected.value = {
    text: word, loading: true, found: false,
    phonetic: "", pos: "", translation: "",
    alreadySaved: false, adding: false, addError: "",
  };
  if (ttsSupported) speak(word);

  // 2. 同时拉本地 preview（快）和 AI usage（慢）
  loadPreview(word);
  loadUsage(word);
}

async function loadPreview(word: string) {
  try {
    const data = await api.previewWord(word);
    if (!selected.value || selected.value.text !== word) return;
    if (data.found) {
      selected.value = {
        ...selected.value, loading: false, found: true,
        phonetic: data.phonetic, pos: data.pos,
        translation: data.translation, alreadySaved: data.already_saved,
      };
    } else {
      selected.value = { ...selected.value, loading: false, found: false };
    }
  } catch {
    if (selected.value) selected.value = { ...selected.value, loading: false, found: false };
  }
}

async function loadUsage(word: string) {
  if (usageAbort) usageAbort.abort();
  usageAbort = new AbortController();
  usage.value = { loading: true, text: "", error: "" };
  let accumulated = "";
  await api.wordUsageStream(
    word,
    (delta) => {
      accumulated += delta;
      // Only update if the user hasn't switched to another word in the meantime
      if (selected.value?.text === word && usage.value) {
        usage.value = { ...usage.value, text: accumulated };
      }
    },
    (msg) => {
      if (selected.value?.text === word && usage.value) {
        usage.value = { ...usage.value, loading: false, error: msg };
      }
    },
    usageAbort.signal,
  );
  if (selected.value?.text === word && usage.value) {
    usage.value = { ...usage.value, loading: false };
  }
}
```

### 6.4 用法面板分段渲染

```typescript
// computed 把 usage.text 按 markers 拆成两段
const usageSections = computed(() => {
  const t = usage.value?.text || "";
  // markers: 【用法】 and 【记忆方法】
  const usageMatch = t.match(/【用法】([\s\S]*?)(?=【记忆方法】|$)/);
  const memoMatch = t.match(/【记忆方法】([\s\S]*?)$/);
  return {
    usage: usageMatch ? usageMatch[1].trim() : "",
    memo: memoMatch ? memoMatch[1].trim() : "",
  };
});
```

模板里两块分别显示 `usageSections.usage` 和 `usageSections.memo`。流式期间任一为空就显示一个加载指示。

### 6.5 关闭 selected 时取消请求

```typescript
function closeSelected() {
  if (usageAbort) usageAbort.abort();
  usageAbort = null;
  selected.value = null;
  usage.value = null;
}
```

切方向时也调 `closeSelected()`。

### 6.6 修点击 bug · 显式编辑按钮

模板 source pane 改成：

```vue
<section class="pane glass">
  <div class="pane-head">
    <span class="pane-label">{{ sourceLabel }}</span>
    <span class="pane-meta tertiary">
      <template v-if="wordCount">{{ wordCount }} {{ direction === 'en-to-zh' ? '词' : '字' }} · </template>{{ charCount }} 字符
    </span>
    <button
      v-if="mode === 'read'"
      class="edit-btn"
      @click="enterEditMode"
      title="返回编辑"
    >✏️ 编辑</button>
  </div>
  <!-- textarea 或 reading 区 -->
</section>
```

`.reading` div 上**移除** `@click="enterEditMode"`。原文区只有词可点（触发 selected），其它地方点了无反应。

### 6.7 单词卡 🔊 按钮

word panel 模板里：

```vue
<div class="wp-head">
  <span class="wp-word">{{ selected.text }}</span>
  <button
    v-if="ttsSupported"
    class="wp-tts"
    @click="speak(selected.text)"
    title="重播"
  >🔊</button>
  <span v-if="selected.phonetic" class="wp-phon">{{ selected.phonetic }}</span>
  <span v-if="selected.pos" class="wp-pos">{{ selected.pos }}</span>
</div>
```

`.wp-tts` 样式：圆形 28px，玻璃背景，hover 加深。和 Dashboard 的 `.speaker` 一致。

### 6.8 底部固定高度

```css
.bottom {
  display: grid;
  grid-template-columns: 1fr 1fr;   /* 两等列 */
  gap: 14px;
  min-height: 180px;
}
.word-panel, .usage-panel {
  min-height: 180px;
  padding: 14px 18px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.word-panel { border-left: 3px solid var(--brand); }
.usage-panel { border-left: 3px solid var(--accent); }
```

中→英 模式下整个 `.bottom` 区**隐藏**（中文单词不支持点选）。

### 6.9 用法面板模板

```vue
<section v-if="direction === 'en-to-zh'" class="usage-panel glass">
  <div class="up-head">
    <span class="up-label">💡 AI 用法 &amp; 记忆法</span>
    <span v-if="usage?.loading" class="up-dot" />
  </div>

  <!-- 没选词 -->
  <div v-if="!selected" class="up-empty tertiary small">
    点单词后，这里会出现这个词的用法解释和记忆方法
  </div>

  <!-- 选了词但还在加载且没字 -->
  <div v-else-if="usage?.loading && !usage.text" class="up-loading muted">
    AI 生成中…
  </div>

  <!-- 错误 -->
  <div v-else-if="usage?.error" class="wp-error">
    {{ usage.error }}
  </div>

  <!-- 流式输出中 / 完成 -->
  <template v-else-if="usage">
    <div v-if="usageSections.usage" class="up-section">
      <h4>用法说明</h4>
      <div class="up-body">{{ usageSections.usage }}</div>
    </div>
    <div v-if="usageSections.memo" class="up-section">
      <h4>记忆方法</h4>
      <div class="up-body">{{ usageSections.memo }}</div>
    </div>
  </template>
</section>
```

`.up-dot` 是右上角小圆点，流式期间脉动。

### 6.10 取消进行中的请求时机

| 触发 | 取消什么 |
|---|---|
| 切换方向 | translateAbort + usageAbort |
| 用户改原文（新的 schedule） | translateAbort |
| 点新单词 | usageAbort（preview 不取消，本地查很快）|
| 点关闭按钮 | usageAbort |
| 组件卸载 | 两个都取消 |

### 6.11 样式细节

- `.bottom` 左右等列（`grid-template-columns: 1fr 1fr`）
- 单词卡左 3px 边墨绿 `--brand`，用法卡左 3px 边暖褐 `--accent` —— 视觉上一冷一暖区分作用
- `.wp-tts` 沿用 Dashboard `.speaker` 样式（28-30px 圆，玻璃底）
- 用法卡的 `h4` 段标题：墨绿小帽 `text-transform: uppercase`，11px
- 用法文字 13.5px，行高 1.65
- 加载指示 `.up-dot`：6×6 圆，`--accent` 色，1.4s 闪烁
- 移动端 `<1000px`：底部两列变单列堆叠

---

## 7. localStorage / 持久化

- `wordglass.reader` 持久化 `{en, zh}` —— 保留
- `wordglass.reader.dir` 持久化方向 —— 保留
- **不持久化** selected / usage —— 选词状态每次开页重置

---

## 8. 错误处理

| 场景 | 行为 |
|---|---|
| 翻译流式拿不到响应（网络断）| `error.value = e.message`，译文区清空，loading 关闭 |
| 翻译流式中途返回 error 事件 | 同上 |
| 用法流式 AI 未配置 | 用法面板显示 wp-error 红字，不影响单词卡 |
| 用法流式失败 | 同上，单词卡 + 加入按钮仍可用 |
| TTS 不可用（旧浏览器）| 🔊 按钮不显示，TTS 不调用，无影响 |
| 用户快速点多个单词 | usageAbort 取消前一个，最新点的优先 |

---

## 9. 性能 / 验收

- 译文区从触发到看到第一个字 < 1s（取决于 AI 首 token 延迟）
- 全译文出现速度 ≈ AI 生成速率（10-50 token/s 常见）
- 用户点单词到看到第一个用法字 < 2s
- TTS 在 macOS Safari、Chrome、Firefox 都支持（已有 `tts.ts` composable）
- 暗色 / 亮色都正常
- `npm run build` 通过；TypeScript 类型严格
- 切换方向时进行中的请求被正确取消（不会"残留写入"前一个方向）

---

## 10. 实施顺序（plan 阶段细化）

1. 后端 `Provider.chat_stream` + `OpenAIProvider.chat_stream`
2. 后端 `/api/translate/stream` 端点
3. 后端 `/api/words/usage` 端点
4. 前端 `api.ts` streamSSE 工具 + 两个流式封装
5. 前端 Reader.vue：用流式 doTranslate 替换旧的；显式编辑按钮；移除 `.reading` 上的 @click
6. 前端 Reader.vue：单词卡 🔊 按钮 + 自动 TTS；usage 状态 + 流式拉取 + 分段渲染
7. 前端 Reader.vue：底部两等列布局，固定 min-height
8. 跑 build + 手动 smoke：明色 / 暗色 / 切方向 / 流式可见 / 点词流式用法 / 关闭、Esc / TTS

---

## 11. 不做（明确）

- 不持久化用法面板内容 / 不缓存 usage
- 不为 Anthropic / Google 实现原生流式（用默认 fallback）
- 不把流式接口暴露到 Dashboard 等其它页面
- 不把用法面板做成独立组件（保持 Reader.vue 内）
- 不引入 EventSource（用 fetch + ReadableStream，更可控、能带 Authorization header）
