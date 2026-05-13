<script setup lang="ts">
import { onMounted, ref } from "vue";
import { api } from "../../api";

const status = ref<{ ecdict: boolean; tatoeba: boolean }>({ ecdict: false, tatoeba: false });
const loading = ref(false);
const error = ref("");

async function reload() {
  loading.value = true;
  error.value = "";
  try {
    status.value = await api.offlineStatus();
  } catch (e: any) {
    error.value = e.message || "查询失败";
  } finally {
    loading.value = false;
  }
}

onMounted(reload);
</script>

<template>
  <div>
    <header class="panel-head">
      <h2>离线数据</h2>
      <button class="chip" @click="reload" :disabled="loading">⟳ 刷新</button>
    </header>

    <p class="muted small intro">
      离线词典让你不配 AI 也能查词。Tatoeba 让你不配 AI 也能有例句。
    </p>

    <div v-if="error" class="error">{{ error }}</div>

    <div class="grid">
      <div class="dcard">
        <div class="dcard-head">
          <span class="d-name">ECDICT</span>
          <span class="d-status" :class="{ on: status.ecdict, off: !status.ecdict }">
            {{ status.ecdict ? "✓ 已启用" : "✗ 未启用" }}
          </span>
        </div>
        <div class="d-body muted small">
          77 万英文词条 · 音标 / 词性 / 中文释义。本地词典毫秒级返回，加单词不调 AI。
        </div>
        <div class="d-foot tertiary small">
          路径：<code>backend/data/ecdict.db</code>（~135MB）<br>
          重装：<code>sudo bash /opt/wordglass/deploy/install.sh</code>
        </div>
      </div>

      <div class="dcard">
        <div class="dcard-head">
          <span class="d-name">Tatoeba 例句库</span>
          <span class="d-status" :class="{ on: status.tatoeba, off: !status.tatoeba }">
            {{ status.tatoeba ? "✓ 已启用" : "✗ 未启用" }}
          </span>
        </div>
        <div class="d-body muted small">
          英汉对照真实语料。加单词时自动配 5 个由易到难的例句，无 AI 调用。
        </div>
        <div class="d-foot tertiary small">
          路径：<code>backend/data/tatoeba.db</code>（~30-80MB）<br>
          安装：<code>scripts/build_tatoeba.py</code>（10-20 分钟，下载 ~200MB 原始数据）
        </div>
      </div>
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
  margin-bottom: 14px;
}
.panel-head h2 {
  font-family: var(--font-serif);
  font-size: 18px;
  font-weight: 700;
  margin: 0;
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
.intro { margin-bottom: 14px; }
.error { color: var(--danger); font-size: 12px; padding: 8px 0; }

.grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 12px;
}

.dcard {
  background: var(--glass-bg-dim);
  border: 1px solid var(--hairline);
  border-radius: var(--radius-md);
  padding: 14px 16px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.dcard-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
}
.d-name {
  font-family: var(--font-serif);
  font-size: 15px;
  font-weight: 700;
  color: var(--text-primary);
}
.d-status {
  font-size: 11px;
  font-weight: 600;
  padding: 2px 9px;
  border-radius: 999px;
}
.d-status.on {
  background: color-mix(in srgb, var(--success) 18%, transparent);
  color: var(--success);
}
.d-status.off {
  background: color-mix(in srgb, var(--warn) 18%, transparent);
  color: var(--warn);
}
.d-body {
  line-height: 1.55;
}
.d-foot {
  font-size: 11px;
  line-height: 1.55;
  padding-top: 4px;
  border-top: 1px dashed var(--hairline);
}
code {
  font-family: var(--font-mono);
  font-size: 11px;
  background: var(--glass-bg);
  padding: 1px 5px;
  border-radius: 4px;
}
.small { font-size: 12px; }
.muted { color: var(--text-secondary); }
</style>
