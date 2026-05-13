# WordGlass UI 重设计实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 WordGlass 前端从「Apple Liquid Glass + 紫粉渐变」改成「Liquid Glass + 英文书感 · 墨绿+暖褐」，明暗主题都重做。零功能改动。

**Architecture:** token-driven。`glass.css` 重写所有 CSS 变量（颜色、字体、圆角、阴影、blob）；各组件 / 视图只改 `font-family` 引用和硬编码颜色 → 改成 token 引用。每个文件一个任务，每个任务以 `npm run build` 通过 + commit 结束。最后一个任务做手动视觉 QA。

**Tech Stack:** Vue 3 + Vite + TypeScript + `vue-tsc -b && vite build`。无前端测试框架（不在范围内 —— 验证靠 build + 视觉 QA）。

**前置：** spec `docs/superpowers/specs/2026-05-13-ui-redesign-design.md`，每个任务都引用了 spec 对应章节。

---

## 任务依赖图

```
T1 (glass.css)  ← 所有后续任务都依赖这里的 token
  ├── T2 SideBar.vue
  ├── T3 Dashboard.vue
  ├── T4 Reader.vue
  ├── T5 Library.vue
  ├── T6 Practice.vue
  ├── T7 Settings.vue
  ├── T8 AddBar.vue
  ├── T9 WordCard.vue
  ├── T10 WordDetail.vue
  ├── T11 Heatmap.vue
  └── T12 LetterSlots.vue

T13 (手动 QA) ← 全部完成后
```

T2-T12 之间相互独立，可以并行。

---

## Task 1: 重写 glass.css 设计 token

**Files:**
- Modify: `frontend/src/styles/glass.css`（整体重写，~265 → ~280 行）

**Spec ref:** §2 设计 Token、§4 glass.css 改动

- [ ] **Step 1: 用以下内容完整替换 `frontend/src/styles/glass.css`**

```css
/* WordGlass — Liquid Glass + 英文书感设计系统 · 明暗主题 */

:root {
  /* Brand · evergreen 墨绿 */
  --brand: #4a6e3e;
  --brand-soft: rgba(74, 110, 62, 0.14);
  --brand-strong: #2e4a26;          /* 主按钮填充 */
  --brand-strong-text: #f5efe1;     /* 主按钮文字 */

  /* Accent · sepia 暖褐（次要强调） */
  --accent: #b89165;
  --accent-soft: rgba(184, 145, 101, 0.14);

  /* Text */
  --text-primary: #2a3422;
  --text-secondary: #5a6549;
  --text-tertiary: #8a8870;

  /* States */
  --success: #5a8a3e;
  --danger: #b94a3a;
  --warn: #c87a2e;

  /* Glass surfaces */
  --glass-bg: rgba(252, 247, 234, 0.62);
  --glass-bg-strong: rgba(252, 247, 234, 0.82);
  --glass-bg-dim: rgba(252, 247, 234, 0.40);
  --glass-border: rgba(86, 110, 80, 0.22);
  --glass-shadow: 0 8px 24px rgba(50, 60, 40, 0.10);
  --glass-shadow-lg: 0 20px 48px rgba(50, 60, 40, 0.16);

  --hairline: rgba(86, 110, 80, 0.16);
  --hairline-strong: rgba(86, 110, 80, 0.28);

  /* Background blobs · 米黄 + 橄榄 + 暖褐 */
  --bg-base: linear-gradient(135deg, #f5efe1 0%, #ebe3cf 100%);
  --bg-blob-1: rgba(228, 209, 169, 0.78);
  --bg-blob-2: rgba(151, 175, 136, 0.55);
  --bg-blob-3: rgba(184, 145, 95, 0.45);
  --bg-blob-1-stronger: rgba(228, 209, 169, 0.55);
  --bg-blob-2-stronger: rgba(151, 175, 136, 0.45);
  --bg-blob-3-stronger: rgba(184, 145, 95, 0.40);

  /* Fonts */
  --font-ui: -apple-system, BlinkMacSystemFont, "PingFang SC",
             "Helvetica Neue", "Microsoft YaHei", sans-serif;
  --font-serif: "Iowan Old Style", "Charter", "Source Serif Pro",
                "Cambria", Georgia, "Songti SC", serif;
  --font-mono: ui-monospace, "SF Mono", Menlo, monospace;

  /* Radii */
  --radius-sm: 12px;
  --radius-md: 18px;
  --radius-card: 14px;
  --radius-lg: 24px;
  --radius-xl: 32px;
}

[data-theme="dark"] {
  --brand: #b8d49a;
  --brand-soft: rgba(184, 212, 154, 0.18);
  --brand-strong: #b8d49a;
  --brand-strong-text: #16221a;

  --accent: #d8b483;
  --accent-soft: rgba(216, 180, 131, 0.18);

  --text-primary: #ede4cf;
  --text-secondary: #b4ad8d;
  --text-tertiary: #7d7860;

  --success: #a3c98a;
  --danger: #e08070;
  --warn: #e0a060;

  --glass-bg: rgba(30, 42, 32, 0.55);
  --glass-bg-strong: rgba(34, 48, 36, 0.78);
  --glass-bg-dim: rgba(30, 42, 32, 0.35);
  --glass-border: rgba(184, 212, 154, 0.20);
  --glass-shadow: 0 8px 28px rgba(0, 0, 0, 0.45);
  --glass-shadow-lg: 0 24px 60px rgba(0, 0, 0, 0.55);

  --hairline: rgba(184, 212, 154, 0.14);
  --hairline-strong: rgba(184, 212, 154, 0.22);

  --bg-base: linear-gradient(135deg, #0e1810 0%, #16221a 100%);
  --bg-blob-1: rgba(151, 175, 136, 0.35);
  --bg-blob-2: rgba(180, 145, 95, 0.30);
  --bg-blob-3: rgba(80, 110, 75, 0.40);
  --bg-blob-1-stronger: rgba(151, 175, 136, 0.40);
  --bg-blob-2-stronger: rgba(180, 145, 95, 0.35);
  --bg-blob-3-stronger: rgba(80, 110, 75, 0.50);
}

* { box-sizing: border-box; }

html, body, #app {
  margin: 0;
  padding: 0;
  min-height: 100vh;
}

body {
  font-family: var(--font-ui);
  font-size: 15px;
  line-height: 1.5;
  color: var(--text-primary);
  -webkit-font-smoothing: antialiased;
  text-rendering: optimizeLegibility;
  background:
    radial-gradient(circle at 8% 12%, var(--bg-blob-1), transparent 45%),
    radial-gradient(circle at 92% 8%, var(--bg-blob-2), transparent 45%),
    radial-gradient(circle at 50% 100%, var(--bg-blob-3), transparent 50%),
    var(--bg-base);
  background-attachment: fixed;
  min-height: 100vh;
  transition: color 300ms ease;
}

body::before {
  content: "";
  position: fixed;
  inset: -10vmin;
  pointer-events: none;
  z-index: -1;
  background:
    radial-gradient(40vmin 40vmin at 20% 30%, var(--bg-blob-1-stronger), transparent 60%),
    radial-gradient(35vmin 35vmin at 85% 70%, var(--bg-blob-2-stronger), transparent 60%),
    radial-gradient(30vmin 30vmin at 60% 20%, var(--bg-blob-3-stronger), transparent 60%);
  animation: drift 24s ease-in-out infinite alternate;
}

@keyframes drift {
  0% { transform: translate3d(0, 0, 0) scale(1); }
  100% { transform: translate3d(2vmin, -3vmin, 0) scale(1.05); }
}

/* === Glass primitive === */
.glass {
  background: var(--glass-bg);
  backdrop-filter: blur(22px) saturate(180%);
  -webkit-backdrop-filter: blur(22px) saturate(180%);
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-card);
  box-shadow: var(--glass-shadow);
}

.glass-strong {
  background: var(--glass-bg-strong);
  backdrop-filter: blur(26px) saturate(200%);
  -webkit-backdrop-filter: blur(26px) saturate(200%);
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-card);
  box-shadow: var(--glass-shadow);
}

.glass-dim {
  background: var(--glass-bg-dim);
  backdrop-filter: blur(18px) saturate(160%);
  -webkit-backdrop-filter: blur(18px) saturate(160%);
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-md);
}

/* === Buttons === */
.btn {
  appearance: none;
  border: 1px solid var(--glass-border);
  background: var(--glass-bg-strong);
  backdrop-filter: blur(20px) saturate(180%);
  -webkit-backdrop-filter: blur(20px) saturate(180%);
  border-radius: 999px;
  padding: 10px 20px;
  font: inherit;
  font-weight: 500;
  color: var(--text-primary);
  cursor: pointer;
  transition: transform 120ms ease, box-shadow 200ms ease, background 200ms ease;
}

.btn:hover {
  background: var(--glass-bg-strong);
  filter: brightness(1.08);
  box-shadow: 0 4px 16px rgba(50, 60, 40, 0.12);
}

.btn:active { transform: scale(0.97); }

.btn-primary {
  background: var(--brand-strong);
  color: var(--brand-strong-text);
  border-color: transparent;
}

.btn-primary:hover {
  background: var(--brand-strong);
  filter: brightness(1.08);
}

.btn-ghost {
  background: transparent;
  border-color: var(--glass-border);
}

/* === Inputs === */
.input {
  width: 100%;
  appearance: none;
  border: 1px solid var(--glass-border);
  background: var(--glass-bg);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  border-radius: var(--radius-md);
  padding: 14px 18px;
  font: inherit;
  font-size: 16px;
  color: var(--text-primary);
  outline: none;
  transition: border-color 200ms ease, box-shadow 200ms ease, background 200ms ease;
}

.input:focus {
  border-color: color-mix(in srgb, var(--brand) 50%, transparent);
  background: var(--glass-bg-strong);
  box-shadow: 0 0 0 4px var(--brand-soft);
}

.input::placeholder { color: var(--text-tertiary); }

/* === Layout helpers === */
.container {
  max-width: 1080px;
  margin: 0 auto;
  padding: 0 24px;
}

.muted { color: var(--text-secondary); }
.tertiary { color: var(--text-tertiary); }

/* === Font utility classes === */
.serif { font-family: var(--font-serif); }
.ui    { font-family: var(--font-ui); }
.mono  { font-family: var(--font-mono); }

/* === Animations === */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 200ms ease, transform 200ms ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
  transform: translateY(8px);
}

.stagger {
  animation: stagger-reveal 0.7s cubic-bezier(0.16, 1, 0.3, 1) both;
  animation-delay: calc(var(--stagger, 0) * 0.12s);
}

@keyframes stagger-reveal {
  from { opacity: 0; transform: translateY(20px); }
  to { opacity: 1; transform: translateY(0); }
}

@media (prefers-reduced-motion: reduce) {
  body::before { animation: none; }
  .stagger { animation: none; opacity: 1; transform: none; }
}

/* Scrollbar polish */
::-webkit-scrollbar { width: 10px; height: 10px; }
::-webkit-scrollbar-thumb {
  background: var(--hairline-strong);
  border-radius: 999px;
  border: 2px solid transparent;
  background-clip: padding-box;
}
::-webkit-scrollbar-thumb:hover {
  background: var(--text-tertiary);
  background-clip: padding-box;
}
```

