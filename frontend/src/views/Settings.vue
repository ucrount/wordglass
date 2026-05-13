<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { api, type SettingsIn, type SettingsOut, type ProviderPreset } from "../api";
import { useAuth } from "../composables/auth";

import AiProviderPanel from "../components/settings/AiProviderPanel.vue";
import TestPanel from "../components/settings/TestPanel.vue";
import AuthPanel from "../components/settings/AuthPanel.vue";
import AiLogsPanel from "../components/settings/AiLogsPanel.vue";
import SysLogsPanel from "../components/settings/SysLogsPanel.vue";
import OfflinePanel from "../components/settings/OfflinePanel.vue";
import AboutPanel from "../components/settings/AboutPanel.vue";
import AdminPanel from "../components/settings/AdminPanel.vue";

const { isAdmin } = useAuth();

type Tab = "ai" | "test" | "auth" | "log_ai" | "log_sys" | "offline" | "about" | "admin";

const STORAGE_KEY_TAB = "wordglass.settings.tab";

function loadTab(): Tab {
  const v = localStorage.getItem(STORAGE_KEY_TAB) || "ai";
  const valid: Tab[] = ["ai", "test", "auth", "log_ai", "log_sys", "offline", "about", "admin"];
  return (valid.includes(v as Tab) ? v : "ai") as Tab;
}

const tab = ref<Tab>(loadTab());
function setTab(t: Tab) {
  tab.value = t;
  localStorage.setItem(STORAGE_KEY_TAB, t);
}

const presets = ref<ProviderPreset[]>([]);
const original = ref<SettingsOut | null>(null);
const form = ref<{
  provider_type: SettingsIn["provider_type"];
  base_url: string;
  api_key: string;
  model: string;
  auth_token: string;
}>({
  provider_type: "openai",
  base_url: "",
  api_key: "",
  model: "",
  auth_token: "",
});

const loading = ref(true);
const message = ref<{ kind: "ok" | "err"; text: string } | null>(null);

async function load() {
  loading.value = true;
  try {
    const [s, p] = await Promise.all([api.getSettings(), api.listPresets()]);
    original.value = s;
    presets.value = p.presets;
    form.value = {
      provider_type: s.provider_type as SettingsIn["provider_type"],
      base_url: s.base_url,
      api_key: "",
      model: s.model,
      auth_token: "",
    };
  } catch (e: any) {
    message.value = { kind: "err", text: e.message || "加载失败" };
  } finally {
    loading.value = false;
  }
}

function buildPayload(): SettingsIn {
  return {
    provider_type: form.value.provider_type,
    base_url: form.value.base_url,
    api_key: form.value.api_key,
    model: form.value.model,
    auth_token: form.value.auth_token,
  };
}

async function save() {
  message.value = null;
  try {
    const updated = await api.saveSettings(buildPayload());
    original.value = updated;
    form.value.api_key = "";
    form.value.auth_token = "";
    message.value = { kind: "ok", text: "已保存" };
    setTimeout(() => { if (message.value?.kind === "ok") message.value = null; }, 2500);
  } catch (e: any) {
    message.value = { kind: "err", text: e.message || "保存失败" };
  }
}

const aiBadge = ref(0);
const sysBadge = ref(0);

onMounted(load);

const tabs = computed(() => [
  { group: "配置", items: [
    { id: "ai" as const,   icon: "⚙",  label: "AI Provider" },
    { id: "test" as const, icon: "🔌", label: "测试 & 诊断" },
    { id: "auth" as const, icon: "🔒", label: "访问令牌" },
  ]},
  { group: "日志 & 监控", items: [
    { id: "log_ai" as const,  icon: "🤖", label: "AI 调用记录", badge: aiBadge.value },
    { id: "log_sys" as const, icon: "📋", label: "系统日志",    badge: sysBadge.value },
  ]},
  ...(isAdmin.value ? [{
    group: "管理",
    items: [{ id: "admin" as const, icon: "👑", label: "管理员" }],
  }] : []),
  { group: "关于", items: [
    { id: "offline" as const, icon: "📚", label: "离线数据" },
    { id: "about" as const,   icon: "ℹ",  label: "版本信息" },
  ]},
]);
</script>

