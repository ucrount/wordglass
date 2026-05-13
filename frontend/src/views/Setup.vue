<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { api } from "../api";
import { useAuth } from "../composables/auth";

const router = useRouter();
const { setSession } = useAuth();

const username = ref("");
const password = ref("");
const password2 = ref("");
const loading = ref(false);
const error = ref("");

async function submit() {
  if (!username.value || !password.value) return;
  if (password.value !== password2.value) {
    error.value = "两次输入的密码不一致";
    return;
  }
  loading.value = true;
  error.value = "";
  try {
    const r = await api.setup(username.value, password.value);
    setSession(r.token, { id: 0, username: r.username, is_admin: r.is_admin });
    try {
      const me = await api.me();
      setSession(r.token, me);
    } catch { /* keep partial */ }
    router.replace("/");
  } catch (e: any) {
    error.value = e.message || "初始化失败";
  } finally {
    loading.value = false;
  }
}

onMounted(async () => {
  try {
    const s = await api.setupStatus();
    if (!s.needs_setup) {
      router.replace({ name: "login" });
    }
  } catch { /* network */ }
});
</script>

<template>
  <div class="auth-page">
    <div class="floating-bg">
      <span class="w w1">serendipity</span>
      <span class="w w2">epiphany</span>
      <span class="w w3">resilience</span>
      <span class="w w4">solitude</span>
    </div>
    <div class="auth-card glass-strong">
      <div class="brand-row">
        <span class="brand-dot" />
        <span class="brand-name">WordGlass</span>
      </div>
      <p class="brand-tagline">首次使用 · 创建管理员账号</p>
      <h2 class="form-h">👑 初始化</h2>
      <p class="muted small intro">
        这是首次访问，请创建管理员账号。之后所有现有数据（如果有）会归到这个账号下。
      </p>
      <form @submit.prevent="submit">
        <div class="field">
          <label>管理员用户名</label>
          <input v-model="username" class="input" autocomplete="username" autofocus
                 placeholder="3-20 位字母数字下划线" />
        </div>
        <div class="field">
          <label>密码</label>
          <input v-model="password" class="input" type="password" autocomplete="new-password"
                 placeholder="至少 6 位" />
        </div>
        <div class="field">
          <label>再次输入密码</label>
          <input v-model="password2" class="input" type="password" autocomplete="new-password" />
        </div>
        <div v-if="error" class="error">{{ error }}</div>
        <button type="submit" class="btn btn-primary auth-btn" :disabled="loading">
          {{ loading ? "创建中…" : "完成初始化" }}
        </button>
      </form>
    </div>
  </div>
</template>

<style scoped>
.auth-page {
  position: relative;
  min-height: 100vh;
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 32px;
}
.floating-bg { position: absolute; inset: 0; pointer-events: none; overflow: hidden; z-index: 0; }
.floating-bg .w {
  position: absolute;
  font-family: var(--font-serif); font-style: italic;
  color: color-mix(in srgb, var(--brand) 12%, transparent);
  font-weight: 700; user-select: none;
}
.floating-bg .w1 { top: 8%; left: 5%; transform: rotate(-8deg); font-size: 64px; }
.floating-bg .w2 { top: 62%; left: 48%; font-size: 82px; }
.floating-bg .w3 { top: 26%; right: 4%; font-size: 54px; transform: rotate(6deg); color: color-mix(in srgb, var(--accent) 16%, transparent); }
.floating-bg .w4 { bottom: 8%; left: 10%; font-size: 48px; color: color-mix(in srgb, var(--accent) 14%, transparent); transform: rotate(-4deg); }
.auth-card { position: relative; z-index: 2; width: 100%; max-width: 420px; padding: 36px 36px 30px; }
.brand-row { display: flex; align-items: center; gap: 10px; margin-bottom: 4px; }
.brand-dot {
  width: 22px; height: 28px; border-radius: 3px;
  background: linear-gradient(180deg, var(--brand) 0%, var(--accent) 100%);
  box-shadow: 0 2px 6px rgba(50, 60, 40, 0.25);
  position: relative; flex-shrink: 0;
}
.brand-dot::after {
  content: ""; position: absolute; left: 4px; right: 4px; top: 5px; height: 1px;
  background: rgba(255, 255, 255, 0.45);
  box-shadow: 0 4px 0 rgba(255, 255, 255, 0.30), 0 8px 0 rgba(255, 255, 255, 0.20);
}
.brand-name { font-family: var(--font-serif); font-size: 22px; font-weight: 700; }
.brand-tagline { font-size: 12px; color: var(--text-secondary); margin: 4px 0 22px; }
.form-h { font-family: var(--font-serif); font-size: 24px; font-weight: 700; margin: 0 0 8px; }
.intro { margin: 0 0 16px; font-size: 12px; color: var(--text-secondary); line-height: 1.55; }
.muted { color: var(--text-secondary); }
.small { font-size: 12px; }
.field { margin-bottom: 12px; }
.field label { display: block; font-size: 11px; font-weight: 600; color: var(--text-secondary); margin-bottom: 4px; letter-spacing: 0.04em; text-transform: uppercase; }
.auth-btn { width: 100%; margin-top: 8px; }
.error { color: var(--danger); font-size: 12.5px; padding: 8px 12px; border-radius: 8px; background: color-mix(in srgb, var(--danger) 10%, transparent); margin: 4px 0 8px; }
</style>
