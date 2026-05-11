<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from "vue";
import { RouterLink } from "vue-router";
import { api, type ReviewResult, type WordOut } from "../api";

type Mode = "word" | "sentence";

const MODES: { value: Mode; label: string; hint: string }[] = [
  { value: "word", label: "仅单词", hint: "看英文回想中文释义" },
  { value: "sentence", label: "单词 + 句子", hint: "看例句填空，结合上下文回想" },
];

const RATINGS: { value: ReviewResult; label: string; key: string; cls: string }[] = [
  { value: "again", label: "不会", key: "1", cls: "again" },
  { value: "hard", label: "模糊", key: "2", cls: "hard" },
  { value: "good", label: "认识", key: "3", cls: "good" },
  { value: "easy", label: "熟练", key: "4", cls: "easy" },
];

const mode = ref<Mode>("word");
const queue = ref<WordOut[]>([]);
const current = ref(0);
const revealed = ref(false);
const submitting = ref(false);
const loading = ref(true);
const loadError = ref("");
const session = ref({ done: 0, correct: 0 });

const word = computed<WordOut | null>(() => queue.value[current.value] ?? null);
const total = computed(() => queue.value.length);
const finished = computed(() => total.value > 0 && current.value >= total.value);

async function load() {
  loading.value = true;
  loadError.value = "";
  try {
    queue.value = await api.dueWords(50);
    current.value = 0;
    revealed.value = false;
    session.value = { done: 0, correct: 0 };
  } catch (e: any) {
    loadError.value = e.message || "加载失败";
  } finally {
    loading.value = false;
  }
}

function reveal() {
  if (revealed.value || !word.value) return;
  revealed.value = true;
}

async function rate(result: ReviewResult) {
  if (!revealed.value || submitting.value || !word.value) return;
  submitting.value = true;
  if (result === "good" || result === "easy") session.value.correct += 1;
  session.value.done += 1;
  try {
    await api.submitReview(word.value.id, mode.value, result);
  } catch {
    // ignore — local progress matters more than backend sync for this card
  }
  setTimeout(() => {
    revealed.value = false;
    current.value += 1;
    submitting.value = false;
  }, 220);
}

// Build a cloze sentence: replace the target word (any inflection) with blanks.
const cloze = computed(() => {
  const w = word.value;
  if (!w || !w.examples?.length) return null;
  const ex = w.examples[0];
  const safe = w.text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  // match the stem + optional letters/apostrophe so "run" matches "running", "child" matches "children"
  const re = new RegExp(`\\b${safe}[\\w']*\\b`, "i");
  const match = ex.en.match(re);
  const blanked = match ? ex.en.replace(re, "_____") : ex.en;
  return { en: ex.en, zh: ex.zh, blanked, found: !!match };
});

function handleKey(e: KeyboardEvent) {
  if (loading.value || finished.value || total.value === 0) return;
  if ((e.target as HTMLElement)?.tagName === "INPUT") return;
  if (e.key === " " || e.key === "Enter") {
    e.preventDefault();
    if (!revealed.value) reveal();
    return;
  }
  if (revealed.value) {
    const r = RATINGS.find((r) => r.key === e.key);
    if (r) rate(r.value);
  }
}

onMounted(() => {
  window.addEventListener("keydown", handleKey);
  load();
});
onUnmounted(() => {
  window.removeEventListener("keydown", handleKey);
});
</script>

