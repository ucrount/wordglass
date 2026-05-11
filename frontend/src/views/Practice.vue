<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from "vue";
import { RouterLink } from "vue-router";
import { api, type ReviewResult, type WordOut } from "../api";
import { isSpeechSupported, speak, stopSpeaking } from "../composables/tts";

type Mode = "zh-to-en" | "en-to-zh" | "dictation";
type Stage = "word" | "sentence" | "rated";
type Status = "typing" | "correct" | "wrong" | "revealed";

const MODES: { value: Mode; label: string; hint: string }[] = [
  { value: "zh-to-en", label: "中 → 英", hint: "看中文释义，敲出英文单词" },
  { value: "en-to-zh", label: "英 → 中", hint: "看英文单词，敲出中文释义" },
  { value: "dictation", label: "听写", hint: "听发音，敲出英文单词" },
];

const RATINGS: { value: ReviewResult; label: string; key: string; cls: string }[] = [
  { value: "again", label: "不会", key: "1", cls: "again" },
  { value: "hard", label: "模糊", key: "2", cls: "hard" },
  { value: "good", label: "认识", key: "3", cls: "good" },
  { value: "easy", label: "熟练", key: "4", cls: "easy" },
];

const mode = ref<Mode>(
  (localStorage.getItem("wordglass.practiceMode") as Mode) || "zh-to-en"
);
const queue = ref<WordOut[]>([]);
const current = ref(0);
const stage = ref<Stage>("word");
const status = ref<Status>("typing");
const input = ref("");
const shake = ref(false);
const submitting = ref(false);
const loading = ref(true);
const loadError = ref("");
const session = ref({ done: 0, correct: 0 });
const inputRef = ref<HTMLInputElement | null>(null);

const word = computed<WordOut | null>(() => queue.value[current.value] ?? null);
const total = computed(() => queue.value.length);
const finished = computed(() => total.value > 0 && current.value >= total.value);
const ttsSupported = isSpeechSupported();

// ─── Cloze (sentence stage) ────────────────────────────────────────────────
const cloze = computed(() => {
  const w = word.value;
  if (!w || !w.examples?.length) return null;
  const ex = w.examples[0];
  const safe = w.text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const re = new RegExp(`\\b${safe}[\\w']*\\b`, "i");
  const match = ex.en.match(re);
  if (!match) return null;
  return {
    en: ex.en,
    zh: ex.zh,
    blanked: ex.en.replace(re, "_____"),
    target: match[0],
  };
});

const hasExample = computed(() => cloze.value !== null);

