# 主页换组件：薄弱词 + Practice 专练模式 · 设计稿

**日期**: 2026-05-14
**目标**: 删掉主页右侧的"学习热力图"组件，换成"最薄弱的词"列表。点单词或"集中练"CTA 跳到 Practice 页面，Practice 支持 `?word_ids=1,2,3` 查询参数只练这几个词。

---

## 1. 范围与约束

### 范围内
- 后端 `app/routes/stats.py` —— 新增 `GET /api/stats/weak-words?limit=N`
- 前端 `frontend/src/api.ts` —— 加 `weakWords(limit)` 方法 + 类型
- 前端 `frontend/src/components/Heatmap.vue` —— **删除**（不再使用）
- 前端 `frontend/src/components/WeakWords.vue` —— **新建**
- 前端 `frontend/src/views/Dashboard.vue` —— 用 WeakWords 替换 Heatmap，去掉 `heat` ref 和 `refreshHeatmap()` 调用
- 前端 `frontend/src/views/Practice.vue` —— 支持 `?word_ids=<comma-separated>` 查询参数

### 范围外
- 删除后端 `/api/stats/heatmap` 路由（前端不再调用，但保留向后兼容）
- 改 Practice 的复习算法 / 间隔重复逻辑
- 新增"专练模式"的复杂 UI 标识（共用现有 Practice 页面，只是 queue 不同）
- 给 WordDetail 加跳转入口

### 不能损坏
- Dashboard 上其它组件：AddBar / Recent / 今日待复习 / 3 个 stat 卡
- Practice 现有的 tab 切换、方向切换、字母槽、抽认卡逻辑
- "今日待复习"卡片的「开始练习 →」CTA（继续跳 `/practice` 无参数）

---

## 2. 后端 · `/api/stats/weak-words`

新增 endpoint，返回"复习过 + 出错最多 / 掌握度最低"的词。

### 2.1 排序逻辑

```
SELECT * FROM words
WHERE user_id = :user_id
  AND review_count > 0      -- 必须练过才算「薄弱」
ORDER BY
  (review_count - correct_count) DESC,   -- 错得最多的优先
  mastery ASC,                            -- 同样错的次数，掌握度低的优先
  created_at DESC                         -- 平局取新的
LIMIT :limit
```

如果 `review_count = 0`（一次都没练过），不算薄弱 —— 这些只是"还没复习"。

### 2.2 路由

```python
# app/routes/stats.py 末尾追加：

@router.get("/weak-words")
def weak_words(
    limit: int = Query(default=5, ge=1, le=20),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
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

无新表 / 无 schema 改动。

### 2.3 返回格式

```json
{
  "items": [
    {
      "id": 42,
      "text": "serendipity",
      "translation": "机缘巧合",
      "phonetic": "/ˌserənˈdɪpəti/",
      "mastery": 1,
      "review_count": 4,
      "correct_count": 1,
      "wrong_count": 3
    }
  ]
}
```

---

## 3. 前端 · api.ts

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

// 在 api 对象末尾追加：
weakWords: (limit = 5) =>
  request<{ items: WeakWordItem[] }>(`/api/stats/weak-words?limit=${limit}`),
```

---

## 4. 前端 · `WeakWords.vue`

替代 Heatmap 占据 Dashboard 右侧 sidebar 顶部。组件接口：

- Props: `limit?: number = 5`
- 自动 onMounted 调 `api.weakWords(limit)`
- 每行可点击 → `router.push("/practice?word_ids=" + id)`
- 底部 CTA「→ 集中练这 N 个」→ `router.push("/practice?word_ids=" + ids.join(","))`
- 空态：当无返回（用户从没练习过）显示「练习几次后，这里会列出你最常出错的词」

### 4.1 模板（关键部分）

```vue
<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { api, type WeakWordItem } from "../api";

defineProps<{ limit?: number }>();

const router = useRouter();
const items = ref<WeakWordItem[]>([]);
const loading = ref(false);

async function reload() {
  loading.value = true;
  try {
    const { items: list } = await api.weakWords(5);
    items.value = list;
  } catch { /* keep empty */ } finally {
    loading.value = false;
  }
}

function practiceOne(id: number) {
  router.push({ path: "/practice", query: { word_ids: String(id) } });
}

function practiceAll() {
  const ids = items.value.map((w) => w.id).join(",");
  router.push({ path: "/practice", query: { word_ids: ids } });
}

const masteryPips = (m: number) => [0, 1, 2, 3, 4].map((i) => i < m);

onMounted(reload);
defineExpose({ reload });
</script>

<template>
  <section class="weak-widget glass">
    <div class="widget-head">
      <h3>最薄弱的词</h3>
      <span class="tertiary small">复习过但反复出错</span>
    </div>

    <div v-if="loading && items.length === 0" class="empty tertiary small">加载中…</div>
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
          <span class="weak-word">{{ w.text }}</span>
          <div class="weak-tr">{{ w.translation || '（无翻译）' }}</div>
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
```

### 4.2 样式

参考现有 `WordCard.vue` 和 widget 风格，但更紧凑：

