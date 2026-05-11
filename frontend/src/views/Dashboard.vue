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

const FEATURES = [
  {
    icon: "🪄",
    title: "AI 一次给齐",
    body: "粘个单词，自动返回中文释义、IPA 音标、词性标签，外加 3 个真实场景下的英文例句和翻译。",
  },
  {
    icon: "🗓️",
    title: "智能阶梯复习",
    body: "答错的明天再见、答对的隔得越来越远（1d / 3d / 7d / 21d / 60d），到时间它会出现在练习列表，你不用管。",
  },
  {
    icon: "🎮",
    title: "字母方格练习",
    body: "看中文敲英文，一个字母一个方格，敲对就亮、敲错就抖。比单纯背诵留下来的肌肉记忆深得多。",
  },
  {
    icon: "🎧",
    title: "听写训练",
    body: "浏览器原生发音引擎自动朗读单词，听完直接敲，按 S 重听。强化「听到立刻反应」的能力。",
  },
];

onMounted(refresh);
</script>

<template>
  <div class="dashboard">
    <!-- ─── Hero ─────────────────────────────────────────── -->
    <section class="hero">
      <div class="badge stagger" style="--stagger: 0">
        <span class="dot-anim" />
        AI 翻译 · 即时例句 · 智能复习
      </div>

      <h1 class="title stagger" style="--stagger: 1">
        把陌生的单词，<br />
        逼成你的 <span class="highlight">掌握</span>
      </h1>

      <p class="tagline stagger muted" style="--stagger: 2">
        AI 自动准备翻译、音标和真实例句，三种练习模式陪你反复敲，
        <br class="mobile-hide" />
        直到看到就能脱口而出。
      </p>

      <div class="cta-wrap stagger" style="--stagger: 3">
        <AddBar @added="refresh" />
      </div>
    </section>

    <!-- ─── Stats ────────────────────────────────────────── -->
    <section class="stats">
      <div class="stat glass stagger" style="--stagger: 4">
        <div class="num">{{ stats.total }}</div>
        <div class="label tertiary">单词总数</div>
      </div>
      <RouterLink
        to="/practice"
        class="stat glass clickable stagger"
        :class="{ pulse: stats.due_today > 0 }"
        style="--stagger: 5"
      >
        <div class="num">{{ stats.due_today }}</div>
        <div class="label tertiary">今日待复习</div>
      </RouterLink>
      <div class="stat glass stagger" style="--stagger: 6">
        <div class="num">{{ stats.mastered }}</div>
        <div class="label tertiary">已掌握</div>
      </div>
      <div class="stat glass stagger" style="--stagger: 7">
        <div class="num">{{ stats.added_this_week }}</div>
        <div class="label tertiary">本周新增</div>
      </div>
    </section>

    <!-- ─── Why ──────────────────────────────────────────── -->
    <section class="why">
      <div class="section-title">
        <h2>为什么这样设计</h2>
        <p class="muted">把「认识」练成「会用」，每个环节都有依据</p>
      </div>
      <div class="features">
        <div
          v-for="(f, i) in FEATURES"
          :key="f.title"
          class="feature glass"
          :style="`--stagger: ${i}`"
        >
          <div class="feature-icon">{{ f.icon }}</div>
          <h3>{{ f.title }}</h3>
          <p class="muted">{{ f.body }}</p>
        </div>
      </div>
    </section>

    <!-- ─── Recent ───────────────────────────────────────── -->
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
.dashboard {
  display: flex;
  flex-direction: column;
  gap: 64px;
  padding-bottom: 40px;
}

/* ─── Hero ─────────────────────────────────────────── */
.hero {
  text-align: center;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 24px;
  padding: 56px 0 16px;
}

.badge {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 6px 16px;
  border-radius: 999px;
  background: var(--glass-bg-strong);
  backdrop-filter: blur(16px);
  border: 1px solid var(--glass-border);
  font-size: 13px;
  font-weight: 500;
  color: var(--text-secondary);
  letter-spacing: -0.005em;
  box-shadow: var(--glass-shadow);
}

.dot-anim {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--brand);
  box-shadow: 0 0 0 0 var(--brand);
  animation: ping 1.8s ease-in-out infinite;
}

