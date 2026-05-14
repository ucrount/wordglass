<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { api, type CategoriesOut, type WordBrief } from "../api";
import WordDetail from "../components/WordDetail.vue";

type View = "tiles" | "category" | "search";

interface CategoryBucket {
  name: string;
  total: number;
  words: WordBrief[];
  avgMastery: number;
  isUncategorized: boolean;
}

const router = useRouter();

const allWords = ref<WordBrief[]>([]);
const cats = ref<CategoriesOut>({ counts: {}, order: [] });
const loading = ref(false);
const error = ref("");
const message = ref("");
const recategorizing = ref(false);

const q = ref("");
const selectedCategory = ref<string | null>(null);
const detailId = ref<number | null>(null);

const view = computed<View>(() => {
  if (q.value.trim()) return "search";
  if (selectedCategory.value !== null) return "category";
  return "tiles";
});

function toBucket(name: string, words: WordBrief[], isUncat: boolean): CategoryBucket {
  const sorted = [...words].sort(
    (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
  );
  const avg =
    words.reduce((s, w) => s + (w.mastery || 0), 0) / Math.max(1, words.length);
  return {
    name,
    total: words.length,
    words: sorted,
    avgMastery: avg,
    isUncategorized: isUncat,
  };
}

const buckets = computed<CategoryBucket[]>(() => {
  const byCat: Record<string, WordBrief[]> = {};
  for (const w of allWords.value) {
    const cat = w.category || "未分类";
    if (!byCat[cat]) byCat[cat] = [];
    byCat[cat].push(w);
  }
  const result: CategoryBucket[] = [];
  if ((byCat["未分类"] || []).length > 0) {
    result.push(toBucket("未分类", byCat["未分类"], true));
  }
  for (const name of cats.value.order) {
    if (name === "未分类") continue;
    const words = byCat[name] || [];
    if (words.length === 0) continue;
    result.push(toBucket(name, words, false));
  }
  // Fallback: words whose category isn't in cats.order (shouldn't happen, but be safe)
  for (const [name, words] of Object.entries(byCat)) {
    if (name === "未分类") continue;
    if (cats.value.order.includes(name)) continue;
    if (words.length === 0) continue;
    result.push(toBucket(name, words, false));
  }
  return result;
});

const selectedBucket = computed<CategoryBucket | undefined>(() =>
  selectedCategory.value
    ? buckets.value.find((b) => b.name === selectedCategory.value)
    : undefined
);

const categoryWords = computed<WordBrief[]>(() =>
  selectedBucket.value ? selectedBucket.value.words : []
);

const searchResults = computed<WordBrief[]>(() => {
  const term = q.value.trim().toLowerCase();
  if (!term) return [];
  return allWords.value.filter(
    (w) =>
      w.text.toLowerCase().includes(term) ||
      (w.translation || "").toLowerCase().includes(term)
  );
});

const totalCount = computed(() => allWords.value.length);
const masteredCount = computed(
  () => allWords.value.filter((w) => (w.mastery || 0) >= 5).length
);
const uncategorizedCount = computed(
  () => allWords.value.filter((w) => !w.category).length
);

function masteryPips(avg: number): boolean[] {
  const filled = Math.round(avg);
  return [0, 1, 2, 3, 4].map((i) => i < filled);
}

async function loadAll() {
  loading.value = true;
  error.value = "";
  try {
    const [list, c] = await Promise.all([
      api.listWords({ limit: 500 }),
      api.listCategories(),
    ]);
    allWords.value = list;
    cats.value = c;
  } catch (e: any) {
    error.value = e.message || "加载失败";
  } finally {
    loading.value = false;
  }
}

function enterCategory(name: string) {
  selectedCategory.value = name;
  q.value = "";
}

function exitCategory() {
  selectedCategory.value = null;
}

function openDetail(id: number) {
  detailId.value = id;
}

function closeDetail() {
  detailId.value = null;
}

async function onDeleted(id: number) {
  allWords.value = allWords.value.filter((w) => w.id !== id);
  detailId.value = null;
  try {
    cats.value = await api.listCategories();
  } catch {
    /* keep stale order */
  }
}

function practiceCategory(b: CategoryBucket) {
  if (b.total === 0) return;
  const ids = b.words.map((w) => w.id).join(",");
  router.push({ path: "/practice", query: { word_ids: ids } });
}

async function recategorize() {
  if (recategorizing.value) return;
  if (uncategorizedCount.value === 0) return;
  if (
    !confirm(
      `将为 ${uncategorizedCount.value} 个未分类单词请求 AI 分类，可能产生少量调用费用。继续？`
    )
  )
    return;
  recategorizing.value = true;
  message.value = "";
  try {
    const res = await api.recategorize();
    message.value = `已分类 ${res.updated} / ${res.total} 个单词`;
    await loadAll();
  } catch (e: any) {
    message.value = e.message || "分类失败";
  } finally {
    recategorizing.value = false;
    setTimeout(() => {
      message.value = "";
    }, 4000);
  }
}

onMounted(loadAll);
</script>

<template>
  <div class="library">
    <header class="page-head">
      <div>
        <h1>单词库</h1>
        <p class="muted small">
          {{ totalCount }} 个 · {{ masteredCount }} 已掌握
          <span v-if="uncategorizedCount > 0" class="warn-chip">
            · {{ uncategorizedCount }} 未分类
          </span>
        </p>
      </div>
    </header>

    <div class="search-bar glass">
      <span class="search-icon">🔎</span>
      <input
        v-model="q"
        class="search-input"
        placeholder="搜索单词或翻译…"
        type="search"
      />
      <button
        v-if="view === 'category'"
        class="back-btn"
        @click="exitCategory"
      >
        ← 返回所有分类
      </button>
      <span v-else-if="view === 'tiles'" class="cta-summary">
        {{ buckets.length }} 个分类
      </span>
    </div>

    <div v-if="error" class="state error glass-dim">
      {{ error }}
      <button class="btn btn-ghost" style="margin-left: 12px" @click="loadAll">
        重试
      </button>
    </div>

    <div v-else-if="loading && allWords.length === 0" class="state muted glass-dim">
      加载中…
    </div>

    <div v-else-if="totalCount === 0" class="state muted glass-dim">
      <p>词库还是空的</p>
      <p class="tertiary small">去主页 / 阅读翻译 里加几个单词吧</p>
    </div>

    <!-- ─── Content area ──────────────────────────────── -->
    <div v-else class="content-area">
      <!-- ═════ Tiles view ═════ -->
      <div v-if="view === 'tiles'" class="tile-grid">
        <button
          v-for="b in buckets"
          :key="b.name"
          class="tile glass"
          :class="{ uncat: b.isUncategorized }"
          @click="enterCategory(b.name)"
        >
          <div class="tile-head">
            <span class="tile-name">
              <span v-if="b.isUncategorized" class="uncat-dot">•</span>{{ b.name }}
            </span>
            <span class="tile-count">{{ b.total }} 个</span>
          </div>
          <div class="tile-words">
            <span
              v-for="w in b.words.slice(0, 4)"
              :key="w.id"
              class="tile-word"
            >{{ w.text }}</span>
            <span v-if="b.total > 4" class="tile-more">+{{ b.total - 4 }}</span>
          </div>
          <div class="tile-foot">
            <span
              v-if="b.isUncategorized"
              class="tile-action accent"
              :class="{ disabled: recategorizing }"
              @click.stop="recategorize"
            >{{ recategorizing ? "AI 分类中…" : "🤖 AI 分类" }}</span>
            <span
              v-else
              class="tile-action"
              @click.stop="practiceCategory(b)"
            >▶ 练这 {{ b.total }} 个</span>
            <div
              class="tile-pips"
              :title="`平均掌握度 ${b.avgMastery.toFixed(1)} / 5`"
            >
              <span
                v-for="(on, i) in masteryPips(b.avgMastery)"
                :key="i"
                class="p"
                :class="{ on }"
              />
            </div>
          </div>
        </button>
      </div>

      <!-- ═════ Category view ═════ -->
      <div v-else-if="view === 'category'" class="cat-view">
        <div class="cat-view-head">
          <h2>
            <span v-if="selectedBucket?.isUncategorized" class="uncat-dot">•</span>
            {{ selectedCategory }}
          </h2>
          <span class="muted small">{{ categoryWords.length }} 个</span>
          <button
            v-if="categoryWords.length > 0 && !selectedBucket?.isUncategorized"
            class="cat-prac"
            @click="practiceCategory(selectedBucket!)"
          >
            ▶ 练这 {{ categoryWords.length }} 个
          </button>
          <button
            v-else-if="selectedBucket?.isUncategorized && categoryWords.length > 0"
            class="cat-prac accent"
            :disabled="recategorizing"
            @click="recategorize"
          >
            {{ recategorizing ? "AI 分类中…" : "🤖 AI 分类这些" }}
          </button>
        </div>

        <div v-if="categoryWords.length === 0" class="state muted glass-dim">
          这个分类暂时没有单词
        </div>
        <div v-else class="word-grid">
          <div
            v-for="w in categoryWords"
            :key="w.id"
            class="word-row"
            @click="openDetail(w.id)"
          >
            <div class="row-text">
              <div class="row-w">{{ w.text }}</div>
              <div class="row-t">{{ w.translation || "（无翻译）" }}</div>
            </div>
            <div class="row-pips">
              <span
                v-for="(on, i) in masteryPips(w.mastery)"
                :key="i"
                class="p"
                :class="{ on }"
              />
            </div>
          </div>
        </div>
      </div>

      <!-- ═════ Search view ═════ -->
      <div v-else class="search-view">
        <div class="search-result-head">
          匹配到 <strong>{{ searchResults.length }}</strong> 个单词
          <span v-if="searchResults.length === 0" class="muted small">
            · 试试别的搜索词
          </span>
        </div>
        <div v-if="searchResults.length > 0" class="word-grid">
          <div
            v-for="w in searchResults"
            :key="w.id"
            class="word-row"
            @click="openDetail(w.id)"
          >
            <div class="row-text">
              <div class="row-w">{{ w.text }}</div>
              <div class="row-t">
                {{ w.translation || "（无翻译）" }}
                <span v-if="w.category" class="row-cat">· {{ w.category }}</span>
              </div>
            </div>
            <div class="row-pips">
              <span
                v-for="(on, i) in masteryPips(w.mastery)"
                :key="i"
                class="p"
                :class="{ on }"
              />
            </div>
          </div>
        </div>
      </div>
    </div>

    <Transition name="fade">
      <div v-if="message" class="msg-toast glass-dim">{{ message }}</div>
    </Transition>

    <WordDetail :word-id="detailId" @close="closeDetail" @deleted="onDeleted" />
  </div>
</template>

<style scoped>
.library {
  display: flex;
  flex-direction: column;
  gap: 18px;
  height: calc(100vh - 68px);
  min-height: 0;
}

/* ─── Header ───────────────────────────────────────── */
.page-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 14px;
  flex-shrink: 0;
}
.page-head h1 {
  font-family: var(--font-serif);
  font-size: 26px;
  font-weight: 700;
  letter-spacing: -0.02em;
  margin: 0;
}
.page-head p {
  margin: 4px 0 0;
  font-size: 12px;
  color: var(--text-tertiary);
}
.small { font-size: 12px; }
.warn-chip {
  color: var(--accent);
  font-weight: 600;
}