<template>
  <div class="practice">
    <!-- Header (only while actively reviewing) -->
    <div v-if="!loading && !loadError && total > 0 && !finished" class="header">
      <div class="modes glass">
        <button
          v-for="m in MODES"
          :key="m.value"
          :class="{ active: mode === m.value }"
          @click="mode = m.value"
        >
          {{ m.label }}
        </button>
      </div>
      <div class="progress">
        <span class="num">{{ current + 1 }}</span>
        <span class="tertiary"> / {{ total }}</span>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="state glass">
      <div class="big-emoji">⏳</div>
      <p class="muted">加载今日待复习…</p>
    </div>

    <!-- Error -->
    <div v-else-if="loadError" class="state glass">
      <div class="big-emoji">⚠️</div>
      <p class="error-msg">{{ loadError }}</p>
      <button class="btn" @click="load">重试</button>
    </div>

    <!-- No due words -->
    <div v-else-if="total === 0" class="state glass">
      <div class="big-emoji">✨</div>
      <h2>今天没有需要复习的单词</h2>
      <p class="muted">去添加几个新单词，或者明天再来吧。</p>
      <RouterLink to="/" class="btn btn-primary">返回首页</RouterLink>
    </div>

    <!-- Session complete -->
    <div v-else-if="finished" class="state glass finished">
      <div class="big-emoji">🎉</div>
      <h2>这一组完成了</h2>
      <div class="result-stats">
        <div><span class="big">{{ session.done }}</span><span class="muted"> 张</span></div>
        <div class="dot tertiary">·</div>
        <div><span class="big good">{{ session.correct }}</span><span class="muted"> 答对</span></div>
      </div>
      <div class="actions">
        <button class="btn btn-primary" @click="load">再来一组</button>
        <RouterLink to="/" class="btn btn-ghost">回首页</RouterLink>
      </div>
    </div>

    <!-- Active card -->
    <div v-else-if="word" class="card-stage">
      <Transition name="card" mode="out-in">
        <div :key="word.id + '-' + mode" class="flash glass-strong">
          <!-- Word-only mode -->
          <template v-if="mode === 'word'">
            <div class="word-text">{{ word.text }}</div>
            <div v-if="word.phonetic" class="phonetic">{{ word.phonetic }}</div>
            <div v-if="word.pos" class="pos">{{ word.pos }}</div>

            <Transition name="reveal">
              <div v-if="revealed" class="answer">
                <div class="translation">{{ word.translation || "（无翻译）" }}</div>
                <div v-if="word.examples?.length" class="example">
                  <div class="en">{{ word.examples[0].en }}</div>
                  <div v-if="word.examples[0].zh" class="zh tertiary">
                    {{ word.examples[0].zh }}
                  </div>
                </div>
              </div>
            </Transition>
          </template>

          <!-- Sentence cloze mode -->
          <template v-else>
            <template v-if="cloze">
              <div class="prompt-hint tertiary">填入缺失的单词</div>
              <div class="sentence">{{ cloze.blanked }}</div>
              <div v-if="cloze.zh" class="sentence-zh tertiary">{{ cloze.zh }}</div>

              <Transition name="reveal">
                <div v-if="revealed" class="answer">
                  <div class="word-text small">{{ word.text }}</div>
                  <div v-if="word.phonetic" class="phonetic">{{ word.phonetic }}</div>
                  <div class="translation">{{ word.translation || "（无翻译）" }}</div>
                </div>
              </Transition>
            </template>
            <template v-else>
              <div class="word-text">{{ word.text }}</div>
              <p class="muted small-note">这个词暂无例句，下方按钮可继续，或切回「仅单词」模式</p>

              <Transition name="reveal">
                <div v-if="revealed" class="answer">
                  <div class="translation">{{ word.translation || "（无翻译）" }}</div>
                </div>
              </Transition>
            </template>
          </template>
        </div>
      </Transition>

      <!-- Actions -->
      <div class="actions" :class="{ flipped: revealed }">
        <button v-if="!revealed" class="btn btn-primary big" @click="reveal">
          显示答案 <span class="kbd">空格</span>
        </button>
        <div v-else class="ratings">
          <button
            v-for="r in RATINGS"
            :key="r.value"
            class="btn rating"
            :class="r.cls"
            :disabled="submitting"
            @click="rate(r.value)"
          >
            <div class="label">{{ r.label }}</div>
            <div class="kbd small">{{ r.key }}</div>
          </button>
        </div>
      </div>

      <div class="hint tertiary">
        快捷键：空格 翻面 · 1 不会 · 2 模糊 · 3 认识 · 4 熟练
      </div>
    </div>
  </div>
</template>

<style scoped>
.practice {
  display: flex;
  flex-direction: column;
  gap: 24px;
  min-height: 70vh;
}

/* ─── Header ───────────────────────────────────────── */
.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.modes {
  display: inline-flex;
  padding: 4px;
  border-radius: 999px;
  border-radius: 999px;
}

.modes button {
  appearance: none;
  background: transparent;
  border: none;
  padding: 8px 18px;
  border-radius: 999px;
  font: inherit;
  font-weight: 500;
  font-size: 14px;
  color: var(--text-secondary);
  cursor: pointer;
  transition: background 200ms ease, color 200ms ease, box-shadow 200ms ease;
}

.modes button.active {
  background: rgba(255, 255, 255, 0.85);
  color: var(--text-primary);
  box-shadow: 0 2px 6px rgba(31, 38, 135, 0.1);
}

.progress {
  font-size: 14px;
  color: var(--text-tertiary);
}

.progress .num {
  font-size: 20px;
  font-weight: 700;
  color: var(--text-primary);
}

/* ─── State cards (loading / error / empty / done) ─── */
.state {
  padding: 64px 32px;
  text-align: center;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  margin-top: 24px;
}

.big-emoji {
  font-size: 64px;
  line-height: 1;
  margin-bottom: 6px;
}

.state h2 {
  margin: 4px 0 0;
  font-size: 26px;
  font-weight: 600;
  letter-spacing: -0.01em;
}

.error-msg {
  color: var(--danger);
}

.finished .result-stats {
  display: flex;
  gap: 18px;
  align-items: baseline;
  margin-top: 12px;
  font-size: 18px;
}

.finished .big {
  font-size: 40px;
  font-weight: 700;
  letter-spacing: -0.02em;
  color: var(--text-primary);
}

.finished .big.good {
  color: var(--success);
}

.state .actions {
  margin-top: 20px;
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  justify-content: center;
}

/* ─── Card ─────────────────────────────────────────── */
.card-stage {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 28px;
}

