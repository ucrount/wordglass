<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { RouterLink } from "vue-router";
import { api, type HeatmapData, type Stats, type WordBrief, type WordOut } from "../api";
import AddBar from "../components/AddBar.vue";
import Heatmap from "../components/Heatmap.vue";
import WordCard from "../components/WordCard.vue";
import { isSpeechSupported, speak } from "../composables/tts";

const stats = ref<Stats>({ total: 0, due_today: 0, mastered: 0, added_this_week: 0 });
const recent = ref<WordBrief[]>([]);
const heat = ref<HeatmapData>({ days: {}, since: "" });
const recentError = ref("");
const initialLoad = ref(true);

const lastAdded = ref<WordOut | null>(null);

const ttsSupported = isSpeechSupported();

async function refreshStats() {
  try {
    stats.value = await api.stats();
  } catch (e) {
    /* swallow */
  }
}
async function refreshHeatmap() {
  try {
    heat.value = await api.heatmap(84);
  } catch (e) {
    /* swallow */
  }
}
async function refreshRecent() {
  recentError.value = "";
  try {
    recent.value = await api.listWords({ limit: 20 });
  } catch (e: any) {
    recentError.value = e.message || "加载失败";
  }
}
async function refreshAll() {
  await Promise.all([refreshStats(), refreshHeatmap(), refreshRecent()]);
  initialLoad.value = false;
}

function onAdded(w: WordOut) {
  lastAdded.value = w;
  refreshAll();
  if (ttsSupported) setTimeout(() => speak(w.text), 100);
}

function clearPreview() {
  lastAdded.value = null;
}

const activeDays = computed(() => Object.keys(heat.value.days).length);
const totalActions = computed(() =>
  Object.values(heat.value.days).reduce((a, b) => a + b, 0)
);

onMounted(refreshAll);
</script>

<template>
  <div class="dashboard">
    <!-- Page header (compact) -->
    <header class="page-head stagger" style="--stagger: 0">
      <h1>主页</h1>
      <p class="muted small">粘个单词，AI 立刻给翻译和 3 个不同语境的例句。</p>
    </header>

    <!-- Two-column body, flex-fills remaining viewport height -->
    <div class="body-grid">
      <!-- ─── LEFT MAIN COLUMN ───────────────────────────── -->
      <div class="col-main">
        <section class="stagger" style="--stagger: 1">
          <AddBar @added="onAdded" />
        </section>

        <!-- Either preview OR recent — same slot, internally scrollable -->
        <Transition name="fade" mode="out-in">
          <section
            v-if="lastAdded"
            key="preview"
            class="preview glass-strong stagger"
            style="--stagger: 2"
          >
            <div class="preview-head">
              <div class="word-row">
                <span class="word-text">{{ lastAdded.text }}</span>
                <button
                  v-if="ttsSupported"
                  class="speaker"
                  @click="speak(lastAdded.text)"
                  title="朗读"
                >🔊</button>
                <span v-if="lastAdded.phonetic" class="phonetic">{{ lastAdded.phonetic }}</span>
                <span v-if="lastAdded.pos" class="pos">{{ lastAdded.pos }}</span>
              </div>
              <button class="close" @click="clearPreview" title="关闭">×</button>
            </div>
            <div class="translation">{{ lastAdded.translation }}</div>

            <div v-if="lastAdded.examples.length > 0" class="examples">
              <div
                v-for="(ex, i) in lastAdded.examples"
                :key="ex.id"
                class="example"
              >
                <div class="example-num">{{ i + 1 }}</div>
                <div class="example-body">
                  <div class="example-en">{{ ex.en }}</div>
                  <div v-if="ex.zh" class="example-zh tertiary">{{ ex.zh }}</div>
                </div>
              </div>
            </div>

            <div class="preview-actions">
              <RouterLink to="/practice" class="btn btn-primary">立即练习 →</RouterLink>
              <button class="btn btn-ghost" @click="clearPreview">再加一个</button>
            </div>
          </section>

          <section
            v-else
            key="recent"
            class="recent stagger"
            style="--stagger: 2"
          >
            <div class="section-head">
              <h2>最近添加</h2>
              <RouterLink to="/library" class="link">查看全部 →</RouterLink>
            </div>

            <div v-if="recentError" class="hint-card error glass-dim">
              {{ recentError }}
              <div class="tertiary small">检查后端是否启动 / 设置页 AI 是否配置</div>
            </div>

            <div v-else-if="initialLoad" class="hint-card glass-dim">
              <span class="muted">加载中…</span>
            </div>

            <div v-else-if="recent.length === 0" class="hint-card glass-dim">
              <span class="muted">还没有保存的单词。</span>
              <span class="tertiary small">在上方搜索框粘一个英文单词试试。</span>
            </div>

            <!-- Horizontal scrolling carousel — bounded vertical height -->
            <div v-else class="recent-row">
              <WordCard v-for="w in recent" :key="w.id" :word="w" />
            </div>
          </section>
        </Transition>
      </div>

      <!-- ─── RIGHT SIDEBAR ───────────────────────────────── -->
      <aside class="col-side">
        <section class="widget glass stagger" style="--stagger: 3">
          <div class="widget-head">
            <h3>学习热力图</h3>
            <span class="tertiary small">{{ activeDays }} 天 · {{ totalActions }} 次</span>
          </div>
          <Heatmap :data="heat.days" :weeks="12" />
        </section>

        <section class="widget glass due-widget stagger" style="--stagger: 4">
          <div class="due-row">
            <div class="due-left">
              <span class="num-gradient" :class="{ none: stats.due_today === 0 }">
                {{ stats.due_today }}
              </span>
              <span class="due-label">
                <div class="muted small">今日待复习</div>
                <div class="tertiary" style="font-size: 11px">
                  {{ stats.due_today === 0 ? "今天没有需要复习的词" : "趁热打铁巩固一下" }}
                </div>
              </span>
            </div>
            <RouterLink
              v-if="stats.due_today > 0"
              to="/practice"
              class="btn btn-primary"
            >
              开始
            </RouterLink>
          </div>
        </section>

        <section class="stat-row stagger" style="--stagger: 5">
          <div class="stat glass">
            <span class="stat-icon">📚</span>
            <span class="stat-info">
              <span class="stat-num">{{ stats.total }}</span>
              <span class="muted stat-label">总数</span>
            </span>
          </div>
          <div class="stat glass">
            <span class="stat-icon">🎯</span>
            <span class="stat-info">
              <span class="stat-num">{{ stats.due_today }}</span>
              <span class="muted stat-label">待复习</span>
            </span>
          </div>
          <div class="stat glass">
            <span class="stat-icon">✨</span>
            <span class="stat-info">
              <span class="stat-num">{{ stats.mastered }}</span>
              <span class="muted stat-label">已掌握</span>
            </span>
          </div>
          <div class="stat glass">
            <span class="stat-icon">🚀</span>
            <span class="stat-info">
              <span class="stat-num">{{ stats.added_this_week }}</span>
              <span class="muted stat-label">本周</span>
            </span>
          </div>
        </section>
      </aside>
    </div>
  </div>
