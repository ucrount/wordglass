# 单词库 v2 · 分类磁贴重设计

**日期**: 2026-05-14
**目标**: 把单词库从「左分类栏 + 右网格」改成「分类磁贴」内容库风。每个分类是一张大卡，包含样例词、平均掌握度、"练这 N 个"直接行动按钮。点磁贴进入该分类的完整词列表。视口锁定 + 简洁大气。

---

## 1. 范围与约束

### 范围内
- `frontend/src/views/Library.vue` —— 整体重写（模板 + 样式 + script）
- 无后端改动 —— 全部利用现有 endpoints

### 范围外
- `WordDetail.vue` 组件 —— 保留，词点击仍开抽屉
- `WordCard.vue` 组件 —— 仍可用，但本次 Library 不直接用它（用新的 word-row）
- 后端任何 endpoint
- 路由 / API
- 其它视图

### 不能损坏
- 搜索单词
- AI 重新分类未分类的词（🤖 按钮）
- 单词详情抽屉的全部交互（音标、例句、删除）
- 暗色 / 亮色主题
- 移动端响应式
- 单词被删除后 Library 立刻更新

---

## 2. 三种视图模式

Library 内部维护 `view` 状态：

| view | 触发条件 | 显示内容 |
|---|---|---|
| `"tiles"` | 默认 | 分类磁贴网格 |
| `"category"` | 点击某个磁贴 | 该分类的所有单词（带返回按钮）|
| `"search"` | 搜索框非空 | 跨分类匹配的扁平单词列表 |

搜索框始终在顶部可见。任何模式下都能搜。

### 2.1 状态变量

```typescript
type View = "tiles" | "category" | "search";

const view = computed<View>(() => {
  if (q.value.trim()) return "search";
  if (selectedCategory.value !== null) return "category";
  return "tiles";
});

const q = ref("");
const selectedCategory = ref<string | null>(null);  // 分类名 / "未分类"
const allWords = ref<WordBrief[]>([]);              // 一次性加载所有词
const cats = ref<CategoriesOut>({ counts: {}, order: [] });
const detailId = ref<number | null>(null);          // 抽屉用

const selectedBucket = computed(() =>
  selectedCategory.value
    ? buckets.value.find(b => b.name === selectedCategory.value)
    : undefined,
);

function enterCategory(name: string) {
  selectedCategory.value = name;
  q.value = "";  // 清搜索，确保 view 切到 category
}

function exitCategory() {
  selectedCategory.value = null;
}

function openDetail(id: number) {
  detailId.value = id;
}

function closeDetail() {
  detailId.value = null;
}
```

### 2.2 模式切换逻辑

- 搜索框输入 → q 变 → view 自动到 "search"
- 清空搜索 → view 回 "tiles"（或 "category" 如果之前是分类视图）
- 点磁贴 → `selectedCategory = name`，view = "category"
- 点「返回」 → `selectedCategory = null`，view = "tiles"

---

## 3. 数据加载

### 3.1 一次性加载策略

`onMounted` 拉所有单词（≤500），客户端分桶 / 排序 / 算 stats。

```typescript
async function loadAll() {
  loading.value = true;
  try {
    const [list, c] = await Promise.all([
      api.listWords({ limit: 500 }),
      api.listCategories(),
    ]);
    allWords.value = list;
    cats.value = c;
  } catch (e: any) {
    error.value = e.message || "加载失败";
  } finally {
    loading.value = false;
  }
}
```

### 3.2 按分类分桶

```typescript
interface CategoryBucket {
  name: string;
  total: number;
  words: WordBrief[];         // 按 created_at DESC 排序
  avgMastery: number;
  isUncategorized: boolean;
}

const buckets = computed<CategoryBucket[]>(() => {
  const byCat: Record<string, WordBrief[]> = {};
  for (const w of allWords.value) {
    const cat = w.category || "未分类";
    if (!byCat[cat]) byCat[cat] = [];
    byCat[cat].push(w);
  }
  // 排序：未分类放第一（如果有），其它按现有 cats.order 顺序
  const result: CategoryBucket[] = [];
  // Uncategorized first if has any
  if ((byCat["未分类"] || []).length > 0) {
    result.push(toBucket("未分类", byCat["未分类"], true));
  }
  for (const name of cats.value.order) {
    if (name === "未分类") continue;
    const words = byCat[name] || [];
    if (words.length === 0) continue;     // 空分类不显示磁贴
    result.push(toBucket(name, words, false));
  }
  return result;
});

function toBucket(name: string, words: WordBrief[], isUncat: boolean): CategoryBucket {
  const sorted = [...words].sort((a, b) =>
    new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
  );
  const avg = words.reduce((s, w) => s + (w.mastery || 0), 0) / Math.max(1, words.length);
  return {
    name,
    total: words.length,
    words: sorted,
    avgMastery: avg,
    isUncategorized: isUncat,
  };
}
```

