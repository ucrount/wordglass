# Reader v2 重设计 · 设计稿

**日期**: 2026-05-13
**目标**: 在保留所有现有阅读 + 翻译功能的前提下，把 Reader 页面改造成：
1. 顶部加翻译方向 toggle（英→中 / 中→英）
2. 原文清空时译文也清空（保留现有行为，明确化）
3. 移除浮动 popup，改成底部"单词详情面板"
4. 后端 `/api/translate` 加 `target_lang` 参数支持中→英

---

## 1. 范围与约束

### 范围内
- `frontend/src/views/Reader.vue` —— 全面重写交互（保留 token 化样式系统）
- `frontend/src/api.ts` —— `translateText(text, target_lang?)` 加可选第二参
- `backend/app/routes/translate.py` —— `TranslateIn` 加 `target_lang`，根据值切换 system prompt

### 范围外
- 中文反向词典（不引入，本地无字典数据，AI 兜底成本高）
- Reader 内的更多模式（不加例句、不加段落级标注）
- 多个翻译方向的独立缓存（每次切换都清空）
- 长文本分段、流式输出（仍 v1 一次性翻译）
- AI provider 抽象的改动

### 不能损坏的现有行为
- 自动翻译（粘贴立刻翻、停顿 1.2s 触发）
- localStorage 持久化原文 + 译文（key 不变 / 视情况扩展）
- 编辑态 / 阅读态切换（点空白处回编辑、文本变化触发翻译）
- 顶部进度条 + 加载横幅
- 顶部品牌色系（墨绿 + 暖褐 + 玻璃）
- 主题切换、暗色样式
- 单词加入单词库 → 同步刷新 Dashboard 计数（事件已通过 API 直达）

---

## 2. 后端改动 · `/api/translate`

### 2.1 请求 schema

```python
from typing import Literal

class TranslateIn(BaseModel):
    text: str = Field(..., min_length=1, max_length=5000)
    target_lang: Literal["zh", "en"] = "zh"  # 默认值保留现有行为
```

### 2.2 System prompt 分支

```python
SYSTEM_TO_ZH = (
    "You are a translator. Translate the user's English text to fluent, "
    "natural Simplified Chinese. Preserve paragraph breaks. "
    "Output ONLY the translation — no notes, no quotes, no English."
)

SYSTEM_TO_EN = (
    "You are a translator. Translate the user's Chinese text to fluent, "
    "natural English. Preserve paragraph breaks. "
    "Output ONLY the translation — no notes, no quotes, no Chinese."
)
```

`translate()` 根据 `payload.target_lang` 选 system prompt，其它不变。

### 2.3 兼容性
- 旧前端不传 `target_lang` → 默认 `"zh"` → 行为完全一致
- 输出仍然是 `{ translation: string }`，schema 不变

---

## 3. 前端 API 改动 · `api.ts`

```typescript
translateText: (text: string, target_lang: "zh" | "en" = "zh") =>
  request<{ translation: string }>("/api/translate", {
    method: "POST",
    body: JSON.stringify({ text, target_lang }),
  }),
```

向后兼容（默认参数）。Dashboard 没改用现有签名。

---

## 4. 前端 Reader.vue 改动

### 4.1 新增状态

```typescript
type Direction = "en-to-zh" | "zh-to-en";
const STORAGE_KEY_DIR = "wordglass.reader.dir";
const direction = ref<Direction>(loadDir());

interface SelectedWord {
  text: string;
  loading: boolean;
  found: boolean;
  phonetic: string;
  pos: string;
  translation: string;
  alreadySaved: boolean;
  adding: boolean;
  addError: string;
}
const selected = ref<SelectedWord | null>(null);  // 替代原 popup
```

### 4.2 状态语义

- `direction` 决定哪一面是原文，哪一面是译文：
  - `en-to-zh` → 左 = English，右 = Chinese
  - `zh-to-en` → 左 = Chinese，右 = English
- 现有 `english` 和 `chinese` ref 含义不变，**都按内容语言命名**，不按位置。展示时根据方向决定哪个进左 pane / 哪个进右 pane。

### 4.3 切换方向

