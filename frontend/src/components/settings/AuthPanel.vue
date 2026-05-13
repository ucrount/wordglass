<script setup lang="ts">
import type { SettingsIn, SettingsOut } from "../../api";

defineProps<{
  form: {
    provider_type: SettingsIn["provider_type"];
    base_url: string;
    api_key: string;
    model: string;
    auth_token: string;
  };
  original: SettingsOut | null;
  message: { kind: "ok" | "err"; text: string } | null;
}>();

const emit = defineEmits<{ (e: "save"): void }>();
</script>

<template>
  <div>
    <header class="panel-head">
      <h2>访问令牌</h2>
      <span class="badge" :class="{ ok: original?.auth_token_set, warn: !original?.auth_token_set }">
        {{ original?.auth_token_set ? "已设置" : "未设置（接口开放）" }}
      </span>
    </header>

    <p class="muted small intro">
      如果你的 VPS 公网暴露在 0.0.0.0，建议设一个随机串保护接口。设了之后浏览器会自动把它带在请求里（存浏览器本地）。
    </p>

    <section class="row">
      <label>新令牌</label>
      <input v-model="form.auth_token" class="input" type="text" placeholder="留空表示不修改；填 none 清除" />
      <div class="help">
        留空 = 保持不变 · 填 <code>none</code> = 清除现有令牌
      </div>
    </section>

    <Transition name="fade">
      <div v-if="message" class="msg" :class="message.kind">{{ message.text }}</div>
    </Transition>

    <div class="actions">
      <button class="btn btn-primary" @click="emit('save')">💾 保存</button>
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
  margin-bottom: 16px;
}
.panel-head h2 {
  font-family: var(--font-serif);
  font-size: 18px;
  font-weight: 700;
  margin: 0;
}
.badge {
  font-size: 11px;
  padding: 2px 9px;
  border-radius: 999px;
  font-weight: 600;
}
.badge.ok { background: color-mix(in srgb, var(--success) 18%, transparent); color: var(--success); }
.badge.warn { background: color-mix(in srgb, var(--warn) 18%, transparent); color: var(--warn); }

.intro { margin-bottom: 14px; }
.row { display: flex; flex-direction: column; gap: 6px; margin-bottom: 14px; }
.row > label { font-size: 12px; font-weight: 600; color: var(--text-secondary); }
.help { font-size: 11.5px; color: var(--text-tertiary); }
code {
  font-family: var(--font-mono);
  font-size: 11.5px;
  background: var(--glass-bg-dim);
  padding: 1px 6px;
  border-radius: 4px;
}

.msg {
  padding: 10px 14px;
  border-radius: var(--radius-md);
  font-size: 13px;
  margin-bottom: 12px;
}
.msg.ok { background: color-mix(in srgb, var(--success) 18%, transparent); color: var(--success); }
.msg.err { background: color-mix(in srgb, var(--danger) 16%, transparent); color: var(--danger); }

.actions { display: flex; justify-content: flex-end; }

.fade-enter-active, .fade-leave-active { transition: opacity 200ms; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>
