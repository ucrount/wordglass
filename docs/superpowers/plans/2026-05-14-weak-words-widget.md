# 薄弱词 widget · 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 删除 Dashboard 的热力图，换成"最薄弱的词"列表；Practice 支持 `?word_ids=` 专练模式，从 widget 点单词或批量练习直接进入只练这几个的页面。

**Architecture:** 后端 `/api/stats/weak-words` 按 `(review_count - correct_count) DESC, mastery ASC` 排序返回 top N。前端新组件 `WeakWords.vue` 替代 `Heatmap.vue`；`Practice.vue` 监听 `route.query.word_ids` 决定 queue 来源（`api.getWord` 并发拉取 vs `api.dueWords`）。

**Tech Stack:** FastAPI + SQLAlchemy · Vue 3 + TypeScript · `vue-tsc -b && vite build` 验证。

**前置：** spec `docs/superpowers/specs/2026-05-14-weak-words-widget-design.md`

---

## 任务结构

```
T1 后端 /api/stats/weak-words endpoint
T2 前端 api.ts 加 weakWords + 类型
T3 前端新建 WeakWords.vue 组件
T4 前端 Dashboard.vue 用 WeakWords 替换 Heatmap
T5 前端删除 Heatmap.vue
T6 前端 Practice.vue 支持 ?word_ids= 专练模式
T7 Build + 手动 smoke
```

T2-T6 顺序：T2 必先；T3 依赖 T2；T4 依赖 T3；T5 只是 rm；T6 独立。

---

## Task 1: 后端 `/api/stats/weak-words` endpoint

**Files:**
- Modify: `backend/app/routes/stats.py`

**Spec ref:** §2

- [ ] **Step 1: 在 `backend/app/routes/stats.py` 文件末尾追加 endpoint**

```python


@router.get("/weak-words")
def weak_words(
    limit: int = Query(default=5, ge=1, le=20),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    """Return top-N words the user has reviewed but gets wrong most often.

    Sort key:
      1. wrong_count = review_count - correct_count, DESC
      2. mastery, ASC
      3. created_at, DESC (tie-breaker, newer first)

    Only words with review_count > 0 are considered — never-reviewed words
    aren't "weak", they're just "未练".
    """
    rows = (
        db.query(Word)
        .filter(Word.user_id == user.id, Word.review_count > 0)
        .order_by(
            (Word.review_count - Word.correct_count).desc(),
            Word.mastery.asc(),
            Word.created_at.desc(),
        )
        .limit(limit)
        .all()
    )
    return {
        "items": [
            {
                "id": w.id,
                "text": w.text,
                "translation": w.translation or "",
                "phonetic": w.phonetic or "",
                "mastery": w.mastery,
                "review_count": w.review_count,
                "correct_count": w.correct_count,
                "wrong_count": (w.review_count or 0) - (w.correct_count or 0),
            }
            for w in rows
        ]
    }
```

- [ ] **Step 2: 语法检查**

```bash
cd /Users/mm/wordglass/backend && python3 -m py_compile app/routes/stats.py && echo "syntax ok"
```

Expected: `syntax ok`

- [ ] **Step 3: 提交**

```bash
cd /Users/mm/wordglass && git add backend/app/routes/stats.py && git commit -m "$(cat <<'EOF'
stats: add GET /api/stats/weak-words

Returns top-N words the current user has reviewed but gets wrong most often.
Sort: wrong_count DESC, mastery ASC, created_at DESC. Excludes never-reviewed
words (review_count > 0 filter).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: 前端 `api.ts` 加 `weakWords` + 类型

**Files:**
- Modify: `frontend/src/api.ts`

**Spec ref:** §3

- [ ] **Step 1: 在 `frontend/src/api.ts` 末尾的现有类型定义区域追加 `WeakWordItem`**

定位：在 `export interface SystemLogRecord` 之后、`export interface CurlReq` 之前（或任意类型集中区），插入：

```typescript
export interface WeakWordItem {
  id: number;
  text: string;
  translation: string;
  phonetic: string;
  mastery: number;
  review_count: number;
  correct_count: number;
  wrong_count: number;
}
```

- [ ] **Step 2: 在 `export const api = { ... }` 的最后一个方法之后追加 `weakWords`**

定位：在 `listUsers: ...` 之后、`};` 之前，插入：

```typescript

  weakWords: (limit = 5) =>
    request<{ items: WeakWordItem[] }>(`/api/stats/weak-words?limit=${limit}`),
