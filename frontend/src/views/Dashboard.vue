<script setup lang="ts">
import { onMounted, onUnmounted, ref } from "vue";
import { RouterLink } from "vue-router";
import { api, type Stats, type WordBrief, type WordOut } from "../api";
import AddBar from "../components/AddBar.vue";
import WeakWords from "../components/WeakWords.vue";
import WordCard from "../components/WordCard.vue";
import { isSpeechSupported, speak } from "../composables/tts";

const stats = ref<Stats>({ total: 0, due_today: 0, mastered: 0, added_this_week: 0 });
const recent = ref<WordBrief[]>([]);
const recentError = ref("");
const initialLoad = ref(true);
const lastAdded = ref<WordOut | null>(null);
const enriching = ref(false);

const ttsSupported = isSpeechSupported();

async function refreshStats() {
  try { stats.value = await api.stats(); } catch { /* ignore */ }
}
async function refreshRecent() {
  recentError.value = "";
  try {
    const list = await api.listWords({ limit: 4 });
    recent.value = list;
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
  await Promise.all([refreshStats(), refreshRecent()]);
  initialLoad.value = false;
}

let pollTimer: ReturnType<typeof setTimeout> | null = null;
function stopPolling() {
  if (pollTimer) {
    clearTimeout(pollTimer);
    pollTimer = null;
  }
  enriching.value = false;
}

function pollEnrichment(wordId: number) {
  stopPolling();
  const deadline = Date.now() + 18_000;
  const tick = async () => {
    if (Date.now() > deadline) { stopPolling(); return; }
    try {
      const fresh = await api.getWord(wordId);
      if (lastAdded.value && lastAdded.value.id === wordId) {
        lastAdded.value = fresh;
      }
      const done = !!fresh.category && fresh.examples.length > 0;
      if (done) { stopPolling(); refreshRecent(); return; }
    } catch { /* keep polling */ }
    pollTimer = setTimeout(tick, 1500);
  };
  enriching.value = true;
  pollTimer = setTimeout(tick, 1500);
}

function onAdded(w: WordOut) {
  lastAdded.value = w;
  refreshStats();
  refreshRecent();
  if (ttsSupported) setTimeout(() => speak(w.text), 100);
  if (!w.category || w.examples.length === 0) {
    pollEnrichment(w.id);
  }
}

onMounted(refreshAll);
onUnmounted(stopPolling);
</script>

<template>
  <div class="dashboard">
    <header class="page-head">
      <h1>主页</h1>
      <p class="muted small">粘个英文单词，AI 立刻翻译 + 3 个例句</p>
    </header>

    <div class="body-grid">
      <!-- ─── LEFT MAIN COLUMN ─────────────────────────── -->
      <div class="col-main">
        <AddBar @added="onAdded" class="addbar" />

        <!-- Hero preview — flex: 1 fills vertical space -->
        <section class="preview glass-strong">
          <template v-if="lastAdded">
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
            <div class="translation">{{ lastAdded.translation || "（无翻译）" }}</div>

            <div class="examples">
              <div
                v-for="(ex, i) in lastAdded.examples"
                :key="ex.id"
                class="example"
              >
                <div class="example-num">{{ i + 1 }}</div>
                <div class="example-body">
                  <div class="example-en">{{ ex.en }}</div>
                  <div v-if="ex.zh" class="example-zh">{{ ex.zh }}</div>
                </div>
              </div>
              <div v-if="lastAdded.examples.length === 0" class="examples-empty">
                这个词暂无例句
              </div>
            </div>
          </template>

          <template v-else-if="initialLoad">
            <div class="empty-state">
              <p class="muted">加载中…</p>
            </div>
          </template>

          <template v-else>
            <div class="empty-state">
              <div class="emoji">👋</div>
              <p class="muted">在上方输入框粘一个英文单词</p>
              <p class="tertiary small">AI 立刻给你翻译和 3 个不同语境的例句</p>
            </div>
          </template>
        </section>

        <!-- Recent: 4 cards in one row -->
        <section class="recent-section">
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
        <!-- Consolidated stats card: due (big) + 3 mini stats -->
        <section class="stats-card glass">
          <div class="due-row">
            <span class="due-num" :class="{ none: stats.due_today === 0 }">{{ stats.due_today }}</span>
            <span class="due-unit">个</span>
          </div>
          <p class="due-hint">
            {{
              stats.due_today === 0
                ? "今天没有需要复习的词，加几个新词吧"
                : "今日待复习 · 趁热打铁巩固"
            }}
          </p>
          <RouterLink
            to="/practice"
            class="btn btn-primary due-btn"
          >
            {{ stats.due_today > 0 ? "开始练习 →" : "去练习页" }}
          </RouterLink>
          <div class="stats-row">
            <div class="stat-mini">
              <div class="stat-num">{{ stats.total }}</div>
              <div class="stat-label">总数</div>
            </div>
            <div class="stat-mini">
              <div class="stat-num">{{ stats.mastered }}</div>
              <div class="stat-label">已掌握</div>
            </div>
            <div class="stat-mini">
              <div class="stat-num">{{ stats.added_this_week }}</div>
              <div class="stat-label">本周</div>
            </div>
          </div>
        </section>

        <!-- Weak words: fills remaining vertical space -->
        <div class="weak-fill">
          <WeakWords />
        </div>
      </aside>
    </div>
  </div>
</template>

<style scoped>
.dashboard {
  display: flex;
  flex-direction: column;
  gap: 22px;
  height: calc(100vh - 68px);
  min-height: 0;
}

/* Page head */
.page-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 14px;
  flex-shrink: 0;
  flex-wrap: wrap;
}
.page-head h1 {
  font-family: var(--font-serif);
  font-size: 26px;
  font-weight: 700;
  letter-spacing: -0.02em;
  margin: 0;
}
.page-head p {
  margin: 0;
  font-size: 12px;
  color: var(--text-tertiary);
}
.small { font-size: 12px; }