### 3.3 搜索匹配

```typescript
const searchResults = computed<WordBrief[]>(() => {
  const term = q.value.trim().toLowerCase();
  if (!term) return [];
  return allWords.value.filter(w =>
    w.text.toLowerCase().includes(term) ||
    (w.translation || "").toLowerCase().includes(term)
  );
});
```

### 3.4 选中分类的词

```typescript
const categoryWords = computed<WordBrief[]>(() => {
  if (!selectedCategory.value) return [];
  const bucket = buckets.value.find(b => b.name === selectedCategory.value);
  return bucket ? bucket.words : [];
});
```

### 3.5 删除后刷新

`onDeleted(id)` 从 `allWords` 移除该词，重新触发 buckets / searchResults computed。同时调 `api.listCategories()` 拿最新计数（虽然 buckets 是客户端算的，但 cats.order 还是要 sync）。

### 3.6 AI 重新分类后刷新

调用 `api.recategorize()` 成功后，`loadAll()` 重新拉全量。

---

## 4. UI 结构

### 4.1 顶层布局

```vue
<div class="library">
  <!-- Header -->
  <header class="page-head">
    <div>
      <h1>单词库</h1>
      <p class="muted small">
        {{ totalCount }} 个 · {{ masteredCount }} 已掌握
        <span v-if="uncategorizedCount > 0" class="warn-chip">
          · {{ uncategorizedCount }} 未分类
        </span>
      </p>
    </div>
  </header>

  <!-- Search bar (always on top) -->
  <div class="search-bar glass">
    <span class="search-icon">🔎</span>
    <input
      v-model="q"
      class="search-input"
      placeholder="搜索单词或翻译…"
      type="search"
    />
    <button
      v-if="view === 'category'"
      class="back-btn"
      @click="exitCategory"
    >← 返回所有分类</button>
    <span v-else-if="view === 'tiles'" class="cta-summary">
      {{ totalCount }} 个单词
    </span>
  </div>

  <!-- Content area (scrolls) -->
  <div class="content-area">
    <TilesView v-if="view === 'tiles'" :buckets="buckets" ... />
    <CategoryView v-else-if="view === 'category'" :name="..." :words="categoryWords" ... />
    <SearchView v-else :words="searchResults" ... />
  </div>

  <WordDetail :word-id="detailId" @close="closeDetail" @deleted="onDeleted" />
</div>
```

实际不抽子组件，三个视图模式都在 Library.vue 内用 v-if / v-else-if 切换。

### 4.2 视口锁定（参考 Reader/Dashboard）

```css
.library {
  display: flex;
  flex-direction: column;
  gap: 18px;
  height: calc(100vh - 68px);
  min-height: 0;
}
.content-area {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
}
```

### 4.3 Header（紧凑）

```css
.page-head {
  display: flex; align-items: baseline; justify-content: space-between;
  gap: 14px;
  flex-shrink: 0;
}
.page-head h1 {
  font-family: var(--font-serif);
  font-size: 26px; font-weight: 700;
  letter-spacing: -0.02em;
  margin: 0;
}
.page-head p {
  margin: 4px 0 0;
  font-size: 12px;
  color: var(--text-tertiary);
}
.warn-chip {
  color: var(--accent);
  font-weight: 600;
}
```

### 4.4 搜索条

```css
.search-bar {
  display: flex; align-items: center; gap: 12px;
  padding: 10px 18px;
  flex-shrink: 0;
}
.search-icon { font-size: 14px; opacity: 0.5; }
.search-input {
  flex: 1; background: transparent; border: none;
  font-size: 14px; color: var(--text-primary);
  outline: none; padding: 6px 0;
}
.search-input::placeholder { color: var(--text-tertiary); }
.back-btn {
  appearance: none; border: 1px solid var(--glass-border);
  background: var(--glass-bg-dim);
  padding: 5px 14px; border-radius: 999px;
  font-size: 12px; font-weight: 600;
  color: var(--brand);
  cursor: pointer;
}
.back-btn:hover { background: var(--brand-soft); }
.cta-summary {
  font-size: 11.5px; color: var(--text-tertiary);
  font-variant-numeric: tabular-nums;
}
```

