<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { api, type CategoriesOut, type WordBrief } from "../api";
import WordCard from "../components/WordCard.vue";
import WordDetail from "../components/WordDetail.vue";

const words = ref<WordBrief[]>([]);
const loading = ref(false);
const error = ref("");

const cats = ref<CategoriesOut>({ counts: {}, order: [] });
const catsLoading = ref(false);
const recategorizing = ref(false);
const recatMessage = ref("");

const q = ref("");
const selectedCategory = ref<string | null>(null); // null = 全部
const selectedMastery = ref<number | null>(null);  // null = 全部

const detailId = ref<number | null>(null);

const MASTERY_OPTIONS: { value: number | null; label: string }[] = [
  { value: null, label: "全部" },
  { value: 0, label: "未学" },
  { value: 1, label: "1" },
  { value: 2, label: "2" },
  { value: 3, label: "3" },
  { value: 4, label: "4" },
  { value: 5, label: "已掌握" },
];

const totalCount = computed(() =>
  Object.values(cats.value.counts).reduce((a, b) => a + b, 0)
);

const uncategorizedCount = computed(() => cats.value.counts["未分类"] ?? 0);

async function refreshCategories() {
  catsLoading.value = true;
  try {
    cats.value = await api.listCategories();
  } catch {
    /* ignore */
  } finally {
    catsLoading.value = false;
  }
}

async function refreshWords() {
  loading.value = true;
  error.value = "";
  try {
    words.value = await api.listWords({
      q: q.value.trim() || undefined,
      category: selectedCategory.value ?? undefined,
      mastery: selectedMastery.value ?? undefined,
      limit: 200,
    });
  } catch (e: any) {
    error.value = e.message || "加载失败";
  } finally {
    loading.value = false;
  }
}

let searchTimer: ReturnType<typeof setTimeout> | null = null;
watch(q, () => {
  if (searchTimer) clearTimeout(searchTimer);
  searchTimer = setTimeout(refreshWords, 200);
});
watch([selectedCategory, selectedMastery], refreshWords);

function selectCategory(name: string | null) {
  selectedCategory.value = name;
}

function openDetail(id: number) {
  detailId.value = id;
}

function closeDetail() {
  detailId.value = null;
}

async function onDeleted(id: number) {
  words.value = words.value.filter((w) => w.id !== id);
  detailId.value = null;
  await refreshCategories();
}

async function handleRecategorize() {
  if (recategorizing.value) return;
  if (uncategorizedCount.value === 0) return;
  if (
    !confirm(
      `将为 ${uncategorizedCount.value} 个未分类单词请求 AI 分类，可能产生少量调用费用。继续？`
    )
  )
    return;
  recategorizing.value = true;
  recatMessage.value = "";
  try {
    const res = await api.recategorize();
    recatMessage.value = `已分类 ${res.updated} / ${res.total} 个单词`;
    await Promise.all([refreshCategories(), refreshWords()]);
  } catch (e: any) {
    recatMessage.value = e.message || "分类失败";
  } finally {
    recategorizing.value = false;
    setTimeout(() => (recatMessage.value = ""), 4000);
  }
}

onMounted(async () => {
  await Promise.all([refreshCategories(), refreshWords()]);
});
</script>

<template>
  <div class="library">
    <header class="page-head">
      <div>
        <h1>单词库</h1>
        <p class="muted small">{{ totalCount }} 个单词 · 按分类与掌握度筛选</p>
      </div>
      <button
        class="btn btn-ghost recat-btn"
        :disabled="recategorizing || uncategorizedCount === 0"
        :title="uncategorizedCount === 0 ? '所有单词都已分类' : ''"
        @click="handleRecategorize"
      >
        {{
          recategorizing
            ? "AI 分类中…"
            : uncategorizedCount > 0
              ? `🤖 AI 分类 ${uncategorizedCount} 个未分类`
              : "✓ 已全部分类"
        }}
      </button>
    </header>

    <div v-if="recatMessage" class="recat-toast glass-dim">{{ recatMessage }}</div>

    <div class="body-grid">
      <!-- ─── LEFT: category rail ──────────────────────── -->
      <aside class="cat-rail glass">
        <h3 class="rail-title">分类</h3>
        <button
          class="cat-item"
          :class="{ active: selectedCategory == null }"
          @click="selectCategory(null)"
        >
          <span class="cat-name">全部</span>
          <span class="cat-count">{{ totalCount }}</span>
        </button>
        <button
          v-for="name in cats.order"
          :key="name"
          class="cat-item"
          :class="{
            active: selectedCategory === name,
            empty: (cats.counts[name] ?? 0) === 0,
            uncat: name === '未分类',
          }"
          @click="selectCategory(name)"
        >
          <span class="cat-name">{{ name }}</span>
          <span class="cat-count">{{ cats.counts[name] ?? 0 }}</span>
        </button>
      </aside>

      <!-- ─── RIGHT: search + word grid ────────────────── -->
      <section class="main-col">
        <div class="toolbar">
          <div class="search-wrap">
            <span class="search-icon">🔎</span>
            <input
              v-model="q"
              class="input search-input"
              placeholder="搜索单词或翻译…"
              type="search"
            />
          </div>
          <div class="mastery-chips">
            <button
              v-for="opt in MASTERY_OPTIONS"
              :key="opt.label"
              class="m-chip"
              :class="{ active: selectedMastery === opt.value }"
              @click="selectedMastery = opt.value"
            >
              {{ opt.label }}
            </button>
          </div>
        </div>

        <div v-if="error" class="state error glass-dim">{{ error }}</div>
        <div v-else-if="loading && words.length === 0" class="state muted glass-dim">
          加载中…
        </div>
        <div v-else-if="words.length === 0" class="state muted glass-dim">
          <p>没有匹配的单词</p>
          <p class="tertiary small">试试别的搜索词或清掉筛选条件</p>
        </div>
        <div v-else class="word-grid">
          <div
            v-for="w in words"
            :key="w.id"
            class="word-cell"
            @click="openDetail(w.id)"
          >
            <WordCard :word="w" />
            <span v-if="w.category" class="overlay-cat">{{ w.category }}</span>
          </div>
        </div>
      </section>
    </div>

    <WordDetail :word-id="detailId" @close="closeDetail" @deleted="onDeleted" />
  </div>