</template>

<style scoped>
.dashboard {
  display: flex;
  flex-direction: column;
  gap: 14px;
  height: 100%;
  min-height: 0;
}

/* Stagger */
.stagger {
  animation: stagger-fade 0.55s cubic-bezier(0.16, 1, 0.3, 1) both;
  animation-delay: calc(var(--stagger, 0) * 0.07s);
}
@keyframes stagger-fade {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}
@media (prefers-reduced-motion: reduce) {
  .stagger { animation: none; }
}

/* Page head */
.page-head { flex-shrink: 0; }
.page-head h1 {
  font-size: 22px;
  font-weight: 700;
  letter-spacing: -0.02em;
  margin: 0;
}
.page-head p { margin: 2px 0 0; font-size: 13px; }
.small { font-size: 12px; }

/* Body grid — fills remaining viewport */
.body-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.65fr) minmax(320px, 1fr);
  gap: 16px;
  flex: 1;
  min-height: 0;
}

@media (max-width: 1080px) {
  .body-grid { grid-template-columns: 1fr; }
}

.col-main,
.col-side {
  display: flex;
  flex-direction: column;
  gap: 14px;
  min-height: 0;
  min-width: 0;
}

/* ─── Preview ──────────────────────────────────────── */
.preview {
  padding: 18px 22px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  border-left: 3px solid var(--brand);
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

.preview-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
}

.word-row {
  display: flex;
  align-items: baseline;
  gap: 10px;
  flex-wrap: wrap;
}

.word-text {
  font-size: clamp(24px, 2.6vw, 30px);
  font-weight: 700;
  letter-spacing: -0.02em;
  color: var(--text-primary);
  line-height: 1.1;
}

.speaker {
  appearance: none;
  border: none;
  background: rgba(0, 0, 0, 0.04);
  width: 30px;
  height: 30px;
  border-radius: 50%;
  font-size: 14px;
  cursor: pointer;
  transition: background 200ms ease, transform 200ms ease;
  align-self: center;
}
[data-theme="dark"] .speaker { background: rgba(255, 255, 255, 0.06); }
.speaker:hover { transform: scale(1.08); background: var(--brand-soft); }

.phonetic {
  font-family: ui-monospace, "SF Mono", Menlo, monospace;
  font-size: 13px;
  color: var(--text-tertiary);
}

