<script setup lang="ts">
import { onMounted, ref } from "vue";
import { api } from "../../api";

interface UserRow {
  id: number;
  username: string;
  is_admin: boolean;
  created_at: string;
  last_login_at: string | null;
}

const inviteCode = ref("");
const registrationEnabled = ref(true);
const users = ref<UserRow[]>([]);
const loading = ref(false);
const error = ref("");
const copied = ref(false);

async function reload() {
  loading.value = true;
  error.value = "";
  try {
    const inv = await api.getInvite();
    inviteCode.value = inv.invite_code;
    registrationEnabled.value = inv.registration_enabled;
    const { items } = await api.listUsers();
    users.value = items;
  } catch (e: any) {
    error.value = e.message || "加载失败";
  } finally {
    loading.value = false;
  }
}

async function regenerate() {
  if (!confirm("重新生成邀请码会让旧的失效，确定？")) return;
  try {
    const inv = await api.regenerateInvite();
    inviteCode.value = inv.invite_code;
  } catch (e: any) {
    error.value = e.message || "重新生成失败";
  }
}

async function toggleRegistration() {
  try {
    const inv = await api.setRegistration(!registrationEnabled.value);
    registrationEnabled.value = inv.registration_enabled;
  } catch (e: any) {
    error.value = e.message || "切换失败";
  }
}

async function copyInvite() {
  try {
    await navigator.clipboard.writeText(inviteCode.value);
    copied.value = true;
    setTimeout(() => { copied.value = false; }, 1600);
  } catch { /* ignore */ }
}

function fmtDate(s: string | null) {
  if (!s) return "—";
  try {
    return new Date(s).toLocaleString("zh-CN", { hour12: false });
  } catch { return s; }
}

onMounted(reload);
</script>

<template>
  <div>
    <header class="panel-head">
      <h2>👑 管理员</h2>
      <button class="chip" @click="reload" :disabled="loading">⟳ 刷新</button>
    </header>

    <div v-if="error" class="error">{{ error }}</div>

    <section class="row">
      <label>邀请码</label>
      <div class="invite-box">
        <code class="invite-code">{{ inviteCode || "（未生成）" }}</code>
        <button class="chip" @click="copyInvite">{{ copied ? "✓ 已复制" : "📋 复制" }}</button>
        <button class="chip warn" @click="regenerate">🔁 重新生成</button>
      </div>
      <div class="help">把这串给要注册的朋友。重新生成会让旧码立刻失效。</div>
    </section>

    <section class="row">
      <label>开放注册</label>
      <label class="toggle">
        <input type="checkbox" :checked="registrationEnabled" @change="toggleRegistration" />
        <span>{{ registrationEnabled ? "已开启 · 持邀请码的人可注册" : "已关闭 · 任何人都不能注册" }}</span>
      </label>
    </section>

    <hr class="divider" />

    <h3>用户列表（{{ users.length }} 个）</h3>
    <table class="users">
      <thead>
        <tr><th>用户名</th><th>角色</th><th>注册时间</th><th>最近登录</th></tr>
      </thead>
      <tbody>
        <tr v-for="u in users" :key="u.id">
          <td><strong>{{ u.username }}</strong></td>
          <td>
            <span class="role" :class="{ admin: u.is_admin }">
              {{ u.is_admin ? "👑 admin" : "普通" }}
            </span>
          </td>
          <td>{{ fmtDate(u.created_at) }}</td>
          <td>{{ fmtDate(u.last_login_at) }}</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<style scoped>
.panel-head {
  display: flex; align-items: baseline; justify-content: space-between;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--hairline);
  margin-bottom: 16px;
}
.panel-head h2 {
  font-family: var(--font-serif); font-size: 18px; font-weight: 700; margin: 0;
}

.chip {
  appearance: none;
  border: 1px solid var(--hairline);
  background: var(--glass-bg-dim);
  padding: 3px 11px;
  border-radius: 999px;
  cursor: pointer;
  font-size: 11.5px;
  color: var(--text-secondary);
}
.chip:hover { color: var(--text-primary); }
.chip.warn:hover { background: color-mix(in srgb, var(--warn) 10%, transparent); color: var(--warn); }

.row { display: flex; flex-direction: column; gap: 6px; margin-bottom: 16px; }
.row > label { font-size: 12px; font-weight: 600; color: var(--text-secondary); }
.help { font-size: 11.5px; color: var(--text-tertiary); }

.invite-box {
  display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
  padding: 10px 12px;
  background: var(--glass-bg-dim);
  border: 1px solid var(--hairline);
  border-radius: var(--radius-md);
}
.invite-code {
  font-family: var(--font-mono);
  font-size: 13px;
  color: var(--brand);
  flex: 1;
  word-break: break-all;
}

.toggle {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  font-size: 12.5px;
  color: var(--text-primary);
}

.divider { border: none; border-top: 1px solid var(--hairline); margin: 18px 0; }

h3 { font-size: 13.5px; margin: 0 0 8px; font-weight: 700; }

.users {
  width: 100%;
  border-collapse: collapse;
  font-size: 12.5px;
  background: var(--glass-bg-dim);
  border: 1px solid var(--hairline);
  border-radius: var(--radius-md);
  overflow: hidden;
}
.users th, .users td {
  padding: 8px 12px;
  text-align: left;
  border-bottom: 1px solid var(--hairline);
}
.users th {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--text-secondary);
  background: var(--glass-bg);
}
.users tr:last-child td { border-bottom: none; }

.role { font-size: 11px; padding: 1px 7px; border-radius: 4px; background: var(--glass-bg-dim); color: var(--text-secondary); }
.role.admin {
  background: color-mix(in srgb, var(--brand) 18%, transparent);
  color: var(--brand);
  font-weight: 600;
}

.error { color: var(--danger); font-size: 12px; padding: 8px 0; }
</style>