```typescript
function setDirection(d: Direction) {
  if (d === direction.value) return;
  cancelDebounce();
  direction.value = d;
  // 清空两边 + 取消选中单词 + 回到编辑态
  english.value = "";
  chinese.value = "";
  selected.value = null;
  mode.value = "edit";
  lastTranslatedText = "";
  localStorage.setItem(STORAGE_KEY_DIR, d);
}
```

### 4.4 翻译流程

```typescript
async function doTranslate() {
  // 取「源语言」内容
  const source = direction.value === "en-to-zh" ? english.value : chinese.value;
  const targetLang = direction.value === "en-to-zh" ? "zh" : "en";
  const text = source.trim();
  if (!text || loading.value) return;

  loading.value = true;
  try {
    const res = await api.translateText(text, targetLang);
    // 写到「目标语言」存储
    if (direction.value === "en-to-zh") {
      chinese.value = res.translation;
    } else {
      english.value = res.translation;
    }
    lastTranslatedText = text;
    // 不在 textarea 聚焦时切回阅读态（保留现行为）
    if (sourceText().trim() === text && !textareaFocused()) {
      mode.value = "read";
    }
  } catch (e: any) {
    error.value = e.message || "翻译失败";
  } finally {
    loading.value = false;
  }
}
```

`scheduleTranslate` 中也用 `direction.value` 取源语言内容。

### 4.5 原文清空 → 译文清空

watch source 字段时（根据方向是 `english` 或 `chinese`），如果新值 trim 后为空，把目标字段也置空、selected 清掉、回到编辑态。

### 4.6 词点击行为（en→中模式独有）

```typescript
function isWord(t: { kind: "word" | "gap" }): boolean {
  return t.kind === "word";
}

function onWordClick(event: MouseEvent, word: string) {
  if (direction.value !== "en-to-zh") return;  // 中→英模式下点词无效
  event.stopPropagation();
  loadWordDetail(word);
}

async function loadWordDetail(word: string) {
  selected.value = {
    text: word, loading: true, found: false, phonetic: "", pos: "",
    translation: "", alreadySaved: false, adding: false, addError: "",
  };
  try {
    const data = await api.previewWord(word);
    if (selected.value?.text !== word) return;  // 用户已点其它词
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
```

### 4.7 中文原文渲染

`tokens` computed 仍按英文单词正则切片，仅在 `direction === "en-to-zh"` 时使用。

中→英模式下：
- 阅读态 (`.reading` 区) 直接渲染纯文本（`<div class="reading-plain">{{ chinese }}</div>`，`white-space: pre-wrap`），不分词、不绑 click handler、不渲染 `<span class="w">`
- textarea 提示词改为「把中文段落粘进来 / 输入要翻译成英文的内容…」
- 模式切换逻辑（点空白 → edit）保留

### 4.8 移除原 popup
- 整个 `.popup` DOM 块删除
- `popup` ref 删除（被 `selected` 替代）
- 阅读态下被选中的单词加 `.w.active` 高亮：`:class="{ active: selected?.text === t.text }"`
- 不再需要 `document.click` 关闭 popup
- Esc 改为：如有 `selected`，置 null 关闭面板

```typescript
function onKey(e: KeyboardEvent) {
  if (e.key === "Escape" && selected.value) selected.value = null;
}
```

`onMounted` 只注册 keydown，不再注册全局 click。`onBeforeUnmount` 同步清理。

### 4.9 底部面板布局