/* ─── Search bar ───────────────────────────────────── */
.search-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 18px;
  flex-shrink: 0;
}
.search-icon {
  font-size: 14px;
  opacity: 0.5;
}
.search-input {
  flex: 1;
  background: transparent;
  border: none;
  font-size: 14px;
  color: var(--text-primary);
  outline: none;
  padding: 6px 0;
}
.search-input::placeholder {
  color: var(--text-tertiary);
}
.back-btn {
  appearance: none;
  border: 1px solid var(--glass-border);
  background: var(--glass-bg-dim);
  padding: 5px 14px;
  border-radius: 999px;
  font: inherit;
  font-size: 12px;
  font-weight: 600;
  color: var(--brand);
  cursor: pointer;
  transition: background 150ms ease;
}
.back-btn:hover {
  background: var(--brand-soft);
}
.cta-summary {
  font-size: 11.5px;
  color: var(--text-tertiary);
  font-variant-numeric: tabular-nums;
}

/* ─── Content area (scrolls) ───────────────────────── */
.content-area {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding-right: 4px;
}

/* ─── Tiles view ───────────────────────────────────── */
.tile-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 14px;
  align-content: start;
}

.tile {
  appearance: none;
  border: 1px solid var(--glass-border);
  text-align: left;
  cursor: pointer;
  padding: 16px 18px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  position: relative;
  overflow: hidden;
  transition:
    background 200ms ease,
    transform 120ms ease,
    border-color 200ms ease;
  font: inherit;
  color: var(--text-primary);
}
.tile::before {
  content: "";
  position: absolute;
  inset: 0;
  background: linear-gradient(
    135deg,
    color-mix(in srgb, var(--brand) 6%, transparent),
    transparent 60%
  );
  pointer-events: none;
}
.tile:hover {
  background: var(--glass-bg-strong);
  transform: translateY(-1px);
  border-color: color-mix(in srgb, var(--brand) 30%, var(--glass-border));
}
.tile.uncat {
  border-color: color-mix(in srgb, var(--accent) 30%, var(--glass-border));
}
.tile.uncat::before {
  background: linear-gradient(
    135deg,
    color-mix(in srgb, var(--accent) 8%, transparent),
    transparent 60%
  );
}

