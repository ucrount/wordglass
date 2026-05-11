<script setup lang="ts">
import { RouterLink } from "vue-router";
import { useTheme } from "../composables/theme";

const { theme, toggle } = useTheme();
</script>

<template>
  <header class="navbar glass-strong">
    <div class="container nav-inner">
      <RouterLink to="/" class="brand">
        <span class="dot" />
        WordGlass
      </RouterLink>
      <nav class="links">
        <RouterLink to="/" exact-active-class="active">概览</RouterLink>
        <RouterLink to="/library" active-class="active">单词库</RouterLink>
        <RouterLink to="/practice" active-class="active">练习</RouterLink>
        <button
          class="icon-btn"
          :title="theme === 'dark' ? '切到亮色' : '切到暗色'"
          @click="toggle"
        >
          <span class="theme-icon">{{ theme === "dark" ? "☀" : "🌙" }}</span>
        </button>
        <RouterLink to="/settings" active-class="active" class="icon-link" title="设置">
          <span class="gear">⚙</span>
        </RouterLink>
      </nav>
    </div>
  </header>
</template>

<style scoped>
.navbar {
  position: sticky;
  top: 0;
  z-index: 50;
  border-radius: 0;
  border-left: none;
  border-right: none;
  border-top: none;
  margin-bottom: 32px;
}

.nav-inner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 56px;
}

.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  text-decoration: none;
  color: var(--text-primary);
  font-weight: 600;
  font-size: 17px;
  letter-spacing: -0.01em;
}

.dot {
  width: 22px;
  height: 22px;
  border-radius: 7px;
  background: linear-gradient(135deg, #a8c5ff 0%, #d1b3ff 50%, #ffb3c7 100%);
  box-shadow: 0 2px 8px rgba(120, 140, 220, 0.3);
}

.links {
  display: flex;
  align-items: center;
  gap: 4px;
}

.links a {
  text-decoration: none;
  color: var(--text-secondary);
  padding: 8px 16px;
  border-radius: 999px;
  font-size: 14px;
  font-weight: 500;
  transition: background 200ms ease, color 200ms ease;
}

.links a:hover {
  background: var(--glass-bg-dim);
  color: var(--text-primary);
}

.links a.active {
  background: var(--glass-bg-strong);
  color: var(--text-primary);
}

.icon-link, .icon-btn {
  padding: 8px 12px !important;
  font-size: 16px;
  line-height: 1;
  background: transparent;
  border: none;
  cursor: pointer;
  color: var(--text-secondary);
}

.icon-btn {
  border-radius: 999px;
  transition: background 200ms ease, transform 300ms ease;
}

.icon-btn:hover {
  background: var(--glass-bg-dim);
}

.theme-icon {
  display: inline-block;
  transition: transform 400ms cubic-bezier(0.34, 1.56, 0.64, 1);
}

.icon-btn:hover .theme-icon {
  transform: rotate(180deg) scale(1.1);
}

.gear {
  display: inline-block;
  transition: transform 400ms ease;
}

.icon-link:hover .gear {
  transform: rotate(90deg);
}
</style>