// ─── Validation helpers ───────────────────────────────────────────────────
function normalize(s: string) {
  return s.trim().toLowerCase().replace(/[.,!?;:'"…，。！？；：""'']/g, "");
}

function checkEn(typed: string, target: string): boolean {
  if (!typed.trim()) return false;
  return normalize(typed) === normalize(target);
}

function checkZh(typed: string, translation: string): boolean {
  const trimmed = typed.trim();
  if (!trimmed) return false;
  // Translations look like "生动的；逼真的，活泼的"; accept any of the chunks
  // OR a substring match for lenient grading
  const parts = translation
    .split(/[；;,，、\/]/)
    .map((p) => p.replace(/[\.。]+$/, "").trim())
    .filter(Boolean);
  return parts.some(
    (p) => p === trimmed || p.includes(trimmed) || trimmed.includes(p)
  );
}

// ─── Data loading ─────────────────────────────────────────────────────────
async function load() {
  loading.value = true;
  loadError.value = "";
  try {
    queue.value = await api.dueWords(50);
    current.value = 0;
    session.value = { done: 0, correct: 0 };
    resetCard();
  } catch (e: any) {
    loadError.value = e.message || "加载失败";
  } finally {
    loading.value = false;
  }
}

function focusInput() {
  nextTick(() => inputRef.value?.focus());
}

function resetCard() {
  stage.value = "word";
  status.value = "typing";
  input.value = "";
  stopSpeaking();
  focusInput();
  // Auto-play audio for dictation mode
  if (mode.value === "dictation" && word.value) {
    setTimeout(() => speak(word.value!.text), 250);
  }
}

// ─── Word stage submit / reveal ───────────────────────────────────────────
function submitWord() {
  if (status.value === "correct" || status.value === "revealed") {
    advanceFromWord();
    return;
  }
  const w = word.value;
  if (!w) return;
  let ok = false;
  if (mode.value === "en-to-zh") {
    ok = checkZh(input.value, w.translation);
  } else {
    ok = checkEn(input.value, w.text);
  }
  if (ok) {
    status.value = "correct";
    setTimeout(() => speak(w.text), 80);
    setTimeout(advanceFromWord, 700);
  } else {
    status.value = "wrong";
    shake.value = true;
    setTimeout(() => (shake.value = false), 380);
    setTimeout(() => (status.value = "typing"), 600);
  }
}

function revealWord() {
  if (status.value === "correct") return;
  status.value = "revealed";
  if (word.value) setTimeout(() => speak(word.value!.text), 80);
  setTimeout(advanceFromWord, 900);
}

function advanceFromWord() {
  if (hasExample.value) {
    stage.value = "sentence";
    status.value = "typing";
    input.value = "";
    focusInput();
  } else {
    stage.value = "rated";
  }
}

// ─── Sentence stage submit / reveal ───────────────────────────────────────
function submitSentence() {
  if (status.value === "correct" || status.value === "revealed") {
    stage.value = "rated";
    return;
  }
  const target = cloze.value?.target;
  if (!target) {
    stage.value = "rated";
    return;
  }
  if (checkEn(input.value, target)) {
    status.value = "correct";
    if (word.value) setTimeout(() => speak(word.value!.text), 80);
    setTimeout(() => (stage.value = "rated"), 700);
  } else {
    status.value = "wrong";
    shake.value = true;
    setTimeout(() => (shake.value = false), 380);
    setTimeout(() => (status.value = "typing"), 600);
  }
}

function revealSentence() {
  if (status.value === "correct") return;
  status.value = "revealed";
  if (word.value) setTimeout(() => speak(word.value!.text), 80);
  setTimeout(() => (stage.value = "rated"), 900);
}

// ─── Rating ───────────────────────────────────────────────────────────────
async function rate(result: ReviewResult) {
  if (submitting.value || !word.value) return;
  submitting.value = true;
  if (result === "good" || result === "easy") session.value.correct += 1;
  session.value.done += 1;
  try {
    await api.submitReview(word.value.id, mode.value, result);
  } catch {
    /* ignore — local progress wins */
  }
  setTimeout(() => {
    current.value += 1;
    resetCard();
    submitting.value = false;
  }, 220);
}

// ─── Actions glue ─────────────────────────────────────────────────────────
function onPrimaryAction() {
  if (stage.value === "word") submitWord();
  else if (stage.value === "sentence") submitSentence();
}

function onReveal() {
  if (stage.value === "word") revealWord();
  else if (stage.value === "sentence") revealSentence();
}

function replayAudio() {
  if (word.value) speak(word.value.text);
}

// ─── Watchers ─────────────────────────────────────────────────────────────
watch(mode, (m) => {
  localStorage.setItem("wordglass.practiceMode", m);
  resetCard();
});

// ─── Keyboard ─────────────────────────────────────────────────────────────
function handleKey(e: KeyboardEvent) {
  if (loading.value || finished.value || total.value === 0) return;
  const tag = (e.target as HTMLElement)?.tagName;
  const inField = tag === "INPUT" || tag === "TEXTAREA";

  // S → replay audio (only when not typing, since 's' is a letter)
  if (!inField && (e.key === "s" || e.key === "S")) {
    e.preventDefault();
    replayAudio();
    return;
  }
  // Tab → reveal/skip
  if (e.key === "Tab" && stage.value !== "rated") {
    e.preventDefault();
    onReveal();
    return;
  }
  // 1-4 → ratings (only when rating)
  if (stage.value === "rated") {
    const r = RATINGS.find((rr) => rr.key === e.key);
    if (r) {
      e.preventDefault();
      rate(r.value);
    }
  }
}

onMounted(() => {
  window.addEventListener("keydown", handleKey);
  load();
});
onUnmounted(() => {
  window.removeEventListener("keydown", handleKey);
  stopSpeaking();
});
</script>

<template>
  <div class="practice">
    <!-- Header (only while reviewing) -->
    <div v-if="!loading && !loadError && total > 0 && !finished" class="header">
      <div class="modes glass">
        <button
          v-for="m in MODES"
          :key="m.value"
          :class="{ active: mode === m.value }"
          :title="m.hint"
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

    <!-- Stage dots -->
    <div
      v-if="!loading && !loadError && total > 0 && !finished"
      class="stage-dots"
    >
      <span :class="['dot', stage === 'word' ? 'active' : 'done']">
        ① 单词
      </span>
      <template v-if="hasExample">
        <span class="arrow tertiary">→</span>
        <span
          :class="[
            'dot',
            stage === 'sentence' ? 'active' : stage === 'rated' ? 'done' : '',
          ]"
        >
          ② 例句
        </span>
      </template>
      <span class="arrow tertiary">→</span>
      <span :class="['dot', stage === 'rated' ? 'active' : '']">③ 评分</span>
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
        <div class="dot-sep tertiary">·</div>
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
        <div :key="word.id + '-' + mode + '-' + stage" class="flash glass-strong" :class="{ shake }">
          <!-- ━━━━━ STAGE: WORD ━━━━━ -->
          <template v-if="stage === 'word'">
            <!-- Prompt by mode -->
            <template v-if="mode === 'zh-to-en'">
              <div class="prompt-hint tertiary">敲出英文</div>
              <div class="big-zh">{{ word.translation || "（无翻译）" }}</div>
              <div v-if="word.pos" class="pos">{{ word.pos }}</div>
            </template>

            <template v-else-if="mode === 'en-to-zh'">
              <div class="prompt-hint tertiary">敲出中文释义</div>
              <div class="word-display">
                <span class="word-text">{{ word.text }}</span>
                <button
                  v-if="ttsSupported"
                  class="speaker"
                  type="button"
                  title="重听 (S)"
                  @click="replayAudio"
                >🔊</button>
              </div>
              <div v-if="word.phonetic" class="phonetic">{{ word.phonetic }}</div>
            </template>

            <template v-else>
              <div class="prompt-hint tertiary">听写：敲出听到的单词</div>
              <button
                v-if="ttsSupported"
                class="big-speaker"
                type="button"
                title="重听 (S)"
                @click="replayAudio"
              >🔊</button>
              <div v-else class="muted">浏览器不支持语音合成，请使用其他模式</div>
            </template>

            <!-- Input -->
            <div class="input-row" :class="status">
              <input
                ref="inputRef"
                v-model="input"
                class="answer-input"
                :type="mode === 'en-to-zh' ? 'text' : 'text'"
                :placeholder="mode === 'en-to-zh' ? '中文释义…' : '英文单词…'"
                :disabled="status === 'correct' || status === 'revealed'"
                autocomplete="off"
                autocapitalize="off"
                autocorrect="off"
                spellcheck="false"
                @keyup.enter="onPrimaryAction"
              />
              <Transition name="pop">
                <span v-if="status === 'correct'" class="mark ok">✓</span>
                <span v-else-if="status === 'wrong'" class="mark err">✗</span>
              </Transition>
            </div>

            <!-- Reveal panel: show after correct or skipped -->
            <Transition name="reveal">
              <div v-if="status === 'correct' || status === 'revealed'" class="answer-panel">
                <div class="row-flex">
                  <span class="answer-word">{{ word.text }}</span>
                  <span v-if="word.phonetic" class="phonetic">{{ word.phonetic }}</span>
                </div>
                <div class="answer-zh">{{ word.translation }}</div>
              </div>
            </Transition>
          </template>

          <!-- ━━━━━ STAGE: SENTENCE ━━━━━ -->
          <template v-else-if="stage === 'sentence' && cloze">
            <div class="prompt-hint tertiary">把缺失的单词敲出来</div>
            <div class="sentence">{{ cloze.blanked }}</div>
            <div v-if="cloze.zh" class="sentence-zh tertiary">{{ cloze.zh }}</div>

            <div class="input-row" :class="status">
              <input
                ref="inputRef"
                v-model="input"
                class="answer-input"
                type="text"
                placeholder="填入单词…"
                :disabled="status === 'correct' || status === 'revealed'"
                autocomplete="off"
                autocapitalize="off"
                autocorrect="off"
                spellcheck="false"
                @keyup.enter="onPrimaryAction"
              />
              <Transition name="pop">
                <span v-if="status === 'correct'" class="mark ok">✓</span>
                <span v-else-if="status === 'wrong'" class="mark err">✗</span>
              </Transition>
            </div>

            <Transition name="reveal">
              <div v-if="status === 'correct' || status === 'revealed'" class="answer-panel">
                <div class="answer-word">{{ cloze.target }}</div>
                <div class="sentence-full tertiary">{{ cloze.en }}</div>
              </div>
            </Transition>
          </template>

          <!-- ━━━━━ STAGE: RATED ━━━━━ -->
          <template v-else>
            <div class="prompt-hint tertiary">这道题感觉如何？</div>
            <div class="word-display">
              <span class="word-text" style="font-size: clamp(34px, 6vw, 44px)">{{ word.text }}</span>
              <button
                v-if="ttsSupported"
                class="speaker"
                type="button"
                @click="replayAudio"
              >🔊</button>
            </div>
            <div v-if="word.phonetic" class="phonetic">{{ word.phonetic }}</div>
            <div class="answer-zh" style="font-size: 18px">{{ word.translation }}</div>
          </template>
        </div>
      </Transition>

      <!-- Actions row -->
      <div class="actions">
        <template v-if="stage === 'rated'">
          <div class="ratings">
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
        </template>
        <template v-else>
          <button
            class="btn btn-ghost"
            type="button"
            @click="onReveal"
            :disabled="status === 'correct'"
          >
            显示答案 <span class="kbd">Tab</span>
          </button>
          <button
            class="btn btn-primary"
            type="button"
            @click="onPrimaryAction"
            :disabled="status === 'correct' || status === 'revealed'"
          >
            提交 <span class="kbd">Enter</span>
          </button>
        </template>
      </div>

      <div class="hint tertiary">
        快捷键：Enter 提交 · Tab 显示答案 · S 重听 · 1 2 3 4 评分
      </div>
    </div>
  </div>
</template>

<style scoped>
.practice {
  display: flex;
  flex-direction: column;
  gap: 18px;
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

/* ─── Stage dots ───────────────────────────────────── */
.stage-dots {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  font-size: 13px;
  color: var(--text-tertiary);
}

.stage-dots .dot {
  padding: 4px 12px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.4);
  border: 1px solid rgba(255, 255, 255, 0.3);
  transition: all 250ms ease;
}

.stage-dots .dot.active {
  background: var(--accent);
  color: white;
  border-color: var(--accent);
  font-weight: 600;
}

.stage-dots .dot.done {
  background: rgba(52, 199, 89, 0.18);
  border-color: rgba(52, 199, 89, 0.3);
  color: #186a2a;
}

.stage-dots .arrow {
  opacity: 0.5;
}

/* ─── State cards ──────────────────────────────────── */
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
  gap: 22px;
}