- [ ] **Step 2: 跑 build 确认无类型 / 语法错误**

```bash
cd /Users/mm/wordglass/frontend && npm run build
```

Expected: 退出码 0，`vue-tsc` 和 `vite build` 都通过。如果 build 已经在 dev 模式跑着，先停。

- [ ] **Step 3: 提交**

```bash
cd /Users/mm/wordglass && git add frontend/src/styles/glass.css && git commit -m "$(cat <<'EOF'
Rewrite design tokens: evergreen + sepia palette, serif + sans font stack

All component colors and fonts now flow through CSS variables. Adds
--brand/--accent split, --brand-strong button color pair, --font-serif/-ui/-mono,
--radius-card, .serif/.ui/.mono utility classes.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: SideBar.vue — 书脊品牌图标 + 衬线品牌名

**Files:**
- Modify: `frontend/src/components/SideBar.vue:104-115`（品牌区）
- Modify: `frontend/src/components/SideBar.vue:117-123`（`.dot` 改成书脊形）

**Spec ref:** §3.2

- [ ] **Step 1: 改 `.brand` 选择器 —— 加衬线字体**

Edit `frontend/src/components/SideBar.vue` 把：

```css
.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  text-decoration: none;
  color: var(--text-primary);
  font-weight: 700;
  font-size: 17px;
  letter-spacing: -0.01em;
  padding: 6px 12px 14px;
  border-bottom: 1px solid var(--hairline);
}
```

改成：

```css
.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  text-decoration: none;
  color: var(--text-primary);
  font-family: var(--font-serif);
  font-weight: 700;
  font-size: 17px;
  letter-spacing: -0.01em;
  padding: 6px 12px 14px;
  border-bottom: 1px solid var(--hairline);
}
```

- [ ] **Step 2: 把 `.dot` 改成书脊形**

把：

```css
.dot {
  width: 22px;
  height: 22px;
  border-radius: 7px;
  background: linear-gradient(135deg, #a8c5ff 0%, #d1b3ff 50%, #ffb3c7 100%);
  box-shadow: 0 2px 8px rgba(120, 140, 220, 0.3);
}
```

改成：

```css
.dot {
  width: 18px;
  height: 22px;
  border-radius: 2px;
  background: linear-gradient(180deg, var(--brand) 0%, var(--accent) 100%);
  box-shadow:
    1px 0 0 var(--hairline),
    inset -1px 0 0 rgba(255, 255, 255, 0.10),
    0 2px 6px rgba(50, 60, 40, 0.18);
  position: relative;
  flex-shrink: 0;
}

.dot::after {
  content: "";
  position: absolute;
  left: 3px;
  right: 3px;
  top: 4px;
  height: 1px;
  background: rgba(255, 255, 255, 0.45);
  box-shadow:
    0 3px 0 rgba(255, 255, 255, 0.30),
    0 6px 0 rgba(255, 255, 255, 0.20);
}
```

- [ ] **Step 3: 跑 build**

```bash
cd /Users/mm/wordglass/frontend && npm run build
```

Expected: 通过。

- [ ] **Step 4: 提交**

```bash
cd /Users/mm/wordglass && git add frontend/src/components/SideBar.vue && git commit -m "$(cat <<'EOF'
SideBar: book-spine brand icon + serif brand name

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Dashboard.vue — 衬线排版 + 渐变换色

**Files:**
- Modify: `frontend/src/views/Dashboard.vue`（多处 `<style scoped>` 内）

**Spec ref:** §3.3

- [ ] **Step 1: H1 加衬线**

把 `.page-head h1`：

```css
.page-head h1 {
  font-size: 22px;
  font-weight: 700;
  letter-spacing: -0.02em;
  margin: 0;
}
```

改成：

```css
.page-head h1 {
  font-family: var(--font-serif);
  font-size: 22px;
  font-weight: 700;
  letter-spacing: -0.02em;
  margin: 0;
}
```

- [ ] **Step 2: `.word-text` 加衬线**

把：

```css
.word-text {
  font-size: clamp(24px, 2.5vw, 30px);
  font-weight: 700;
  letter-spacing: -0.02em;
  color: var(--text-primary);
  line-height: 1.1;
}
```

改成：

```css
.word-text {
  font-family: var(--font-serif);
  font-size: clamp(24px, 2.5vw, 30px);
  font-weight: 700;
  letter-spacing: -0.02em;
  color: var(--text-primary);
  line-height: 1.1;
}
```

- [ ] **Step 3: `.translation` 颜色从 `--brand` 改成 `--accent`**

把：

```css
.translation {
  font-size: 16px;
  font-weight: 500;
  color: var(--brand);
  flex-shrink: 0;
  word-wrap: break-word;
}
```

改成：

```css
.translation {
  font-size: 16px;
  font-weight: 500;
  color: var(--accent);
  flex-shrink: 0;
  word-wrap: break-word;
}
```

- [ ] **Step 4: `.example-en` 加衬线斜体**

把：

```css
.example-en {
  font-size: 14px;
  color: var(--text-primary);
  line-height: 1.5;
}
```

改成：

```css
.example-en {
  font-family: var(--font-serif);
  font-style: italic;
  font-size: 14px;
  color: var(--text-primary);
  line-height: 1.5;
}
```

- [ ] **Step 5: `.big-num` 渐变从紫粉换成绿褐**

把：

```css
.big-num {
  font-size: clamp(60px, 7vw, 96px);
  font-weight: 800;
  letter-spacing: -0.03em;
  line-height: 1;
  background: linear-gradient(135deg, #8b5cf6 0%, #ec4899 100%);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
  color: transparent;
}
```

改成：

```css
.big-num {
  font-family: var(--font-serif);
  font-size: clamp(60px, 7vw, 96px);
  font-weight: 700;
  letter-spacing: -0.03em;
  line-height: 1;
  background: linear-gradient(135deg, var(--brand) 0%, var(--accent) 100%);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
  color: transparent;
}
```

- [ ] **Step 6: `.stat-num` 加衬线**

把：

```css
.stat-num {
  font-size: 18px;
  font-weight: 800;
  letter-spacing: -0.02em;
  line-height: 1.1;
}
```

改成：

```css
.stat-num {
  font-family: var(--font-serif);
  font-size: 18px;
  font-weight: 700;
  letter-spacing: -0.02em;
  line-height: 1.1;
}
```

- [ ] **Step 7: `.speaker` 暗色硬编码白色清理**

把：

```css
.speaker {
  appearance: none;
  border: none;
  background: rgba(0, 0, 0, 0.04);
  width: 30px;
  height: 30px;
  border-radius: 50%;
  font-size: 14px;
  cursor: pointer;
  transition: background 200ms ease, transform 200ms ease;
  align-self: center;
}
[data-theme="dark"] .speaker { background: rgba(255, 255, 255, 0.06); }
.speaker:hover { transform: scale(1.08); background: var(--brand-soft); }
```

改成：

```css
.speaker {
  appearance: none;
  border: none;
  background: var(--glass-bg-dim);
  width: 30px;
  height: 30px;
  border-radius: 50%;
  font-size: 14px;
  cursor: pointer;
  transition: background 200ms ease, transform 200ms ease;
  align-self: center;
}
.speaker:hover { transform: scale(1.08); background: var(--brand-soft); }
```

- [ ] **Step 8: `.pos` 暗色硬编码白色清理**

把：

```css
.pos {
  padding: 2px 8px;
  border-radius: 6px;
  background: rgba(0, 0, 0, 0.05);
  font-size: 11px;
  color: var(--text-secondary);
}
[data-theme="dark"] .pos { background: rgba(255, 255, 255, 0.08); }
```

改成：

```css
.pos {
  font-family: var(--font-serif);
  font-style: italic;
  padding: 2px 8px;
  border-radius: 6px;
  background: var(--brand-soft);
  color: var(--brand);
  font-size: 11px;
}
```

- [ ] **Step 9: 跑 build**

```bash
cd /Users/mm/wordglass/frontend && npm run build
```

Expected: 通过。

- [ ] **Step 10: 提交**

```bash
cd /Users/mm/wordglass && git add frontend/src/views/Dashboard.vue && git commit -m "$(cat <<'EOF'
Dashboard: serif typography, accent-colored translation, evergreen→sepia gradient

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Reader.vue — 衬线 + 加载横幅换色

**Files:**
- Modify: `frontend/src/views/Reader.vue`（多处 `<style scoped>` 内）

**Spec ref:** §3.4

- [ ] **Step 1: H1 加衬线**

把：

```css
.title-block h1 {
  margin: 0 0 4px;
  font-size: 22px;
  font-weight: 700;
  letter-spacing: -0.02em;
  display: flex;
  align-items: center;
  gap: 14px;
  flex-wrap: wrap;
}
```

改成：

```css
.title-block h1 {
  font-family: var(--font-serif);
  margin: 0 0 4px;
  font-size: 22px;
  font-weight: 700;
  letter-spacing: -0.02em;
  display: flex;
  align-items: center;
  gap: 14px;
  flex-wrap: wrap;
}
```

- [ ] **Step 2: `.loading-banner` 渐变换色**

把：

```css
.loading-banner {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 14px 4px 12px;
  border-radius: 999px;
  background: linear-gradient(135deg, #8b5cf6 0%, #ec4899 100%);
  color: #fff;
  font-size: 13px;
  font-weight: 600;
  letter-spacing: 0.01em;
  box-shadow: 0 4px 16px rgba(139, 92, 246, 0.35);
  animation: banner-pulse 1.8s ease-in-out infinite;
}
```

改成：

```css
.loading-banner {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 14px 4px 12px;
  border-radius: 999px;
  background: linear-gradient(135deg, var(--brand) 0%, var(--accent) 100%);
  color: var(--brand-strong-text);
  font-size: 13px;
  font-weight: 600;
  letter-spacing: 0.01em;
  box-shadow: 0 4px 16px rgba(74, 110, 62, 0.35);
  animation: banner-pulse 1.8s ease-in-out infinite;
}
```

- [ ] **Step 3: `banner-pulse` keyframes 换色**

把：

```css
@keyframes banner-pulse {
  0%, 100% { box-shadow: 0 4px 16px rgba(139, 92, 246, 0.35); }
  50%      { box-shadow: 0 4px 24px rgba(236, 72, 153, 0.55); }
}
```

改成：

```css
@keyframes banner-pulse {
  0%, 100% { box-shadow: 0 4px 16px rgba(74, 110, 62, 0.35); }
  50%      { box-shadow: 0 4px 24px rgba(184, 145, 101, 0.55); }
}
```

- [ ] **Step 4: `.popup-word` 加衬线**

把：

```css
.popup-word {
  font-size: 17px;
  font-weight: 700;
  color: var(--text-primary);
}
```

改成：

```css
.popup-word {
  font-family: var(--font-serif);
  font-size: 17px;
  font-weight: 700;
  color: var(--text-primary);
}
```

- [ ] **Step 5: `.popup-trans` 颜色换成 `--accent`**

把：

```css
.popup-trans {
  font-size: 14px;
  color: var(--brand);
  font-weight: 500;
  line-height: 1.55;
}
```

改成：

```css
.popup-trans {
  font-size: 14px;
  color: var(--accent);
  font-weight: 500;
  line-height: 1.55;
}
```

- [ ] **Step 6: `.popup-pos` 暗色硬编码清理 + 衬线**

把：

```css
.popup-pos {
  background: rgba(0, 0, 0, 0.05);
  padding: 2px 8px;
  border-radius: 999px;
  color: var(--text-secondary);
}
[data-theme="dark"] .popup-pos { background: rgba(255, 255, 255, 0.08); }
```

改成：

```css
.popup-pos {
  font-family: var(--font-serif);
  font-style: italic;
  background: var(--brand-soft);
  padding: 2px 8px;
  border-radius: 999px;
  color: var(--brand);
}
```

- [ ] **Step 7: 跑 build**

```bash
cd /Users/mm/wordglass/frontend && npm run build
```

Expected: 通过。

- [ ] **Step 8: 提交**

```bash
cd /Users/mm/wordglass && git add frontend/src/views/Reader.vue && git commit -m "$(cat <<'EOF'
Reader: serif H1/popup word, evergreen→sepia loading banner

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Library.vue — H1 衬线

**Files:**
- Modify: `frontend/src/views/Library.vue:239-244`

**Spec ref:** §3.5

- [ ] **Step 1: H1 加衬线**

把：

```css
.page-head h1 {
  font-size: 22px;
  font-weight: 700;
  letter-spacing: -0.02em;
  margin: 0;
}
```

改成：

```css
.page-head h1 {
  font-family: var(--font-serif);
  font-size: 22px;
  font-weight: 700;
  letter-spacing: -0.02em;
  margin: 0;
}
```

Library 的其它颜色都是 token 引用，token 改了就跟着改了。

- [ ] **Step 2: 跑 build**

```bash
cd /Users/mm/wordglass/frontend && npm run build
```

Expected: 通过。

- [ ] **Step 3: 提交**

```bash
cd /Users/mm/wordglass && git add frontend/src/views/Library.vue && git commit -m "$(cat <<'EOF'
Library: serif H1

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: Practice.vue — 衬线 + 大量硬编码蓝色清理

**Files:**
- Modify: `frontend/src/views/Practice.vue`（多处 `<style scoped>` 内）

**Spec ref:** §3.6（含 spec 之外的硬编码颜色清理）

> 这是单一文件里改动最多的任务 —— Practice.vue 之前用了大量 `rgba(0, 122, 255, ...)` (iOS 蓝)、白色硬编码。

- [ ] **Step 1: `.tab.active` 白色背景换 token**

把：

```css
.tab.active {
  background: rgba(255, 255, 255, 0.9);
  color: var(--text-primary);
  box-shadow: 0 2px 8px rgba(31, 38, 135, 0.12);
}

.tab:hover:not(.active) {
  background: rgba(255, 255, 255, 0.4);
  color: var(--text-primary);
}
```

改成：

```css
.tab.active {
  background: var(--glass-bg-strong);
  color: var(--text-primary);
  box-shadow: 0 2px 8px rgba(50, 60, 40, 0.12);
}

.tab:hover:not(.active) {
  background: var(--glass-bg-dim);
  color: var(--text-primary);
}
```

- [ ] **Step 2: `.direction` 容器和按钮改 token**

把：

```css
.direction {
  display: inline-flex;
  align-self: center;
  gap: 4px;
  padding: 4px;
  background: rgba(255, 255, 255, 0.45);
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.4);
}
```

改成：

```css
.direction {
  display: inline-flex;
  align-self: center;
  gap: 4px;
  padding: 4px;
  background: var(--glass-bg-dim);
  border-radius: 999px;
  border: 1px solid var(--glass-border);
}
```

并把：

```css
.direction button.active {
  background: rgba(0, 122, 255, 0.16);
  color: #003fbb;
}
```

改成：

```css
.direction button.active {
  background: var(--brand-soft);
  color: var(--brand);
}
```

- [ ] **Step 3: `.word-text`、`.big-zh`、`.sentence-zh-prompt`、`.sentence-en-prompt`、`.answer-word` 用衬线 + 颜色清理**

把：

```css
.big-zh {
  font-size: clamp(28px, 5vw, 38px);
  font-weight: 600;
  letter-spacing: -0.01em;
  color: var(--text-primary);
  text-align: center;
  line-height: 1.3;
  max-width: 580px;
}
```

改成（中文衬线下要好看，所以中文 prompt 也用 serif —— 系统栈下中文走 Songti SC）：

```css
.big-zh {
  font-family: var(--font-serif);
  font-size: clamp(28px, 5vw, 38px);
  font-weight: 600;
  letter-spacing: -0.01em;
  color: var(--text-primary);
  text-align: center;
  line-height: 1.3;
  max-width: 580px;
}
```

把：

```css
.word-text {
  font-size: clamp(38px, 7vw, 50px);
  font-weight: 700;
  letter-spacing: -0.02em;
  color: var(--text-primary);
}
```

改成：

```css
.word-text {
  font-family: var(--font-serif);
  font-size: clamp(38px, 7vw, 50px);
  font-weight: 700;
  letter-spacing: -0.02em;
  color: var(--text-primary);
}
```

把：

```css
.sentence-zh-prompt {
  font-size: clamp(22px, 4vw, 28px);
  font-weight: 600;
  letter-spacing: -0.01em;
  color: var(--text-primary);
  text-align: center;
  line-height: 1.4;
  max-width: 600px;
}

.sentence-en-prompt {
  font-size: clamp(20px, 3.5vw, 26px);
  font-weight: 500;
  font-style: italic;
  color: var(--text-primary);
  text-align: center;
  line-height: 1.45;
  max-width: 600px;
}
```

改成：

```css
.sentence-zh-prompt {
  font-family: var(--font-serif);
  font-size: clamp(22px, 4vw, 28px);
  font-weight: 600;
  letter-spacing: -0.01em;
  color: var(--text-primary);
  text-align: center;
  line-height: 1.4;
  max-width: 600px;
}

.sentence-en-prompt {
  font-family: var(--font-serif);
  font-size: clamp(20px, 3.5vw, 26px);
  font-weight: 500;
  font-style: italic;
  color: var(--text-primary);
  text-align: center;
  line-height: 1.45;
  max-width: 600px;
}
```

把：

```css
.answer-word {
  font-size: 28px;
  font-weight: 700;
  color: var(--accent);
  letter-spacing: -0.01em;
}
```

改成：

```css
.answer-word {
  font-family: var(--font-serif);
  font-size: 28px;
  font-weight: 700;
  color: var(--brand);
  letter-spacing: -0.01em;
}
```

- [ ] **Step 4: `.pos` 颜色换 token + 衬线**

把：

```css
.pos {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 8px;
  background: rgba(0, 0, 0, 0.05);
  font-size: 12px;
  color: var(--text-secondary);
}
```

改成：

```css
.pos {
  font-family: var(--font-serif);
  font-style: italic;
  display: inline-block;
  padding: 3px 10px;
  border-radius: 8px;
  background: var(--brand-soft);
  font-size: 12px;
  color: var(--brand);
}
```

- [ ] **Step 5: `.finished .big` 加衬线**

把：

```css
.finished .big {
  font-size: 38px;
  font-weight: 700;
  color: var(--text-primary);
}
```

改成：

```css
.finished .big {
  font-family: var(--font-serif);
  font-size: 38px;
  font-weight: 700;
  color: var(--text-primary);
}
```

并 `.progress .num`：

```css
.progress .num {
  font-size: 18px;
  font-weight: 700;
  color: var(--text-primary);
}
```

改成：

```css
.progress .num {
  font-family: var(--font-serif);
  font-size: 18px;
  font-weight: 700;
  color: var(--text-primary);
}
```

- [ ] **Step 6: speaker 系列颜色清理**

把：

```css
.speaker {
  background: rgba(0, 0, 0, 0.04);
  width: 40px;
  height: 40px;
  border-radius: 50%;
  font-size: 18px;
}
.speaker:hover { background: rgba(0, 0, 0, 0.08); transform: scale(1.08); }

.speaker-small {
  background: rgba(0, 0, 0, 0.05);
  width: 30px;
  height: 30px;
  border-radius: 50%;
  font-size: 14px;
}
.speaker-small:hover { background: rgba(0, 0, 0, 0.1); }

.speaker-mini {
  background: var(--accent-soft);
  padding: 6px 12px;
  border-radius: 999px;
  font-size: 13px;
  color: var(--accent);
}
.speaker-mini:hover { background: rgba(0, 122, 255, 0.2); }
```

改成：

```css
.speaker {
  background: var(--glass-bg-dim);
  width: 40px;
  height: 40px;
  border-radius: 50%;
  font-size: 18px;
}
.speaker:hover { background: var(--brand-soft); transform: scale(1.08); }

.speaker-small {
  background: var(--glass-bg-dim);
  width: 30px;
  height: 30px;
  border-radius: 50%;
  font-size: 14px;
}
.speaker-small:hover { background: var(--brand-soft); }

.speaker-mini {
  background: var(--brand-soft);
  padding: 6px 12px;
  border-radius: 999px;
  font-size: 13px;
  color: var(--brand);
}
.speaker-mini:hover { background: color-mix(in srgb, var(--brand) 28%, transparent); }
```

- [ ] **Step 7: `.big-speaker` 用 brand 替换蓝**

把：

```css
.big-speaker {
  appearance: none;
  border: none;
  background: var(--accent-soft);
  width: 104px;
  height: 104px;
  border-radius: 50%;
  font-size: 50px;
  cursor: pointer;
  transition: transform 200ms ease, background 200ms ease;
  animation: pulse 1.6s ease-in-out infinite;
}

.big-speaker:hover {
  background: rgba(0, 122, 255, 0.2);
  transform: scale(1.06);
  animation: none;
}

@keyframes pulse {
  0%, 100% { box-shadow: 0 0 0 0 rgba(0, 122, 255, 0.4); }
  50% { box-shadow: 0 0 0 18px rgba(0, 122, 255, 0); }
}
```

改成：

```css
.big-speaker {
  appearance: none;
  border: none;
  background: var(--brand-soft);
  width: 104px;
  height: 104px;
  border-radius: 50%;
  font-size: 50px;
  color: var(--brand);
  cursor: pointer;
  transition: transform 200ms ease, background 200ms ease;
  animation: pulse 1.6s ease-in-out infinite;
}

.big-speaker:hover {
  background: color-mix(in srgb, var(--brand) 28%, transparent);
  transform: scale(1.06);
  animation: none;
}

@keyframes pulse {
  0%, 100% { box-shadow: 0 0 0 0 rgba(74, 110, 62, 0.4); }
  50% { box-shadow: 0 0 0 18px rgba(74, 110, 62, 0); }
}
```

- [ ] **Step 8: `.answer-input` 系列清理白色和蓝色硬编码**

把：

```css
.answer-input {
  width: 100%;
  appearance: none;
  border: 2px solid rgba(255, 255, 255, 0.5);
  background: rgba(255, 255, 255, 0.65);
  border-radius: 14px;
  padding: 14px 18px;
  font: inherit;
  font-size: 18px;
  font-weight: 500;
  text-align: center;
  color: var(--text-primary);
  outline: none;
  transition: border-color 200ms ease, box-shadow 200ms ease, background 200ms ease;
}

.answer-input::placeholder { color: var(--text-tertiary); font-weight: 400; }

.answer-input:focus {
  border-color: rgba(0, 122, 255, 0.5);
  background: rgba(255, 255, 255, 0.9);
  box-shadow: 0 0 0 4px var(--accent-soft);
}

.text-input-row.correct .answer-input {
  border-color: var(--success);
  background: rgba(52, 199, 89, 0.1);
  box-shadow: 0 0 0 4px rgba(52, 199, 89, 0.18);
}

.text-input-row.wrong .answer-input {
  border-color: var(--danger);
  background: rgba(255, 59, 48, 0.08);
  animation: shake 380ms cubic-bezier(0.36, 0.07, 0.19, 0.97) both;
}
```

改成：

```css
.answer-input {
  width: 100%;
  appearance: none;
  border: 2px solid var(--glass-border);
  background: var(--glass-bg);
  border-radius: var(--radius-card);
  padding: 14px 18px;
  font: inherit;
  font-size: 18px;
  font-weight: 500;
  text-align: center;
  color: var(--text-primary);
  outline: none;
  transition: border-color 200ms ease, box-shadow 200ms ease, background 200ms ease;
}

.answer-input::placeholder { color: var(--text-tertiary); font-weight: 400; }

.answer-input:focus {
  border-color: color-mix(in srgb, var(--brand) 50%, transparent);
  background: var(--glass-bg-strong);
  box-shadow: 0 0 0 4px var(--brand-soft);
}

.text-input-row.correct .answer-input {
  border-color: var(--success);
  background: color-mix(in srgb, var(--success) 12%, var(--glass-bg));
  box-shadow: 0 0 0 4px color-mix(in srgb, var(--success) 22%, transparent);
}

.text-input-row.wrong .answer-input {
  border-color: var(--danger);
  background: color-mix(in srgb, var(--danger) 10%, var(--glass-bg));
  animation: shake 380ms cubic-bezier(0.36, 0.07, 0.19, 0.97) both;
}
```

- [ ] **Step 9: rating 评分按钮配色重做（用 token + 自然色阶）**

把：

```css
.btn.rating:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 18px rgba(31, 38, 135, 0.12);
}