.pos {
  padding: 2px 8px;
  border-radius: 6px;
  background: rgba(0, 0, 0, 0.05);
  font-size: 11px;
  color: var(--text-secondary);
}
[data-theme="dark"] .pos { background: rgba(255, 255, 255, 0.08); }

.close {
  appearance: none;
  border: none;
  background: transparent;
  font-size: 22px;
  line-height: 1;
  color: var(--text-tertiary);
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 8px;
  transition: background 200ms ease;
}
.close:hover { background: rgba(0, 0, 0, 0.05); color: var(--text-primary); }
[data-theme="dark"] .close:hover { background: rgba(255, 255, 255, 0.08); }

.translation {
  font-size: 16px;
  font-weight: 500;
  color: var(--brand);
}

.examples {
  display: flex;
  flex-direction: column;
  gap: 8px;
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding-right: 4px;
}

.examples::-webkit-scrollbar { width: 6px; }
.examples::-webkit-scrollbar-track { background: transparent; }
.examples::-webkit-scrollbar-thumb {
  background: var(--hairline-strong);
  border-radius: 999px;
}
.examples::-webkit-scrollbar-thumb:hover { background: var(--brand); opacity: 0.6; }

.example {
  display: flex;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 10px;
  background: var(--glass-bg-dim);
  border: 1px solid var(--hairline);
}

.example-num {
  flex-shrink: 0;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: var(--brand-soft);
  color: var(--brand);
  font-size: 11px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
}

.example-body { min-width: 0; flex: 1; }
.example-en {
  font-size: 14px;
  color: var(--text-primary);
  line-height: 1.5;
}
.example-zh {
  margin-top: 2px;
  font-size: 12px;
  line-height: 1.5;
}

.preview-actions {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}

.preview-actions .btn {
  text-decoration: none;
  padding: 8px 18px;
  font-size: 14px;
}

/* ─── Recent words (horizontal scroll) ─────────────── */
.recent {
  display: flex;
  flex-direction: column;
  gap: 10px;
  flex: 1;
  min-height: 0;
}

.section-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  flex-shrink: 0;
}
.section-head h2 {
  font-size: 15px;
  font-weight: 600;
  letter-spacing: -0.01em;
  margin: 0;
}
.link {
  text-decoration: none;
  color: var(--brand);
  font-size: 12px;
  font-weight: 600;
}

.recent-row {
  display: flex;
  flex-direction: row;
  gap: 12px;
  overflow-x: auto;
  overflow-y: hidden;
  padding-bottom: 10px;
  flex: 1;
  align-items: stretch;
  min-height: 0;
}

.recent-row > * {
  flex: 0 0 220px;
  height: 100%;
}

.recent-row::-webkit-scrollbar { height: 6px; }
.recent-row::-webkit-scrollbar-track { background: transparent; }
.recent-row::-webkit-scrollbar-thumb {
  background: var(--hairline-strong);
  border-radius: 999px;
}
.recent-row::-webkit-scrollbar-thumb:hover { background: var(--brand); opacity: 0.6; }

.hint-card {
  padding: 24px;
  text-align: center;
  color: var(--text-secondary);
  display: flex;
  flex-direction: column;
  gap: 4px;
  flex: 1;
  align-items: center;
  justify-content: center;
}
.hint-card.error { color: var(--danger); }

/* ─── Right sidebar widgets ────────────────────────── */
.widget {
  padding: 16px 18px;
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
  letter-spacing: -0.01em;
}

/* Due widget — compact horizontal */
.due-widget { padding: 14px 18px; }

.due-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.due-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.num-gradient {
  font-size: 38px;
  font-weight: 800;
  letter-spacing: -0.025em;
  line-height: 1;
  background: linear-gradient(135deg, #8b5cf6 0%, #ec4899 100%);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
  color: transparent;
}

.num-gradient.none {
  background: none;
  color: var(--text-tertiary);
  -webkit-text-fill-color: var(--text-tertiary);
}

.due-label { display: flex; flex-direction: column; }

.due-row .btn {
  padding: 8px 18px;
  font-size: 13px;
  white-space: nowrap;
  text-decoration: none;
}

/* Stats — single row of 4, compact */
.stat-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 10px;
}

.stat {
  padding: 12px 12px;
  display: flex;
  align-items: center;
  gap: 8px;
  text-decoration: none;
  color: var(--text-primary);
  min-width: 0;
}

.stat-icon { font-size: 18px; line-height: 1; flex-shrink: 0; }
.stat-info { display: flex; flex-direction: column; min-width: 0; }
.stat-num {
  font-size: 19px;
  font-weight: 800;
  letter-spacing: -0.02em;
  line-height: 1.1;
}
.stat-label { font-size: 11px; }

/* ─── Responsive: when stacked (narrow), allow page scroll ─── */
@media (max-width: 1080px) {
  .dashboard { height: auto; }
  .recent-row { overflow-x: auto; }
}
</style>
