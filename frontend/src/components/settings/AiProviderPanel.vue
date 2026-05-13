<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { api, type ProviderPreset, type SettingsIn, type SettingsOut, type ProviderType } from "../../api";

const props = defineProps<{
  form: {
    provider_type: SettingsIn["provider_type"];
    base_url: string;
    api_key: string;
    model: string;
    auth_token: string;
  };
  original: SettingsOut | null;
  presets: ProviderPreset[];
  message: { kind: "ok" | "err"; text: string } | null;
}>();

const emit = defineEmits<{ (e: "save"): void }>();

const showKey = ref(false);
const fetchingModels = ref(false);
const models = ref<string[]>([]);
const fetchMsg = ref("");

const activePreset = computed(() =>
  props.presets.find((p) => p.id === props.form.provider_type),
);

function applyPresetExample(example: { base_url: string; model: string }) {
  props.form.base_url = example.base_url;
  props.form.model = example.model;
}

async function fetchModels() {
  fetchingModels.value = true;
  fetchMsg.value = "";
  try {
    const { models: list } = await api.listModels({
      provider_type: props.form.provider_type,
      base_url: props.form.base_url,
      api_key: props.form.api_key,
      model: props.form.model,
    } as SettingsIn);
    models.value = list;
    fetchMsg.value = list.length ? `拉到 ${list.length} 个模型` : "未返回模型列表（接口可能不支持）";
  } catch (e: any) {
    fetchMsg.value = e.message || "获取失败";
  } finally {
    fetchingModels.value = false;
  }
}

watch(
  () => props.form.provider_type,
  (newType, oldType) => {
    if (oldType === undefined) return;
    const preset = props.presets.find((p) => p.id === newType);
    if (preset && preset.examples.length > 0) {
      if (!props.form.base_url) props.form.base_url = preset.examples[0].base_url;
      if (!props.form.model) props.form.model = preset.examples[0].model;
    }
    models.value = [];
  },
);

function modelHint() {
  const m = props.form.model.toLowerCase();
  if (m.includes("reasoner") || m.includes("-pro") || m.includes("v4-pro")) {
    return "⚠ 这看着像推理 / pro 模型，首 token 通常 10-50s 很慢。Reader 体验差。建议改成 -chat / -flash 系。";
  }
  return "";
}
</script>

<template>
  <div>
    <header class="panel-head">
      <h2>AI Provider</h2>
      <span class="badge" :class="{ ok: original?.configured, warn: !original?.configured }">
        {{ original?.configured ? "已配置" : "未配置" }}
      </span>
    </header>

    <section class="row">
      <label>协议类型</label>
      <div class="providers">
        <label
          v-for="p in presets"
          :key="p.id"
          class="provider-card"
          :class="{ active: form.provider_type === p.id }"
        >
          <input
            type="radio"
            :value="p.id"
            v-model="(form.provider_type as ProviderType)"
            class="visually-hidden"
          />
          <div class="p-name">{{ p.label }}</div>
          <div class="p-desc tertiary">{{ p.description }}</div>
        </label>
      </div>
      <div v-if="activePreset && activePreset.examples.length > 0" class="quick-fills">
        <span class="tertiary small">⚡ 快速填入：</span>
        <button
          v-for="ex in activePreset.examples"
          :key="ex.base_url"
          class="chip"
          type="button"
          @click="applyPresetExample(ex)"
        >{{ ex.name }}</button>
      </div>
    </section>

    <section class="row">
      <label>Base URL</label>
      <input v-model="form.base_url" class="input" type="text" placeholder="https://api.deepseek.com/v1" />
      <div class="help">
        可填官方地址、第三方代理或本地服务（如 Ollama 的 http://127.0.0.1:11434/v1）
      </div>
    </section>

    <section class="row">
      <label>API Key</label>
      <div class="key-row">
        <input
          v-model="form.api_key"
          class="input"
          :type="showKey ? 'text' : 'password'"
          :placeholder="original?.api_key_set ? `已保存（${original.api_key_preview}），留空表示不修改` : '粘贴你的 API Key'"
          autocomplete="off"
        />
        <button class="eye-btn" type="button" @click="showKey = !showKey" :title="showKey ? '隐藏' : '显示'">
          {{ showKey ? "🙈" : "👁" }}
        </button>
      </div>
    </section>

    <section class="row">
      <label>Model</label>
      <div class="model-row">
        <input
          v-model="form.model"
          class="input"
          type="text"
          placeholder="deepseek-chat"
          list="m-list"
        />
        <datalist id="m-list">
          <option v-for="m in models" :key="m" :value="m" />
        </datalist>
        <button class="btn" type="button" :disabled="fetchingModels" @click="fetchModels">
          {{ fetchingModels ? "拉取中…" : "🔄 拉取模型" }}
        </button>
      </div>
      <div v-if="modelHint()" class="hint warn">{{ modelHint() }}</div>
      <div v-if="fetchMsg" class="hint">{{ fetchMsg }}</div>
      <div v-if="models.length" class="model-pills">
        <button
          v-for="m in models"
          :key="m"
          type="button"
          class="chip"
          :class="{ active: form.model === m }"
          @click="form.model = m"
        >{{ m }}</button>
      </div>
    </section>

    <Transition name="fade">
      <div v-if="message" class="msg" :class="message.kind">{{ message.text }}</div>
    </Transition>

    <div class="actions">
      <button class="btn btn-primary" @click="emit('save')">💾 保存设置</button>
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