.btn.rating.again {
  background: rgba(255, 59, 48, 0.16);
  color: #b8170c;
  border-color: rgba(255, 59, 48, 0.28);
}
.btn.rating.again:hover { background: rgba(255, 59, 48, 0.24); }

.btn.rating.hard {
  background: rgba(255, 149, 0, 0.18);
  color: #b86700;
  border-color: rgba(255, 149, 0, 0.3);
}
.btn.rating.hard:hover { background: rgba(255, 149, 0, 0.26); }

.btn.rating.good {
  background: rgba(0, 122, 255, 0.18);
  color: #003fbb;
  border-color: rgba(0, 122, 255, 0.3);
}
.btn.rating.good:hover { background: rgba(0, 122, 255, 0.26); }

.btn.rating.easy {
  background: rgba(52, 199, 89, 0.18);
  color: #186a2a;
  border-color: rgba(52, 199, 89, 0.32);
}
.btn.rating.easy:hover { background: rgba(52, 199, 89, 0.26); }
```

改成（"不会 / 模糊 / 认识 / 熟练" 用 红→橙→绿→深绿 同主题色阶）：

```css
.btn.rating:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 18px rgba(50, 60, 40, 0.12);
}

.btn.rating.again {
  background: color-mix(in srgb, var(--danger) 16%, transparent);
  color: var(--danger);
  border-color: color-mix(in srgb, var(--danger) 32%, transparent);
}
.btn.rating.again:hover {
  background: color-mix(in srgb, var(--danger) 26%, transparent);
}

