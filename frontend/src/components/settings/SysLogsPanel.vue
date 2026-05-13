<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from "vue";
import { api, type SystemLogRecord } from "../../api";

const emit = defineEmits<{ (e: "count", n: number): void }>();

const logs = ref<SystemLogRecord[]>([]);
const filter = ref<"" | "translate" | "usage" | "error">("");
const error = ref("");

let abort: AbortController | null = null;
const containerRef = ref<HTMLElement | null>(null);
let autoScroll = true;

function fmtTime(ts: number): string {
  const d = new Date(ts * 1000);
  return d.toLocaleTimeString("zh-CN", { hour12: false }) + "." + String(d.getMilliseconds()).padStart(3, "0");
}

function fieldsOf(rec: SystemLogRecord): { k: string; v: unknown }[] {
  return Object.entries(rec)
    .filter(([k]) => k !== "id" && k !== "ts" && k !== "event")
    .map(([k, v]) => ({ k, v }));
}

function matchesFilter(rec: SystemLogRecord): boolean {
  if (!filter.value) return true;
  if (filter.value === "error") {
    return rec.event.includes("error") || rec.event.includes(".err");
  }
  return rec.event.startsWith(filter.value);
}

const visible = computed(() => logs.value.filter(matchesFilter));

function onScroll() {
  if (!containerRef.value) return;
  const el = containerRef.value;
  autoScroll = el.scrollHeight - el.scrollTop - el.clientHeight < 40;
}

function scrollToBottom() {
  if (!autoScroll) return;
  nextTick(() => {
    if (containerRef.value) {
      containerRef.value.scrollTop = containerRef.value.scrollHeight;
    }
  });
}

function connect() {
  if (abort) abort.abort();
  abort = new AbortController();
  logs.value = [];
  emit("count", 0);
  void api.streamSystemLogs(
    (rec) => {
      logs.value.push(rec);
      if (logs.value.length > 500) logs.value.shift();
      emit("count", logs.value.length);
      scrollToBottom();
    },
    (msg) => { error.value = msg; },
    abort.signal,
  );
}

async function doClear() {
  if (!confirm("清空系统日志缓冲？（连接保持）")) return;
  try {
    await api.clearSystemLogs();
    logs.value = [];
    emit("count", 0);
  } catch (e: any) {
    error.value = e.message || "清空失败";
  }
}

function reconnect() {
  error.value = "";
  connect();
}

onMounted(() => {
  connect();
});

onBeforeUnmount(() => {
  if (abort) abort.abort();
});
</script>

<template>
  <div>
    <header class="panel-head">
      <h2>系统日志</h2>
      <span class="meta tertiary small">⏵ 实时流式 · 最近 200 条</span>
    </header>

    <div class="filter-bar">
      <button class="chip" :class="{ active: filter === '' }" @click="filter = ''">
        全部
      </button>
      <button class="chip" :class="{ active: filter === 'translate' }" @click="filter = 'translate'">
        translate
      </button>
      <button class="chip" :class="{ active: filter === 'usage' }" @click="filter = 'usage'">
        usage
      </button>
      <button class="chip danger-tab" :class="{ active: filter === 'error' }" @click="filter = 'error'">
        ⚠ error
      </button>
      <button class="chip" style="margin-left: auto" @click="reconnect">⟳ 重连</button>
      <button class="chip danger" @click="doClear">🗑 清空</button>
    </div>

    <div v-if="error" class="error">⚠ {{ error }}</div>

    <div
      ref="containerRef"
      class="log-stream"
      @scroll="onScroll"
    >
      <div v-if="visible.length === 0" class="empty tertiary">
        暂无匹配日志。回到 Reader 页面操作，这里会实时滚出 translate.* / usage.* 事件。
      </div>
      <div
        v-for="rec in visible"
        :key="rec.id"
        class="log-line"
      >
        <span class="time">{{ fmtTime(rec.ts) }}</span>
        <span class="event">{{ rec.event }}</span>
        <span
          v-for="{ k, v } in fieldsOf(rec)"
          :key="k"
          class="kv"
        ><span class="k">{{ k }}=</span><span class="v">{{ typeof v === 'string' ? `"${v}"` : v }}</span></span>
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
.chip.danger-tab.active {
  background: color-mix(in srgb, var(--danger) 14%, transparent);
  color: var(--danger);
  border-color: color-mix(in srgb, var(--danger) 32%, transparent);
}
.chip.danger:hover {
  background: color-mix(in srgb, var(--danger) 10%, transparent);
  color: var(--danger);
}

.error {
  color: var(--danger);
  font-size: 12px;
  padding: 8px 12px;
  margin-bottom: 8px;
}

.log-stream {
  background: #1d2017;
  color: #cbd6b8;
  border-radius: 10px;
  padding: 10px 12px;
  font-family: var(--font-mono);
  font-size: 11.5px;
  line-height: 1.6;
  height: 380px;
  overflow-y: auto;
}

.empty {
  padding: 32px 12px;
  text-align: center;
  font-size: 12px;
  color: #7a8470;
}

.log-line {
  padding: 1px 0;
  white-space: pre;
  word-break: break-all;
}

.time { color: #7a8470; margin-right: 8px; }
.event {
  color: #d8b483;
  font-weight: 600;
  margin-right: 6px;
}
.kv { margin-right: 8px; }
.kv .k { color: #8aaa6e; }
.kv .v { color: #cbd6b8; }
</style>
