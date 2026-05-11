<script setup lang="ts">
import { onMounted, onUnmounted, ref } from "vue";
import { RouterLink, useRoute } from "vue-router";
import { ApiError, api, getToken, setToken } from "../api";

// One-time onboarding banner: if the backend reports AI is not configured,
// nudge the user to /settings (unless they're already there).
const aiConfigured = ref<boolean | null>(null);
const route = useRoute();

// AUTH_TOKEN dialog state: shown when any API call returns 401.
const tokenDialogOpen = ref(false);
const pendingToken = ref("");

async function checkConfig() {
  try {
    const s = await api.getSettings();
    aiConfigured.value = s.configured;
  } catch {
    aiConfigured.value = false;
  }
}

function on401() {
  if (route.name === "settings") return;
  pendingToken.value = "";
  tokenDialogOpen.value = true;
}

function saveToken() {
  setToken(pendingToken.value.trim());
  tokenDialogOpen.value = false;
  // reload current page so failed requests retry with the new token
  window.location.reload();
}

function dismiss() {
  tokenDialogOpen.value = false;
}

// Wrap fetch errors globally — we listen on a window event the API client dispatches
function handleErrorEvent(e: Event) {
  const ce = e as CustomEvent<{ status: number }>;
  if (ce.detail?.status === 401) on401();
}

onMounted(() => {
  checkConfig();
  window.addEventListener("wordglass:api-error", handleErrorEvent);
});
onUnmounted(() => {
  window.removeEventListener("wordglass:api-error", handleErrorEvent);
});
</script>

<template>
  <!-- Onboarding banner -->
  <Transition name="fade">
    <div
      v-if="aiConfigured === false && route.name !== 'settings'"
      class="banner glass-strong"
    >
      <div>
        <strong>👋 还差一步</strong> · AI 服务还没配置，去
        <RouterLink to="/settings" class="link">设置</RouterLink>
        填一下，就能开始添加单词了。
      </div>
    </div>
  </Transition>

  <!-- Token dialog -->
  <Transition name="fade">
    <div v-if="tokenDialogOpen" class="modal-mask" @click.self="dismiss">
      <div class="modal glass-strong">
        <h2>🔐 需要访问令牌</h2>
        <p class="muted">
          你的后端开启了访问令牌保护，先填一下才能用。可以在 VPS 上执行：
        </p>
        <pre class="code">sudo cat /opt/wordglass/backend/.env | grep AUTH_TOKEN</pre>
        <p class="muted">把等号后面那串粘到这里：</p>
        <input
          v-model="pendingToken"
          class="input"
          type="text"
          placeholder="粘贴 AUTH_TOKEN"
          autofocus
          @keyup.enter="saveToken"
        />
        <div class="actions">
          <button class="btn" @click="dismiss">取消</button>
          <button class="btn btn-primary" :disabled="!pendingToken.trim()" @click="saveToken">
            保存并重试
          </button>
        </div>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
.banner {
  position: sticky;
  top: 80px;
  z-index: 40;
  padding: 12px 18px;
  border-radius: var(--radius-md);
  margin: 8px 0 20px;
  font-size: 14px;
}

.banner .link {
  color: var(--accent);
  font-weight: 600;
  text-decoration: none;
}
.banner .link:hover {
  text-decoration: underline;
}

.modal-mask {
  position: fixed;
  inset: 0;
  z-index: 100;
  background: rgba(0, 0, 0, 0.25);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px;
}

.modal {
  width: 100%;
  max-width: 480px;
  padding: 28px;
  border-radius: var(--radius-lg);
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.modal h2 {
  margin: 0;
  font-size: 22px;
  font-weight: 600;
  letter-spacing: -0.01em;
}

.code {
  background: rgba(0, 0, 0, 0.05);
  border-radius: 10px;
  padding: 10px 14px;
  font-family: ui-monospace, monospace;
  font-size: 13px;
  overflow-x: auto;
  margin: 0;
}

.modal .actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 8px;
}
</style>