</template>

<style scoped>
.library {
  display: flex;
  flex-direction: column;
  gap: 14px;
  flex: 1;
  min-height: 0;
}

.page-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-shrink: 0;
}
.page-head h1 {
  font-family: var(--font-serif);
  font-size: 22px;
  font-weight: 700;
  letter-spacing: -0.02em;
  margin: 0;
}
.page-head p { margin: 2px 0 0; font-size: 13px; }
.small { font-size: 12px; }

.recat-btn {
  padding: 8px 16px;
  font-size: 13px;
  white-space: nowrap;
}
.recat-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.recat-toast {
  padding: 8px 14px;
  border-radius: 999px;
  font-size: 13px;
  color: var(--brand);
  align-self: flex-start;
}

.body-grid {
  display: grid;
  grid-template-columns: 220px minmax(0, 1fr);
  gap: 18px;
  flex: 1;
  min-height: 0;
}

/* ─── Category rail ───────────────────────────────── */
.cat-rail {
  padding: 14px 10px;
  display: flex;
  flex-direction: column;
  gap: 2px;
  overflow-y: auto;
  min-height: 0;
}

.rail-title {
  margin: 4px 8px 8px;
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--text-tertiary);
}

.cat-item {
  appearance: none;
  border: none;
  background: transparent;
  text-align: left;
  padding: 8px 10px;
  border-radius: 8px;
  font: inherit;
  font-size: 13px;
  color: var(--text-secondary);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  transition: background 150ms ease, color 150ms ease;
}
.cat-item:hover {
  background: var(--glass-bg-dim);
  color: var(--text-primary);
}
.cat-item.active {
  background: var(--brand-soft);
  color: var(--brand);
  font-weight: 600;
}
.cat-item.empty {
  opacity: 0.5;
}
.cat-item.uncat .cat-name::before {
  content: "• ";
  color: var(--text-tertiary);
}

.cat-count {
  font-size: 11px;
  font-variant-numeric: tabular-nums;
  color: var(--text-tertiary);
  background: var(--glass-bg-dim);
  padding: 1px 7px;
  border-radius: 999px;
  min-width: 24px;
  text-align: center;
}
.cat-item.active .cat-count {
  background: var(--brand);
  color: #fff;
}

/* ─── Main column ─────────────────────────────────── */
.main-col {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-width: 0;
  min-height: 0;
}

.toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  flex-shrink: 0;
}

.search-wrap {
  position: relative;
  flex: 1;
  min-width: 220px;
}
.search-icon {
  position: absolute;
  left: 14px;
  top: 50%;
  transform: translateY(-50%);
  font-size: 14px;
  pointer-events: none;
  opacity: 0.6;
}
.search-input {
  padding-left: 38px;
  padding-top: 10px;
  padding-bottom: 10px;
  font-size: 14px;
}

.mastery-chips {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
}

.m-chip {
  appearance: none;
  border: 1px solid var(--hairline);
  background: transparent;
  padding: 5px 12px;
  border-radius: 999px;
  font: inherit;
  font-size: 12px;
  color: var(--text-secondary);
  cursor: pointer;
  transition: background 150ms ease, color 150ms ease, border-color 150ms ease;
}
.m-chip:hover {
  background: var(--glass-bg-dim);
  color: var(--text-primary);
}
.m-chip.active {
  background: var(--brand);
  color: #fff;
  border-color: transparent;
}

/* ─── Word grid ───────────────────────────────────── */
.word-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 12px;
  overflow-y: auto;
  padding-right: 4px;
  min-height: 0;
}

.word-cell {
  position: relative;
}

.overlay-cat {
  position: absolute;
  top: 8px;
  right: 8px;
  font-size: 10px;
  padding: 2px 8px;
  border-radius: 999px;
  background: var(--brand-soft);
  color: var(--brand);
  font-weight: 600;
  pointer-events: none;
}

.state {
  padding: 40px 20px;
  text-align: center;
  border-radius: var(--radius-md);
}
.state.error { color: var(--danger); }
.state p { margin: 0 0 4px; }

@media (max-width: 900px) {
  .body-grid {
    grid-template-columns: 1fr;
  }
  .cat-rail {
    flex-direction: row;
    overflow-x: auto;
    overflow-y: hidden;
    padding: 10px;
  }
  .rail-title { display: none; }
  .cat-item { flex-shrink: 0; }
}
</style>