---

## 5. Tiles 视图（默认）

3 列网格，每张磁贴一个分类。

```vue
<div v-if="view === 'tiles'" class="tile-grid">
  <button
    v-for="b in buckets"
    :key="b.name"
    class="tile glass"
    :class="{ uncat: b.isUncategorized }"
    @click="enterCategory(b.name)"
  >
    <div class="tile-head">
      <span class="tile-name">
        <span v-if="b.isUncategorized" class="uncat-dot">•</span>{{ b.name }}
      </span>
      <span class="tile-count">{{ b.total }} 个</span>
    </div>
    <div class="tile-words">
      <span
        v-for="w in b.words.slice(0, 4)"
        :key="w.id"
        class="tile-word"
      >{{ w.text }}</span>
      <span v-if="b.total > 4" class="tile-more">+{{ b.total - 4 }}</span>
    </div>
    <div class="tile-foot">
      <span
        v-if="b.isUncategorized"
        class="tile-action accent"
        @click.stop="recategorize"
      >🤖 AI 分类</span>
      <span
        v-else
        class="tile-action"
        @click.stop="practiceCategory(b)"
      >▶ 练这 {{ b.total }} 个</span>
      <div class="tile-pips" :title="`平均掌握度 ${b.avgMastery.toFixed(1)}/5`">
        <span
          v-for="(on, i) in masteryPips(b.avgMastery)"
          :key="i"
          class="p"
          :class="{ on }"
        />
      </div>
    </div>
  </button>
</div>
```

```css
.tile-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 14px;
  align-content: start;
}
.tile {
  appearance: none;
  border: 1px solid var(--glass-border);
  text-align: left;
  cursor: pointer;
  padding: 16px 18px;
  display: flex; flex-direction: column;
  gap: 10px;
  position: relative;
  overflow: hidden;
  transition: background 200ms, transform 120ms, border-color 200ms;
  font: inherit;
  color: var(--text-primary);
}
.tile::before {
  content: ""; position: absolute; inset: 0;
  background: linear-gradient(135deg, color-mix(in srgb, var(--brand) 6%, transparent), transparent 60%);
  pointer-events: none;
}
.tile:hover {
  background: var(--glass-bg-strong);
  transform: translateY(-1px);
  border-color: color-mix(in srgb, var(--brand) 30%, var(--glass-border));
}
.tile.uncat {
  border-color: color-mix(in srgb, var(--accent) 30%, var(--glass-border));
}
.tile.uncat::before {
  background: linear-gradient(135deg, color-mix(in srgb, var(--accent) 8%, transparent), transparent 60%);
}

.tile-head {
  display: flex; align-items: baseline; justify-content: space-between;
}
.tile-name {
  font-family: var(--font-serif);
  font-size: 16px; font-weight: 700;
}
.uncat-dot { color: var(--accent); margin-right: 4px; }
.tile.uncat .tile-name { color: var(--accent); }
.tile-count {
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--text-tertiary);
}

.tile-words {
  display: flex; flex-wrap: wrap; gap: 4px;
  min-height: 22px;
}
.tile-word {
  font-family: var(--font-serif);
  font-style: italic;
  font-size: 11.5px;
  color: var(--text-secondary);
  padding: 2px 7px;
  background: var(--glass-bg-dim);
  border-radius: 4px;
}
.tile-more {
  font-size: 10.5px;
  color: var(--text-tertiary);
  padding: 2px 6px;
  align-self: center;
}

.tile-foot {
  display: flex; align-items: center;
  margin-top: 4px;
  padding-top: 10px;
  border-top: 1px dashed var(--hairline);
  font-size: 11.5px;
}
.tile-action {
  color: var(--brand);
  font-weight: 600;
  cursor: pointer;
}
.tile-action.accent { color: var(--accent); }
.tile-action:hover { text-decoration: underline; }

.tile-pips {
  margin-left: auto;
  display: flex; gap: 2.5px;
}
.tile-pips .p {
  width: 4px; height: 4px;
  border-radius: 50%;
  background: var(--hairline-strong);
}
.tile-pips .p.on { background: var(--brand); }
```

