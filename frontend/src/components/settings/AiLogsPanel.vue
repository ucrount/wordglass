<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { api, type AiCallRecord } from "../../api";

const emit = defineEmits<{ (e: "count", n: number): void }>();

const logs = ref<AiCallRecord[]>([]);
const loading = ref(false);
const filter = ref<"" | "chat" | "stream">("");
const expanded = ref<number | null>(null);
const error = ref("");

async function reload() {
  loading.value = true;
  error.value = "";
  try {
    const { items } = await api.listAiLogs(filter.value || undefined);
    logs.value = items;
    emit("count", items.length);
  } catch (e: any) {
    error.value = e.message || "加载失败";
  } finally {
    loading.value = false;
  }
}

async function doClear() {
  if (!confirm("清空所有 AI 调用记录？")) return;
  try {
    await api.clearAiLogs();
    logs.value = [];
    expanded.value = null;
    emit("count", 0);
  } catch (e: any) {
    error.value = e.message || "清空失败";
  }
}

function fmtTime(ts: number): string {
  const d = new Date(ts * 1000);
  return d.toLocaleTimeString("zh-CN", { hour12: false });
}

function summary(rec: AiCallRecord): string {
  const u = rec.user || "";
  return `${u.slice(0, 60)}${u.length > 60 ? "…" : ""}`;
}

function toggle(id: number) {
  expanded.value = expanded.value === id ? null : id;
}

const visibleLogs = computed(() => logs.value);

onMounted(reload);
</script>

<template>
  <div>
    <header class="panel-head">
      <h2>AI 调用记录</h2>
      <span class="meta tertiary small">最近 50 次 · 内存保留 · 重启后清空</span>
    </header>

    <div class="filter-bar">
      <button class="chip" :class="{ active: filter === '' }" @click="filter = ''; reload()">
        全部 ({{ logs.length }})
      </button>
      <button class="chip" :class="{ active: filter === 'stream' }" @click="filter = 'stream'; reload()">
        stream
      </button>
      <button class="chip" :class="{ active: filter === 'chat' }" @click="filter = 'chat'; reload()">
        chat
      </button>
      <button class="chip" style="margin-left: auto" @click="reload" :disabled="loading">
        {{ loading ? "⟳" : "⟳ 刷新" }}
      </button>
      <button class="chip danger" @click="doClear">🗑 清空</button>
    </div>

    <div v-if="error" class="error">{{ error }}</div>

    <div v-if="visibleLogs.length === 0 && !loading" class="empty tertiary small">
      暂无记录。去 Reader 翻译一段或点击单词后回来看。
    </div>

    <div v-else class="log-list">
      <div
        v-for="rec in visibleLogs"
        :key="rec.id"
        class="log-item"
        :class="{ open: expanded === rec.id, err: rec.status === 'error' }"
        @click="toggle(rec.id)"
      >
        <div class="row-head">
          <span class="time">{{ fmtTime(rec.ts) }}</span>
          <span class="kind" :class="rec.kind">{{ rec.kind }}</span>
          <span class="summary">{{ summary(rec) }}</span>
          <span class="ms">{{ rec.ms.toFixed(0) }}ms</span>
          <span class="status" :class="rec.status">
            {{ rec.status === "ok" ? "✓ " + (rec.http_status || 200) : "✗ " + (rec.http_status || "ERR") }}
          </span>
        </div>

        <div v-if="expanded === rec.id" class="row-detail">
          <div class="kv"><b>model:</b> <code>{{ rec.model }}</code></div>
          <div class="kv"><b>base_url:</b> <code>{{ rec.base_url }}</code></div>
          <div v-if="rec.kind === 'stream' && rec.first_chunk_ms != null" class="kv">
            <b>first_chunk_ms:</b> <code>{{ rec.first_chunk_ms }}</code> · <b>chunks:</b> <code>{{ rec.chunks }}</code> · <b>total_ms:</b> <code>{{ rec.ms }}</code>
          </div>
          <div v-if="rec.error" class="kv err"><b>error:</b> <span>{{ rec.error }}</span></div>
          <details>
            <summary>system prompt ({{ rec.system.length }} chars)</summary>
            <pre>{{ rec.system }}</pre>
          </details>
          <details open>
            <summary>user input ({{ rec.user.length }} chars)</summary>
            <pre>{{ rec.user }}</pre>
          </details>
          <details open>
            <summary>response ({{ rec.response.length }} chars)</summary>
            <pre>{{ rec.response || "(empty)" }}</pre>
          </details>
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
.meta { font-size: 11px; }

