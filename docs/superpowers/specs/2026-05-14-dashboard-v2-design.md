# Dashboard v2 重设计 · 设计稿

**日期**: 2026-05-14
**目标**: 主页布局重做：合并 4 个统计组件成一张卡 + 视口锁定 + flex 撑满让例句永远填满屏幕。功能完全不变，只改视觉与布局。

---

## 1. 范围与约束

### 范围内
- `frontend/src/views/Dashboard.vue` —— 整体重写（模板 + 样式 + 部分 script 调整）

### 范围外
- 后端任何改动（保留所有现有 endpoints）
- `WeakWords.vue` 组件本身（已存在）
- `AddBar.vue` 组件本身（已存在，本次只用它，不动）
- `WordCard.vue` 组件（仍用于 Recent 4 张卡）
- 路由 / API / composables / 其它视图

### 不能损坏的现有行为
- 加单词后的 enrichment 轮询（`pollEnrichment`）
- 添加后 TTS 朗读
- 「今日待复习 → 开始练习 →」CTA 跳 `/practice`
- 数字 = 0 时显示 fallback 文案 / "去练习页"按钮
- Recent "查看全部" 跳 `/library`
- 暗色 / 亮色主题
- 移动端响应式（小于 1080px 单列堆叠）

---

## 2. 整体结构

```
┌─ .dashboard (flex column, height: 100vh - 68px) ──────────────┐
│ .page-head  (h1 + sub-h，固定高)                                │
│ ┌─ .body-grid (flex: 1, grid 2 cols) ──────────────────────┐ │
│ │ ┌─ .col-main (flex col, min-h 0) ──┐ ┌─ .col-side ────┐ │ │
│ │ │ AddBar (auto h)                   │ │ Stats card (auto)│ │
│ │ │ Hero card (flex: 1)               │ │ Weak card (flex 1)│ │
│ │ │   - hero head (auto)              │ │                  │ │ │
│ │ │   - hero-tr (auto)                │ │                  │ │ │
│ │ │   - hero-examples (flex: 1)       │ │                  │ │ │
│ │ │     · 3 examples each flex:1      │ │                  │ │ │
│ │ │ Recent (auto h, 4 cards row)      │ │                  │ │ │
│ │ └───────────────────────────────────┘ └──────────────────┘ │ │
│ └────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
```

`100vh - 68px` —— 减去 `.main-inner` 上下 padding（28 + 40）。

---

## 3. 关键 CSS 设计

### 3.1 视口锁

```css
.dashboard {
  display: flex;
  flex-direction: column;
  gap: 22px;
  height: calc(100vh - 68px);
  min-height: 0;
}
.body-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.6fr) 260px;
  gap: 22px;
  flex: 1;
  min-height: 0;
}
.col-main, .col-side {
  display: flex;
  flex-direction: column;
  gap: 14px;
  min-height: 0;
  min-width: 0;
}
```

### 3.2 AddBar / Recent / Stats 都 flex-shrink: 0

固定高度元素不参与拉伸：

```css
.addbar-card { flex-shrink: 0; }
.recent-section { flex-shrink: 0; }
.stats-card { flex-shrink: 0; }
```

### 3.3 Hero 卡 flex:1

Hero 占满左栏中间剩余空间，内部 flex column：

```css
.preview {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  padding: 22px 26px;
  border-left: 3px solid var(--brand);
}
.examples {
  flex: 1;             /* 占满 hero 内部剩余空间 */
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-top: 14px;
}
.example {
  flex: 1;             /* 3 个例句平分纵向空间 */
  min-height: 0;
  /* ... */
}
```

### 3.4 Weak 卡也 flex:1

右栏 Stats 卡 auto height，Weak 卡撑满剩余：

```css
.weak-widget { /* 在 WeakWords.vue 里 */
  /* 现有样式不动，但要给 flex:1 适配 Dashboard */
}
```

但 `WeakWords.vue` 内部用了 `display: flex; flex-direction: column`，外部容器给它 `flex: 1; min-height: 0` 即可让它撑满。Dashboard 模板里包装。

---

## 4. 组件细节

### 4.1 page-head