.flash {
  width: 100%;
  min-height: 340px;
  padding: 44px 40px;
  border-radius: var(--radius-xl);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 14px;
}

.flash.shake {
  animation: shake 380ms cubic-bezier(0.36, 0.07, 0.19, 0.97) both;
}

@keyframes shake {
  10%, 90% { transform: translateX(-1px); }
  20%, 80% { transform: translateX(2px); }
  30%, 50%, 70% { transform: translateX(-4px); }
  40%, 60% { transform: translateX(4px); }
}

.prompt-hint {
  font-size: 12px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  font-weight: 500;
}

.big-zh {
  font-size: clamp(32px, 5.5vw, 44px);
  font-weight: 600;
  letter-spacing: -0.01em;
  color: var(--text-primary);
  text-align: center;
  line-height: 1.25;
  max-width: 600px;
}

.word-display {
  display: flex;
  align-items: center;
  gap: 12px;
  justify-content: center;
}

.word-text {
  font-size: clamp(40px, 8vw, 56px);
  font-weight: 700;
  letter-spacing: -0.02em;
  color: var(--text-primary);
  line-height: 1.1;
}

.speaker {
  appearance: none;
  border: none;
  background: rgba(0, 0, 0, 0.04);
  width: 40px;
  height: 40px;
  border-radius: 50%;
  font-size: 18px;
  cursor: pointer;
  transition: background 200ms ease, transform 200ms ease;
}

