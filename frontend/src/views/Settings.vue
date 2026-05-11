<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import {
  api,
  type ProviderPreset,
  type ProviderType,
  type SettingsIn,
  type SettingsOut,
} from "../api";

const presets = ref<ProviderPreset[]>([]);
const original = ref<SettingsOut | null>(null);

const form = ref<{
  provider_type: ProviderType;
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

const showKey = ref(false);
const loading = ref(true);
const saving = ref(false);
const testing = ref(false);
const fetchingModels = ref(false);
const message = ref<{ kind: "ok" | "err"; text: string } | null>(null);
const models = ref<string[]>([]);

const activePreset = computed(() =>
  presets.value.find((p) => p.id === form.value.provider_type)
);

async function load() {
  loading.value = true;
  try {
    const [s, p] = await Promise.all([api.getSettings(), api.listPresets()]);
    original.value = s;
    presets.value = p.presets;
    form.value = {
      provider_type: s.provider_type,
      base_url: s.base_url,
      api_key: "", // never preload; user pastes a new one to change
      model: s.model,
      auth_token: "",
    };
  } catch (e: any) {
    message.value = { kind: "err", text: e.message || "加载失败" };
  } finally {
    loading.value = false;
  }
}

function applyPresetExample(example: { base_url: string; model: string }) {
  form.value.base_url = example.base_url;
  form.value.model = example.model;
}

function buildPayload(): SettingsIn {
  return {
    provider_type: form.value.provider_type,
    base_url: form.value.base_url,
    api_key: form.value.api_key, // "" means keep existing on backend
    model: form.value.model,
    auth_token: form.value.auth_token,
  };
}

async function save() {
  saving.value = true;
  message.value = null;
  try {
    const updated = await api.saveSettings(buildPayload());
    original.value = updated;
    form.value.api_key = ""; // cleared after save
    form.value.auth_token = "";
    message.value = { kind: "ok", text: "已保存" };
  } catch (e: any) {
    message.value = { kind: "err", text: e.message || "保存失败" };
  } finally {
    saving.value = false;
  }
}

async function test() {
  testing.value = true;
  message.value = null;
  try {
    const r = await api.testSettings(buildPayload());
    if (r.ok) {
      message.value = { kind: "ok", text: `连接成功：${r.echo || "ok"}` };
    } else {
      message.value = { kind: "err", text: `连接失败：${r.error}` };
    }
  } catch (e: any) {
    message.value = { kind: "err", text: e.message || "测试失败" };
  } finally {
    testing.value = false;
  }
}

async function fetchModels() {
  fetchingModels.value = true;
  message.value = null;
  try {
    const { models: list } = await api.listModels(buildPayload());
    models.value = list;
    if (list.length === 0) {
      message.value = { kind: "err", text: "未返回模型列表（接口可能不支持）" };
    } else {
      message.value = { kind: "ok", text: `拉取到 ${list.length} 个模型` };
    }
  } catch (e: any) {
    message.value = { kind: "err", text: e.message || "获取失败" };
  } finally {
    fetchingModels.value = false;
  }
}

// When user switches provider, auto-fill base_url and model from first preset example
// — but only if those fields are currently empty (don't clobber user edits).
watch(
  () => form.value.provider_type,
  (newType, oldType) => {
    if (oldType === undefined) return;
    const preset = presets.value.find((p) => p.id === newType);
    if (preset && preset.examples.length > 0) {
      if (!form.value.base_url) form.value.base_url = preset.examples[0].base_url;
      if (!form.value.model) form.value.model = preset.examples[0].model;
    }
    models.value = []; // clear stale list when switching provider
  }
);

onMounted(load);
</script>

<template>
  <section class="settings">
    <h1>设置</h1>
    <p class="muted subtitle">配置 AI 服务，全部数据存在后端 SQLite，刷新和换设备都不会丢。</p>

    <div v-if="loading" class="glass placeholder">
      <p>加载中…</p>
    </div>

    <template v-else>
      <!-- 1. Provider -->
      <div class="card glass">
        <div class="card-head">
          <h2>① 协议类型</h2>
          <span v-if="original?.configured" class="badge ok">已配置</span>
          <span v-else class="badge warn">未配置</span>
        </div>

        <div class="providers">
          <label
            v-for="p in presets"
            :key="p.id"
            class="provider"
            :class="{ active: form.provider_type === p.id }"
          >
            <input
              type="radio"
              :value="p.id"
              v-model="form.provider_type"
              class="visually-hidden"
            />
            <div class="provider-label">{{ p.label }}</div>
            <div class="provider-desc tertiary">{{ p.description }}</div>
          </label>
        </div>

        <div v-if="activePreset && activePreset.examples.length > 1" class="quick-fills">
          <span class="tertiary small">快速填入：</span>
          <button
            v-for="ex in activePreset.examples"
            :key="ex.base_url"
            class="chip"
            type="button"
            @click="applyPresetExample(ex)"
          >
            {{ ex.name }}
          </button>
        </div>
      </div>

      <!-- 2. Connection details -->
      <div class="card glass">
        <div class="card-head">
          <h2>② 连接信息</h2>
        </div>

        <div class="field">
          <label>Base URL</label>
          <input
            v-model="form.base_url"
            class="input"
            type="text"
            placeholder="https://api.deepseek.com/v1"
          />
          <div class="tertiary small">
            可填官方地址、第三方代理或本地服务（如 Ollama 的 http://127.0.0.1:11434/v1）
          </div>
        </div>

        <div class="field">
          <label>API Key</label>
          <div class="key-row">
            <input
              v-model="form.api_key"
              class="input"
              :type="showKey ? 'text' : 'password'"
              :placeholder="
                original?.api_key_set
                  ? `已保存（${original.api_key_preview}），留空表示不修改`
                  : '粘贴你的 API Key'
              "
              autocomplete="off"
            />
            <button class="eye" type="button" @click="showKey = !showKey" :title="showKey ? '隐藏' : '显示'">
              {{ showKey ? "🙈" : "👁" }}
            </button>
          </div>
        </div>

        <div class="field">
          <label>Model</label>
          <div class="model-row">
            <input
              v-model="form.model"
              class="input"
              type="text"
              placeholder="deepseek-chat"
              list="models-list"
            />
            <datalist id="models-list">
              <option v-for="m in models" :key="m" :value="m" />
            </datalist>
            <button
              class="btn"
              type="button"
              :disabled="fetchingModels"
              @click="fetchModels"
            >
              {{ fetchingModels ? "拉取中…" : "🔄 获取模型列表" }}
            </button>
          </div>
          <div v-if="models.length > 0" class="model-pills">
            <button
              v-for="m in models"
              :key="m"
              type="button"
              class="chip"
              :class="{ active: form.model === m }"
              @click="form.model = m"
            >
              {{ m }}
            </button>
          </div>
        </div>
      </div>

      <!-- 3. Auth token (optional) -->
      <div class="card glass">
        <div class="card-head">
          <h2>③ 接口访问令牌（可选）</h2>
        </div>
        <p class="muted">
          如果你的 VPS 公网暴露在 0.0.0.0，建议设一个随机串保护接口。设了之后浏览器会自动把它带在请求里（存浏览器本地）。
          <strong v-if="original?.auth_token_set">当前：已设置</strong>
          <strong v-else>当前：未设置（接口开放访问）</strong>
        </p>
        <div class="field">
          <label>新令牌（留空 = 不修改；填 `none` = 清除）</label>
          <input
            v-model="form.auth_token"
            class="input"
            type="text"
            placeholder="留空表示不修改"
          />
        </div>
      </div>

      <!-- Message -->
      <Transition name="fade">
        <div
          v-if="message"
          class="msg glass-dim"
          :class="message.kind"
        >
          {{ message.text }}
        </div>
      </Transition>

      <!-- Actions -->
      <div class="actions">
        <button class="btn" :disabled="testing" @click="test">
          {{ testing ? "测试中…" : "🔌 测试连接" }}
        </button>
        <button class="btn btn-primary" :disabled="saving" @click="save">
          {{ saving ? "保存中…" : "💾 保存设置" }}
        </button>
      </div>
    </template>
  </section>
</template>

<style scoped>
.settings {
  display: flex;
  flex-direction: column;
  gap: 20px;
  max-width: 760px;
  margin: 0 auto;
}

h1 {
  font-size: 32px;
  font-weight: 700;
  letter-spacing: -0.02em;
  margin: 0;
}

.subtitle {
  margin: -8px 0 0;
  font-size: 15px;
}

.placeholder {
  padding: 48px;
  text-align: center;
}

.card {
  padding: 24px 26px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.card-head h2 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  letter-spacing: -0.01em;
}

.badge {
  font-size: 12px;
  padding: 3px 10px;
  border-radius: 999px;
  font-weight: 500;
}
.badge.ok {
  background: rgba(52, 199, 89, 0.18);
  color: #186a2a;
}
.badge.warn {
  background: rgba(255, 149, 0, 0.18);
  color: #b86700;
}

/* Provider radio cards */
.providers {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 10px;
}

.provider {
  cursor: pointer;
  padding: 14px 16px;
  border-radius: var(--radius-md);
  border: 1.5px solid rgba(0, 0, 0, 0.06);
  background: rgba(255, 255, 255, 0.35);
  transition: border-color 200ms ease, background 200ms ease, transform 120ms ease;
}

.provider:hover {
  background: rgba(255, 255, 255, 0.55);
}

.provider.active {
  border-color: var(--accent);
  background: var(--accent-soft);
}

.provider-label {
  font-weight: 600;
  font-size: 15px;
}

.provider-desc {
  font-size: 12px;
  margin-top: 3px;
}

.visually-hidden {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip-path: inset(50%);
}

.quick-fills {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

/* Fields */
.field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.field > label {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-secondary);
}

.small {
  font-size: 12px;
}

.key-row {
  position: relative;
  display: flex;
  align-items: center;
}
.key-row .input {
  padding-right: 44px;
}
.key-row .eye {
  position: absolute;
  right: 6px;
  background: transparent;
  border: none;
  width: 36px;
  height: 36px;
  border-radius: 10px;
  cursor: pointer;
  font-size: 16px;
}
.key-row .eye:hover {
  background: rgba(0, 0, 0, 0.05);
}

.model-row {
  display: flex;
  gap: 10px;
}
.model-row .input {
  flex: 1;
}
.model-row .btn {
  white-space: nowrap;
}

.model-pills {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 4px;
  max-height: 160px;
  overflow-y: auto;
}

.chip {
  appearance: none;
  border: 1px solid rgba(0, 0, 0, 0.08);
  background: rgba(255, 255, 255, 0.5);
  padding: 5px 11px;
  border-radius: 999px;
  cursor: pointer;
  font: inherit;
  font-size: 12px;
  font-family: ui-monospace, "SF Mono", Menlo, monospace;
  color: var(--text-secondary);
  transition: background 200ms ease, color 200ms ease, border-color 200ms ease;
}

.chip:hover {
  background: rgba(255, 255, 255, 0.85);
  color: var(--text-primary);
}

.chip.active {
  background: var(--accent);
  color: white;
  border-color: var(--accent);
}

.msg {
  padding: 12px 18px;
  border-radius: var(--radius-md);
  font-size: 14px;
}
.msg.ok {
  background: rgba(52, 199, 89, 0.18);
  color: #186a2a;
}
.msg.err {
  background: rgba(255, 59, 48, 0.16);
  color: #b8170c;
}

.actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 8px;
}

@media (max-width: 640px) {
  .model-row {
    flex-direction: column;
  }
}
</style>
