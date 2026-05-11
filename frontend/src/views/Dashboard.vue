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
  try { stats.value = await api.stats(); } catch { /* ignore */ }
}
async function refreshHeatmap() {
  try { heat.value = await api.heatmap(84); } catch { /* ignore */ }
}
async function refreshRecent() {
  recentError.value = "";
  try {
    const list = await api.listWords({ limit: 4 });
    recent.value = list;
    // When user hasn't just added one, default the preview to the most recent word
    if (!lastAdded.value && list.length > 0) {
      try {
        lastAdded.value = await api.getWord(list[0].id);
      } catch { /* preview stays empty */ }
    }
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

const activeDays = computed(() => Object.keys(heat.value.days).length);
const totalActions = computed(() =>
  Object.values(heat.value.days).reduce((a, b) => a + b, 0)
);

onMounted(refreshAll);
</script>

<template>
  <div class="dashboard">
    <!-- Compact header -->
    <header class="page-head">
      <h1>主页</h1>
      <p class="muted small">粘个英文单词，AI 立刻给翻译和 3 个不同语境的例句。</p>
    </header>

    <!-- Body grid — fills remaining viewport -->
    <div class="body-grid">
      <!-- ─── LEFT MAIN COLUMN ─────────────────────────── -->
      <div class="col-main">
        <AddBar @added="onAdded" class="addbar" />

        <!-- Preview card — always shown, internal scroll for examples -->
        <section class="preview glass-strong">
          <template v-if="lastAdded">
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
              <RouterLink to="/practice" class="btn btn-primary practice-btn">
                练这个 →
              </RouterLink>
            </div>
            <div class="translation">{{ lastAdded.translation || "（无翻译）" }}</div>

            <div class="examples-head tertiary">
              <span class="dot-purple" />
              {{ lastAdded.examples.length }} 个不同语境的例句
            </div>
            <div class="examples">
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
              <div v-if="lastAdded.examples.length === 0" class="muted small examples-empty">
                这个词暂无例句
              </div>
            </div>
          </template>

          <template v-else-if="initialLoad">
            <div class="empty-state muted">加载中…</div>
          </template>

          <template v-else>
            <div class="empty-state">
              <div class="emoji">👋</div>
              <p class="muted">在上方输入框粘一个英文单词</p>
              <p class="tertiary small">AI 立刻给你翻译和 3 个不同语境的例句</p>
            </div>
          </template>
        </section>

        <!-- Recent: single row of 4 cards -->
        <section class="recent">
          <div class="section-head">
            <h2>最近添加</h2>
            <RouterLink to="/library" class="link">查看全部 →</RouterLink>
          </div>
          <div v-if="recentError" class="hint-card error glass-dim">
            {{ recentError }}
          </div>
          <div v-else-if="!initialLoad && recent.length === 0" class="hint-card glass-dim">
            <span class="muted">还没有保存的单词</span>
          </div>
          <div v-else class="recent-grid">
            <WordCard v-for="w in recent" :key="w.id" :word="w" />
          </div>
        </section>
      </div>

      <!-- ─── RIGHT SIDEBAR ─────────────────────────────── -->
      <aside class="col-side">
        <!-- Heatmap -->
        <section class="widget glass heatmap-widget">
          <div class="widget-head">
            <h3>学习热力图</h3>
            <span class="tertiary small">{{ activeDays }} 天 · {{ totalActions }} 次</span>
          </div>
          <Heatmap :data="heat.days" :weeks="12" />
        </section>

        <!-- BIG today's review -->
        <section class="widget glass due-big-widget">
          <div class="widget-head">
            <h3>今日待复习</h3>
          </div>
          <div class="due-content">
            <div class="due-number" :class="{ none: stats.due_today === 0 }">
              <span class="big-num">{{ stats.due_today }}</span>
              <span class="unit">个</span>
            </div>
            <p class="muted due-hint">
              {{
                stats.due_today === 0
                  ? "今天没有需要复习的词，加几个新词吧"
                  : "到点要再见一面的词，趁热打铁巩固一下"
              }}
            </p>
            <RouterLink
              v-if="stats.due_today > 0"
              to="/practice"
              class="btn btn-primary big-btn"
            >
              开始练习 →
            </RouterLink>
            <RouterLink
              v-else
              to="/practice"
              class="btn btn-ghost big-btn"
            >
              去练习页
            </RouterLink>
          </div>
        </section>

        <!-- 3 compact stats -->
        <section class="stat-row">
          <div class="stat glass">
            <span class="stat-icon">📚</span>
            <span class="stat-info">
              <span class="stat-num">{{ stats.total }}</span>
              <span class="muted stat-label">总数</span>
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
  flex: 1;
  min-height: 0;
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
  grid-template-columns: minmax(0, 1.65fr) minmax(340px, 1fr);
  gap: 32px;
  flex: 1;
  min-height: 0;
}

.col-main,
.col-side {
  display: flex;
  flex-direction: column;
  gap: 14px;
  min-height: 0;
  min-width: 0;
}

/* ─── LEFT COLUMN ─────────────────────────────────── */

/* AddBar — auto height */
.addbar { flex-shrink: 0; }

/* Preview — flex:1 fills available, examples scroll inside */
.preview {
  flex: 1;
  min-height: 0;
  padding: 18px 22px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  border-left: 3px solid var(--brand);
}

.preview-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  flex-shrink: 0;
}