.btn.rating.hard {
  background: color-mix(in srgb, var(--warn) 18%, transparent);
  color: var(--warn);
  border-color: color-mix(in srgb, var(--warn) 32%, transparent);
}
.btn.rating.hard:hover {
  background: color-mix(in srgb, var(--warn) 28%, transparent);
}

.btn.rating.good {
  background: var(--brand-soft);
  color: var(--brand);
  border-color: color-mix(in srgb, var(--brand) 32%, transparent);
}
.btn.rating.good:hover {
  background: color-mix(in srgb, var(--brand) 26%, transparent);
}

.btn.rating.easy {
  background: color-mix(in srgb, var(--success) 18%, transparent);
  color: var(--success);
  border-color: color-mix(in srgb, var(--success) 32%, transparent);
}
.btn.rating.easy:hover {
  background: color-mix(in srgb, var(--success) 28%, transparent);
}
```

- [ ] **Step 10: kbd 标签颜色清理**

把：

```css
.kbd {
  display: inline-block;
  margin-left: 8px;
  padding: 1px 8px;
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.35);
  border: 1px solid rgba(255, 255, 255, 0.5);
  font-family: ui-monospace, monospace;
  font-size: 12px;
  font-weight: 500;
}

.kbd.small {
  margin: 0;
  padding: 0 6px;
  font-size: 11px;
  background: rgba(0, 0, 0, 0.06);
  border-color: rgba(0, 0, 0, 0.08);
}
```

改成：

```css
.kbd {
  display: inline-block;
  margin-left: 8px;
  padding: 1px 8px;
  border-radius: 6px;
  background: var(--glass-bg-dim);
  border: 1px solid var(--glass-border);
  font-family: var(--font-mono);
  font-size: 12px;
  font-weight: 500;
}

