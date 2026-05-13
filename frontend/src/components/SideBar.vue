<script setup lang="ts">
import { ref } from "vue";
import { RouterLink, useRouter } from "vue-router";
import { useTheme } from "../composables/theme";
import { useAuth } from "../composables/auth";

const { theme, toggle } = useTheme();
const { user, clearSession } = useAuth();
const router = useRouter();
const mobileOpen = ref(false);

function logout() {
  clearSession();
  router.replace({ name: "login" });
}

const NAV = [
  { to: "/", label: "主页", icon: "🏠", exact: true },
  { to: "/reader", label: "阅读翻译", icon: "📖" },
  { to: "/library", label: "单词库", icon: "📚" },
  { to: "/practice", label: "练习", icon: "🎯" },
];

const TOOLS = [
  { to: "/settings", label: "设置", icon: "⚙" },
];
</script>

<template>
  <!-- Mobile hamburger trigger -->
  <button
    class="mobile-toggle glass-strong"
    :class="{ open: mobileOpen }"
    @click="mobileOpen = !mobileOpen"
    aria-label="菜单"
  >
    <span class="hb-line" />
    <span class="hb-line" />
    <span class="hb-line" />
  </button>

  <!-- Backdrop for mobile drawer -->
  <Transition name="fade">
    <div v-if="mobileOpen" class="backdrop" @click="mobileOpen = false" />
  </Transition>

  <aside class="sidebar glass-strong" :class="{ 'mobile-open': mobileOpen }">
    <RouterLink to="/" class="brand" @click="mobileOpen = false">
      <span class="dot" />
      <span class="brand-name">WordGlass</span>
    </RouterLink>

    <nav class="nav">
      <RouterLink
        v-for="n in NAV"
        :key="n.to"
        :to="n.to"
        class="nav-item"
        :active-class="!n.exact ? 'active' : ''"
        :exact-active-class="n.exact ? 'active' : ''"
        @click="mobileOpen = false"
      >
        <span class="icon">{{ n.icon }}</span>
        <span class="label">{{ n.label }}</span>
      </RouterLink>

      <div class="divider">
        <span class="divider-label">工具</span>
      </div>

      <RouterLink
        v-for="t in TOOLS"
        :key="t.to"
        :to="t.to"
        class="nav-item"
        active-class="active"
        @click="mobileOpen = false"
      >
        <span class="icon">{{ t.icon }}</span>
        <span class="label">{{ t.label }}</span>
      </RouterLink>
    </nav>

    <div class="footer">
      <div v-if="user" class="user-block">
        <span class="user-icon">👤</span>
        <div class="user-info">
          <div class="username">{{ user.username }}<span v-if="user.is_admin" class="admin-tag">👑</span></div>
          <button class="logout-btn" @click="logout">退出</button>
        </div>
      </div>
      <button class="theme-btn" @click="toggle" :title="theme === 'dark' ? '切到亮色' : '切到暗色'">
        <span class="icon theme-icon">{{ theme === "dark" ? "☀" : "🌙" }}</span>
        <span class="label">{{ theme === "dark" ? "亮色模式" : "暗色模式" }}</span>
      </button>
    </div>
  </aside>
</template>

<style scoped>
.sidebar {
  position: fixed;
  top: 0;
  left: 0;
  bottom: 0;
  width: 220px;
  padding: 24px 14px 16px;
  display: flex;
  flex-direction: column;
  gap: 18px;
  z-index: 40;
  border-radius: 0;
  border-top: none;
  border-left: none;
  border-bottom: none;
  border-right: 1px solid var(--glass-border);
}

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

.nav {
  display: flex;
  flex-direction: column;
  gap: 2px;
  flex: 1;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 14px;
  border-radius: 12px;
  text-decoration: none;
  color: var(--text-secondary);
  font-size: 14px;
  font-weight: 500;
  position: relative;
  transition: background 200ms ease, color 200ms ease;
}

.nav-item .icon {
  font-size: 16px;
  width: 20px;
  text-align: center;
  line-height: 1;
}

.nav-item:hover {
  background: var(--glass-bg-dim);
  color: var(--text-primary);
}

.nav-item.active {
  background: var(--brand-soft);
  color: var(--brand);
  font-weight: 600;
}

.nav-item.active::before {
  content: "";
  position: absolute;
  left: 0;
  top: 50%;
  transform: translateY(-50%);
  width: 3px;
  height: 18px;
  background: var(--brand);
  border-radius: 0 3px 3px 0;
}

.divider {
  position: relative;
  margin: 14px 6px 6px;
  height: 16px;
}

.divider-label {
  font-size: 11px;
  color: var(--text-tertiary);
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

.footer {
  border-top: 1px solid var(--hairline);
  padding-top: 12px;
}

.user-block {
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 8px 12px;
  margin-bottom: 4px;
}
.user-icon { font-size: 16px; opacity: 0.7; }
.user-info { display: flex; flex-direction: column; gap: 2px; min-width: 0; flex: 1; }
.username {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  display: flex;
  align-items: center;
  gap: 4px;
}
.admin-tag {
  font-size: 11px;
}
.logout-btn {
  appearance: none;
  background: transparent;
  border: none;
  padding: 0;
  font: inherit;
  font-size: 11px;
  color: var(--text-tertiary);
  cursor: pointer;
  text-align: left;
}
.logout-btn:hover { color: var(--danger); }

.theme-btn {
  appearance: none;
  border: none;
  background: transparent;
  cursor: pointer;
  width: 100%;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 14px;
  border-radius: 12px;
  color: var(--text-secondary);
  font: inherit;
  font-size: 14px;
  font-weight: 500;
  transition: background 200ms ease, color 200ms ease;
}

.theme-btn:hover {
  background: var(--glass-bg-dim);
  color: var(--text-primary);
}

.theme-btn .icon {
  font-size: 16px;
  width: 20px;
  text-align: center;
  transition: transform 400ms cubic-bezier(0.34, 1.56, 0.64, 1);
}

.theme-btn:hover .icon {
  transform: rotate(180deg);
}

/* Mobile hamburger */
.mobile-toggle {
  display: none;
  position: fixed;
  top: 16px;
  left: 16px;
  z-index: 60;
  width: 42px;
  height: 42px;
  border-radius: 12px;
  align-items: center;
  justify-content: center;
  flex-direction: column;
  gap: 4px;
  cursor: pointer;
  padding: 0;
}

.hb-line {
  display: block;
  width: 18px;
  height: 2px;
  background: var(--text-primary);
  border-radius: 1px;
  transition: transform 200ms ease, opacity 200ms ease;
}

.mobile-toggle.open .hb-line:nth-child(1) {
  transform: translateY(6px) rotate(45deg);
}
.mobile-toggle.open .hb-line:nth-child(2) {
  opacity: 0;
}
.mobile-toggle.open .hb-line:nth-child(3) {
  transform: translateY(-6px) rotate(-45deg);
}

.backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.3);
  backdrop-filter: blur(4px);
  z-index: 35;
}

@media (max-width: 860px) {
  .sidebar {
    transform: translateX(-100%);
    transition: transform 280ms cubic-bezier(0.16, 1, 0.3, 1);
  }
  .sidebar.mobile-open {
    transform: translateX(0);
  }
  .mobile-toggle {
    display: flex;
  }
}
</style>
