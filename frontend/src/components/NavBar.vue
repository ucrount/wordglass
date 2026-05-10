<script setup lang="ts">
import { RouterLink } from "vue-router";
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
  background: rgba(255, 255, 255, 0.4);
  color: var(--text-primary);
}

.links a.active {
  background: rgba(255, 255, 255, 0.7);
  color: var(--text-primary);
}
</style>