### 5.1 `masteryPips` 工具

```typescript
function masteryPips(avg: number): boolean[] {
  // avg 0..5 → 5 个布尔，前 floor(avg) 个亮
  const filled = Math.round(avg);
  return [0, 1, 2, 3, 4].map(i => i < filled);
}
```

### 5.2 「练这 N 个」交互

```typescript
function practiceCategory(b: CategoryBucket) {
  const ids = b.words.map(w => w.id).join(",");
  router.push({ path: "/practice", query: { word_ids: ids } });
}
```

直接 reuse 现有 Practice 专练模式（`?word_ids=`，上次 WeakWords 已经实现）。

### 5.3 「AI 分类」

```typescript
async function recategorize() {
  if (recategorizing.value) return;
  if (!confirm("将为未分类单词请求 AI 分类，可能产生少量调用费用。继续？")) return;
  recategorizing.value = true;
  try {
    const res = await api.recategorize();
    message.value = `已分类 ${res.updated} / ${res.total} 个单词`;
    await loadAll();
  } catch (e: any) {
    message.value = e.message || "分类失败";
  } finally {
    recategorizing.value = false;
    setTimeout(() => { message.value = ""; }, 4000);
  }
}
```

---

## 6. Category 视图（点磁贴后）

```vue
<div v-else-if="view === 'category'" class="cat-view">
  <div class="cat-view-head">
    <h2>
      <span v-if="selectedBucket?.isUncategorized" class="uncat-dot">•</span>
      {{ selectedCategory }}
    </h2>
    <span class="muted small">{{ categoryWords.length }} 个</span>
    <button
      v-if="categoryWords.length > 0 && !selectedBucket?.isUncategorized"
      class="cat-prac"
      @click="practiceCategory(selectedBucket!)"
    >▶ 练这 {{ categoryWords.length }} 个</button>
  </div>

  <div class="word-grid">
    <div
      v-for="w in categoryWords"
      :key="w.id"
      class="word-row"
      @click="openDetail(w.id)"
    >
      <div class="row-text">
        <div class="row-w">{{ w.text }}</div>
        <div class="row-t">{{ w.translation || '（无翻译）' }}</div>
      </div>
      <div class="row-pips">
        <span
          v-for="(on, i) in masteryPips(w.mastery)"
          :key="i"
          class="p"
          :class="{ on }"
        />
      </div>
    </div>
  </div>
</div>
```

```css
.cat-view {
  display: flex; flex-direction: column;
  gap: 14px;
}
.cat-view-head {
  display: flex; align-items: baseline; gap: 14px;
}
.cat-view-head h2 {
  font-family: var(--font-serif);
  font-size: 22px; font-weight: 700;
  margin: 0; letter-spacing: -0.01em;
}
.cat-prac {
  margin-left: auto;
  background: var(--brand-strong);
  color: var(--brand-strong-text);
  border: none;
  padding: 7px 18px; border-radius: 999px;
  font: inherit; font-size: 12.5px; font-weight: 700;
  cursor: pointer;
}

.word-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 10px;
}
.word-row {
  display: flex; align-items: center;
  padding: 11px 14px;
  background: var(--glass-bg-dim);
  border: 1px solid var(--glass-border);
  border-radius: 10px;
  cursor: pointer;
  gap: 10px;
  transition: background 150ms;
}
.word-row:hover { background: var(--glass-bg); }
.row-text { flex: 1; min-width: 0; }
.row-w {
  font-family: var(--font-serif);
  font-size: 14.5px; font-weight: 700;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.row-t {
  font-size: 11px; color: var(--text-tertiary);
  margin-top: 1px;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.row-pips {
  display: flex; gap: 2.5px; flex-shrink: 0;
}
.row-pips .p {
  width: 4px; height: 4px; border-radius: 50%;
  background: var(--hairline-strong);
}
.row-pips .p.on { background: var(--brand); }
```

---

## 7. Search 视图

