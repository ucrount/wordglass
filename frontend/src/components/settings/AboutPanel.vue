<script setup lang="ts">
const VERSION = "0.3.0";
</script>

<template>
  <div>
    <header class="panel-head">
      <h2>版本信息</h2>
      <span class="meta tertiary small">v{{ VERSION }}</span>
    </header>

    <div class="about-card">
      <div class="logo-row">
        <span class="logo-dot" />
        <span class="logo-name">WordGlass</span>
        <span class="version">v{{ VERSION }}</span>
      </div>
      <p class="muted small">
        苹果毛玻璃风格的英语单词学习 web app —— 粘段英文 → 本地词典秒出翻译 → 真实例句 → 多模式反复练习。
      </p>
      <hr class="divider" />
      <div class="links">
        <a href="https://github.com/ucrount/wordglass" target="_blank" rel="noopener">📦 GitHub 仓库</a>
        <a href="https://github.com/ucrount/wordglass/issues" target="_blank" rel="noopener">🐛 反馈 / 提 issue</a>
        <a href="https://github.com/ucrount/wordglass/blob/main/README.md" target="_blank" rel="noopener">📖 文档</a>
      </div>
      <p class="tertiary small license">MIT License</p>
    </div>
  </div>
</template>

<style scoped>
.panel-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--hairline);
  margin-bottom: 14px;
}
.panel-head h2 {
  font-family: var(--font-serif);
  font-size: 18px;
  font-weight: 700;
  margin: 0;
}
.meta { font-family: var(--font-mono); font-size: 11px; }

.about-card {
  padding: 18px 20px;
  background: var(--glass-bg-dim);
  border: 1px solid var(--hairline);
  border-radius: var(--radius-md);
}

.logo-row {
  display: flex;
  align-items: baseline;
  gap: 10px;
  margin-bottom: 8px;
}
.logo-dot {
  width: 14px;
  height: 18px;
  border-radius: 2px;
  background: linear-gradient(180deg, var(--brand) 0%, var(--accent) 100%);
  align-self: center;
  box-shadow: 0 2px 4px rgba(50,60,40,0.25);
}
.logo-name {
  font-family: var(--font-serif);
  font-size: 22px;
  font-weight: 700;
}
.version {
  font-family: var(--font-mono);
  font-size: 13px;
  color: var(--text-tertiary);
}

.divider { border: none; border-top: 1px solid var(--hairline); margin: 14px 0; }

.links {
  display: flex;
  gap: 14px;
  flex-wrap: wrap;
  font-size: 13px;
}
.links a {
  color: var(--brand);
  text-decoration: none;
}
.links a:hover { text-decoration: underline; }

.license {
  font-size: 11px;
  margin-top: 12px;
}
.small { font-size: 13px; }
.muted { color: var(--text-secondary); line-height: 1.55; }
</style>