.kbd.small {
  margin: 0;
  padding: 0 6px;
  font-size: 11px;
  background: var(--glass-bg-dim);
  border-color: var(--hairline);
}
```

- [ ] **Step 11: `.word-text-small` 用 mono token**

把：

```css
.word-text-small {
  font-family: ui-monospace, "SF Mono", Menlo, monospace;
  font-weight: 600;
  color: var(--text-primary);
}
```

改成：

```css
.word-text-small {
  font-family: var(--font-mono);
  font-weight: 600;
  color: var(--text-primary);
}
```

并把：

```css
.phonetic {
  font-family: ui-monospace, "SF Mono", Menlo, monospace;
  font-size: 15px;
  color: var(--text-tertiary);
}
```

改成：

```css
.phonetic {
  font-family: var(--font-mono);
  font-size: 15px;
  color: var(--text-tertiary);
}
```

- [ ] **Step 12: 跑 build**

```bash
cd /Users/mm/wordglass/frontend && npm run build
```

Expected: 通过。

- [ ] **Step 13: 提交**

```bash
cd /Users/mm/wordglass && git add frontend/src/views/Practice.vue && git commit -m "$(cat <<'EOF'
Practice: serif typography, token-driven colors, recolored rating buttons

Drop hardcoded iOS blue (#007aff), iOS green/orange/red — switch to brand/accent/
state tokens with color-mix for tints.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: Settings.vue — H1 衬线 + 硬编码状态色清理

**Files:**
- Modify: `frontend/src/views/Settings.vue`（多处）

**Spec ref:** §3.7（加 spec 之外的状态徽章颜色清理）

- [ ] **Step 1: H1 加衬线**

把：

```css
h1 {
  font-size: 32px;
  font-weight: 700;
  letter-spacing: -0.02em;
  margin: 0;
}
```

改成：

```css
h1 {
  font-family: var(--font-serif);
  font-size: 32px;
  font-weight: 700;
  letter-spacing: -0.02em;
  margin: 0;
}
```

- [ ] **Step 2: provider 卡片白色硬编码清理**

把：

```css
.provider {
  cursor: pointer;
  padding: 14px 16px;
  border-radius: var(--radius-md);
  border: 1.5px solid rgba(0, 0, 0, 0.06);
  background: rgba(255, 255, 255, 0.35);
  transition: border-color 200ms ease, background 200ms ease, transform 120ms ease;
}

.provider:hover {
  background: rgba(255, 255, 255, 0.55);
}

.provider.active {
  border-color: var(--accent);
  background: var(--accent-soft);
}
```

改成（active 改用 brand 而不是 accent 更顺眼）：

```css
.provider {
  cursor: pointer;
  padding: 14px 16px;
  border-radius: var(--radius-md);
  border: 1.5px solid var(--hairline);
  background: var(--glass-bg-dim);
  transition: border-color 200ms ease, background 200ms ease, transform 120ms ease;
}

.provider:hover {
  background: var(--glass-bg);
}

.provider.active {
  border-color: var(--brand);
  background: var(--brand-soft);
}
```

- [ ] **Step 3: chip 颜色清理**

把：

```css
.chip {
  appearance: none;
  border: 1px solid rgba(0, 0, 0, 0.08);
  background: rgba(255, 255, 255, 0.5);
  padding: 5px 11px;
  border-radius: 999px;
  cursor: pointer;
  font: inherit;
  font-size: 12px;
  font-family: ui-monospace, "SF Mono", Menlo, monospace;
  color: var(--text-secondary);
  transition: background 200ms ease, color 200ms ease, border-color 200ms ease;
}

.chip:hover {
  background: rgba(255, 255, 255, 0.85);
  color: var(--text-primary);
}

.chip.active {
  background: var(--accent);
  color: white;
  border-color: var(--accent);
}
```

改成：

```css
.chip {
  appearance: none;
  border: 1px solid var(--hairline);
  background: var(--glass-bg-dim);
  padding: 5px 11px;
  border-radius: 999px;
  cursor: pointer;
  font: inherit;
  font-size: 12px;
  font-family: var(--font-mono);
  color: var(--text-secondary);
  transition: background 200ms ease, color 200ms ease, border-color 200ms ease;
}

.chip:hover {
  background: var(--glass-bg);
  color: var(--text-primary);
}

.chip.active {
  background: var(--brand);
  color: var(--brand-strong-text);
  border-color: var(--brand);
}
```

- [ ] **Step 4: badge / msg 状态色用 token**

把：

```css
.badge.ok {
  background: rgba(52, 199, 89, 0.18);
  color: #186a2a;
}
.badge.warn {
  background: rgba(255, 149, 0, 0.18);
  color: #b86700;
}
```

改成：

```css
.badge.ok {
  background: color-mix(in srgb, var(--success) 18%, transparent);
  color: var(--success);
}
.badge.warn {
  background: color-mix(in srgb, var(--warn) 18%, transparent);
  color: var(--warn);
}
```

把：

```css
.msg.ok {
  background: rgba(52, 199, 89, 0.18);
  color: #186a2a;
}
.msg.err {
  background: rgba(255, 59, 48, 0.16);
  color: #b8170c;
}
```

改成：

```css
.msg.ok {
  background: color-mix(in srgb, var(--success) 18%, transparent);
  color: var(--success);
}
.msg.err {
  background: color-mix(in srgb, var(--danger) 16%, transparent);
  color: var(--danger);
}
```

- [ ] **Step 5: key-row .eye hover 颜色清理**

把：

```css
.key-row .eye:hover {
  background: rgba(0, 0, 0, 0.05);
}
```

改成：

```css
.key-row .eye:hover {
  background: var(--glass-bg-dim);
}
```

- [ ] **Step 6: 跑 build**

```bash
cd /Users/mm/wordglass/frontend && npm run build
```

Expected: 通过。

- [ ] **Step 7: 提交**

```bash
cd /Users/mm/wordglass && git add frontend/src/views/Settings.vue && git commit -m "$(cat <<'EOF'
Settings: serif H1, token-driven colors for provider/chip/badge/msg

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: AddBar.vue — 无大改

**Files:**
- Modify: `frontend/src/components/AddBar.vue`（小动）

**Spec ref:** §3.12

AddBar 已经基本 token-driven。只动 `.plus` 颜色保持 brand，但需要保证是 brand 不是旧紫 —— token 已变。无需改组件，但顺手把 `.bare-input` 加个统一字号。

- [ ] **Step 1: 检查 `.bare-input` 字体（应继承 body 的 font-ui，无需改）**

文件已经没有硬编码颜色，跳过编辑。这个 task 主要是确认。

- [ ] **Step 2: 跑 build**

```bash
cd /Users/mm/wordglass/frontend && npm run build
```

Expected: 通过。无提交（无改动）。

> 如果实施时发现 AddBar 视觉上需要微调，再加一步。但默认跳过提交。

---

## Task 9: WordCard.vue — 衬线单词文字

**Files:**
- Modify: `frontend/src/components/WordCard.vue:48-53`

**Spec ref:** §3.8

- [ ] **Step 1: `.text` 加衬线**

把：

```css
.text {
  font-size: 22px;
  font-weight: 600;
  letter-spacing: -0.01em;
  color: var(--text-primary);
}
```

改成：

```css
.text {
  font-family: var(--font-serif);
  font-size: 22px;
  font-weight: 600;
  letter-spacing: -0.01em;
  color: var(--text-primary);
}
```

- [ ] **Step 2: `.phonetic` 用 mono token**

把：

```css
.phonetic {
  font-size: 13px;
  font-family: ui-monospace, "SF Mono", Menlo, monospace;
}
```

改成：

```css
.phonetic {
  font-size: 13px;
  font-family: var(--font-mono);
}
```

- [ ] **Step 3: `.pip` 默认色用 token**

把：

```css
.pip {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: rgba(0, 0, 0, 0.12);
}

.pip.on {
  background: var(--accent);
}
```

改成：

```css
.pip {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--hairline-strong);
}