.flash {
  width: 100%;
  min-height: 340px;
  padding: 56px 48px;
  border-radius: var(--radius-xl);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 14px;
}

.word-text {
  font-size: clamp(40px, 8vw, 60px);
  font-weight: 700;
  letter-spacing: -0.02em;
  color: var(--text-primary);
  text-align: center;
  line-height: 1.1;
}

.word-text.small {
  font-size: clamp(28px, 5vw, 36px);
}

.phonetic {
  font-family: ui-monospace, "SF Mono", Menlo, monospace;
  font-size: 16px;
  color: var(--text-tertiary);
}

.pos {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 8px;
  background: rgba(0, 0, 0, 0.05);
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: 4px;
}

.prompt-hint {
  font-size: 12px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.sentence {
  font-size: clamp(22px, 4vw, 30px);
  font-weight: 500;
  line-height: 1.45;
  max-width: 560px;
  text-align: center;
  letter-spacing: -0.01em;
}

.sentence-zh {
  font-size: 14px;
}

.small-note {
  font-size: 13px;
  max-width: 320px;
  text-align: center;
}

.answer {
  margin-top: 24px;
  padding-top: 24px;
  border-top: 1px solid rgba(0, 0, 0, 0.08);
  width: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
}

.translation {
  font-size: 22px;
  font-weight: 500;
  color: var(--accent);
  text-align: center;
  line-height: 1.3;
}

.example {
  margin-top: 10px;
  max-width: 520px;
  text-align: center;
}

.example .en {
  font-size: 16px;
  color: var(--text-primary);
  line-height: 1.5;
}

.example .zh {
  margin-top: 4px;
  font-size: 14px;
}

/* ─── Actions ─────────────────────────────────────── */
.actions {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 64px;
}

.btn.big {
  padding: 14px 36px;
  font-size: 16px;
  font-weight: 600;
}

.kbd {
  display: inline-block;
  margin-left: 8px;
  padding: 1px 8px;
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.35);
  border: 1px solid rgba(255, 255, 255, 0.5);
  font-family: ui-monospace, monospace;
  font-size: 12px;
  font-weight: 500;
}

.kbd.small {
  margin: 0;
  padding: 0 6px;
  font-size: 11px;
  background: rgba(0, 0, 0, 0.06);
  border-color: rgba(0, 0, 0, 0.08);
}

.ratings {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  justify-content: center;
}

.btn.rating {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding: 12px 22px;
  min-width: 92px;
  border-radius: 16px;
  font-weight: 600;
  border: 1px solid transparent;
  transition: transform 120ms ease, background 200ms ease, box-shadow 200ms ease;
}

.btn.rating .label {
  font-size: 15px;
}

.btn.rating:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 18px rgba(31, 38, 135, 0.12);
}

.btn.rating.again {
  background: rgba(255, 59, 48, 0.16);
  color: #b8170c;
  border-color: rgba(255, 59, 48, 0.28);
}
.btn.rating.again:hover {
  background: rgba(255, 59, 48, 0.24);
}

.btn.rating.hard {
  background: rgba(255, 149, 0, 0.18);
  color: #b86700;
  border-color: rgba(255, 149, 0, 0.3);
}
.btn.rating.hard:hover {
  background: rgba(255, 149, 0, 0.26);
}

.btn.rating.good {
  background: rgba(0, 122, 255, 0.18);
  color: #003fbb;
  border-color: rgba(0, 122, 255, 0.3);
}
.btn.rating.good:hover {
  background: rgba(0, 122, 255, 0.26);
}

.btn.rating.easy {
  background: rgba(52, 199, 89, 0.18);
  color: #186a2a;
  border-color: rgba(52, 199, 89, 0.32);
}
.btn.rating.easy:hover {
  background: rgba(52, 199, 89, 0.26);
}

.hint {
  font-size: 12px;
  text-align: center;
  letter-spacing: 0.01em;
}

/* ─── Transitions ─────────────────────────────────── */
.card-enter-active,
.card-leave-active {
  transition: opacity 250ms cubic-bezier(0.16, 1, 0.3, 1),
    transform 250ms cubic-bezier(0.16, 1, 0.3, 1);
}
.card-enter-from {
  opacity: 0;
  transform: translateY(20px) scale(0.97);
}
.card-leave-to {
  opacity: 0;
  transform: translateY(-20px) scale(0.97);
}

.reveal-enter-active {
  transition: opacity 380ms cubic-bezier(0.16, 1, 0.3, 1),
    transform 380ms cubic-bezier(0.16, 1, 0.3, 1);
}
.reveal-enter-from {
  opacity: 0;
  transform: translateY(12px);
}

@media (max-width: 640px) {
  .header {
    flex-direction: column;
    align-items: stretch;
  }
  .modes {
    align-self: center;
  }
  .progress {
    text-align: center;
  }
  .flash {
    padding: 40px 24px;
  }
  .btn.rating {
    min-width: 78px;
    padding: 10px 16px;
  }
}
</style>