```vue
<header class="page-head">
  <h1>主页</h1>
  <p class="muted small">粘个英文单词，AI 立刻翻译 + 3 个例句</p>
</header>
```

字号 26px 衬线、留白 22px。布局：sub-h 在 h1 右边而不是下面，节省纵向空间。

```css
.page-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  flex-shrink: 0;
}
.page-head h1 {
  font-family: var(--font-serif);
  font-size: 26px;
  font-weight: 700;
  letter-spacing: -0.02em;
  margin: 0;
}
.page-head p { margin: 0; font-size: 12px; }
```

### 4.2 AddBar（无改动，沿用现有 `.add-bar` 组件）

直接 `<AddBar @added="onAdded" />`，外面包 `flex-shrink: 0`。

### 4.3 Preview hero — 重新设计

新结构：
```vue
<section class="preview glass-strong">
  <template v-if="lastAdded">
    <div class="word-row">
      <span class="word-text">{{ lastAdded.text }}</span>
      <button v-if="ttsSupported" class="speaker" @click="speak(lastAdded.text)">🔊</button>
      <span v-if="lastAdded.phonetic" class="phonetic">{{ lastAdded.phonetic }}</span>
      <span v-if="lastAdded.pos" class="pos">{{ lastAdded.pos }}</span>
    </div>
    <div class="translation">{{ lastAdded.translation || "（无翻译）" }}</div>

    <div class="examples">
      <div v-for="(ex, i) in lastAdded.examples" :key="ex.id" class="example">
        <div class="example-num">{{ i + 1 }}</div>
        <div class="example-body">
          <div class="example-en">{{ ex.en }}</div>
          <div v-if="ex.zh" class="example-zh">{{ ex.zh }}</div>
        </div>
      </div>
      <div v-if="lastAdded.examples.length === 0" class="examples-empty">
        这个词暂无例句
      </div>
    </div>
  </template>

  <template v-else-if="initialLoad">
    <div class="empty-state">加载中…</div>
  </template>

  <template v-else>
    <div class="empty-state">
      <div class="emoji">👋</div>
      <p>在上方输入框粘一个英文单词</p>
      <p class="tertiary small">AI 立刻给你翻译和 3 个不同语境的例句</p>
    </div>
  </template>
</section>
```

变化：
- "练这个 →" 按钮去掉（多余 —— 右栏的"开始练习"是统一入口）
- "3 个不同语境的例句" 标签去掉（多余信息）
- 例句容器 `.examples` `flex:1` 撑满
- 每个 `.example` `flex:1` 三个平分纵向空间
- 例句字号从 14px 提到 14.5px，padding 增加

样式见 §5。

### 4.4 Recent — 保持 4 卡片网格

```vue
<section class="recent-section">
  <div class="section-head">
    <h2>最近添加</h2>
    <RouterLink to="/library" class="link">查看全部 →</RouterLink>
  </div>
  <div class="recent-grid">
    <WordCard v-for="w in recent" :key="w.id" :word="w" />
  </div>
</section>
```

无大改，只把 section-head 字号、margin 微调，整段 `flex-shrink: 0`。

### 4.5 Stats 合并卡（新建）

替代原本的"今日待复习"独立卡 + "3 个 stat 卡"独立 row：

```vue
<section class="stats-card glass">
  <div class="due-row">
    <span class="due-num" :class="{ none: stats.due_today === 0 }">{{ stats.due_today }}</span>
    <span class="due-unit">个</span>
  </div>
  <p class="due-hint">
    {{
      stats.due_today === 0
        ? "今天没有需要复习的词，加几个新词吧"
        : "今日待复习 · 趁热打铁巩固"
    }}
  </p>
  <RouterLink
    :to="'/practice'"
    class="btn btn-primary due-btn"
  >
    {{ stats.due_today > 0 ? "开始练习 →" : "去练习页" }}
  </RouterLink>
  <div class="stats-row">
    <div class="stat-mini">
      <div class="stat-num">{{ stats.total }}</div>
      <div class="stat-label">总数</div>
    </div>
    <div class="stat-mini">
      <div class="stat-num">{{ stats.mastered }}</div>
      <div class="stat-label">已掌握</div>
    </div>
    <div class="stat-mini">
      <div class="stat-num">{{ stats.added_this_week }}</div>
      <div class="stat-label">本周</div>
    </div>
  </div>
</section>
```

