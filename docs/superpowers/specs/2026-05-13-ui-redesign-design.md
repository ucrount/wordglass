# WordGlass UI 重设计 · 设计稿

**日期**: 2026-05-13
**目标**: 在不改变任何功能的前提下，用「玻璃质感 + 英文书气质」的视觉语言重做整个前端 UI；同时支持明色 / 暗色主题。

---

## 1. 范围与约束

### 范围内
- 重写 `frontend/src/styles/glass.css`（设计 token、玻璃 / 按钮 / 输入 primitive、背景 blob、动画、滚动条）
- 调整每个 view 和 component 的 `<style scoped>`：颜色引用、字体引用、留白、圆角、装饰性细节
- 调整 `SideBar.vue` 的品牌图标（书脊形状）和导航 item 样式
- 字体栈：中文/UI 用 `-apple-system`，英文单词/标题用 Iowan Old Style → Charter → Source Serif Pro → Georgia → serif
- 主题切换逻辑保持不变（`composables/theme.ts` 不动）

### 范围外
- 任何业务逻辑、API 调用、路由、状态管理改动
- 任何后端改动
- 新增依赖（衬线字体走系统栈，零安装）
- 新增组件或重构组件树
- 移动端导航行为重做（保留现有 hamburger drawer，只换样式）
- PWA / 字体预加载等性能项

### 不能损坏的现有行为
- `Reader.vue` 的点击单词 → 弹 popup 流程
- `Practice.vue` 的字母槽、抽认卡、间隔重复打分
- `Library.vue` 的搜索 / 分类 / 掌握度筛选
- `Dashboard.vue` 的添加单词后轮询补 enrichment
- `WordDetail.vue` 抽屉的所有交互
- 主题切换、`prefers-color-scheme` 跟随、localStorage 持久化

---

## 2. 设计 Token

所有 token 写在 `glass.css` 的 `:root` 和 `[data-theme="dark"]` 里，组件统一通过 CSS 变量引用。

### 2.1 颜色（亮色）

| 用途 | 变量名 | 值 |
|---|---|---|
| 主文字 | `--text-primary` | `#2a3422` |
| 次要文字 | `--text-secondary` | `#5a6549` |
| 三级文字 | `--text-tertiary` | `#8a8870` |
| 品牌主色（墨绿） | `--brand` | `#4a6e3e` |
| 品牌弱化 | `--brand-soft` | `rgba(74, 110, 62, 0.14)` |
| 强调色（暖褐） | `--accent` | `#b89165` |
| 强调弱化 | `--accent-soft` | `rgba(184, 145, 101, 0.14)` |
| 主按钮填充（深墨绿） | `--brand-strong` | `#2e4a26` |
| 主按钮文字 | `--brand-strong-text` | `#f5efe1` |
| 成功 | `--success` | `#5a8a3e` |
| 危险 | `--danger` | `#b94a3a` |
| 警告 | `--warn` | `#c87a2e` |
| 玻璃面（默认） | `--glass-bg` | `rgba(252, 247, 234, 0.62)` |
| 玻璃面（强） | `--glass-bg-strong` | `rgba(252, 247, 234, 0.82)` |
| 玻璃面（弱） | `--glass-bg-dim` | `rgba(252, 247, 234, 0.40)` |
| 玻璃边 | `--glass-border` | `rgba(86, 110, 80, 0.22)` |
| 细线 | `--hairline` | `rgba(86, 110, 80, 0.16)` |
| 强细线 | `--hairline-strong` | `rgba(86, 110, 80, 0.28)` |
| 玻璃阴影 | `--glass-shadow` | `0 8px 24px rgba(50, 60, 40, 0.10)` |
| 玻璃阴影（大） | `--glass-shadow-lg` | `0 20px 48px rgba(50, 60, 40, 0.16)` |
| 背景底色 | `--bg-base` | `linear-gradient(135deg, #f5efe1 0%, #ebe3cf 100%)` |
| Blob 1 米黄 | `--bg-blob-1` | `rgba(228, 209, 169, 0.78)` |
| Blob 2 橄榄 | `--bg-blob-2` | `rgba(151, 175, 136, 0.55)` |
| Blob 3 暖褐 | `--bg-blob-3` | `rgba(184, 145, 95, 0.45)` |
| Blob 1 强 | `--bg-blob-1-stronger` | `rgba(228, 209, 169, 0.55)` |
| Blob 2 强 | `--bg-blob-2-stronger` | `rgba(151, 175, 136, 0.45)` |
| Blob 3 强 | `--bg-blob-3-stronger` | `rgba(184, 145, 95, 0.40)` |