.speaker:hover {
  background: rgba(0, 0, 0, 0.08);
  transform: scale(1.08);
}

.big-speaker {
  appearance: none;
  border: none;
  background: var(--accent-soft);
  width: 96px;
  height: 96px;
  border-radius: 50%;
  font-size: 44px;
  cursor: pointer;
  transition: transform 200ms ease, background 200ms ease;
}

.big-speaker:hover {
  background: rgba(0, 122, 255, 0.2);
  transform: scale(1.06);
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
}

.sentence {
  font-size: clamp(22px, 4vw, 28px);
  font-weight: 500;
  line-height: 1.45;
  max-width: 580px;
  text-align: center;
  letter-spacing: -0.01em;
}

.sentence-zh {
  font-size: 14px;
}

/* ─── Input ────────────────────────────────────────── */
.input-row {
  position: relative;
  width: min(440px, 90%);
  margin-top: 14px;
}

.answer-input {
  width: 100%;
  appearance: none;
  border: 2px solid rgba(255, 255, 255, 0.5);
  background: rgba(255, 255, 255, 0.6);
  border-radius: 14px;
  padding: 14px 48px 14px 18px;
  font: inherit;
  font-size: 22px;
  font-weight: 500;
  text-align: center;
  letter-spacing: 0.01em;
  color: var(--text-primary);
  outline: none;
  transition: border-color 200ms ease, box-shadow 200ms ease, background 200ms ease;
}