```vue
<!-- 底部单词详情面板 · 只在 en→zh 模式显示 -->
<section
  v-if="direction === 'en-to-zh'"
  class="word-panel glass"
>
  <!-- 空态 -->
  <div v-if="!selected" class="word-panel-empty tertiary">
    <span class="hint-emoji">🔎</span>
    点任意英文单词查看读法和释义
  </div>

  <!-- 加载态 -->
  <div v-else-if="selected.loading" class="word-panel-loading muted">
    查询「{{ selected.text }}」…
  </div>

  <!-- 找到了 -->
  <div v-else-if="selected.found" class="word-panel-detail">
    <div class="wp-head">
      <span class="wp-word">{{ selected.text }}</span>
      <span v-if="selected.phonetic" class="wp-phon">{{ selected.phonetic }}</span>
      <span v-if="selected.pos" class="wp-pos">{{ selected.pos }}</span>
    </div>
    <div class="wp-trans">{{ selected.translation }}</div>
    <div class="wp-actions">
      <span v-if="selected.alreadySaved" class="wp-saved">✓ 已在单词库</span>
      <button
        v-else
        class="btn btn-primary"
        :disabled="selected.adding"
        @click="addSelectedWord"
      >
        {{ selected.adding ? "添加中…" : "+ 加入单词库" }}
      </button>
      <button class="btn btn-ghost wp-close" @click="selected = null">关闭</button>
    </div>
    <div v-if="selected.addError" class="wp-error">{{ selected.addError }}</div>
  </div>

  <!-- 未收录 -->
  <div v-else class="word-panel-not-found">
    <div class="wp-head">
      <span class="wp-word">{{ selected.text }}</span>
    </div>
    <div class="muted small">
      本地词典没收录这个词。配置了 AI 的话可以直接「加入单词库」让 AI 兜底翻译。
    </div>
    <div class="wp-actions">
      <button
        class="btn btn-primary"
        :disabled="selected.adding"
        @click="addSelectedWord"
      >
        {{ selected.adding ? "添加中…" : "+ 加入单词库" }}
      </button>
      <button class="btn btn-ghost wp-close" @click="selected = null">关闭</button>
    </div>
    <div v-if="selected.addError" class="wp-error">{{ selected.addError }}</div>
  </div>
</section>
```

### 4.10 方向 toggle 组件

放在页面 header 右侧，胶囊样式：

```vue
<div class="dir-toggle">
  <button :class="{ active: direction === 'en-to-zh' }" @click="setDirection('en-to-zh')">
    英 → 中
  </button>
  <button :class="{ active: direction === 'zh-to-en' }" @click="setDirection('zh-to-en')">
    中 → 英
  </button>
</div>
```

样式参考 Practice.vue 现有的 `.direction` toggle（已 token 化），可以 copy 一份本地版本或者把 token-driven 版本提取为公共 class（**本次不提取，保持现有组件边界**）。

### 4.11 面板的左 / 右映射

```typescript
const sourceText = computed({
  get: () => direction.value === "en-to-zh" ? english.value : chinese.value,
  set: (v: string) => {
    if (direction.value === "en-to-zh") english.value = v;
    else chinese.value = v;
  },
});

const targetText = computed(() => direction.value === "en-to-zh" ? chinese.value : english.value);

const sourceLabel = computed(() => direction.value === "en-to-zh" ? "原文（English）" : "原文（中文）");
const targetLabel = computed(() => direction.value === "en-to-zh" ? "译文（中文）" : "译文（English）");
```

textarea 改用 `sourceText` 双向绑定。

---

## 5. 数据 / Storage

### 5.1 localStorage keys

| Key | 值 | 说明 |
|---|---|---|
| `wordglass.reader` | `{ en, zh }` | 现有，保留 |
| `wordglass.reader.dir` | `"en-to-zh" \| "zh-to-en"` | **新增**，启动时读取 |

切换方向清空时也要把 `wordglass.reader` 写回 `{ en: "", zh: "" }`。

### 5.2 启动逻辑

1. 读 `wordglass.reader.dir`，无则默认 `"en-to-zh"`
2. 读 `wordglass.reader` 得到 `{ en, zh }`
3. 根据 direction 决定初始 `mode`：源字段非空 → `"read"`，否则 `"edit"`
4. `lastTranslatedText` 初始化为当前源字段的值

---

## 6. UI 细节 / 视觉

### 6.1 整体布局