样式见 §5.4。

### 4.6 WeakWords —— 直接复用现有组件

```vue
<WeakWords class="weak-fill" />
```

包装类 `.weak-fill { flex: 1; min-height: 0; display: flex; flex-direction: column; }`。

WeakWords 组件内部已经是 flex column，会自然填满外部容器。**WeakWords.vue 本体不改**。

---

## 5. 完整样式

### 5.1 容器与栅格

```css
.dashboard {
  display: flex;
  flex-direction: column;
  gap: 22px;
  height: calc(100vh - 68px);
  min-height: 0;
}

.page-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 14px;
  flex-shrink: 0;
  flex-wrap: wrap;
}
.page-head h1 {
  font-family: var(--font-serif);
  font-size: 26px;
  font-weight: 700;
  letter-spacing: -0.02em;
  margin: 0;
}
.page-head p {
  margin: 0;
  font-size: 12px;
  color: var(--text-tertiary);
}
.small { font-size: 12px; }

.body-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.6fr) 260px;
  gap: 22px;
  flex: 1;
  min-height: 0;
}

.col-main,
.col-side {
  display: flex;
  flex-direction: column;
  gap: 14px;
  min-height: 0;
  min-width: 0;
}
```

### 5.2 AddBar 包装

```css
.addbar { flex-shrink: 0; }
```

### 5.3 Hero card

```css
.preview {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  padding: 22px 26px;
  border-left: 3px solid var(--brand);
  gap: 6px;
}

.word-row {
  display: flex;
  align-items: baseline;
  gap: 14px;
  flex-wrap: wrap;
  flex-shrink: 0;
}

.word-text {
  font-family: var(--font-serif);
  font-size: 34px;
  font-weight: 700;
  letter-spacing: -0.02em;
  line-height: 1.1;
  color: var(--text-primary);
}

.speaker {
  appearance: none;
  border: none;
  background: var(--glass-bg-dim);
  width: 32px;
  height: 32px;
  border-radius: 50%;
  font-size: 14px;
  cursor: pointer;
  align-self: center;
  transition: background 200ms, transform 200ms;
}
.speaker:hover { background: var(--brand-soft); transform: scale(1.08); }

.phonetic {
  font-family: var(--font-mono);
  font-size: 13px;
  color: var(--text-tertiary);
}

.pos {
  font-family: var(--font-serif);
  font-style: italic;
  font-size: 12px;
  padding: 1px 8px;
  border-radius: 6px;
  background: var(--brand-soft);
  color: var(--brand);
}

.translation {
  font-size: 16px;
  font-weight: 500;
  color: var(--accent);
  flex-shrink: 0;
  word-wrap: break-word;
}

.examples {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-top: 14px;
}

.example {
  flex: 1;
  min-height: 0;
  display: flex;
  gap: 14px;
  padding: 14px 16px;
  border-radius: 12px;
  background: color-mix(in srgb, var(--brand) 5%, transparent);
  border: 1px solid var(--hairline);
  align-items: flex-start;
}

.example-num {
  flex-shrink: 0;
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: var(--brand-soft);
  color: var(--brand);
  font-size: 11px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
}

.example-body {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 5px;
}

.example-en {
  font-family: var(--font-serif);
  font-style: italic;
  font-size: 14.5px;
  line-height: 1.6;
  color: var(--text-primary);
}

.example-zh {
  font-size: 12px;
  color: var(--text-tertiary);
  line-height: 1.55;
}

.examples-empty {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-secondary);
  font-size: 13px;
}

.empty-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6px;
  text-align: center;
  color: var(--text-secondary);
}
.empty-state .emoji { font-size: 40px; line-height: 1; }
.empty-state p { margin: 0; }
.empty-state .small { font-size: 12px; color: var(--text-tertiary); }
```

### 5.4 Stats card