.pip.on {
  background: var(--brand);
}
```

- [ ] **Step 4: 跑 build**

```bash
cd /Users/mm/wordglass/frontend && npm run build
```

Expected: 通过。

- [ ] **Step 5: 提交**

```bash
cd /Users/mm/wordglass && git add frontend/src/components/WordCard.vue && git commit -m "$(cat <<'EOF'
WordCard: serif word text, token-driven pip/phonetic

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 10: WordDetail.vue — 衬线 + 紫色硬编码清理

**Files:**
- Modify: `frontend/src/components/WordDetail.vue`（多处）

**Spec ref:** §3.9

> 这个组件之前有 `rgba(139, 92, 246, 0.25)` 残留（旧紫）。

- [ ] **Step 1: `.word-text` 加衬线**

把：

```css
.word-text {
  font-size: clamp(32px, 4vw, 40px);
  font-weight: 800;
  letter-spacing: -0.02em;
  color: var(--text-primary);
  line-height: 1.1;
}
```

改成：

```css
.word-text {
  font-family: var(--font-serif);
  font-size: clamp(32px, 4vw, 40px);
  font-weight: 700;
  letter-spacing: -0.02em;
  color: var(--text-primary);
  line-height: 1.1;
}
```

- [ ] **Step 2: `.speaker:hover` 紫色硬编码清理**

