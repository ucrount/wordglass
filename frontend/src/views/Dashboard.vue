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

// Just-added word, shown as a rich preview in the main column
const lastAdded = ref<WordOut | null>(null);

const ttsSupported = isSpeechSupported();

async function refreshStats() {
  try {
    const s = await api.stats();
    stats.value = s;
  } catch (e) {
    /* surface elsewhere */
  }
}

async function refreshHeatmap() {
  try {
    heat.value = await api.heatmap(35);
  } catch (e) {
    /* heatmap stays empty on error, not fatal */
  }
}

async function refreshRecent() {
  recentError.value = "";
  try {
    const list = await api.listWords({ limit: 12 });
    recent.value = list;
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
    <!-- Page header -->
    <header class="page-head stagger" style="--stagger: 0">
      <div>
        <h1>主页</h1>
        <p class="muted">粘个单词进来，AI 立刻给你翻译和 5 个不同语境的例句。</p>
      </div>
    </header>

    <!-- Two-column grid -->
    <div class="grid-2col">
      <!-- ─── LEFT MAIN COLUMN ─────────────────────────── -->
      <div class="col-main">
        <!-- Add word search box -->
        <section class="stagger" style="--stagger: 1">
          <AddBar @added="onAdded" />
        </section>

        <!-- Just-added preview -->
        <Transition name="reveal-pop">
          <section v-if="lastAdded" class="preview glass-strong">
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
              <div class="examples-head tertiary">
                <span class="dot-purple" />
                {{ lastAdded.examples.length }} 个不同语境的例句
              </div>
              <div
                v-for="(ex, i) in lastAdded.examples"
                :key="ex.id"
                class="example"
                :style="`--stagger: ${i}`"
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
        </Transition>

        <!-- Recent words -->
        <section class="recent stagger" style="--stagger: 2">
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

          <div v-else class="grid">
            <WordCard v-for="w in recent" :key="w.id" :word="w" />
          </div>
        </section>
      </div>

      <!-- ─── RIGHT SIDEBAR ─────────────────────────────── -->
      <aside class="col-side">
        <!-- Heatmap -->
        <section class="widget glass stagger" style="--stagger: 3">
          <div class="widget-head">
            <h3>学习热力图</h3>
            <span class="tertiary small">近 35 天</span>
          </div>
          <Heatmap :data="heat.days" :weeks="5" />
          <div class="heat-stats">
            <div>
              <span class="big">{{ activeDays }}</span>
              <span class="muted small"> 天有活动</span>
            </div>
            <div>
              <span class="big">{{ totalActions }}</span>
              <span class="muted small"> 次练习</span>
            </div>
          </div>
        </section>

        <!-- Today's due reminder -->
        <section class="widget glass stagger" style="--stagger: 4">
          <div class="widget-head">
            <h3>今日待复习</h3>
          </div>
          <div class="due-big" :class="{ none: stats.due_today === 0 }">
            <span class="num-gradient">{{ stats.due_today }}</span>
            <span class="tertiary small">个</span>
          </div>
          <p class="muted small">
            {{
              stats.due_today === 0
                ? "今天没有需要复习的词，去添加新词吧。"
                : "到点要再见一面的词，趁热打铁。"
            }}
          </p>
          <RouterLink
            v-if="stats.due_today > 0"
            to="/practice"
            class="btn btn-primary block"
          >
            开始练习
          </RouterLink>
        </section>

        <!-- Stats 2x2 -->
        <section class="stat-grid stagger" style="--stagger: 5">
          <div class="stat glass">
            <div class="stat-icon">📚</div>
            <div class="stat-num">{{ stats.total }}</div>
            <div class="muted small">单词总数</div>
          </div>
          <RouterLink to="/practice" class="stat glass clickable">
            <div class="stat-icon">🎯</div>
            <div class="stat-num">{{ stats.due_today }}</div>
            <div class="muted small">今日待复习</div>
          </RouterLink>
          <div class="stat glass">
            <div class="stat-icon">✨</div>
            <div class="stat-num">{{ stats.mastered }}</div>
            <div class="muted small">已掌握</div>
          </div>
          <div class="stat glass">
            <div class="stat-icon">🚀</div>
            <div class="stat-num">{{ stats.added_this_week }}</div>
            <div class="muted small">本周新增</div>
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
  gap: 24px;
}

/* Stagger fade-in */
.stagger {
  animation: stagger-fade 0.55s cubic-bezier(0.16, 1, 0.3, 1) both;
  animation-delay: calc(var(--stagger, 0) * 0.08s);
}
@keyframes stagger-fade {
  from { opacity: 0; transform: translateY(14px); }
  to { opacity: 1; transform: translateY(0); }
}
@media (prefers-reduced-motion: reduce) {
  .stagger { animation: none; }
}

/* Page head */
.page-head h1 {
  font-size: 28px;
  font-weight: 700;
  letter-spacing: -0.02em;
  margin: 0 0 4px;
}
.page-head p {
  margin: 0;
  font-size: 14px;
}

/* Two-column grid */
.grid-2col {
  display: grid;
  grid-template-columns: minmax(0, 1.65fr) minmax(300px, 1fr);
  gap: 24px;
  align-items: start;
}

@media (max-width: 1080px) {
  .grid-2col { grid-template-columns: 1fr; }
}

.col-main, .col-side {
  display: flex;
  flex-direction: column;
  gap: 20px;
  min-width: 0;
}

/* ─── Preview card (just-added word) ─────────────── */
.preview {
  padding: 24px 26px;
  display: flex;
  flex-direction: column;
  gap: 14px;
  border-left: 4px solid var(--brand);
}

.preview-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.word-row {
  display: flex;
  align-items: baseline;
  gap: 10px;
  flex-wrap: wrap;
}

.word-text {
  font-size: clamp(28px, 3.5vw, 36px);
  font-weight: 700;
  letter-spacing: -0.02em;
  color: var(--text-primary);
  line-height: 1.1;
}

.speaker {
  appearance: none;
  border: none;
  background: rgba(0, 0, 0, 0.04);
  width: 34px;
  height: 34px;
  border-radius: 50%;
  font-size: 16px;
  cursor: pointer;
  transition: background 200ms ease, transform 200ms ease;
  align-self: center;
}
[data-theme="dark"] .speaker { background: rgba(255, 255, 255, 0.06); }
.speaker:hover { transform: scale(1.08); background: var(--brand-soft); }

.phonetic {
  font-family: ui-monospace, "SF Mono", Menlo, monospace;
  font-size: 14px;
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
  font-size: 24px;
  line-height: 1;
  color: var(--text-tertiary);
  cursor: pointer;
  padding: 4px 10px;
  border-radius: 8px;
  transition: background 200ms ease;
}
.close:hover { background: rgba(0, 0, 0, 0.05); color: var(--text-primary); }
[data-theme="dark"] .close:hover { background: rgba(255, 255, 255, 0.08); }

.translation {
  font-size: 17px;
  font-weight: 500;
  color: var(--brand);
}

.examples {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-top: 2px;
}

.examples-head {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  margin-bottom: 4px;
}

.dot-purple {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--brand);
}