```

- [ ] **Step 3: 跑 build**

```bash
cd /Users/mm/wordglass/frontend && npm run build 2>&1 | tail -3
```

Expected: 通过。

- [ ] **Step 4: 提交**

```bash
cd /Users/mm/wordglass && git add frontend/src/api.ts && git commit -m "api: add weakWords() + WeakWordItem type

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: 创建 `WeakWords.vue` 组件

**Files:**
- Create: `frontend/src/components/WeakWords.vue`

**Spec ref:** §4

- [ ] **Step 1: 创建 `frontend/src/components/WeakWords.vue`**

```vue
<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { api, type WeakWordItem } from "../api";

defineProps<{ limit?: number }>();

const router = useRouter();
const items = ref<WeakWordItem[]>([]);
const loading = ref(false);
const error = ref("");

async function reload() {
  loading.value = true;
  error.value = "";
  try {
    const { items: list } = await api.weakWords(5);
    items.value = list;
  } catch (e: any) {
    error.value = e.message || "加载失败";
  } finally {
    loading.value = false;
  }
}

function practiceOne(id: number) {
  router.push({ path: "/practice", query: { word_ids: String(id) } });
}

function practiceAll() {
  if (items.value.length === 0) return;
  const ids = items.value.map((w) => w.id).join(",");
  router.push({ path: "/practice", query: { word_ids: ids } });
}

const masteryPips = (m: number) => [0, 1, 2, 3, 4].map((i) => i < m);

defineExpose({ reload });
onMounted(reload);
</script>

<template>
  <section class="weak-widget glass">
    <div class="widget-head">
      <h3>最薄弱的词</h3>
      <span class="tertiary small">复习过但反复出错</span>
    </div>

    <div v-if="loading && items.length === 0" class="empty tertiary small">
      加载中…
    </div>

    <div v-else-if="error" class="empty error small">{{ error }}</div>

    <div v-else-if="items.length === 0" class="empty tertiary small">
      练习几次后，这里会列出你最常出错的词。
    </div>

    <div v-else class="weak-list">
      <div
        v-for="w in items"
        :key="w.id"
        class="weak-item"
        @click="practiceOne(w.id)"
        :title="`练这一个：${w.text}`"
      >
        <div class="weak-text">
          <div class="weak-word">{{ w.text }}</div>
          <div class="weak-tr tertiary">{{ w.translation || '（无翻译）' }}</div>
        </div>
        <div class="weak-pips" :title="`掌握度 ${w.mastery}/5`">
          <span
            v-for="(on, i) in masteryPips(w.mastery)"
            :key="i"
            class="pip"
            :class="{ on }"
          />
        </div>
        <span class="weak-stat">{{ w.wrong_count }} 错</span>
      </div>
      <button class="practice-all" @click="practiceAll">
        → 集中练这 {{ items.length }} 个
      </button>
    </div>
  </section>
</template>

<style scoped>
.weak-widget {
  padding: 14px 18px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.widget-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
}
.widget-head h3 {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}
.small { font-size: 11px; }
.tertiary { color: var(--text-tertiary); }
.error { color: var(--danger); }

.empty {
  padding: 12px 4px;
  text-align: center;
  line-height: 1.5;
}

.weak-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.weak-item {
  display: grid;
  grid-template-columns: 1fr auto auto;
  align-items: center;
  gap: 10px;
  padding: 7px 10px;
  border-radius: 8px;
  background: var(--glass-bg-dim);
  border: 1px solid var(--hairline);
  cursor: pointer;
  transition: background 150ms ease, border-color 150ms ease;
}
.weak-item:hover {
  background: var(--brand-soft);
  border-color: color-mix(in srgb, var(--brand) 32%, transparent);
}

.weak-text {
  min-width: 0;
}
.weak-word {
  font-family: var(--font-serif);
  font-weight: 700;
  font-size: 13.5px;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.weak-tr {
  font-size: 11px;
  font-style: italic;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-top: 1px;
}

.weak-pips {
  display: flex;
  gap: 2px;
}
.weak-pips .pip {
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background: var(--hairline-strong);
}
.weak-pips .pip.on {
  background: var(--brand);
}

.weak-stat {
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 600;
  color: var(--danger);
  white-space: nowrap;
}

.practice-all {
  appearance: none;
  border: 1px dashed var(--hairline-strong);
  background: transparent;
  color: var(--brand);
  font: inherit;
  font-size: 11.5px;
  font-weight: 600;
  padding: 7px 10px;
  border-radius: 8px;
  cursor: pointer;
  margin-top: 2px;
  transition: background 150ms ease, border-color 150ms ease;
}
.practice-all:hover {
  background: var(--brand-soft);
  border-color: var(--brand);
  border-style: solid;
}
</style>
```