```css
.stats-card {
  padding: 22px 22px 18px;
  text-align: center;
  flex-shrink: 0;
}

.due-row {
  display: flex;
  align-items: baseline;
  justify-content: center;
  gap: 6px;
}

.due-num {
  font-family: var(--font-serif);
  font-size: 68px;
  font-weight: 700;
  line-height: 1;
  background: linear-gradient(135deg, var(--brand) 0%, var(--accent) 100%);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
  color: transparent;
  letter-spacing: -0.03em;
}
.due-num.none {
  background: none;
  -webkit-text-fill-color: var(--text-tertiary);
  color: var(--text-tertiary);
}

.due-unit {
  font-size: 13px;
  color: var(--text-tertiary);
}

.due-hint {
  font-size: 12px;
  color: var(--text-secondary);
  margin: 6px 0 14px;
  line-height: 1.45;
}

.due-btn {
  display: inline-block;
  padding: 8px 22px;
  border-radius: 999px;
  font-size: 12.5px;
  font-weight: 700;
  letter-spacing: 0.02em;
  text-decoration: none;
}

.stats-row {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  margin-top: 18px;
  padding-top: 16px;
  border-top: 1px solid var(--hairline);
}

.stat-mini {
  text-align: center;
}

.stat-num {
  font-family: var(--font-serif);
  font-size: 22px;
  font-weight: 700;
  color: var(--text-primary);
  line-height: 1;
}

.stat-label {
  font-size: 10px;
  color: var(--text-tertiary);
  margin-top: 4px;
  letter-spacing: 0.04em;
}
```

### 5.5 Recent section

```css
.recent-section { flex-shrink: 0; }

.section-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  margin-bottom: 8px;
}
.section-head h2 {
  margin: 0;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--text-secondary);
}
.link {
  text-decoration: none;
  color: var(--brand);
  font-size: 11px;
  font-weight: 600;
}

.recent-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 10px;
}

.hint-card {
  padding: 16px;
  text-align: center;
  color: var(--text-secondary);
  font-size: 13px;
}
.hint-card.error { color: var(--danger); }
```

### 5.6 WeakWords wrapper

```css
.weak-fill {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}
```

注意：`WeakWords.vue` 自己内部已经 flex column。让它的最外层 `<section class="weak-widget glass">` 适配父容器 flex:1。如果发现 list 内容溢出不滚，可能要在 WeakWords 内部加 `overflow-y: auto` 到 `.weak-list`。本次先观察，必要时回组件再加。

### 5.7 移动端

```css
@media (max-width: 1080px) {
  .dashboard {
    height: auto;
    min-height: 0;
  }
  .body-grid {
    grid-template-columns: 1fr;
    flex: 0 0 auto;
  }
  .recent-grid {
    grid-template-columns: repeat(2, 1fr);
  }
  .preview { min-height: 280px; flex: 0 0 auto; }
  .example { flex: 0 0 auto; }
}
```

窄屏不锁视口，回归自然滚动。

---

## 6. script 改动

### 6.1 删除

- 删除"练这个 →"相关引用（如果有）
- 删除"3 个不同语境的例句"相关计算属性（无）

### 6.2 保留

- `stats / recent / lastAdded / enriching / initialLoad` 全部保留
- `refreshStats / refreshRecent / refreshAll / onAdded / pollEnrichment / stopPolling` 全部保留
- TTS 集成保留

### 6.3 模板小调整

- 「练这个 →」按钮删除
- 「3 个不同语境的例句」小标题删除
- 整个右栏从原来 3 个 widget（Weak + Due + 3 Stats row）变 2 个（Stats 合并 + Weak）

---

## 7. 验收

- Dashboard 整页填满视口（除上 28 / 下 40 padding）
- Hero 单词字号 34px，3 个例句平分 hero 剩余空间
- 屏幕越高例句越宽敞，永远没大空白
- 右栏顶部一张统计大卡：68px 渐变大数字 + 按钮 + 3 stat 细线分隔
- 右栏下方 WeakWords 撑满剩余高度
- "今日待复习 = 0" 时大数字变灰、按钮变成"去练习页"
- 加单词后 hero 实时更新，TTS 朗读
- 暗色 / 亮色 OK
- `npm run build` 通过
- 移动端单列、自然滚动

---

## 8. 不做

- 不改 WeakWords 组件本身
- 不改后端任何 endpoint
- 不动 Heatmap（已删除）
- 不动 AddBar 内部
- 不重做 WordCard
- 不加新功能 / 新数据展示