<template>
  <section class="settings">
    <header class="page-head">
      <h1>设置</h1>
      <p class="muted small">AI 配置、连接测试、调用日志和系统诊断都在这里</p>
    </header>

    <div v-if="loading" class="placeholder glass">加载中…</div>

    <div v-else class="settings-layout glass">
      <aside class="settings-nav">
        <template v-for="group in tabs" :key="group.group">
          <div class="nav-h">{{ group.group }}</div>
          <button
            v-for="item in group.items"
            :key="item.id"
            class="nav-item"
            :class="{ active: tab === item.id }"
            @click="setTab(item.id)"
          >
            <span class="ico">{{ item.icon }}</span>
            <span class="label">{{ item.label }}</span>
            <span v-if="(item as any).badge" class="nav-badge">{{ (item as any).badge }}</span>
          </button>
        </template>
      </aside>

      <div class="settings-content">
        <Transition name="fade" mode="out-in">
          <AiProviderPanel
            v-if="tab === 'ai'"
            :form="form"
            :original="original"
            :presets="presets"
            :message="message"
            @save="save"
          />
          <TestPanel
            v-else-if="tab === 'test'"
            :form="form"
            :original="original"
          />
          <AuthPanel
            v-else-if="tab === 'auth'"
            :form="form"
            :original="original"
            :message="message"
            @save="save"
          />
          <AiLogsPanel
            v-else-if="tab === 'log_ai'"
            @count="(n) => aiBadge = n"
          />
          <SysLogsPanel
            v-else-if="tab === 'log_sys'"
            @count="(n) => sysBadge = n"
          />
          <OfflinePanel v-else-if="tab === 'offline'" />
          <AdminPanel v-else-if="tab === 'admin'" />
          <AboutPanel v-else-if="tab === 'about'" />
        </Transition>
      </div>
    </div>
  </section>
</template>

<style scoped>
.settings {
  display: flex;
  flex-direction: column;
  gap: 14px;
  max-width: 1100px;
  margin: 0 auto;
}

h1 {
  font-family: var(--font-serif);
  font-size: 22px;
  font-weight: 700;
  letter-spacing: -0.02em;
  margin: 0;
}

.small { font-size: 13px; }

.placeholder { padding: 48px; text-align: center; color: var(--text-secondary); }

.settings-layout {
  display: grid;
  grid-template-columns: 200px 1fr;
  gap: 0;
  min-height: 560px;
  padding: 0;
  overflow: hidden;
}

.settings-nav {
  padding: 18px 12px;
  border-right: 1px solid var(--hairline);
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.nav-h {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--text-tertiary);
  padding: 8px 12px 6px;
  margin-top: 4px;
}
.nav-h:first-child { margin-top: 0; }

.nav-item {
  appearance: none;
  background: transparent;
  border: none;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  border-radius: 10px;
  font: inherit;
  font-size: 13px;
  color: var(--text-secondary);
  cursor: pointer;
  text-align: left;
  position: relative;
  transition: background 150ms, color 150ms;
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
  height: 16px;
  background: var(--brand);
  border-radius: 0 2px 2px 0;
}
.nav-item .ico {
  width: 16px;
  font-style: normal;
  opacity: 0.7;
}
.nav-item.active .ico { opacity: 1; }
.nav-item .label { flex: 1; }
.nav-badge {
  font-size: 10px;
  font-weight: 700;
  padding: 1px 7px;
  border-radius: 999px;
  background: var(--brand-soft);
  color: var(--brand);
  font-variant-numeric: tabular-nums;
}

.settings-content {
  padding: 22px 26px;
  min-width: 0;
  overflow-y: auto;
  max-height: calc(100vh - 180px);
}

.fade-enter-active, .fade-leave-active {
  transition: opacity 150ms ease, transform 150ms ease;
}
.fade-enter-from, .fade-leave-to {
  opacity: 0;
  transform: translateY(4px);
}

@media (max-width: 860px) {
  .settings-layout {
    grid-template-columns: 1fr;
  }
  .settings-nav {
    border-right: none;
    border-bottom: 1px solid var(--hairline);
    flex-direction: row;
    overflow-x: auto;
    padding: 10px;
  }
  .nav-h { display: none; }
  .nav-item { flex-shrink: 0; }
  .settings-content { padding: 18px 16px; max-height: none; }
}
</style>