- [ ] **Step 2: build**

```bash
cd /Users/mm/wordglass/frontend && npm run build 2>&1 | tail -3
```

Expected: 通过。

- [ ] **Step 3: 提交**

```bash
cd /Users/mm/wordglass && git add frontend/src/components/WeakWords.vue && git commit -m "components: WeakWords — top-N error-prone words with click-to-practice

Each row is clickable to jump into Practice focus mode on that single word.
A bottom CTA opens focus mode on all listed words at once.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: Dashboard 用 WeakWords 替换 Heatmap

**Files:**
- Modify: `frontend/src/views/Dashboard.vue`

**Spec ref:** §5

- [ ] **Step 1: 改 import 块**

打开 `frontend/src/views/Dashboard.vue`，找到顶部 import 区域。把 `import Heatmap from "../components/Heatmap.vue";` 改成 `import WeakWords from "../components/WeakWords.vue";`：

```typescript
import { computed, onMounted, onUnmounted, ref } from "vue";
import { RouterLink } from "vue-router";
import { api, type Stats, type WordBrief, type WordOut } from "../api";
import AddBar from "../components/AddBar.vue";
import WeakWords from "../components/WeakWords.vue";
import WordCard from "../components/WordCard.vue";
import { isSpeechSupported, speak } from "../composables/tts";
```

注意：
- 删了 `Heatmap` import
- 删了 `HeatmapData` 类型 import（在 `api` 那一行）—— 它原本在 `import { api, type HeatmapData, type Stats, ... }` 里，把 `type HeatmapData,` 去掉

- [ ] **Step 2: 删 heatmap state + functions + computed**

把：

```typescript
const heat = ref<HeatmapData>({ days: {}, since: "" });
```

整行删除。

把：

```typescript
async function refreshHeatmap() {
  try { heat.value = await api.heatmap(84); } catch { /* ignore */ }
}
```

整个函数删除。

把 `refreshAll` 函数里的 `refreshHeatmap()` 调用删除：

```typescript
async function refreshAll() {
  await Promise.all([refreshStats(), refreshRecent()]);
  initialLoad.value = false;
}
```

（原本是 `Promise.all([refreshStats(), refreshHeatmap(), refreshRecent()])`，去掉中间那个）

把 `onAdded` 里的 `refreshHeatmap()` 调用删除：

```typescript
function onAdded(w: WordOut) {
  lastAdded.value = w;
  refreshStats();
  refreshRecent();
  if (ttsSupported) setTimeout(() => speak(w.text), 100);
  if (!w.category || w.examples.length === 0) {
    pollEnrichment(w.id);
  }
}
```

把：

```typescript
const activeDays = computed(() => Object.keys(heat.value.days).length);
const totalActions = computed(() =>
  Object.values(heat.value.days).reduce((a, b) => a + b, 0)
);
```

整个两块 computed 删除。

- [ ] **Step 3: 改模板**

找到模板里的 heatmap section：

```vue
<!-- Heatmap -->
<section class="widget glass heatmap-widget">
  <div class="widget-head">
    <h3>学习热力图</h3>
    <span class="tertiary small">{{ activeDays }} 天 · {{ totalActions }} 次</span>
  </div>
  <Heatmap :data="heat.days" :weeks="12" />