```vue
<div v-else class="search-view">
  <div class="search-result-head">
    匹配到 <strong>{{ searchResults.length }}</strong> 个单词
    <span v-if="searchResults.length === 0" class="muted small">
      · 试试别的搜索词
    </span>
  </div>
  <div v-if="searchResults.length > 0" class="word-grid">
    <div
      v-for="w in searchResults"
      :key="w.id"
      class="word-row"
      @click="openDetail(w.id)"
    >
      <div class="row-text">
        <div class="row-w">{{ w.text }}</div>
        <div class="row-t">
          {{ w.translation || '（无翻译）' }}
          <span v-if="w.category" class="row-cat">· {{ w.category }}</span>
        </div>
      </div>
      <div class="row-pips">
        <span
          v-for="(on, i) in masteryPips(w.mastery)"
          :key="i"
          class="p"
          :class="{ on }"
        />
      </div>
    </div>
  </div>
</div>
```

```css
.search-view {
  display: flex; flex-direction: column;
  gap: 14px;
}
.search-result-head {
  font-size: 13px; color: var(--text-secondary);
}
.row-cat {
  font-size: 10px;
  color: var(--brand);
  margin-left: 4px;
}
```

---

## 8. AI 分类提示 toast

```vue
<Transition name="fade">
  <div v-if="message" class="msg-toast glass-dim">{{ message }}</div>
</Transition>
```

```css
.msg-toast {
  position: fixed;
  bottom: 30px;
  left: 50%; transform: translateX(-50%);
  padding: 10px 18px;
  border-radius: 999px;
  font-size: 13px;
  color: var(--brand);
  z-index: 50;
}
```

---

## 9. 移动端

```css
@media (max-width: 900px) {
  .library {
    height: auto;
    min-height: 0;
  }
  .content-area {
    overflow: visible;
  }
  .tile-grid {
    grid-template-columns: 1fr;
  }
  .word-grid {
    grid-template-columns: 1fr;
  }
}
```

---

## 10. WordDetail 抽屉

完全保留现有 `<WordDetail :word-id="detailId" @close="closeDetail" @deleted="onDeleted" />`，无改动。

`onDeleted(id)` 实现：

```typescript
function onDeleted(id: number) {
  allWords.value = allWords.value.filter(w => w.id !== id);
  detailId.value = null;
  // re-fetch categories order in case a category becomes empty
  api.listCategories().then(c => { cats.value = c; }).catch(() => {});
}
```

不需要重新拉所有 words，删一个客户端去掉即可。

---

## 11. 错误处理

- `loadAll()` 失败 → 顶部显示 `error` 红字，"重试" 按钮
- `recategorize()` 失败 → toast 红字
- 单个单词删除失败 → WordDetail 内部已处理
- 空状态：
  - 整个词库为空 → tile-grid 区显示空态提示「还没保存的单词，去主页加几个吧」+ link
  - 某分类为空（删完了）→ 自动从 buckets 移除（buckets computed filter words.length===0）
  - 搜索无匹配 → "试试别的搜索词"

---

## 12. 验收

- 默认进 Library 看到分类磁贴网格，3 列 auto-fill
- 未分类磁贴（如果有未分类词）在最前，暖褐色边框，"🤖 AI 分类" 按钮
- 其它磁贴：分类名 + 数量 + 4 个样例词 + "▶ 练这 N 个" + 平均掌握度小点
- 点磁贴 body → 进入该分类视图，显示该分类所有词的紧凑列表
- 点磁贴上的「▶ 练 N 个」→ 跳 `/practice?word_ids=...`
- 在 Category 视图点「← 返回」→ 回 tiles 视图
- 搜索框输入 → 立刻切到 search 视图，跨分类匹配；清空 → 自动回 tiles
- 点任意单词行 → WordDetail 抽屉
- 删除单词 → 抽屉关闭，列表立刻去掉该词；如果该分类变空，对应磁贴消失
- AI 分类 → toast 「已分类 X / Y 个」，磁贴重新生成
- 暗色 / 亮色都正常
- 移动端 <900px 单列堆叠
- `npm run build` 通过

---

## 13. 不做

- 不引入多选 / 批量练（用户没要求；分类磁贴的"练这 N 个"已经覆盖最常见的批量需求）
- 不引入掌握度筛选 chip（之前 8 个 chip 用户嫌乱；分类视图里如需要可后续加）
- 不动 WordDetail 抽屉
- 不引入新的后端 endpoint
- 不引入分页（500 词上限对个人使用足够）
- 不动 WordCard.vue（保留给 Dashboard）
