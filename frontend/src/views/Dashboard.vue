<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { RouterLink } from "vue-router";
import { api, type HeatmapData, type Stats, type WordBrief } from "../api";
import AddBar from "../components/AddBar.vue";
import Heatmap from "../components/Heatmap.vue";
import WordCard from "../components/WordCard.vue";

const stats = ref<Stats>({ total: 0, due_today: 0, mastered: 0, added_this_week: 0 });
const recent = ref<WordBrief[]>([]);
const heat = ref<HeatmapData>({ days: {}, since: "" });
const loadError = ref("");

async function refresh() {
  try {
    const [s, list, h] = await Promise.all([
      api.stats(),
      api.listWords({ limit: 12 }),
      api.heatmap(35),
    ]);
    stats.value = s;
    recent.value = list;
    heat.value = h;
    loadError.value = "";
  } catch (e: any) {
    loadError.value = e.message || "加载失败";
  }
}

const activeDays = computed(() => Object.keys(heat.value.days).length);
const totalActions = computed(() =>
  Object.values(heat.value.days).reduce((a, b) => a + b, 0)
);

onMounted(refresh);
</script>

<template>
  <div class="dashboard">
    <!-- Page header -->
    <header class="page-head stagger" style="--stagger: 0">
      <div>
        <h1>主页</h1>
        <p class="muted">今天来背几个词，反复练，直到看到就脱口而出。</p>
      </div>
    </header>

    <!-- Row 1: Due review (left) + Heatmap (right) -->
    <section class="row row-top">
      <div class="widget glass stagger" style="--stagger: 1">
        <div class="widget-head">
          <h2>今日待复习</h2>
          <RouterLink v-if="stats.due_today > 0" to="/practice" class="link-arrow">
            开始练习 →
          </RouterLink>
        </div>
        <div class="due-body">
          <div class="due-number" :class="{ none: stats.due_today === 0 }">
            <span class="big">{{ stats.due_today }}</span>
            <span class="unit">个</span>
          </div>
          <p v-if="stats.due_today === 0" class="muted small">
            今天没有待复习的词。添加新词或明天再来。
          </p>
          <p v-else class="muted small">
            到点要再见一面的词，趁热打铁巩固一下吧。
          </p>
        </div>
        <AddBar @added="refresh" />
      </div>

      <div class="widget glass stagger" style="--stagger: 2">
        <div class="widget-head">
          <h2>学习热力图</h2>
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
      </div>
    </section>

    <!-- Row 2: 4 stat cards -->
    <section class="row stats">
      <div class="stat glass stagger" style="--stagger: 3">
        <div class="stat-icon">📚</div>
        <div>
          <div class="num">{{ stats.total }}</div>
          <div class="muted small">单词总数</div>
        </div>
      </div>
      <RouterLink
        to="/practice"
        class="stat glass clickable stagger"
        :class="{ pulse: stats.due_today > 0 }"
        style="--stagger: 4"
      >
        <div class="stat-icon">🎯</div>
        <div>
          <div class="num">{{ stats.due_today }}</div>
          <div class="muted small">今日待复习</div>
        </div>
      </RouterLink>
      <div class="stat glass stagger" style="--stagger: 5">
        <div class="stat-icon">✨</div>
        <div>
          <div class="num">{{ stats.mastered }}</div>
          <div class="muted small">已掌握</div>
        </div>
      </div>
      <div class="stat glass stagger" style="--stagger: 6">
        <div class="stat-icon">🚀</div>
        <div>
          <div class="num">{{ stats.added_this_week }}</div>
          <div class="muted small">本周新增</div>
        </div>
      </div>
    </section>

    <!-- Row 3: Recent words -->
    <section class="recent stagger" style="--stagger: 7">
      <div class="section-head">
        <h2>最近添加</h2>
        <RouterLink to="/library" class="link">查看全部 →</RouterLink>
      </div>

      <div v-if="loadError" class="error glass-dim">
        {{ loadError }}
        <span class="tertiary">— 检查后端是否已启动，或前往设置页配置 AI</span>
      </div>

      <div v-else-if="recent.length === 0" class="empty glass-dim">
        还没有保存的单词，在上方输入框里添加第一个吧 ✨
      </div>

      <div v-else class="grid">
        <WordCard v-for="w in recent" :key="w.id" :word="w" />
      </div>
    </section>
  </div>
</template>

<style scoped>
.dashboard {
  display: flex;
  flex-direction: column;
  gap: 32px;
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

/* Stagger utility (page-level, custom faster) */
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

/* Row 1: due + heatmap */
.row-top {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

@media (max-width: 900px) {
  .row-top { grid-template-columns: 1fr; }
}

.widget {
  padding: 22px 24px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.widget-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
}

.widget-head h2 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  letter-spacing: -0.01em;
}

.link-arrow {
  text-decoration: none;
  color: var(--brand);
  font-size: 13px;
  font-weight: 600;
  transition: opacity 200ms ease;
}

.link-arrow:hover {
  opacity: 0.75;
}

.due-body {
  margin-bottom: 4px;
}

.due-number {
  display: flex;
  align-items: baseline;
  gap: 6px;
  margin-bottom: 4px;
}

.due-number .big {
  font-size: 48px;
  font-weight: 800;
  letter-spacing: -0.025em;
  line-height: 1;
  background: linear-gradient(135deg, #8b5cf6 0%, #ec4899 100%);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
  -webkit-text-fill-color: transparent;
}

.due-number.none .big {
  background: none;
  color: var(--text-tertiary);
  -webkit-text-fill-color: var(--text-tertiary);
}

.due-number .unit {
  font-size: 14px;
  color: var(--text-tertiary);
}

.small { font-size: 13px; }

.heat-stats {
  display: flex;
  gap: 18px;
  margin-top: 6px;
}

.heat-stats .big {
  font-size: 18px;
  font-weight: 700;
  margin-right: 2px;
}

/* Row 2: stats */
.stats {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 14px;
}

.stat {
  padding: 18px 20px;
  display: flex;
  align-items: center;
  gap: 14px;
  text-decoration: none;
  color: var(--text-primary);
  transition: transform 200ms ease, box-shadow 200ms ease;
}

.stat.clickable:hover {
  transform: translateY(-3px);
  box-shadow: var(--glass-shadow-lg);
}

.stat-icon {
  font-size: 28px;
  line-height: 1;
}

.stat .num {
  font-size: 28px;
  font-weight: 800;
  letter-spacing: -0.02em;
  line-height: 1.1;
}

.stat.pulse {
  position: relative;
  overflow: hidden;
}

.stat.pulse::after {
  content: "";
  position: absolute;
  inset: 0;
  border-radius: inherit;
  border: 2px solid var(--brand);
  opacity: 0.4;
  animation: pulse 1.8s ease-in-out infinite;
  pointer-events: none;
}

@keyframes pulse {
  0%, 100% { opacity: 0; transform: scale(1); }
  50% { opacity: 0.8; transform: scale(1.02); }
}

@media (max-width: 900px) {
  .stats { grid-template-columns: repeat(2, 1fr); }
}

/* Recent words */
.section-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  margin-bottom: 14px;
}

.section-head h2 {
  font-size: 18px;
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
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 14px;
}

.empty,
.error {
  padding: 28px;
  text-align: center;
  color: var(--text-secondary);
}
.error { color: var(--danger); }

@media (max-width: 540px) {
  .stat-icon { font-size: 22px; }
  .stat .num { font-size: 22px; }
  .due-number .big { font-size: 38px; }
}
</style>