.row { margin-bottom: 16px; display: flex; flex-direction: column; gap: 6px; }
.row > label {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
}
.help, .hint, .small { font-size: 11.5px; color: var(--text-tertiary); }
.hint.warn { color: var(--warn); }

.providers {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 8px;
}
.provider-card {
  cursor: pointer;
  padding: 12px 14px;
  border-radius: var(--radius-md);
  border: 1.5px solid var(--hairline);
  background: var(--glass-bg-dim);
  transition: border-color 200ms, background 200ms;
}
.provider-card:hover { background: var(--glass-bg); }
.provider-card.active {
  border-color: var(--brand);
  background: var(--brand-soft);
}
.p-name { font-weight: 700; font-size: 14px; }
.p-desc { font-size: 11.5px; margin-top: 2px; line-height: 1.4; }

.quick-fills {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  align-items: center;
  margin-top: 4px;
}

.key-row { position: relative; display: flex; align-items: center; }
.key-row .input { padding-right: 44px; }
.eye-btn {
  position: absolute; right: 6px;
  background: transparent; border: none;
  width: 34px; height: 34px;
  border-radius: 8px; cursor: pointer;
  font-size: 15px;
}
.eye-btn:hover { background: var(--glass-bg-dim); }

.model-row { display: flex; gap: 10px; align-items: center; }
.model-row .input { flex: 1; }
.model-row .btn { white-space: nowrap; }

.model-pills {
  display: flex; flex-wrap: wrap; gap: 6px;
  margin-top: 4px;
  max-height: 160px;
  overflow-y: auto;
}

.chip {
  appearance: none;
  border: 1px solid var(--hairline);
  background: var(--glass-bg-dim);
  padding: 4px 10px;
  border-radius: 999px;
  cursor: pointer;
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--text-secondary);
  transition: background 150ms;
}
.chip:hover { background: var(--glass-bg); color: var(--text-primary); }
.chip.active {
  background: var(--brand);
  color: var(--brand-strong-text);
  border-color: var(--brand);
}

.visually-hidden {
  position: absolute;
  width: 1px; height: 1px;
  overflow: hidden;
  clip-path: inset(50%);
}

.msg {
  padding: 10px 14px;
  border-radius: var(--radius-md);
  font-size: 13px;
  margin-bottom: 12px;
}
.msg.ok { background: color-mix(in srgb, var(--success) 18%, transparent); color: var(--success); }
.msg.err { background: color-mix(in srgb, var(--danger) 16%, transparent); color: var(--danger); }

.actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 12px; }

.fade-enter-active, .fade-leave-active { transition: opacity 200ms; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>