</section>
```

整段替换成：

```vue
<WeakWords />
```

- [ ] **Step 4: 删除现已无引用的 `.heatmap-widget` 样式（在 `<style scoped>` 内）**

找到：

```css
.heatmap-widget { flex-shrink: 0; }
```

删掉这一行。

- [ ] **Step 5: build**

```bash
cd /Users/mm/wordglass/frontend && npm run build 2>&1 | tail -3
```

Expected: 通过。

- [ ] **Step 6: 提交**

```bash
cd /Users/mm/wordglass && git add frontend/src/views/Dashboard.vue && git commit -m "Dashboard: replace Heatmap with WeakWords

The heatmap was passive 'how active you've been' data with no next action.
WeakWords surfaces 'which words you keep getting wrong' with click-to-drill.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: 删除 Heatmap.vue

**Files:**
- Delete: `frontend/src/components/Heatmap.vue`

**Spec ref:** §7

- [ ] **Step 1: 确认无引用后删除**

```bash
grep -rn "Heatmap" /Users/mm/wordglass/frontend/src 2>&1 | grep -v "components/Heatmap.vue:"
```

Expected: 无输出。如果有命中说明 Task 4 漏了一处，回去清理。

- [ ] **Step 2: 删文件**

```bash
rm /Users/mm/wordglass/frontend/src/components/Heatmap.vue
```

- [ ] **Step 3: build**

```bash
cd /Users/mm/wordglass/frontend && npm run build 2>&1 | tail -3
```

Expected: 通过。

- [ ] **Step 4: 提交**

```bash
cd /Users/mm/wordglass && git add -A frontend/src/components/Heatmap.vue && git commit -m "components: delete Heatmap.vue (no longer used)

Backend /api/stats/heatmap endpoint kept for backward compat.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: Practice 支持 `?word_ids=` 专练模式

**Files:**
- Modify: `frontend/src/views/Practice.vue`

**Spec ref:** §6

- [ ] **Step 1: 加 `useRoute` + `useRouter` + `computed` 到 import**

找到 Practice.vue 顶部 script 现有的 vue 和 vue-router 导入。把：

```typescript
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from "vue";
import { RouterLink } from "vue-router";
```

改成：

```typescript
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from "vue";
import { RouterLink, useRoute, useRouter } from "vue-router";
```

- [ ] **Step 2: 在现有 reactive state 区域底部（`session` 之后、`load()` 之前）加 route + focus computed**

具体位置：在 `const session = ref(...)` 那一行附近。加：

```typescript
const route = useRoute();
const router = useRouter();

const isFocusMode = computed(() => {
  const v = route.query.word_ids;
  return typeof v === "string" && v.length > 0;
});

function exitFocus() {
  router.push({ path: "/practice" });
}
```

- [ ] **Step 3: 改 `load()` 函数支持 word_ids 模式**

把：

```typescript
async function load() {
  loading.value = true;
  loadError.value = "";
  try {
    queue.value = await api.dueWords(50);
    current.value = 0;
    session.value = { done: 0, correct: 0 };
    resetCard();
  } catch (e: any) {
    loadError.value = e.message || "加载失败";
  } finally {
    loading.value = false;
  }
}
```

改成：

```typescript
async function load() {
  loading.value = true;
  loadError.value = "";
  try {
    const raw = route.query.word_ids;
    if (typeof raw === "string" && raw.length > 0) {
      const ids = raw
        .split(",")
        .map((s) => parseInt(s.trim(), 10))
        .filter((n) => !Number.isNaN(n));
      if (ids.length > 0) {
        const results = await Promise.all(ids.map((id) => api.getWord(id)));
        queue.value = results;
      } else {
        queue.value = [];
      }
    } else {
      queue.value = await api.dueWords(50);
    }
    current.value = 0;
    session.value = { done: 0, correct: 0 };
    resetCard();
  } catch (e: any) {
    loadError.value = e.message || "加载失败";
  } finally {
    loading.value = false;
  }
}
```

- [ ] **Step 4: 加 watcher 监听 query 变化**

在 `watch(direction, ...)` 之后（约文件中部）追加：

```typescript
watch(() => route.query.word_ids, () => {
  load();
});
```

- [ ] **Step 5: 模板加 focus banner**

找到模板最外层 `<div class="practice">` 开头之后、`<div v-if="!loading && !loadError && total > 0 && !finished" class="tabs glass">` 之前，加：

```vue
<div v-if="isFocusMode && !loading && !loadError" class="focus-banner glass-dim">
  <span class="focus-icon">💪</span>
  <span class="focus-text">专练模式 · {{ total }} 个词</span>
  <button class="exit-focus" @click="exitFocus">退出专练</button>