- 容器 `.weak-widget`：复用 `.glass` 卡片
- 每行 `.weak-item`：grid 3 列（单词+释义 / mastery pips / 错次），padding 6-8px，hover 背景变 `--glass-bg-strong`
- `.weak-word`：衬线 13px
- `.weak-tr`：斜体小字 11px
- `.weak-stat`：`--danger` 色，10px mono
- `.practice-all`：底部 CTA，全宽，glass dim 背景，hover 变 brand

具体 CSS 参考 mockup（见之前的浏览器伴侣页）。

---

## 5. 前端 · Dashboard.vue 改动

### 5.1 导入

```typescript
// 删除：
import Heatmap from "../components/Heatmap.vue";

// 加：
import WeakWords from "../components/WeakWords.vue";
```

### 5.2 删除 heatmap 相关 state 和函数

```typescript
// 删除：
const heat = ref<HeatmapData>({ days: {}, since: "" });
async function refreshHeatmap() { ... }

// 删除 refreshAll 里的 refreshHeatmap() 调用
// 删除 onAdded 里的 refreshHeatmap() 调用
// 删除 activeDays / totalActions 两个 computed
```

`HeatmapData` 类型从 import 列表里删掉。

### 5.3 模板替换

把：

```vue
<section class="widget glass heatmap-widget">
  <div class="widget-head">
    <h3>学习热力图</h3>
    <span class="tertiary small">{{ activeDays }} 天 · {{ totalActions }} 次</span>
  </div>
  <Heatmap :data="heat.days" :weeks="12" />
</section>
```

改成：

```vue
<WeakWords class="weak-widget-wrap" />
```

`.heatmap-widget` 的 CSS 选择器可以删；新增 `.weak-widget-wrap`（如果需要 sidebar 间距对齐就保留）。实际上 `.col-side` 已经有 `gap: 14px`，不需要额外包裹样式。

### 5.4 onAdded 简化

```typescript
function onAdded(w: WordOut) {
  lastAdded.value = w;
  refreshStats();
  refreshRecent();
  // refreshHeatmap();  ← 删
  if (ttsSupported) setTimeout(() => speak(w.text), 100);
  if (!w.category || w.examples.length === 0) {
    pollEnrichment(w.id);
  }
}
```

---

## 6. 前端 · Practice.vue 支持 `?word_ids=`

### 6.1 改 load() 函数

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
import { useRoute } from "vue-router";
const route = useRoute();

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
        // 并发拉取所有指定的词
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

### 6.2 路由变化时重新 load

加 watcher 监听 `route.query.word_ids`：当从某词跳来再跳别的词，需要重新 load。

```typescript
import { watch } from "vue";

watch(() => route.query.word_ids, () => {
  load();
});
```

### 6.3 UI 提示「专练模式」

`Practice.vue` 顶部如果是 word_ids 模式，加一个 banner 提示「专练 N 个薄弱词 · 完成后可回主页继续」。

```vue
<div v-if="isFocusMode" class="focus-banner glass-dim">
  💪 专练模式 · {{ queue.length }} 个词
  <button class="link-btn" @click="exitFocus">退出专练</button>
</div>
```

```typescript
const isFocusMode = computed(() => {
  const v = route.query.word_ids;
  return typeof v === "string" && v.length > 0;
});
function exitFocus() {
  router.push({ path: "/practice" });
  // watcher 会触发 load() 重新拿 due 队列
}
```

样式：banner 暖褐色背景，与 brand-soft 区分。

### 6.4 「再来一组」按钮的行为

`/practice?word_ids=42` 完成后点「再来一组」会再次加载同一个词 —— 行为对，无需改。
要回到 due 队列点「回首页」或「退出专练」。

---

## 7. 删除 Heatmap.vue

`frontend/src/components/Heatmap.vue` 已无引用，可直接 `rm`。后端 `/api/stats/heatmap` 端点保留（向后兼容，万一有人在外部脚本依赖）。

---

## 8. 错误处理

- `weakWords` 接口失败 → 组件显示加载失败小字，不影响其它 dashboard 组件
- Practice 加载 word_ids 时若某 id 不存在（404） → `Promise.all` rejects → 走 `loadError` 流程，红字提示"加载失败"。可以容错：用 `Promise.allSettled` 过滤掉 404，只练成功加载的；本次先用 `Promise.all` 简单实现，rare case 不优化
- word_ids 全部无效（如 `?word_ids=abc`）→ queue 为空 → 走"今天没有需要复习的单词"分支

---

## 9. 验收

- Dashboard 右侧 sidebar 顶部不再是热力图，而是"最薄弱的词"
- 新用户（无练习记录）→ 空态文案"练习几次后…"
- 老用户（有错过的词）→ 列出 top 5，每行单词 + 释义 + mastery pips + 错次
- 点单行 → 跳 `/practice?word_ids=X` → Practice 只显示这一个词
- 点「→ 集中练这 N 个」→ Practice 显示这 N 个词
- 专练模式下 Practice 顶部显示 banner 「💪 专练模式 · N 个词」+ 退出按钮
- "回首页"按钮回 Dashboard 不带任何 query
- 暗色 / 亮色都正常
- `npm run build` 通过
- 后端 `python3 -m py_compile` 通过

---

## 10. 不做

- 不批量编辑 / 删除薄弱词
- 不显示曾错的具体次数（4/3 那种）—— 只显示总错次足够
- 不动 Practice 的间隔重复评分逻辑
- 不为专练模式单独算 mastery 阶梯 —— 共用现有的