### 2.2 颜色（暗色 `[data-theme="dark"]`）

| 用途 | 变量名 | 值 |
|---|---|---|
| 主文字 | `--text-primary` | `#ede4cf` |
| 次要文字 | `--text-secondary` | `#b4ad8d` |
| 三级文字 | `--text-tertiary` | `#7d7860` |
| 品牌主色（亮墨绿） | `--brand` | `#b8d49a` |
| 品牌弱化 | `--brand-soft` | `rgba(184, 212, 154, 0.18)` |
| 强调色（亮暖褐） | `--accent` | `#d8b483` |
| 强调弱化 | `--accent-soft` | `rgba(216, 180, 131, 0.18)` |
| 主按钮填充 | `--brand-strong` | `#b8d49a` |
| 主按钮文字 | `--brand-strong-text` | `#16221a` |
| 成功 | `--success` | `#a3c98a` |
| 危险 | `--danger` | `#e08070` |
| 警告 | `--warn` | `#e0a060` |
| 玻璃面 | `--glass-bg` | `rgba(30, 42, 32, 0.55)` |
| 玻璃面（强） | `--glass-bg-strong` | `rgba(34, 48, 36, 0.78)` |
| 玻璃面（弱） | `--glass-bg-dim` | `rgba(30, 42, 32, 0.35)` |
| 玻璃边 | `--glass-border` | `rgba(184, 212, 154, 0.20)` |
| 细线 | `--hairline` | `rgba(184, 212, 154, 0.14)` |
| 强细线 | `--hairline-strong` | `rgba(184, 212, 154, 0.22)` |
| 玻璃阴影 | `--glass-shadow` | `0 8px 28px rgba(0, 0, 0, 0.45)` |
| 玻璃阴影（大） | `--glass-shadow-lg` | `0 24px 60px rgba(0, 0, 0, 0.55)` |
| 背景底色 | `--bg-base` | `linear-gradient(135deg, #0e1810 0%, #16221a 100%)` |
| Blob 1 | `--bg-blob-1` | `rgba(151, 175, 136, 0.35)` |
| Blob 2 | `--bg-blob-2` | `rgba(180, 145, 95, 0.30)` |
| Blob 3 | `--bg-blob-3` | `rgba(80, 110, 75, 0.40)` |
| Blob 1 强 | `--bg-blob-1-stronger` | `rgba(151, 175, 136, 0.40)` |
| Blob 2 强 | `--bg-blob-2-stronger` | `rgba(180, 145, 95, 0.35)` |
| Blob 3 强 | `--bg-blob-3-stronger` | `rgba(80, 110, 75, 0.50)` |

命名约定：`--brand` 系列（绿系）用于品牌色和按钮；`--accent` 系列（褐系）用于次要强调（翻译显色、渐变副色）。

### 2.3 字体

```css
--font-ui: -apple-system, BlinkMacSystemFont, "PingFang SC",
           "Helvetica Neue", "Microsoft YaHei", sans-serif;

--font-serif: "Iowan Old Style", "Charter", "Source Serif Pro",
              "Cambria", Georgia, "Songti SC", serif;

--font-mono: ui-monospace, "SF Mono", Menlo, monospace;
```

**用法约定**:
- `body` 默认 `--font-ui`
- 英文单词显示（hero 单词、word card 标题、reader 中的单词、单词库 word card）→ `--font-serif`
- 页面 H1（"主页"、"单词库" 等中文标题）→ `--font-serif`（衬线下中文走 Songti SC，气质和谐）
- 词性 pos 标签 → `--font-serif` + `font-style: italic`
- 例句英文 → `--font-serif` + `italic`，例句中文 → `--font-ui` 普通
- 大数字（待复习数、统计） → `--font-serif` 700
- 音标 → `--font-mono`
- 其它一律 `--font-ui`

### 2.4 圆角

保留现有 4 档（`--radius-sm: 12px / -md: 18px / -lg: 24px / -xl: 32px`），但常用卡片缩到 `14px` —— 增加一个新 token：
```css
--radius-card: 14px;
```
书感意味着圆角不要太"果冻"。胶囊 / 圆形（按钮、tag、avatar）保留 `999px`。

### 2.5 阴影、模糊

`backdrop-filter: blur(22px) saturate(180%)`（之前是 24px），更"扁平"一点点贴合书感。

---

## 3. 组件级修改

> 全部为「样式与文案微调」级别，不动 script / template 结构 (除非下面明确写出)。

### 3.1 `App.vue`
不动。

