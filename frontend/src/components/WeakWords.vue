<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { api, type WeakWordItem } from "../api";

defineProps<{ limit?: number }>();

const router = useRouter();
const items = ref<WeakWordItem[]>([]);
const loading = ref(false);
const error = ref("");

async function reload() {
  loading.value = true;
  error.value = "";
  try {
    const { items: list } = await api.weakWords(5);
    items.value = list;
  } catch (e: any) {
    error.value = e.message || "加载失败";
  } finally {
    loading.value = false;
  }
}

function practiceOne(id: number) {
  router.push({ path: "/practice", query: { word_ids: String(id) } });
}

function practiceAll() {
  if (items.value.length === 0) return;
  const ids = items.value.map((w) => w.id).join(",");
  router.push({ path: "/practice", query: { word_ids: ids } });
}

const masteryPips = (m: number) => [0, 1, 2, 3, 4].map((i) => i < m);

defineExpose({ reload });
onMounted(reload);
</script>

<template>
  <section class="weak-widget glass">
    <div class="widget-head">
      <h3>最薄弱的词</h3>
      <span class="tertiary small">复习过但反复出错</span>
    </div>

    <div v-if="loading && items.length === 0" class="empty tertiary small">
      加载中…
    </div>

    <div v-else-if="error" class="empty error small">{{ error }}</div>

    <div v-else-if="items.length === 0" class="empty tertiary small">
      练习几次后，这里会列出你最常出错的词。
    </div>

    <div v-else class="weak-list">
      <div
        v-for="w in items"
        :key="w.id"
        class="weak-item"
        @click="practiceOne(w.id)"
        :title="`练这一个：${w.text}`"
      >
        <div class="weak-text">
          <div class="weak-word">{{ w.text }}</div>
          <div class="weak-tr tertiary">{{ w.translation || '（无翻译）' }}</div>
        </div>
        <div class="weak-pips" :title="`掌握度 ${w.mastery}/5`">
          <span
            v-for="(on, i) in masteryPips(w.mastery)"
            :key="i"
            class="pip"
            :class="{ on }"
          />
        </div>
        <span class="weak-stat">{{ w.wrong_count }} 错</span>
      </div>
      <button class="practice-all" @click="practiceAll">
        → 集中练这 {{ items.length }} 个
      </button>
    </div>
  </section>
</template>

<style scoped>
.weak-widget {
  padding: 14px 18px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.widget-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
}
.widget-head h3 {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}
.small { font-size: 11px; }
.tertiary { color: var(--text-tertiary); }
.error { color: var(--danger); }

.empty {
  padding: 12px 4px;
  text-align: center;
  line-height: 1.5;
}

.weak-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.weak-item {
  display: grid;
  grid-template-columns: 1fr auto auto;
  align-items: center;
  gap: 10px;
  padding: 7px 10px;
  border-radius: 8px;
  background: var(--glass-bg-dim);
  border: 1px solid var(--hairline);
  cursor: pointer;
  transition: background 150ms ease, border-color 150ms ease;
}
.weak-item:hover {
  background: var(--brand-soft);
  border-color: color-mix(in srgb, var(--brand) 32%, transparent);
}

.weak-text {
  min-width: 0;
}
.weak-word {
  font-family: var(--font-serif);
  font-weight: 700;
  font-size: 13.5px;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.weak-tr {
  font-size: 11px;
  font-style: italic;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-top: 1px;
}

.weak-pips {
  display: flex;
  gap: 2px;
}
.weak-pips .pip {
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background: var(--hairline-strong);
}
.weak-pips .pip.on {
  background: var(--brand);
}

.weak-stat {
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 600;
  color: var(--danger);
  white-space: nowrap;
}

.practice-all {
  appearance: none;
  border: 1px dashed var(--hairline-strong);
  background: transparent;
  color: var(--brand);
  font: inherit;
  font-size: 11.5px;
  font-weight: 600;
  padding: 7px 10px;
  border-radius: 8px;
  cursor: pointer;
  margin-top: 2px;
  transition: background 150ms ease, border-color 150ms ease;
}
.practice-all:hover {
  background: var(--brand-soft);
  border-color: var(--brand);
  border-style: solid;
}
</style>