.filter-bar {
  display: flex;
  gap: 6px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}

.chip {
  appearance: none;
  border: 1px solid var(--hairline);
  background: var(--glass-bg-dim);
  padding: 3px 11px;
  border-radius: 999px;
  cursor: pointer;
  font: inherit;
  font-size: 11.5px;
  color: var(--text-secondary);
}
.chip:hover { color: var(--text-primary); }
.chip.active {
  background: var(--brand-soft);
  color: var(--brand);
  border-color: color-mix(in srgb, var(--brand) 32%, transparent);
  font-weight: 600;
}
.chip.danger:hover {
  background: color-mix(in srgb, var(--danger) 10%, transparent);
  color: var(--danger);
}

.empty {
  padding: 32px 12px;
  text-align: center;
}

.error {
  color: var(--danger);
  font-size: 12px;
  padding: 8px 12px;
  margin-bottom: 8px;
}

.log-list {
  background: var(--glass-bg-dim);
  border-radius: var(--radius-md);
  border: 1px solid var(--hairline);
  overflow: hidden;
}

.log-item {
  padding: 8px 12px;
  border-bottom: 1px solid var(--hairline);
  cursor: pointer;
  transition: background 100ms;
}
.log-item:last-child { border-bottom: none; }
.log-item:hover { background: var(--glass-bg); }
.log-item.open { background: var(--glass-bg); }

.row-head {
  display: grid;
  grid-template-columns: 75px 60px 1fr 70px 70px;
  gap: 10px;
  align-items: center;
  font-size: 11.5px;
}

.time {
  color: var(--text-tertiary);
  font-family: var(--font-mono);
  font-size: 10.5px;
}

.kind {
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 700;
  padding: 1px 7px;
  border-radius: 4px;
  text-align: center;
  background: var(--brand-soft);
  color: var(--brand);
}
.kind.chat { background: color-mix(in srgb, var(--accent) 18%, transparent); color: var(--accent); }

.summary {
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  font-size: 12px;
}

.ms {
  text-align: right;
  font-family: var(--font-mono);
  font-size: 10.5px;
  color: var(--text-secondary);
}

.status {
  text-align: right;
  font-size: 11px;
  font-weight: 600;
  color: var(--success);
  font-family: var(--font-mono);
}
.status.error { color: var(--danger); }

.row-detail {
  margin-top: 10px;
  padding: 10px 12px;
  background: var(--glass-bg-strong);
  border-radius: 8px;
  font-size: 12px;
  border: 1px solid var(--hairline);
}
.kv { margin-bottom: 4px; font-size: 11.5px; }
.kv.err { color: var(--danger); }
.kv b { font-weight: 600; color: var(--text-secondary); margin-right: 4px; }
.kv code {
  font-family: var(--font-mono);
  font-size: 11px;
  background: var(--glass-bg-dim);
  padding: 1px 6px;
  border-radius: 4px;
}

details {
  margin-top: 6px;
  font-size: 11.5px;
}
details summary {
  cursor: pointer;
  color: var(--brand);
  font-weight: 600;
  padding: 3px 0;
}
details pre {
  margin: 4px 0;
  padding: 8px 10px;
  background: #1d2017;
  color: #cbd6b8;
  border-radius: 6px;
  font-family: var(--font-mono);
  font-size: 11px;
  white-space: pre-wrap;
  max-height: 200px;
  overflow-y: auto;
  word-break: break-word;
}
</style>