### 3.2 `SideBar.vue`
- **品牌图标 `.dot`** 改成"书脊"形状：高 22px / 宽 18px / radius 2px，从 `--brand` 渐变到 `--accent`，并用伪元素叠两条横向高光（细节：见 mockup 中 `.brand .mono`）
- **品牌名 `.brand-name`** 改用 `--font-serif`，权重 700
- **激活态左侧标尺**（`.nav-item.active::before`）颜色从原来的 `--brand` 沿用，但宽度从 3px → 3px 不变，高度从 18 → 16
- 全部紫色引用替换为 `--brand`（CSS 变量已经统一，无需改组件代码 —— 只要 token 改了组件就跟着变）

### 3.3 `Dashboard.vue`
- `.h1` 加 `font-family: var(--font-serif)`
- `.word-text` 加 `font-family: var(--font-serif)`
- `.translation` 颜色从 `var(--brand)` 改成 `var(--accent)`（变成暖褐色，呼应"翻译是次要色"的层次）
- `.preview` 左侧 `border-left: 3px solid var(--brand)` 保留
- `.example-en` 加 `font-family: var(--font-serif); font-style: italic`
- `.dot-purple`（class 名留着，只换颜色）：背景从原 `--brand` 不变
- `.big-num` 渐变从 `linear-gradient(135deg, #8b5cf6 0%, #ec4899 100%)` 改成 `linear-gradient(135deg, var(--brand) 0%, var(--accent) 100%)`
- `.due-number.none .big-num` 的 fallback 颜色不动
- `.stat-num` 加 `font-family: var(--font-serif)`

### 3.4 `Reader.vue`
- 页面 H1 衬线
- `.loading-banner` 渐变从紫粉改成 `linear-gradient(135deg, var(--brand) 0%, var(--accent) 100%)`，shadow 颜色对应改
- `.banner-pulse` 关键帧的 box-shadow 颜色对应改
- `.pane-label` 颜色和字号不变
- `.reading` 长文本字体保持 sans（避免一整段英文衬线下中英文标点对齐难看；衬线只用于"被强调"的单词显示，不用于阅读流）
- `.popup-word` 加 `font-family: var(--font-serif)`
- `.popup-trans` 颜色从 `var(--brand)` 改成 `var(--accent)`
- `.skeleton-line` 渐变背景使用 `var(--brand-soft)` —— 自动跟主题
- `.top-progress` 渐变中间色用 `var(--brand)`
- `.empty-emoji` 不动

### 3.5 `Library.vue`
- 页面 H1 衬线
- `.cat-item.active` 沿用 `var(--brand-soft)` 和 `var(--brand)`（无需改组件代码，token 变就跟着变）
- `.cat-count` 的 active 态背景 `var(--brand)` 不变
- `.m-chip.active` 同上
- `.overlay-cat`（分类标签）颜色 `var(--brand)`、背景 `var(--brand-soft)` —— token 自动跟随

### 3.6 `Practice.vue`
- 页面 H1 衬线
- 所有英文单词的展示位置加 `font-family: var(--font-serif)`（实施时按 `Practice.vue` 现有 selector 添加 —— 抽认卡正面单词、整句中翻英的英文等）
- 评分按钮、字母槽底色沿用 `var(--brand-soft)` / `var(--accent-soft)`，配色自然跟随

### 3.7 `Settings.vue`
- 页面 H1 衬线
- 表单组件用 `.input` / `.btn` primitive，token 变即可

### 3.8 `WordCard.vue`
- 单词文字 `.text` / `.word` 加 `font-family: var(--font-serif)`

### 3.9 `WordDetail.vue`
- 标题 / 单词位 衬线
- 删除按钮 `--danger` 颜色不动

### 3.10 `Heatmap.vue`
- 单元格颜色级别用 `var(--brand)` 的不同透明度叠加（已有结构基本如此）—— 看现有实现，把硬编码的紫色替换为 `var(--brand)` 的 alpha 变体

### 3.11 `LetterSlots.vue`
- 槽位边色 `var(--hairline-strong)`，激活态 `var(--brand)` —— token 跟随

### 3.12 `AddBar.vue`
- "加入"按钮使用 `.btn-primary`，token 变即可
- 输入框使用 `.input` primitive

### 3.13 `GlassCard.vue`
- 不变（只是包了 `.glass` class）

### 3.14 `GlobalGuards.vue`
- 不变（无视觉表现）

---

## 4. `glass.css` 全文级改动