.tile-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 10px;
}
.tile-name {
  font-family: var(--font-serif);
  font-size: 16px;
  font-weight: 700;
}
.uncat-dot {
  color: var(--accent);
  margin-right: 4px;
}
.tile.uncat .tile-name {
  color: var(--accent);
}
.tile-count {
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--text-tertiary);
}

.tile-words {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  min-height: 22px;
}
.tile-word {
  font-family: var(--font-serif);
  font-style: italic;
  font-size: 11.5px;
  color: var(--text-secondary);
  padding: 2px 7px;
  background: var(--glass-bg-dim);
  border-radius: 4px;
}
.tile-more {
  font-size: 10.5px;
  color: var(--text-tertiary);
  padding: 2px 6px;
  align-self: center;
}

.tile-foot {
  display: flex;
  align-items: center;
  margin-top: 4px;
  padding-top: 10px;
  border-top: 1px dashed var(--hairline);
  font-size: 11.5px;
}
.tile-action {
  color: var(--brand);
  font-weight: 600;
  cursor: pointer;
  transition: text-decoration 100ms ease;
}
.tile-action.accent {
  color: var(--accent);
}
.tile-action.disabled {
  opacity: 0.6;
  cursor: wait;
}
.tile-action:hover:not(.disabled) {
  text-decoration: underline;
}

