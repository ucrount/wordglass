<script setup lang="ts">
import { onMounted, ref } from "vue";
import { RouterLink } from "vue-router";
import { api, type Stats, type WordBrief } from "../api";
import AddBar from "../components/AddBar.vue";
import WordCard from "../components/WordCard.vue";

const stats = ref<Stats>({ total: 0, due_today: 0, mastered: 0, added_this_week: 0 });
const recent = ref<WordBrief[]>([]);
const loadError = ref("");

async function refresh() {
  try {
    const [s, list] = await Promise.all([api.stats(), api.listWords({ limit: 12 })]);
    stats.value = s;
    recent.value = list;
    loadError.value = "";
  } catch (e: any) {
    loadError.value = e.message || "加载失败";
  }
}

onMounted(refresh);
</script>

<template>
  <div class="dashboard">
    <section class="hero">
      <h1>欢迎回来 👋</h1>
      <p class="muted">遇到不认识的单词，扔进来 — 翻译、例句和复习计划，自动给你准备好。</p>
    </section>

    <AddBar @added="refresh" />

    <section class="stats">
      <div class="stat glass">
        <div class="num">{{ stats.total }}</div>
        <div class="label tertiary">单词总数</div>
      </div>
      <RouterLink to="/practice" class="stat glass clickable" :class="{ pulse: stats.due_today > 0 }">
        <div class="num">{{ stats.due_today }}</div>
        <div class="label tertiary">今日待复习</div>
      </RouterLink>
      <div class="stat glass">
        <div class="num">{{ stats.mastered }}</div>
        <div class="label tertiary">已掌握</div>
      </div>
      <div class="stat glass">
        <div class="num">{{ stats.added_this_week }}</div>
        <div class="label tertiary">本周新增</div>
      </div>
    </section>

    <section class="recent">
      <div class="section-head">
        <h2>最近添加</h2>
        <RouterLink to="/library" class="link">查看全部 →</RouterLink>
      </div>

    <div v-if="loadError" class="error glass-dim">
      {{ loadError }}
      <span class="tertiary">— 检查后端是否已启动，或前往设置页配置 AI</span>
    </div>

    <div v-else-if="recent.length === 0" class="empty glass-dim">
      还没有保存的单词，在上面输入框里添加第一个吧 ✨
    </div>

    <div v-else class="grid">
      <WordCard v-for="w in recent" :key="w.id" :word="w" />
    </div>
  </section>
  </div>
</template>

<style scoped>
.hero {
  margin: 8px 0 28px;
}

h1 {
  font-size: 36px;
  font-weight: 700;
  letter-spacing: -0.02em;
  margin: 0 0 8px;
}

.hero p {
  font-size: 16px;
  margin: 0;
}

.stats {
  margin: 32px 0;
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}

@media (max-width: 720px) {
  .stats {
    grid-template-columns: repeat(2, 1fr);
  }
}

.stat {
  padding: 20px 22px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  text-decoration: none;
  color: var(--text-primary);
}

.stat.clickable {
  transition: transform 200ms ease, box-shadow 200ms ease;
}

.stat.clickable:hover {
  transform: translateY(-2px);
  box-shadow: var(--glass-shadow-lg);
}

.stat .num {
  font-size: 36px;
  font-weight: 700;
  letter-spacing: -0.02em;
}

.stat .label {
  font-size: 13px;
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
  border: 2px solid rgba(0, 122, 255, 0.4);
  animation: pulse 1.8s ease-in-out infinite;
  pointer-events: none;
}

@keyframes pulse {
  0%, 100% {
    opacity: 0;
    transform: scale(1);
  }
  50% {
    opacity: 1;
    transform: scale(1.02);
  }
}

.recent {
  margin-top: 12px;
}

.section-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  margin-bottom: 16px;
}

.section-head h2 {
  font-size: 22px;
  font-weight: 600;
  letter-spacing: -0.01em;
  margin: 0;
}

.link {
  text-decoration: none;
  color: var(--accent);
  font-size: 14px;
  font-weight: 500;
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
.error {
  color: var(--danger);
}
</style>