```
┌─────────────────────────────────────────────────┐
│ 📖 阅读 & 翻译       [英→中] [中→英]   (提示词)  │
│                                                  │
│ ┌───────────────┐  ┌───────────────┐             │
│ │ 原文（English） │  │ 译文（中文）    │             │
│ │ (textarea or  │  │ (chinese or   │             │
│ │  read mode)   │  │  empty/skel)  │             │
│ │               │  │               │             │
│ └───────────────┘  └───────────────┘             │
│                                                  │
│ ┌─────────────────────────────────────────────┐  │
│ │ 单词详情面板 (en→中 模式下显示)               │  │
│ │ word /phonetic/ pos                          │  │
│ │ translation                                  │  │
│ │ [+ 加入单词库] [关闭]                         │  │
│ └─────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────┘
```

### 6.2 方向 toggle 样式（沿用 Practice 模式）

```css
.dir-toggle {
  display: inline-flex;
  gap: 4px;
  padding: 4px;
  background: var(--glass-bg-dim);
  border-radius: 999px;
  border: 1px solid var(--glass-border);
}
.dir-toggle button {
  appearance: none;
  background: transparent;
  border: none;
  padding: 6px 16px;
  border-radius: 999px;
  font: inherit;
  font-size: 13px;
  font-weight: 500;
  color: var(--text-secondary);
  cursor: pointer;
  transition: background 150ms ease, color 150ms ease;
}
.dir-toggle button.active {
  background: var(--brand-soft);
  color: var(--brand);
}
.dir-toggle button:hover:not(.active) {
  color: var(--text-primary);
}
```

### 6.3 底部面板样式

- 玻璃卡（`.glass`）
- 内边距 `18px 22px`
- 左侧 3px 墨绿边框（与 Dashboard hero 卡呼应）
- 高度自适应内容；空态较矮（约 70px），有内容时 120-160px
- 不可滚动（内容溢出靠 word-wrap，不内滚）
- 词性、音标样式与 Reader 现有 popup 内的样式复用
- 词字号 26px 衬线（比 popup 大）

### 6.4 已选中单词在原文里的高亮

`.w.active` 沿用现样式（墨绿背景 + 白字）。当 `selected` 清掉时 active 也清掉。

### 6.5 中→英模式的原文区

`textarea` 提示词改为「把中文段落粘进来 / 输入要翻译成英文的内容…」。阅读态下中文文字不可点（光标默认 text，不变手指）。

---

## 7. 错误处理

- 中→英时后端要求 AI 已配置。如未配置返回 502 + 友好消息「AI 未配置，无法翻译整段文本…」。前端在 `.error` 里显示，引导去设置页。
- API 调用失败保留现 `error` ref 显示。
- 切换方向后立刻清空 `error`。

---

## 8. 验收

- 切方向：两边内容清空、底部面板（如可见）也清空、UI 立即响应
- 翻译方向 en→中：粘 English → 几秒后右边出中文（与现行为完全一致）
- 翻译方向 中→英：粘 Chinese → 几秒后右边出 English（新功能）
- 点单词：英文单词点击后底部面板出读法、释义、+加入按钮
- 加入单词库：点击后状态变成「✓ 已在单词库」，无错则面板可保留显示直到用户主动关闭或点其他单词
- 删除全部原文：译文同步消失
- localStorage 持久化：刷新后方向、原文、译文都还在
- 暗色 / 亮色主题正常
- TypeScript 编译通过（`npm run build`）
- Dashboard、Library、Practice、Settings 五个页面完全不受影响

---

## 9. 实施顺序（plan 阶段细化）

1. 后端 `TranslateIn` 加 `target_lang`，分支 system prompt
2. `api.ts` `translateText` 加可选第二参
3. Reader.vue：加 direction state + storage 持久化 + setDirection
4. Reader.vue：sourceText / targetText computed + textarea / reading 区切换
5. Reader.vue：移除 popup DOM + 把交互改为底部面板
6. Reader.vue：方向 toggle 组件
7. Reader.vue：中→英 模式下面板隐藏、词不可点
8. 跑 build + 手动验收（启 dev、明暗都过、五种交互组合）

---

## 10. 不做（明确避免漂移）

- 不引入流式翻译
- 不引入翻译历史 / 多翻译会话
- 不把 popup 留下来同时存在
- 不动 Dashboard、Library、Practice、Settings 的 Reader 相关代码
- 不把 `.dir-toggle` 抽到 glass.css 公共类（保持本地）