.tile-pips {
  margin-left: auto;
  display: flex;
  gap: 2.5px;
}
.tile-pips .p {
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background: var(--hairline-strong);
}
.tile-pips .p.on {
  background: var(--brand);
}

/* ─── Category view ────────────────────────────────── */
.cat-view {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.cat-view-head {
  display: flex;
  align-items: baseline;
  gap: 14px;
  flex-wrap: wrap;
}
.cat-view-head h2 {
  font-family: var(--font-serif);
  font-size: 22px;
  font-weight: 700;
  margin: 0;
  letter-spacing: -0.01em;
}
.cat-prac {
  margin-left: auto;
  background: var(--brand-strong, var(--brand));
  color: var(--brand-strong-text, #fff);
  border: none;
  padding: 7px 18px;
  border-radius: 999px;
  font: inherit;
  font-size: 12.5px;
  font-weight: 700;
  cursor: pointer;
  transition: opacity 150ms ease;
}
.cat-prac:hover {
  opacity: 0.9;
}
.cat-prac.accent {
  background: var(--accent);
}
.cat-prac:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

/* ─── Word grid + rows ─────────────────────────────── */
.word-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 10px;
}
.word-row {
  display: flex;
  align-items: center;
  padding: 11px 14px;
  background: var(--glass-bg-dim);
  border: 1px solid var(--glass-border);
  border-radius: 10px;
  cursor: pointer;
  gap: 10px;
  transition: background 150ms ease, border-color 150ms ease;
}
.word-row:hover {
  background: var(--glass-bg);
  border-color: color-mix(in srgb, var(--brand) 20%, var(--glass-border));
}
.row-text {
  flex: 1;
  min-width: 0;
}
.row-w {
  font-family: var(--font-serif);
  font-size: 14.5px;
  font-weight: 700;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.row-t {
  font-size: 11px;
  color: var(--text-tertiary);
  margin-top: 1px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.row-cat {
  font-size: 10px;
  color: var(--brand);
  margin-left: 4px;
}
.row-pips {
  display: flex;
  gap: 2.5px;
  flex-shrink: 0;
}
.row-pips .p {
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background: var(--hairline-strong);
}
.row-pips .p.on {
  background: var(--brand);
}

/* ─── Search view ──────────────────────────────────── */
.search-view {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.search-result-head {
  font-size: 13px;
  color: var(--text-secondary);
}
.search-result-head strong {
  color: var(--text-primary);
  font-weight: 700;
}

/* ─── States ───────────────────────────────────────── */
.state {
  padding: 36px 20px;
  text-align: center;
  border-radius: var(--radius-md);
}
.state.error {
  color: var(--danger);
}
.state p {
  margin: 0 0 4px;
}

/* ─── Toast ────────────────────────────────────────── */
.msg-toast {
  position: fixed;
  bottom: 30px;
  left: 50%;
  transform: translateX(-50%);
  padding: 10px 18px;
  border-radius: 999px;
  font-size: 13px;
  color: var(--brand);
  z-index: 50;
  box-shadow: 0 12px 32px rgba(0, 0, 0, 0.2);
}
.fade-enter-active,
.fade-leave-active {
  transition: opacity 200ms ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

/* ─── Mobile ───────────────────────────────────────── */
@media (max-width: 900px) {
  .library {
    height: auto;
    min-height: 0;
  }
  .content-area {
    overflow: visible;
  }
  .tile-grid {
    grid-template-columns: 1fr;
  }
  .word-grid {
    grid-template-columns: 1fr;
  }
}
</style>