.example {
  display: flex;
  gap: 12px;
  padding: 12px 14px;
  border-radius: 12px;
  background: var(--glass-bg-dim);
  border: 1px solid var(--hairline);
  animation: stagger-fade 0.5s cubic-bezier(0.16, 1, 0.3, 1) both;
  animation-delay: calc(var(--stagger, 0) * 0.06s + 0.2s);
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

.example-body { min-width: 0; flex: 1; }

.example-en {
  font-size: 15px;
  color: var(--text-primary);
  line-height: 1.5;
}

.example-zh {
  margin-top: 3px;
  font-size: 13px;
  line-height: 1.5;
}

.preview-actions {
  display: flex;
  gap: 10px;
  margin-top: 6px;
}

.preview-actions .btn {
  text-decoration: none;
}

.reveal-pop-enter-active,
.reveal-pop-leave-active {
  transition: opacity 300ms cubic-bezier(0.16, 1, 0.3, 1),
    transform 300ms cubic-bezier(0.16, 1, 0.3, 1);
  overflow: hidden;
}

.reveal-pop-enter-from {
  opacity: 0;
  transform: translateY(-12px) scale(0.98);
}

.reveal-pop-leave-to {
  opacity: 0;
  transform: scale(0.98);
}

/* ─── Right sidebar widgets ───────────────────────── */
.widget {
  padding: 20px 22px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.widget-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
}

.widget-head h3 {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  letter-spacing: -0.01em;
}

.heat-stats {
  display: flex;
  gap: 16px;
  margin-top: 4px;
}

.heat-stats .big {
  font-size: 17px;
  font-weight: 700;
  margin-right: 2px;
}

.due-big {
  display: flex;
  align-items: baseline;
  gap: 6px;
}

.num-gradient {
  font-size: 52px;
  font-weight: 800;
  letter-spacing: -0.025em;
  line-height: 1;
  background: linear-gradient(135deg, #8b5cf6 0%, #ec4899 100%);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
  color: transparent;
}

.due-big.none .num-gradient {
  background: none;
  color: var(--text-tertiary);
  -webkit-text-fill-color: var(--text-tertiary);
}

.btn.block {
  width: 100%;
  text-align: center;
  display: inline-block;
  text-decoration: none;
  margin-top: 4px;
}

/* Stats 2x2 */
.stat-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.stat {
  padding: 16px 18px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  text-decoration: none;
  color: var(--text-primary);
  transition: transform 200ms ease, box-shadow 200ms ease;
}

.stat.clickable:hover {
  transform: translateY(-2px);
  box-shadow: var(--glass-shadow-lg);
}

.stat-icon { font-size: 22px; line-height: 1; }
.stat-num {
  font-size: 26px;
  font-weight: 800;
  letter-spacing: -0.02em;
  line-height: 1.1;
  margin-top: 2px;
}

/* ─── Recent words ─────────────────────────────── */
.section-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  margin-bottom: 12px;
}
.section-head h2 {
  font-size: 17px;
  font-weight: 600;
  letter-spacing: -0.01em;
  margin: 0;
}

.link {
  text-decoration: none;
  color: var(--brand);
  font-size: 13px;
  font-weight: 600;
}

.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 12px;
}

.hint-card {
  padding: 24px;
  text-align: center;
  color: var(--text-secondary);
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.hint-card.error { color: var(--danger); }
.small { font-size: 12px; }
</style>