.word-row {
  display: flex;
  align-items: baseline;
  gap: 10px;
  flex-wrap: wrap;
  min-width: 0;
}

.word-text {
  font-size: clamp(24px, 2.5vw, 30px);
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

.practice-btn {
  text-decoration: none;
  padding: 6px 14px;
  font-size: 13px;
  white-space: nowrap;
  flex-shrink: 0;
}

.translation {
  font-size: 16px;
  font-weight: 500;
  color: var(--brand);
  flex-shrink: 0;
  word-wrap: break-word;
}

.examples-head {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  flex-shrink: 0;
}

.dot-purple {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--brand);
}

/* The scrolling region inside the preview */
.examples {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding-right: 4px;
}

.examples::-webkit-scrollbar { width: 6px; }
.examples::-webkit-scrollbar-track { background: transparent; }
.examples::-webkit-scrollbar-thumb {
  background: var(--hairline-strong);
  border-radius: 999px;
}
.examples::-webkit-scrollbar-thumb:hover { background: var(--brand); }

.example {
  display: flex;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 10px;
  background: var(--glass-bg-dim);
  border: 1px solid var(--hairline);
  flex-shrink: 0;
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
  font-size: 12.5px;
  line-height: 1.5;
}

.examples-empty {
  text-align: center;
  padding: 20px;
}

.empty-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6px;
  text-align: center;
}
.empty-state .emoji { font-size: 36px; line-height: 1; }
.empty-state p { margin: 0; }

/* Recent — auto height, 4 cards in a single row */
.recent { flex-shrink: 0; }

.section-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  margin-bottom: 8px;
}

.section-head h2 {
  font-size: 14px;
  font-weight: 600;
  margin: 0;
  letter-spacing: -0.01em;
}

.link {
  text-decoration: none;
  color: var(--brand);
  font-size: 12px;
  font-weight: 600;
}

.recent-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 10px;
}

.hint-card {
  padding: 16px;
  text-align: center;
  color: var(--text-secondary);
  font-size: 13px;
}
.hint-card.error { color: var(--danger); }

/* ─── RIGHT COLUMN ────────────────────────────────── */

.widget {
  padding: 14px 18px;
  display: flex;
  flex-direction: column;
  gap: 8px;
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
}

.heatmap-widget { flex-shrink: 0; }

/* The BIG due widget — flex 1 to take all remaining space */
.due-big-widget {
  flex: 1;
  min-height: 0;
  padding: 16px 20px;
}

.due-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
  text-align: center;
  padding: 8px 0;
  min-height: 0;
}

.due-number {
  display: flex;
  align-items: baseline;
  gap: 6px;
}

.big-num {
  font-size: clamp(60px, 7vw, 96px);
  font-weight: 800;
  letter-spacing: -0.03em;
  line-height: 1;
  background: linear-gradient(135deg, #8b5cf6 0%, #ec4899 100%);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
  color: transparent;
}

.due-number.none .big-num {
  background: none;
  color: var(--text-tertiary);
  -webkit-text-fill-color: var(--text-tertiary);
}

.unit {
  font-size: 18px;
  color: var(--text-tertiary);
}

.due-hint {
  font-size: 13px;
  max-width: 280px;
  line-height: 1.5;
  margin: 0;
}

.big-btn {
  text-decoration: none;
  padding: 12px 28px;
  font-size: 15px;
  font-weight: 600;
}

/* Stats — 3 compact cards in a row */
.stat-row {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
  flex-shrink: 0;
}

.stat {
  padding: 10px 12px;
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.stat-icon { font-size: 18px; line-height: 1; flex-shrink: 0; }
.stat-info { display: flex; flex-direction: column; min-width: 0; }
.stat-num {
  font-size: 18px;
  font-weight: 800;
  letter-spacing: -0.02em;
  line-height: 1.1;
}
.stat-label { font-size: 11px; }

/* When stacked (narrow screens), allow natural flow */
@media (max-width: 1080px) {
  .body-grid { grid-template-columns: 1fr; }
  .dashboard { flex: none; }
  .preview, .due-big-widget { flex: none; }
  .examples { max-height: 240px; }
  .recent-grid { grid-template-columns: repeat(2, 1fr); }
}
</style>
