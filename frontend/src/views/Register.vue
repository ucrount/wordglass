<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRouter, RouterLink } from "vue-router";
import { api } from "../api";
import { useAuth } from "../composables/auth";

const router = useRouter();
const { setSession } = useAuth();

const username = ref("");
const password = ref("");
const inviteCode = ref("");
const loading = ref(false);
const error = ref("");
const registrationEnabled = ref(true);

async function submit() {
  if (!username.value || !password.value || !inviteCode.value) return;
  loading.value = true;
  error.value = "";
  try {
    const r = await api.register(username.value, password.value, inviteCode.value);
    setSession(r.token, { id: 0, username: r.username, is_admin: r.is_admin });
    try {
      const me = await api.me();
      setSession(r.token, me);
    } catch { /* keep partial */ }
    router.replace("/");
  } catch (e: any) {
    error.value = e.message || "注册失败";
  } finally {
    loading.value = false;
  }
}

onMounted(async () => {
  try {
    const s = await api.setupStatus();
    if (s.needs_setup) {
      router.replace({ name: "setup" });
      return;
    }
    registrationEnabled.value = s.registration_enabled;
    if (!s.registration_enabled) {
      error.value = "管理员已关闭注册。请联系管理员获取账号。";
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
      <p class="brand-tagline">建一个属于你的英文书。</p>
      <h2 class="form-h">注册</h2>
      <form @submit.prevent="submit">
        <div class="field">
          <label>用户名</label>
          <input v-model="username" class="input" autocomplete="username" autofocus
                 placeholder="3-20 位字母数字下划线" />
        </div>
        <div class="field">
          <label>密码</label>
          <input v-model="password" class="input" type="password" autocomplete="new-password"
                 placeholder="至少 6 位" />
        </div>
        <div class="field">
          <label>邀请码</label>
          <input v-model="inviteCode" class="input" type="text" placeholder="向管理员获取" />
        </div>
        <div v-if="error" class="error">{{ error }}</div>
        <button type="submit" class="btn btn-primary auth-btn"
                :disabled="loading || !registrationEnabled">
          {{ loading ? "注册中…" : "创 建 账 号" }}
        </button>
      </form>
      <p class="switch-mode">
        已有账号？<RouterLink to="/login" class="link">直接登录</RouterLink>
      </p>
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
.auth-card { position: relative; z-index: 2; width: 100%; max-width: 380px; padding: 36px 36px 30px; }
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
.form-h { font-family: var(--font-serif); font-size: 24px; font-weight: 700; margin: 0 0 18px; }
.field { margin-bottom: 12px; }
.field label { display: block; font-size: 11px; font-weight: 600; color: var(--text-secondary); margin-bottom: 4px; letter-spacing: 0.04em; text-transform: uppercase; }
.auth-btn { width: 100%; margin-top: 8px; }
.error { color: var(--danger); font-size: 12.5px; padding: 8px 12px; border-radius: 8px; background: color-mix(in srgb, var(--danger) 10%, transparent); margin: 4px 0 8px; }
.switch-mode { text-align: center; font-size: 12px; color: var(--text-secondary); margin-top: 14px; }
.link { color: var(--brand); text-decoration: none; font-weight: 600; }
.link:hover { text-decoration: underline; }
</style>