### 4.1 替换内容
1. `:root` 与 `[data-theme="dark"]` 的所有 token 按 §2 重写
2. 新增 `--font-ui` / `--font-serif` / `--font-mono` token
3. 新增 `--radius-card: 14px`
4. `.glass` / `.glass-strong` / `.glass-dim` 的 `backdrop-filter` 从 `blur(24px)` → `blur(22px)`；圆角从 `--radius-lg` → `--radius-card`
5. `body` 的 `font-family` 改成 `var(--font-ui)`
6. `body::before` 的 keyframes drift 周期从 30s → 24s（稍快但仍温和）
7. `.btn-primary` 的 `background: var(--brand-strong)`，`color: var(--brand-strong-text)` —— 两个 token 在亮暗主题分别已定义，无需手动覆盖
8. `.btn` hover shadow 颜色从 `rgba(31, 38, 135, ...)` 改成 `rgba(50, 60, 40, ...)`
9. 滚动条 thumb hover 颜色（原来硬编码黑色）改成 `var(--hairline-strong)` 的强化版
10. `.input:focus` 的 outline shadow `var(--accent-soft)` —— 暗色下也会自然跟随

### 4.2 新增 utility class
```css
.serif { font-family: var(--font-serif); }
.ui    { font-family: var(--font-ui); }
.mono  { font-family: var(--font-mono); }
```
方便组件内偶尔需要单点切换字体时不再写 inline style。

---

## 5. 主题切换

完全保留现有 `composables/theme.ts` 实现：
- 读 localStorage `wordglass.theme`
- 否则跟系统 `prefers-color-scheme`
- toggle 写 `data-theme` 到 `<html>`
- 同时设 `colorScheme` 让原生表单控件跟随

侧栏底部的"亮色 / 暗色模式"按钮保留 emoji 图标 `☀ / ☾`。

---

## 6. 浏览器支持与降级

1. `backdrop-filter` —— Safari 9+、Chrome 76+、FF 103+ 都已支持。降级方案：当浏览器不支持时，`.glass` 自动退化为 `var(--glass-bg-strong)` 实色背景（已有效果可接受，无需额外 `@supports` 块）
2. 衬线字体走系统栈，**零安装**：macOS/iOS 用 Iowan Old Style，Windows 用 Cambria，Linux 用 DejaVu Serif；中文衬线 macOS/iOS 是 Songti SC，Windows 是 SimSun
3. CSS 变量、`color-mix`：均为已落地特性，沿用现有写法

---

## 7. 实施顺序（写计划时参考）

1. **Token 重写** —— 改 `glass.css` 的 `:root` / `[data-theme="dark"]` / 字体 / 圆角 / blur / blob 时长 / `.btn-primary` 配色 / 滚动条
2. **侧栏品牌图标** —— `SideBar.vue` 的 `.dot` 改成书脊形 + 品牌名衬线
3. **Dashboard 排版** —— `.h1`、`.word-text`、`.example-en`、`.big-num` 渐变、`.translation` 改色、`.stat-num` 衬线
4. **Reader 排版** —— H1 衬线、`.loading-banner` 渐变换色、`.popup-word` 衬线、`.popup-trans` 改色
5. **Library / Practice / Settings / WordCard / WordDetail / Heatmap / LetterSlots / AddBar** —— 标题衬线 + 局部硬编码紫色清理
6. **手动测试** —— 启 `npm run dev`，浏览器实跑，明暗都看，每个页面、每个交互过一遍

---

## 8. 验收标准

- 所有页面在 `<html data-theme="light">` 和 `<html data-theme="dark">` 下都正常渲染，无颜色冲突 / 无对比度过低
- 所有功能可用（添加单词、翻译、点词加入、练习四种模式、库筛选、设置保存）
- TypeScript 编译通过（`npm run build`）
- 视觉上达到 mockup 一致的气质：玻璃磨砂卡片 + 衬线英文 + 墨绿/暖褐 + 飘动暖 blob
- 没有任何文件出现 `#8b5cf6` / `#ec4899` / `#007aff` 等旧色硬编码（除了在备注或暗色 fallback 注释里）

---

## 9. 已识别的小问题（顺手修）

- `Reader.vue` 第 397 行 `.top-progress { left: 220px; }` —— 硬编码侧栏宽度。重设计期间留意保持；如果将来侧栏宽度换 token，这里也改
- `App.vue` 第 30 行 `margin-left: 220px` —— 同上，硬编码
- `SideBar.vue` 第 91 行 `width: 220px` —— 三处硬编码同步。**本次不动**（不在范围内），但如果将来要重构成 token 应一起改

---

## 10. 不改但可能想改的（明确不做，避免实施时漂移）

- 不改图标系统（继续用 emoji）
- 不改组件抽象（不引入 Button.vue / Card.vue 之类）
- 不引入 Tailwind / UnoCSS
- 不引入字体文件（不 self-host Iowan Old Style）
- 不改路由 / 布局结构 / 移动端断点
- 不改文案