把：

```css
.speaker:hover { transform: scale(1.08); background: rgba(139, 92, 246, 0.25); }
```

改成：

```css
.speaker:hover { transform: scale(1.08); background: color-mix(in srgb, var(--brand) 28%, transparent); }
```

- [ ] **Step 3: `.phonetic` 用 mono token**

把：

```css
.phonetic {
  font-family: ui-monospace, "SF Mono", Menlo, monospace;
  font-size: 14px;
  color: var(--text-tertiary);
}
```

改成：

```css
.phonetic {
  font-family: var(--font-mono);
  font-size: 14px;
  color: var(--text-tertiary);
}
```

- [ ] **Step 4: `.chip` 暗色硬编码清理**

把：

```css
.chip {
  padding: 3px 10px;
  border-radius: 999px;
  background: rgba(0, 0, 0, 0.05);
  font-size: 12px;
  color: var(--text-secondary);
}
[data-theme="dark"] .chip { background: rgba(255, 255, 255, 0.08); }
```

改成：

```css
.chip {
  padding: 3px 10px;
  border-radius: 999px;
  background: var(--glass-bg-dim);
  font-size: 12px;
  color: var(--text-secondary);
}
```

- [ ] **Step 5: `.translation` 用 accent**

把：

```css
.translation {
  margin-top: 4px;
  font-size: 18px;
  font-weight: 500;
  color: var(--brand);
  line-height: 1.45;
}
```

改成：

```css
.translation {
  margin-top: 4px;
  font-size: 18px;
  font-weight: 500;
  color: var(--accent);
  line-height: 1.45;
}
```

- [ ] **Step 6: `.stat-num` 加衬线**

把：

```css
.stat-num {
  font-size: 22px;
  font-weight: 800;
  letter-spacing: -0.02em;
  color: var(--text-primary);
}
```

改成：

```css
.stat-num {
  font-family: var(--font-serif);
  font-size: 22px;
  font-weight: 700;
  letter-spacing: -0.02em;
  color: var(--text-primary);
}
```

- [ ] **Step 7: `.example-en` 加衬线斜体**

把：

```css
.example-en {
  font-size: 15px;
  color: var(--text-primary);
  line-height: 1.55;
}
```

改成：

```css
.example-en {
  font-family: var(--font-serif);
  font-style: italic;
  font-size: 15px;
  color: var(--text-primary);
  line-height: 1.55;
}
```

- [ ] **Step 8: `.btn-danger` 颜色用 token**

把：

```css
.btn-danger {
  background: rgba(255, 59, 48, 0.14);
  color: var(--danger);
  border-color: rgba(255, 59, 48, 0.28);
}

.btn-danger:hover {
  background: rgba(255, 59, 48, 0.22);
}
```

改成：

```css
.btn-danger {
  background: color-mix(in srgb, var(--danger) 14%, transparent);
  color: var(--danger);
  border-color: color-mix(in srgb, var(--danger) 28%, transparent);
}

.btn-danger:hover {
  background: color-mix(in srgb, var(--danger) 22%, transparent);
}
```

- [ ] **Step 9: 跑 build**

```bash
cd /Users/mm/wordglass/frontend && npm run build
```

Expected: 通过。

- [ ] **Step 10: 提交**

```bash
cd /Users/mm/wordglass && git add frontend/src/components/WordDetail.vue && git commit -m "$(cat <<'EOF'
WordDetail: serif typography, drop hardcoded purple/red, accent-color translation

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 11: Heatmap.vue — 全部紫色换成 brand

**Files:**
- Modify: `frontend/src/components/Heatmap.vue:231-262`

**Spec ref:** §3.10

> Heatmap 大量 `rgba(139, 92, 246, ...)` 硬编码，必须换。

- [ ] **Step 1: 替换 cell level 颜色**

把：

```css
.cell.level-1 { background: rgba(139, 92, 246, 0.30); }
.cell.level-2 { background: rgba(139, 92, 246, 0.55); }
.cell.level-3 { background: rgba(139, 92, 246, 0.80); }
.cell.level-4 { background: rgba(139, 92, 246, 1); box-shadow: 0 0 8px rgba(139, 92, 246, 0.5); }
```

改成：

```css
.cell.level-1 { background: color-mix(in srgb, var(--brand) 30%, transparent); }
.cell.level-2 { background: color-mix(in srgb, var(--brand) 55%, transparent); }
.cell.level-3 { background: color-mix(in srgb, var(--brand) 80%, transparent); }
.cell.level-4 {
  background: var(--brand);
  box-shadow: 0 0 8px color-mix(in srgb, var(--brand) 50%, transparent);
}
```

- [ ] **Step 2: 替换 legend mini cell 颜色**

把：

```css
.cell-mini.level-1 { background: rgba(139, 92, 246, 0.30); }
.cell-mini.level-2 { background: rgba(139, 92, 246, 0.55); }
.cell-mini.level-3 { background: rgba(139, 92, 246, 0.80); }
.cell-mini.level-4 { background: rgba(139, 92, 246, 1); }
```

改成：

```css
.cell-mini.level-1 { background: color-mix(in srgb, var(--brand) 30%, transparent); }
.cell-mini.level-2 { background: color-mix(in srgb, var(--brand) 55%, transparent); }
.cell-mini.level-3 { background: color-mix(in srgb, var(--brand) 80%, transparent); }
.cell-mini.level-4 { background: var(--brand); }
```

- [ ] **Step 3: `.cell` 和 `.cell-mini` 默认色（已用硬编码黑/白）改 token**

把：

```css
.cell {
  aspect-ratio: 1;
  border-radius: 4px;
  background: rgba(0, 0, 0, 0.06);
  transition: transform 120ms ease, box-shadow 200ms ease;
}

[data-theme="dark"] .cell {
  background: rgba(255, 255, 255, 0.06);
}
```

改成：

```css
.cell {
  aspect-ratio: 1;
  border-radius: 4px;
  background: var(--hairline);
  transition: transform 120ms ease, box-shadow 200ms ease;
}
```

把：

```css
.cell-mini {
  width: 11px;
  height: 11px;
  border-radius: 3px;
  background: rgba(0, 0, 0, 0.06);
}

[data-theme="dark"] .cell-mini {
  background: rgba(255, 255, 255, 0.06);
}
```

改成：

```css
.cell-mini {
  width: 11px;
  height: 11px;
  border-radius: 3px;
  background: var(--hairline);
}
```

- [ ] **Step 4: 跑 build**

```bash
cd /Users/mm/wordglass/frontend && npm run build
```

Expected: 通过。

- [ ] **Step 5: 提交**

```bash
cd /Users/mm/wordglass && git add frontend/src/components/Heatmap.vue && git commit -m "$(cat <<'EOF'
Heatmap: replace hardcoded purple with --brand color-mix alphas

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 12: LetterSlots.vue — 蓝色和绿色硬编码清理

**Files:**
- Modify: `frontend/src/components/LetterSlots.vue:135-205`

**Spec ref:** §3.11

> LetterSlots 有 `rgba(0, 122, 255, ...)` 蓝色和 `#186a2a` 深绿、`#b86700` 棕色硬编码，都要换。

- [ ] **Step 1: `.slot` 基础样式**

把：

```css
.slot {
  position: relative;
  width: 40px;
  height: 52px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 28px;
  font-weight: 700;
  border: 2px solid rgba(0, 0, 0, 0.12);
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.6);
  color: var(--text-primary);
  text-transform: lowercase;
  transition: all 200ms ease;
  user-select: none;
}
```

改成：

