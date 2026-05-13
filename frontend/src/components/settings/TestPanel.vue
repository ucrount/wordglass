<script setup lang="ts">
import { ref, watch } from "vue";
import { api, type SettingsIn, type SettingsOut, type TestResultV2, type ProviderType, type CurlReq } from "../../api";

const props = defineProps<{
  form: {
    provider_type: SettingsIn["provider_type"];
    base_url: string;
    api_key: string;
    model: string;
    auth_token: string;
  };
  original: SettingsOut | null;
}>();

const testing = ref(false);
const result = ref<TestResultV2 | null>(null);
const showRaw = ref(false);

const curl = ref("");
const curlReveal = ref(false);
let curlTimer: ReturnType<typeof setTimeout> | null = null;

async function generateCurl() {
  try {
    const req: CurlReq = {
      provider_type: (props.form.provider_type || "openai") as ProviderType,
      base_url: props.form.base_url,
      api_key: props.form.api_key,
      model: props.form.model,
      reveal_key: curlReveal.value,
    };
    const r = await api.generateCurl(req);
    curl.value = r.command;
  } catch (e: any) {
    curl.value = `# 生成 curl 失败：${e.message || e}`;
  }
}

function scheduleCurl() {
  if (curlTimer) clearTimeout(curlTimer);
  curlTimer = setTimeout(generateCurl, 250);
}

watch(
  () => [props.form.provider_type, props.form.base_url, props.form.model, props.form.api_key, curlReveal.value],
  scheduleCurl,
  { immediate: true },
);

async function runTest() {
  testing.value = true;
  result.value = null;
  showRaw.value = false;
  try {
    result.value = await api.testSettingsV2({
      provider_type: props.form.provider_type,
      base_url: props.form.base_url,
      api_key: props.form.api_key,
      model: props.form.model,
    } as SettingsIn);
  } catch (e: any) {
    result.value = {
      ok: false,
      category: "unknown",
      detail: e?.message || "测试失败",
      raw: "",
      echo: "",
      ms: 0,
    };
  } finally {
    testing.value = false;
  }
}

const CATEGORY_LABEL: Record<string, string> = {
  ok: "连接正常",
  dns: "DNS 解析失败",
  connect: "连接失败",
  timeout: "超时",
  auth: "鉴权失败",
  not_found: "找不到模型/路径",
  rate_limit: "请求超限 / 余额不足",
  upstream: "上游异常",
  unknown: "未知错误",
};

async function copyCurl() {
  try {
    await navigator.clipboard.writeText(curl.value);
  } catch { /* ignore */ }
}
</script>

<template>
  <div>
    <header class="panel-head">
      <h2>测试 &amp; 诊断</h2>
    </header>

    <p class="muted small intro">
      用当前配置发一次 <code>"ping"</code> 测试 AI 连通性。失败时显示具体错误类型，方便对症。
    </p>

    <div class="actions">
      <button class="btn btn-primary" :disabled="testing" @click="runTest">
        {{ testing ? "测试中…" : "🧪 测试连接" }}
      </button>
    </div>

    <Transition name="fade">
      <div v-if="result" class="test-msg" :class="result.ok ? 'ok' : 'err'">
        <div class="test-title">
          {{ result.ok ? "✓" : "✗" }} {{ CATEGORY_LABEL[result.category] || result.category }}
          <span class="tiny">{{ result.ms.toFixed(0) }}ms</span>
        </div>
        <div class="test-detail">{{ result.detail }}</div>
        <div v-if="result.raw" class="raw-toggle">
          <button class="link-btn" @click="showRaw = !showRaw">
            {{ showRaw ? "▾ 隐藏" : "▸ 展开" }} 原始响应
          </button>
          <pre v-if="showRaw" class="raw">{{ result.raw }}</pre>
        </div>
      </div>
    </Transition>

    <hr class="divider" />

    <h3>💻 等效 curl 命令</h3>
    <p class="muted small">
      用当前配置生成。复制到 VPS 终端独立测试，可以排除浏览器/前端因素。
      <label class="reveal-toggle">
        <input type="checkbox" v-model="curlReveal" />
        显示完整 API key（仅本地，不发送）
      </label>
    </p>

    <div class="curl-block">
      <div class="curl-actions">
        <button class="curl-btn" @click="copyCurl">📋 复制</button>
      </div>
      <pre>{{ curl }}</pre>
    </div>
  </div>
</template>

<style scoped>
.panel-head {
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

.intro { margin-bottom: 12px; }
.actions { margin-bottom: 14px; }

.btn-primary { padding: 7px 18px; font-size: 13px; font-weight: 600; }

code {
  font-family: var(--font-mono);
  font-size: 12px;
  background: var(--glass-bg-dim);
  padding: 1px 6px;
  border-radius: 4px;
}

.test-msg {
  padding: 12px 14px;
  border-radius: var(--radius-md);
  border: 1px solid;
  margin-bottom: 14px;
}
.test-msg.ok {
  background: color-mix(in srgb, var(--success) 12%, transparent);
  color: var(--success);
  border-color: color-mix(in srgb, var(--success) 32%, transparent);
}
.test-msg.err {
  background: color-mix(in srgb, var(--danger) 12%, transparent);
  color: var(--danger);
  border-color: color-mix(in srgb, var(--danger) 32%, transparent);
}
.test-title {
  font-weight: 700;
  font-size: 13.5px;
  display: flex;
  align-items: baseline;
  gap: 8px;
}
.tiny {
  font-family: var(--font-mono);
  font-size: 11px;
  opacity: 0.7;
}
.test-detail {
  font-size: 12.5px;
  color: var(--text-primary);
  margin-top: 4px;
  line-height: 1.55;
  white-space: pre-wrap;
}
.raw-toggle { margin-top: 6px; font-size: 11.5px; }
.raw {
  margin-top: 6px;
  padding: 8px 10px;
  background: #1d2017;
  color: #cbd6b8;
  border-radius: 8px;
  font-size: 11px;
  font-family: var(--font-mono);
  white-space: pre-wrap;
  max-height: 200px;
  overflow-y: auto;
}
.link-btn {
  appearance: none;
  background: transparent;
  border: none;
  color: var(--brand);
  cursor: pointer;
  font: inherit;
  font-size: inherit;
  padding: 0;
}

.divider { border: none; border-top: 1px solid var(--hairline); margin: 18px 0; }

h3 {
  font-size: 13.5px;
  margin: 0 0 4px;
  font-weight: 700;
  color: var(--text-primary);
}

.reveal-toggle {
  margin-left: 8px;
  font-size: 11px;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.curl-block {
  position: relative;
  background: #1d2017;
  color: #cbd6b8;
  border-radius: 10px;
  padding: 14px 16px;
  margin-top: 8px;
  font-family: var(--font-mono);
  font-size: 12px;
  line-height: 1.6;
  overflow-x: auto;
}
.curl-block pre {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-all;
}
.curl-actions {
  position: absolute;
  top: 8px;
  right: 8px;
}
.curl-btn {
  padding: 3px 10px;
  font-size: 11px;
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.10);
  color: #cbd6b8;
  border: none;
  cursor: pointer;
}
.curl-btn:hover { background: rgba(255, 255, 255, 0.18); }

.muted { color: var(--text-secondary); }
.small { font-size: 12px; }

.fade-enter-active, .fade-leave-active { transition: opacity 200ms; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>