/* Body grid */
.body-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.6fr) 260px;
  gap: 22px;
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

/* ─── LEFT ────────────────────────────────────────── */

.addbar { flex-shrink: 0; }

.preview {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  padding: 22px 26px;
  border-left: 3px solid var(--brand);
  gap: 6px;
}

.word-row {
  display: flex;
  align-items: baseline;
  gap: 14px;
  flex-wrap: wrap;
  flex-shrink: 0;
}

.word-text {
  font-family: var(--font-serif);
  font-size: 34px;
  font-weight: 700;
  letter-spacing: -0.02em;
  line-height: 1.1;
  color: var(--text-primary);
}

.speaker {
  appearance: none;
  border: none;
  background: var(--glass-bg-dim);
  width: 32px;
  height: 32px;
  border-radius: 50%;
  font-size: 14px;
  cursor: pointer;
  align-self: center;
  transition: background 200ms, transform 200ms;
}
.speaker:hover { background: var(--brand-soft); transform: scale(1.08); }

.phonetic {
  font-family: var(--font-mono);
  font-size: 13px;
  color: var(--text-tertiary);
}

.pos {
  font-family: var(--font-serif);
  font-style: italic;
  font-size: 12px;
  padding: 1px 8px;
  border-radius: 6px;
  background: var(--brand-soft);
  color: var(--brand);
}

.translation {
  font-size: 16px;
  font-weight: 500;
  color: var(--accent);
  flex-shrink: 0;
  word-wrap: break-word;
}

.examples {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-top: 14px;
}

.example {
  flex: 1;
  min-height: 0;
  display: flex;
  gap: 14px;
  padding: 14px 16px;
  border-radius: 12px;
  background: color-mix(in srgb, var(--brand) 5%, transparent);
  border: 1px solid var(--hairline);
  align-items: flex-start;
}

.example-num {
  flex-shrink: 0;
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: var(--brand-soft);
  color: var(--brand);
  font-size: 11px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
}

.example-body {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 5px;
}

.example-en {
  font-family: var(--font-serif);
  font-style: italic;
  font-size: 14.5px;
  line-height: 1.6;
  color: var(--text-primary);
}

.example-zh {
  font-size: 12px;
  color: var(--text-tertiary);
  line-height: 1.55;
}

.examples-empty {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-secondary);
  font-size: 13px;
}

.empty-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6px;
  text-align: center;
  color: var(--text-secondary);
}
.empty-state .emoji { font-size: 40px; line-height: 1; }
.empty-state p { margin: 0; }
.muted { color: var(--text-secondary); }
.tertiary { color: var(--text-tertiary); }

/* Recent */
.recent-section { flex-shrink: 0; }

.section-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  margin-bottom: 8px;
}
.section-head h2 {
  margin: 0;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--text-secondary);
}
.link {
  text-decoration: none;
  color: var(--brand);
  font-size: 11px;
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

/* ─── RIGHT ───────────────────────────────────────── */

.stats-card {
  padding: 22px 22px 18px;
  text-align: center;
  flex-shrink: 0;
}

.due-row {
  display: flex;
  align-items: baseline;
  justify-content: center;
  gap: 6px;
}

.due-num {
  font-family: var(--font-serif);
  font-size: 68px;
  font-weight: 700;
  line-height: 1;
  background: linear-gradient(135deg, var(--brand) 0%, var(--accent) 100%);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
  color: transparent;
  letter-spacing: -0.03em;
}
.due-num.none {
  background: none;
  -webkit-text-fill-color: var(--text-tertiary);
  color: var(--text-tertiary);
}

.due-unit {
  font-size: 13px;
  color: var(--text-tertiary);
}

.due-hint {
  font-size: 12px;
  color: var(--text-secondary);
  margin: 6px 0 14px;
  line-height: 1.45;
}

.due-btn {
  display: inline-block;
  padding: 8px 22px;
  border-radius: 999px;
  font-size: 12.5px;
  font-weight: 700;
  letter-spacing: 0.02em;
  text-decoration: none;
}

.stats-row {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  margin-top: 18px;
  padding-top: 16px;
  border-top: 1px solid var(--hairline);
}

.stat-mini {
  text-align: center;
}

.stat-num {
  font-family: var(--font-serif);
  font-size: 22px;
  font-weight: 700;
  color: var(--text-primary);
  line-height: 1;
}

.stat-label {
  font-size: 10px;
  color: var(--text-tertiary);
  margin-top: 4px;
  letter-spacing: 0.04em;
}

.weak-fill {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}
.weak-fill > :deep(.weak-widget) {
  flex: 1;
  min-height: 0;
}

/* ─── Mobile ──────────────────────────────────────── */
@media (max-width: 1080px) {
  .dashboard {
    height: auto;
    min-height: 0;
  }
  .body-grid {
    grid-template-columns: 1fr;
    flex: 0 0 auto;
  }
  .recent-grid {
    grid-template-columns: repeat(2, 1fr);
  }
  .preview {
    min-height: 280px;
    flex: 0 0 auto;
  }
  .example {
    flex: 0 0 auto;
  }
  .weak-fill {
    flex: 0 0 auto;
  }
}
</style>