```css
.slot {
  position: relative;
  width: 40px;
  height: 52px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: var(--font-serif);
  font-size: 28px;
  font-weight: 700;
  border: 2px solid var(--hairline-strong);
  border-radius: 10px;
  background: var(--glass-bg);
  color: var(--text-primary);
  text-transform: lowercase;
  transition: all 200ms ease;
  user-select: none;
}
```

- [ ] **Step 2: `.slot.active` 蓝色硬编码换成 brand**

把：

```css
.slot.active {
  border-color: var(--accent);
  background: rgba(0, 122, 255, 0.1);
  box-shadow: 0 0 0 4px rgba(0, 122, 255, 0.15);
}

.slot.active::after {
  content: "";
  position: absolute;
  bottom: 6px;
  left: 25%;
  right: 25%;
  height: 2px;
  background: var(--accent);
  border-radius: 1px;
  animation: blink 1s ease-in-out infinite;
}
```

改成：

```css
.slot.active {
  border-color: var(--brand);
  background: var(--brand-soft);
  box-shadow: 0 0 0 4px color-mix(in srgb, var(--brand) 15%, transparent);
}

.slot.active::after {
  content: "";
  position: absolute;
  bottom: 6px;
  left: 25%;
  right: 25%;
  height: 2px;
  background: var(--brand);
  border-radius: 1px;
  animation: blink 1s ease-in-out infinite;
}
```

- [ ] **Step 3: `.slot.filled` 颜色换 success token**

把：

```css
.slot.filled:not(.active) {
  background: rgba(255, 255, 255, 0.9);
  border-color: rgba(52, 199, 89, 0.4);
  color: #186a2a;
}
```

改成：

```css
.slot.filled:not(.active) {
  background: var(--glass-bg-strong);
  border-color: color-mix(in srgb, var(--success) 40%, transparent);
  color: var(--success);
}
```

- [ ] **Step 4: `.slot.shake` 颜色换 danger token**

把：

```css
.slot.shake {
  background: rgba(255, 59, 48, 0.15);
  border-color: var(--danger);
  animation: shake 380ms cubic-bezier(0.36, 0.07, 0.19, 0.97) both;
}
```

改成：

```css
.slot.shake {
  background: color-mix(in srgb, var(--danger) 15%, transparent);
  border-color: var(--danger);
  animation: shake 380ms cubic-bezier(0.36, 0.07, 0.19, 0.97) both;
}
```

- [ ] **Step 5: `.slot.hint` 颜色换 warn token**

把：

```css
.slot.hint {
  background: rgba(255, 149, 0, 0.18);
  border-color: rgba(255, 149, 0, 0.4);
  color: #b86700;
}
```

改成：

```css
.slot.hint {
  background: color-mix(in srgb, var(--warn) 18%, transparent);
  border-color: color-mix(in srgb, var(--warn) 40%, transparent);
  color: var(--warn);
}
```

- [ ] **Step 6: `.slots` 容器字体保持 mono（用于槽与槽之间的标点字符）**

把：

```css
.slots {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: center;
  align-items: center;
  font-family: ui-monospace, "SF Mono", Menlo, monospace;
}
```

改成（仅替换 font-family 引用）：

```css
.slots {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: center;
  align-items: center;
  font-family: var(--font-mono);
}
```

- [ ] **Step 7: 跑 build**

```bash
cd /Users/mm/wordglass/frontend && npm run build
```

Expected: 通过。

- [ ] **Step 8: 提交**

```bash
cd /Users/mm/wordglass && git add frontend/src/components/LetterSlots.vue && git commit -m "$(cat <<'EOF'
LetterSlots: serif slot letters, token-driven active/filled/shake/hint colors

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 13: 手动 QA + grep 残留检查

**Files:** （只读 / 启 dev）

**Spec ref:** §8 验收标准

- [ ] **Step 1: grep 找残留硬编码旧色**

```bash
cd /Users/mm/wordglass/frontend/src && \
grep -rnE '#8b5cf6|#ec4899|#a8c5ff|#d1b3ff|#ffb3c7|139,\s*92,\s*246|236,\s*72,\s*153|0,\s*122,\s*255|255,\s*59,\s*48|52,\s*199,\s*89|255,\s*149,\s*0|#186a2a|#b86700|#b8170c|#003fbb' \
  --include='*.vue' --include='*.css' --include='*.ts'
```

Expected: 无输出。如有命中，逐个评估 —— 大多数应替换为 token，少数（如 keyframes 内的明确色）可保留但要确认是否合适。

- [ ] **Step 2: 跑完整 build**

```bash
cd /Users/mm/wordglass/frontend && npm run build
```

Expected: 通过。

- [ ] **Step 3: 启 dev server，明色主题手动巡检**

```bash
cd /Users/mm/wordglass/frontend && npm run dev
```

打开 http://127.0.0.1:5173 ，确保侧栏底部主题切到 ☀ 亮色，逐项验证：

| 页面 | 检查项 |
|---|---|
| 主页 | H1 衬线 / AddBar 加单词跑通 / hero 单词衬线 / 翻译呈暖褐色 / 例句英文斜体衬线 / "今日待复习"大数字呈墨绿→暖褐渐变 / 热力图呈墨绿色阶 / 统计数字衬线 |
| 阅读翻译 | 粘贴一段英文 → loading-banner 呈墨绿→暖褐渐变 / 翻译完点单词 → popup 单词衬线、翻译暖褐色、词性墨绿斜体 / 阅读区单词 hover 墨绿 |
| 单词库 | 搜索 / 分类切换 / 掌握度筛选 / 点单词 → 详情抽屉单词衬线、翻译暖褐 / 例句衬线斜体 / 删除按钮红色（danger token）|
| 练习 | 切三个 tab / 方向 / 单词练习字母槽：active 槽墨绿、填对槽 success 绿、错位震动红、Tab 提示橙 / 评分按钮四档色阶（红→橙→墨绿→深绿）/ 句子练习中英 prompt 衬线 / 听力大喇叭墨绿 |
| 设置 | 协议卡 active 墨绿边框 + brand-soft 背景 / 状态徽章成功色绿 / chip active 墨绿 / 保存按钮深墨绿 |

- [ ] **Step 4: 暗色主题同样巡检**

侧栏底部点 ☾ 切到暗色，重复 Step 3 巡检清单。重点检查：
- 玻璃卡片在暗色下对比度够（文字清晰可读）
- 渐变（hero "today" 大数字、loading banner）在暗色下色阶正确
- 墨绿和暖褐的暗色版（`#b8d49a` / `#d8b483`）和暗背景对比够

- [ ] **Step 5: 关键交互 smoke test**

| 交互 | 验证 |
|---|---|
| 加单词 + AI 异步分类 | 主页 AddBar 加 "serendipity" → 立刻显示翻译 → 后台分类完成后侧栏分类数 +1 |
| 阅读翻译粘贴 + 点词 | Reader 粘段英文 → 自动翻译 → 点词出 popup → "加入单词库"成功 |
| 字母槽听写 | Practice → 听力 tab → 听发音 → 敲字母 → 完成自动跳下一张 |
| 评分 1-4 键 | 完成一张抽认卡后按数字键 1-4 评分 |
| 主题切换持久化 | 切暗色 → 刷新 → 仍是暗色 |

- [ ] **Step 6: TypeScript 严格检查（重复，确认 final build）**

```bash
cd /Users/mm/wordglass/frontend && npm run build
```

Expected: 通过。

- [ ] **Step 7: 没有问题就标记完成（无需 commit —— QA 不改代码）**

如果 QA 阶段发现问题，回到对应 task 修改并补一个独立的 commit。

---

## 完成

所有 13 个 task 跑完后：
- `frontend/src/styles/glass.css` 已重写为新 token 系统
- 14 个组件 / 视图都已迁移到 token 引用 + 衬线字体
- 整体视觉气质：**Liquid Glass + 英文书感 · 墨绿+暖褐 · 动态暖 blob**
- 明暗主题都生效
- 所有功能保持不变
- 无硬编码旧色残留