@keyframes ping {
  0%, 100% { box-shadow: 0 0 0 0 rgba(139, 92, 246, 0); }
  50% { box-shadow: 0 0 0 5px rgba(139, 92, 246, 0); }
}

.title {
  font-size: clamp(36px, 6.5vw, 64px);
  font-weight: 800;
  letter-spacing: -0.03em;
  line-height: 1.1;
  margin: 0;
  color: var(--text-primary);
}

.highlight {
  position: relative;
  display: inline-block;
  background: linear-gradient(135deg, #8b5cf6 0%, #d946ef 50%, #ec4899 100%);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
  color: transparent;
}

.highlight::after {
  content: "";
  position: absolute;
  left: -4%;
  right: -4%;
  bottom: 4%;
  height: 14%;
  background: linear-gradient(90deg, rgba(139, 92, 246, 0.25), rgba(236, 72, 153, 0.25));
  border-radius: 6px;
  z-index: -1;
  filter: blur(2px);
}

.tagline {
  font-size: clamp(15px, 1.6vw, 17px);
  line-height: 1.55;
  max-width: 580px;
  margin: 0;
}

.cta-wrap {
  width: 100%;
  max-width: 560px;
  margin-top: 8px;
}

/* ─── Stats ────────────────────────────────────────── */
.stats {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 14px;
}

.stat {
  padding: 22px 24px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  text-decoration: none;
  color: var(--text-primary);
  transition: transform 200ms ease, box-shadow 200ms ease;
}

.stat.clickable:hover {
  transform: translateY(-3px);
  box-shadow: var(--glass-shadow-lg);
}

.stat .num {
  font-size: 40px;
  font-weight: 800;
  letter-spacing: -0.025em;
  line-height: 1;
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
  border: 2px solid var(--accent);
  opacity: 0.4;
  animation: pulse 1.8s ease-in-out infinite;
  pointer-events: none;
}

@keyframes pulse {
  0%, 100% { opacity: 0; transform: scale(1); }
  50% { opacity: 0.8; transform: scale(1.02); }
}

/* ─── Section ─────────────────────────────────────── */
.section-title {
  text-align: center;
  margin-bottom: 28px;
}

.section-title h2,
.section-head h2 {
  font-size: clamp(24px, 3vw, 32px);
  font-weight: 700;
  letter-spacing: -0.02em;
  margin: 0 0 6px;
}

.section-title p {
  margin: 0;
  font-size: 15px;
}

/* ─── Features ────────────────────────────────────── */
.features {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}

.feature {
  padding: 28px 24px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  transition: transform 250ms ease, box-shadow 250ms ease, background 250ms ease;
  animation: stagger-reveal 0.7s cubic-bezier(0.16, 1, 0.3, 1) both;
  animation-delay: calc(var(--stagger, 0) * 0.1s + 0.2s);
}

@keyframes stagger-reveal {
  from { opacity: 0; transform: translateY(20px); }
  to { opacity: 1; transform: translateY(0); }
}

.feature:hover {
  transform: translateY(-4px);
  box-shadow: var(--glass-shadow-lg);
}

.feature-icon {
  font-size: 32px;
  line-height: 1;
  margin-bottom: 4px;
}

.feature h3 {
  margin: 0;
  font-size: 17px;
  font-weight: 600;
  letter-spacing: -0.01em;
}

.feature p {
  margin: 0;
  font-size: 13.5px;
  line-height: 1.55;
}

/* ─── Recent ──────────────────────────────────────── */
.section-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  margin-bottom: 16px;
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

.empty, .error {
  padding: 28px;
  text-align: center;
  color: var(--text-secondary);
}
.error { color: var(--danger); }

/* ─── Responsive ──────────────────────────────────── */
@media (max-width: 900px) {
  .stats { grid-template-columns: repeat(2, 1fr); }
  .features { grid-template-columns: repeat(2, 1fr); }
}

@media (max-width: 540px) {
  .features { grid-template-columns: 1fr; }
  .hero { padding-top: 32px; gap: 18px; }
  .stat { padding: 18px; }
  .stat .num { font-size: 32px; }
  .feature { padding: 22px 20px; }
  .mobile-hide { display: none; }
  .dashboard { gap: 48px; }
}
</style>