.answer-input::placeholder {
  color: var(--text-tertiary);
  font-weight: 400;
}

.answer-input:focus {
  border-color: rgba(0, 122, 255, 0.5);
  background: rgba(255, 255, 255, 0.85);
  box-shadow: 0 0 0 4px var(--accent-soft);
}

.input-row.correct .answer-input {
  border-color: var(--success);
  background: rgba(52, 199, 89, 0.1);
  box-shadow: 0 0 0 4px rgba(52, 199, 89, 0.18);
}

.input-row.wrong .answer-input {
  border-color: var(--danger);
  background: rgba(255, 59, 48, 0.08);
}

.mark {
  position: absolute;
  right: 14px;
  top: 50%;
  transform: translateY(-50%);
  width: 28px;
  height: 28px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  font-weight: 700;
}

.mark.ok {
  background: var(--success);
  color: white;
}

.mark.err {
  background: var(--danger);
  color: white;
}

/* ─── Reveal panel ─────────────────────────────────── */
.answer-panel {
  margin-top: 20px;
  padding-top: 18px;
  border-top: 1px solid rgba(0, 0, 0, 0.08);
  width: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
}

.row-flex {
  display: flex;
  align-items: baseline;
  gap: 10px;
}

.answer-word {
  font-size: 30px;
  font-weight: 700;
  color: var(--accent);
  letter-spacing: -0.01em;
}

.answer-zh {
  font-size: 16px;
  color: var(--text-secondary);
  text-align: center;
}

.sentence-full {
  font-size: 14px;
  font-style: italic;
  margin-top: 4px;
}

/* ─── Actions ──────────────────────────────────────── */
.actions {
  display: flex;
  gap: 10px;
  align-items: center;
  justify-content: center;
  min-height: 60px;
  flex-wrap: wrap;
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
  gap: 10px;
  flex-wrap: wrap;
  justify-content: center;
}

.btn.rating {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding: 12px 20px;
  min-width: 88px;
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
.btn.rating.again:hover { background: rgba(255, 59, 48, 0.24); }

.btn.rating.hard {
  background: rgba(255, 149, 0, 0.18);
  color: #b86700;
  border-color: rgba(255, 149, 0, 0.3);
}
.btn.rating.hard:hover { background: rgba(255, 149, 0, 0.26); }

.btn.rating.good {
  background: rgba(0, 122, 255, 0.18);
  color: #003fbb;
  border-color: rgba(0, 122, 255, 0.3);
}
.btn.rating.good:hover { background: rgba(0, 122, 255, 0.26); }

.btn.rating.easy {
  background: rgba(52, 199, 89, 0.18);
  color: #186a2a;
  border-color: rgba(52, 199, 89, 0.32);
}
.btn.rating.easy:hover { background: rgba(52, 199, 89, 0.26); }

.hint {
  font-size: 12px;
  text-align: center;
  letter-spacing: 0.01em;
}

/* ─── Transitions ─────────────────────────────────── */
.card-enter-active,
.card-leave-active {
  transition: opacity 220ms cubic-bezier(0.16, 1, 0.3, 1),
    transform 220ms cubic-bezier(0.16, 1, 0.3, 1);
}
.card-enter-from {
  opacity: 0;
  transform: translateY(14px) scale(0.98);
}
.card-leave-to {
  opacity: 0;
  transform: translateY(-14px) scale(0.98);
}

.reveal-enter-active {
  transition: opacity 380ms cubic-bezier(0.16, 1, 0.3, 1),
    transform 380ms cubic-bezier(0.16, 1, 0.3, 1);
}
.reveal-enter-from {
  opacity: 0;
  transform: translateY(10px);
}

.pop-enter-active {
  transition: opacity 200ms ease, transform 200ms cubic-bezier(0.34, 1.56, 0.64, 1);
}
.pop-enter-from {
  opacity: 0;
  transform: translateY(-50%) scale(0.4);
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
    padding: 32px 20px;
  }
  .answer-input {
    font-size: 18px;
  }
  .btn.rating {
    min-width: 72px;
    padding: 10px 14px;
  }
}
</style>