</div>
```

- [ ] **Step 6: 加 banner 样式**

在 `<style scoped>` 末尾、`</style>` 之前追加：

```css
.focus-banner {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 14px;
  border-radius: 999px;
  font-size: 13px;
  color: var(--accent);
  background: color-mix(in srgb, var(--accent) 12%, transparent);
  border: 1px solid color-mix(in srgb, var(--accent) 32%, transparent);
  align-self: flex-start;
}
.focus-icon { font-size: 14px; }
.focus-text { font-weight: 600; }
.exit-focus {
  appearance: none;
  background: transparent;
  border: none;
  color: var(--text-secondary);
  font: inherit;
  font-size: 11.5px;
  cursor: pointer;
  text-decoration: underline;
  padding: 0;
  margin-left: 4px;
}
.exit-focus:hover { color: var(--text-primary); }
```

- [ ] **Step 7: build**

```bash
cd /Users/mm/wordglass/frontend && npm run build 2>&1 | tail -3
```

Expected: 通过。

- [ ] **Step 8: 提交**

```bash
cd /Users/mm/wordglass && git add frontend/src/views/Practice.vue && git commit -m "$(cat <<'EOF'
Practice: ?word_ids=1,2,3 focus mode — practice only the specified words

When the query string contains word_ids, the queue is built by fetching each
word in parallel instead of pulling the due queue. A banner at the top tells
the user they're in focus mode with an exit button that drops back to the
due queue. Useful from the WeakWords widget on Dashboard.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: Build + smoke

**Files:** 无（验证）

**Spec ref:** §9

- [ ] **Step 1: 全量 build**

```bash
cd /Users/mm/wordglass/frontend && npm run build 2>&1 | tail -5
```

Expected: 通过。

- [ ] **Step 2: 启 dev**

后端：
```bash
cd /Users/mm/wordglass/backend && source .venv/bin/activate && uvicorn app.main:app --reload --port 8000
```

前端：
```bash
cd /Users/mm/wordglass/frontend && npm run dev
```

- [ ] **Step 3: smoke checklist**

| 检查 | 期望 |
|---|---|
| Dashboard 右侧 sidebar 顶部 | 看到「最薄弱的词」框，不再是热力图 |
| 全新用户（无练习） | 显示空态「练习几次后…」 |
| 有错过的词后回 Dashboard | 列表显示 top 5，每行词 + 释义 + mastery pips + 错次 |
| 点单个薄弱词 | 跳 `/practice?word_ids=42`，只有这一个词在 queue，顶部 banner「💪 专练模式 · 1 个词」 |
| 点「→ 集中练这 N 个」 | 跳 `/practice?word_ids=1,2,3,4,5`，5 个词全在 queue |
| 在专练模式点「退出专练」 | URL 变回 `/practice`，queue 变回 due 队列 |
| 在专练模式点「再来一组」 | 同一组词重新加载（query 还在）|
| 在专练模式点「回首页」 | 回 Dashboard 正常 |
| 暗色 / 亮色 | 都正常 |

- [ ] **Step 4: 不提交（QA 不改代码）**

如有问题回到对应 Task 修补，单独 commit。

---

## 完成

7 个 task 跑完后：
- Dashboard 主页右侧没有热力图，是薄弱词列表
- 后端有新 `/api/stats/weak-words` endpoint
- Practice 支持 `?word_ids=` 查询参数 + 顶部 banner + 退出按钮
- Heatmap.vue 已删除

后续 push 在另外的步骤里做。
