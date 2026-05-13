<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from "vue";
import { RouterLink, useRoute, useRouter } from "vue-router";
import { api, type ReviewResult, type WordOut } from "../api";
import { isSpeechSupported, speak, stopSpeaking } from "../composables/tts";
import LetterSlots from "../components/LetterSlots.vue";

type Tab = "word" | "sentence" | "listen";
type Direction = "zh-to-en" | "en-to-zh";
type Status = "typing" | "correct" | "wrong" | "revealed";

const TABS: { value: Tab; label: string; icon: string; hint: string }[] = [
  { value: "word", label: "单词练习", icon: "📝", hint: "拼写单个单词" },
  { value: "sentence", label: "句子练习", icon: "💬", hint: "翻译完整例句" },
  { value: "listen", label: "听力练习", icon: "🎧", hint: "听写英文单词" },
];

const RATINGS: { value: ReviewResult; label: string; key: string; cls: string }[] = [
  { value: "again", label: "不会", key: "1", cls: "again" },
  { value: "hard", label: "模糊", key: "2", cls: "hard" },
  { value: "good", label: "认识", key: "3", cls: "good" },
  { value: "easy", label: "熟练", key: "4", cls: "easy" },
];

const tab = ref<Tab>(
  (localStorage.getItem("wordglass.practiceTab") as Tab) || "word"
);
const direction = ref<Direction>(
  (localStorage.getItem("wordglass.practiceDir") as Direction) || "zh-to-en"
);

const queue = ref<WordOut[]>([]);
const current = ref(0);
const status = ref<Status>("typing");
const textInput = ref(""); // for modes that don't use LetterSlots
const showHint = ref(false); // when Tab pressed, fill slots with answer
const submitting = ref(false);
const loading = ref(true);
const loadError = ref("");
const session = ref({ done: 0, correct: 0 });
const slotsRef = ref<InstanceType<typeof LetterSlots> | null>(null);
const textRef = ref<HTMLTextAreaElement | HTMLInputElement | null>(null);

const route = useRoute();
const router = useRouter();

const isFocusMode = computed(() => {
  const v = route.query.word_ids;
  return typeof v === "string" && v.length > 0;
});

function exitFocus() {
  router.push({ path: "/practice" });
}

const word = computed<WordOut | null>(() => queue.value[current.value] ?? null);
const total = computed(() => queue.value.length);
const finished = computed(() => total.value > 0 && current.value >= total.value);
const ttsSupported = isSpeechSupported();

// The first usable example for sentence/listen modes
const example = computed(() => {
  if (!word.value?.examples?.length) return null;
  return word.value.examples[0];
});

// Whether the current tab+direction needs an example
const needsExample = computed(() => tab.value === "sentence");

// Effective input mode
const useLetterSlots = computed(
  () => (tab.value === "word" && direction.value === "zh-to-en") || tab.value === "listen"
);

// ─── Validation ───────────────────────────────────────────────────────────
function normalize(s: string) {
  return s
    .trim()
    .toLowerCase()
    .replace(/[.,!?;:'"…—\-()\[\]，。！？；：""''《》、（）—]/g, "")
    .replace(/\s+/g, " ");
}

function checkEn(typed: string, target: string): boolean {
  if (!typed.trim()) return false;
  return normalize(typed) === normalize(target);
}

function checkZh(typed: string, translation: string): boolean {
  const t = typed.trim();
  if (!t) return false;
  const parts = translation
    .split(/[；;,，、\/]/)
    .map((p) => p.replace(/[\.。]+$/, "").trim())
    .filter(Boolean);
  return parts.some((p) => p === t || p.includes(t) || t.includes(p));
}

function checkSentenceZh(typed: string, target: string): boolean {
  const t = typed.replace(/\s+/g, "").trim();
  const tgt = target.replace(/\s+/g, "").trim();
  if (!t) return false;
  // Loose: match if user typed ≥70% of the chars in target's order
  if (t === tgt) return true;
  // Fallback: simple inclusion check
  const onlyChars = (s: string) => s.replace(/[，。！？；："'《》、（）.,!?;:'"…]/g, "");
  return onlyChars(t) === onlyChars(tgt);
}

// ─── Data loading ─────────────────────────────────────────────────────────
async function load() {
  loading.value = true;
  loadError.value = "";
  try {
    const raw = route.query.word_ids;
    if (typeof raw === "string" && raw.length > 0) {
      const ids = raw
        .split(",")
        .map((s) => parseInt(s.trim(), 10))
        .filter((n) => !Number.isNaN(n));
      if (ids.length > 0) {
        const results = await Promise.all(ids.map((id) => api.getWord(id)));
        queue.value = results;
      } else {
        queue.value = [];
      }
    } else {
      queue.value = await api.dueWords(50);
    }
    current.value = 0;
    session.value = { done: 0, correct: 0 };
    resetCard();
  } catch (e: any) {
    loadError.value = e.message || "加载失败";
  } finally {
    loading.value = false;
  }
}

function focusInputAfterRender() {
  nextTick(() => {
    if (useLetterSlots.value) {
      // LetterSlots listens to window keydown, nothing to focus
    } else if (textRef.value) {
      textRef.value.focus();
    }
  });
}

function resetCard() {
  status.value = "typing";
  textInput.value = "";
  showHint.value = false;
  stopSpeaking();
  if (slotsRef.value) slotsRef.value.reset();
  focusInputAfterRender();
  if (tab.value === "listen" && word.value) {
    setTimeout(() => speak(word.value!.text), 250);
  }
}

// ─── Submit / reveal / advance ────────────────────────────────────────────
function submit() {
  if (status.value === "correct" || status.value === "revealed") return;
  const w = word.value;
  if (!w) return;
  let ok = false;
  if (tab.value === "word") {
    if (direction.value === "zh-to-en") {
      // LetterSlots emits 'complete' which calls onSlotsComplete directly
      // This path runs if user clicks the explicit submit button without LetterSlots having completed
      return;
    }
    ok = checkZh(textInput.value, w.translation);
  } else if (tab.value === "sentence") {
    const ex = example.value;
    if (!ex) return;
    if (direction.value === "zh-to-en") {
      ok = checkEn(textInput.value, ex.en);
    } else {
      ok = checkSentenceZh(textInput.value, ex.zh);
    }
  } else if (tab.value === "listen") {
    // LetterSlots emits 'complete' for listen mode too
    return;
  }
  if (ok) {
    status.value = "correct";
    if (w && tab.value !== "sentence") {
      setTimeout(() => speak(w.text), 80);
    }
  } else {
    status.value = "wrong";
    setTimeout(() => (status.value = "typing"), 600);
  }
}

function onSlotsComplete() {
  status.value = "correct";
  if (word.value) setTimeout(() => speak(word.value!.text), 80);
}

function onSlotsWrong() {
  // LetterSlots already shakes; just keep status as typing
}

function reveal() {
  if (status.value === "correct") return;
  status.value = "revealed";
  if (useLetterSlots.value) {
    showHint.value = true;
  }
  if (word.value && tab.value !== "sentence") setTimeout(() => speak(word.value!.text), 80);
}

async function rate(result: ReviewResult) {
  if (submitting.value || !word.value) return;
  submitting.value = true;
  if (result === "good" || result === "easy") session.value.correct += 1;
  session.value.done += 1;
  try {
    await api.submitReview(word.value.id, `${tab.value}_${direction.value}`, result);
  } catch {
    /* ignore */
  }
  setTimeout(() => {
    current.value += 1;
    resetCard();
    submitting.value = false;
  }, 220);
}

function replayAudio() {
  if (word.value) speak(word.value.text);
}

// ─── Watchers ─────────────────────────────────────────────────────────────
watch(tab, (t) => {
  localStorage.setItem("wordglass.practiceTab", t);
  // When switching tab, skip cards that don't have examples needed
  if (needsExample.value && !example.value && word.value) {
    // Try to find a word that has examples
    const found = queue.value.findIndex(
      (w, i) => i >= current.value && w.examples && w.examples.length > 0
    );
    if (found >= 0) current.value = found;
  }
  resetCard();
});

watch(direction, (d) => {
  localStorage.setItem("wordglass.practiceDir", d);
  resetCard();
});

watch(() => route.query.word_ids, () => {
  load();
});

// ─── Keyboard ─────────────────────────────────────────────────────────────
function handleKey(e: KeyboardEvent) {
  if (loading.value || finished.value || total.value === 0) return;
  const tag = (e.target as HTMLElement)?.tagName;
  const inField = tag === "INPUT" || tag === "TEXTAREA";

  if (!inField && (e.key === "s" || e.key === "S")) {
    e.preventDefault();
    replayAudio();
    return;
  }
  // Tab → reveal
  if (e.key === "Tab" && status.value !== "correct") {
    e.preventDefault();
    reveal();
    return;
  }
  // 1-4 → ratings (only after answered)
  if (status.value === "correct" || status.value === "revealed") {
    const r = RATINGS.find((rr) => rr.key === e.key);
    if (r) {
      e.preventDefault();
      rate(r.value);
    }
  }
  // Enter in textarea is handled by @keyup.enter on the element itself
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
    <!-- Focus mode banner -->
    <div v-if="isFocusMode && !loading && !loadError" class="focus-banner glass-dim">
      <span class="focus-icon">💪</span>
      <span class="focus-text">专练模式 · {{ total }} 个词</span>
      <button class="exit-focus" @click="exitFocus">退出专练</button>
    </div>

    <!-- Top tabs -->
    <div v-if="!loading && !loadError && total > 0 && !finished" class="tabs glass">
      <button
        v-for="t in TABS"
        :key="t.value"
        class="tab"
        :class="{ active: tab === t.value }"
        :title="t.hint"
        @click="tab = t.value"
      >
        <span class="tab-icon">{{ t.icon }}</span>
        <span class="tab-label">{{ t.label }}</span>
      </button>
      <span class="progress">
        <span class="num">{{ current + 1 }}</span>
        <span class="tertiary"> / {{ total }}</span>
      </span>
    </div>

    <!-- Direction switch (only for word/sentence tabs) -->
    <div
      v-if="!loading && !loadError && total > 0 && !finished && tab !== 'listen'"
      class="direction"
    >
      <button :class="{ active: direction === 'zh-to-en' }" @click="direction = 'zh-to-en'">
        中 → 英
      </button>
      <button :class="{ active: direction === 'en-to-zh' }" @click="direction = 'en-to-zh'">
        英 → 中
      </button>
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
      <div class="state-actions">
        <button class="btn btn-primary" @click="load">再来一组</button>
        <RouterLink to="/" class="btn btn-ghost">回首页</RouterLink>
      </div>
    </div>

    <!-- Active card -->
    <div v-else-if="word" class="card-stage">
      <Transition name="card" mode="out-in">
        <div :key="word.id + '-' + tab + '-' + direction" class="flash glass-strong">
          <!-- ━━━━━ TAB: 单词 (zh→en) ━━━━━ -->
          <template v-if="tab === 'word' && direction === 'zh-to-en'">
            <div class="prompt-hint tertiary">敲出英文单词</div>
            <div class="big-zh">{{ word.translation || "（无翻译）" }}</div>
            <div v-if="word.pos" class="pos">{{ word.pos }}</div>
            <LetterSlots
              ref="slotsRef"
              :target="word.text"
              :disabled="status === 'correct'"
              :show-hint="showHint"
              @complete="onSlotsComplete"
              @wrong="onSlotsWrong"
            />
            <Transition name="reveal">
              <div v-if="status === 'correct' || status === 'revealed'" class="answer-panel">
                <div class="row-flex">
                  <span class="answer-word">{{ word.text }}</span>
                  <button v-if="ttsSupported" class="speaker-small" @click="replayAudio">🔊</button>
                  <span v-if="word.phonetic" class="phonetic">{{ word.phonetic }}</span>
                </div>
              </div>
            </Transition>
          </template>

          <!-- ━━━━━ TAB: 单词 (en→zh) ━━━━━ -->
          <template v-else-if="tab === 'word' && direction === 'en-to-zh'">
            <div class="prompt-hint tertiary">敲出中文释义</div>
            <div class="word-display">
              <span class="word-text">{{ word.text }}</span>
              <button v-if="ttsSupported" class="speaker" @click="replayAudio" title="S 重听">🔊</button>
            </div>
            <div v-if="word.phonetic" class="phonetic">{{ word.phonetic }}</div>
            <div class="text-input-row" :class="status">
              <input
                ref="textRef"
                v-model="textInput"
                class="answer-input"
                type="text"
                placeholder="中文释义…"
                :disabled="status === 'correct' || status === 'revealed'"
                autocomplete="off"
                @keyup.enter="submit"
              />
            </div>
            <Transition name="reveal">
              <div v-if="status === 'correct' || status === 'revealed'" class="answer-panel">
                <div class="answer-zh-big">{{ word.translation }}</div>
              </div>
            </Transition>
          </template>

          <!-- ━━━━━ TAB: 句子 (no example available) ━━━━━ -->
          <template v-else-if="tab === 'sentence' && !example">
            <div class="big-emoji">📭</div>
            <p class="muted">这个词暂时没有例句</p>
            <p class="tertiary small">直接评分跳过，或切到单词/听力模式</p>
          </template>

          <!-- ━━━━━ TAB: 句子 (zh→en) ━━━━━ -->
          <template v-else-if="tab === 'sentence' && direction === 'zh-to-en' && example">
            <div class="prompt-hint tertiary">把这句中文翻译成英文</div>
            <div class="sentence-zh-prompt">{{ example.zh }}</div>
            <div class="word-hint tertiary">提示词：<span class="word-text-small">{{ word.text }}</span></div>
            <div class="text-input-row" :class="status">
              <textarea
                ref="textRef"
                v-model="textInput"
                class="answer-input answer-textarea"
                rows="2"
                placeholder="英文句子…"
                :disabled="status === 'correct' || status === 'revealed'"
                autocomplete="off"
                @keyup.ctrl.enter="submit"
                @keyup.meta.enter="submit"
              ></textarea>
            </div>
            <Transition name="reveal">
              <div v-if="status === 'correct' || status === 'revealed'" class="answer-panel">
                <div class="sentence-full">{{ example.en }}</div>
              </div>
            </Transition>
          </template>

          <!-- ━━━━━ TAB: 句子 (en→zh) ━━━━━ -->
          <template v-else-if="tab === 'sentence' && direction === 'en-to-zh' && example">
            <div class="prompt-hint tertiary">把这句英文翻译成中文</div>
            <div class="sentence-en-prompt">{{ example.en }}</div>
            <button v-if="ttsSupported" class="speaker-mini" @click="replayAudio">🔊 听一下</button>
            <div class="text-input-row" :class="status">
              <textarea
                ref="textRef"
                v-model="textInput"
                class="answer-input answer-textarea"
                rows="2"
                placeholder="中文句子…"
                :disabled="status === 'correct' || status === 'revealed'"
                autocomplete="off"
                @keyup.ctrl.enter="submit"
                @keyup.meta.enter="submit"
              ></textarea>
            </div>
            <Transition name="reveal">
              <div v-if="status === 'correct' || status === 'revealed'" class="answer-panel">
                <div class="sentence-full">{{ example.zh }}</div>
              </div>
            </Transition>
          </template>

          <!-- ━━━━━ TAB: 听力 ━━━━━ -->
          <template v-else-if="tab === 'listen'">
            <div class="prompt-hint tertiary">听发音，敲出英文单词</div>
            <button
              v-if="ttsSupported"
              class="big-speaker"
              @click="replayAudio"
              title="S 重听"
            >🔊</button>
            <div v-else class="muted">浏览器不支持语音合成，请用其他模式</div>
            <LetterSlots
              ref="slotsRef"
              :target="word.text"
              :disabled="status === 'correct' || !ttsSupported"
              :show-hint="showHint"
              @complete="onSlotsComplete"
              @wrong="onSlotsWrong"
            />
            <Transition name="reveal">
              <div v-if="status === 'correct' || status === 'revealed'" class="answer-panel">
                <div class="row-flex">
                  <span class="answer-word">{{ word.text }}</span>
                  <span v-if="word.phonetic" class="phonetic">{{ word.phonetic }}</span>
                </div>
                <div class="answer-zh-big">{{ word.translation }}</div>
              </div>
            </Transition>
          </template>
        </div>
      </Transition>

      <!-- Actions row -->
      <div class="actions">
        <template v-if="status === 'correct' || status === 'revealed' || (tab === 'sentence' && !example)">
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
          <button class="btn btn-ghost" type="button" @click="reveal">
            显示答案 <span class="kbd">Tab</span>
          </button>
          <button
            v-if="!useLetterSlots"
            class="btn btn-primary"
            type="button"
            @click="submit"
          >
            提交 <span class="kbd">{{ tab === 'sentence' ? '⌘ Enter' : 'Enter' }}</span>
          </button>
        </template>
      </div>

      <div class="hint tertiary">
        <span v-if="useLetterSlots">直接键盘敲字母 · </span>
        <span v-else>Enter 提交 · </span>
        Tab 显示答案 · S 重听 · 1 2 3 4 评分
      </div>
    </div>
  </div>
</template>

<style scoped>
.practice {
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-height: 70vh;
}

/* ─── Top tabs ─────────────────────────────────────── */
.tabs {
  display: flex;
  align-items: center;
  padding: 5px;
  border-radius: 999px;
  gap: 4px;
  position: relative;
}

.tab {
  appearance: none;
  background: transparent;
  border: none;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 18px;
  border-radius: 999px;
  font: inherit;
  font-weight: 500;
  font-size: 14px;
  color: var(--text-secondary);
  cursor: pointer;
  transition: background 200ms ease, color 200ms ease, box-shadow 200ms ease;
}

.tab-icon { font-size: 16px; }
.tab-label { letter-spacing: -0.01em; }

.tab.active {
  background: var(--glass-bg-strong);
  color: var(--text-primary);
  box-shadow: 0 2px 8px rgba(50, 60, 40, 0.12);
}

.tab:hover:not(.active) {
  background: var(--glass-bg-dim);
  color: var(--text-primary);
}

.progress {
  margin-left: auto;
  padding-right: 14px;
  font-size: 14px;
  color: var(--text-tertiary);
}

.progress .num {
  font-family: var(--font-serif);
  font-size: 18px;
  font-weight: 700;
  color: var(--text-primary);
}

/* ─── Direction toggle ─────────────────────────────── */
.direction {
  display: inline-flex;
  align-self: center;
  gap: 4px;
  padding: 4px;
  background: var(--glass-bg-dim);
  border-radius: 999px;
  border: 1px solid var(--glass-border);
}

.direction button {
  appearance: none;
  background: transparent;
  border: none;
  padding: 6px 16px;
  border-radius: 999px;
  font: inherit;
  font-size: 13px;
  font-weight: 500;
  color: var(--text-secondary);
  cursor: pointer;
  transition: background 200ms ease;
}

.direction button.active {
  background: var(--brand-soft);
  color: var(--brand);
}

/* ─── State cards ──────────────────────────────────── */
.state {
  padding: 56px 32px;
  text-align: center;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  margin-top: 12px;
}

.big-emoji {
  font-size: 56px;
  line-height: 1;
}

.state h2 {
  margin: 4px 0 0;
  font-size: 24px;
  font-weight: 600;
}

.error-msg { color: var(--danger); }

.finished .result-stats {
  display: flex;
  gap: 18px;
  align-items: baseline;
  margin-top: 12px;
  font-size: 18px;
}

.finished .big {
  font-family: var(--font-serif);
  font-size: 38px;
  font-weight: 700;
  color: var(--text-primary);
}

.finished .big.good { color: var(--success); }

.state-actions {
  margin-top: 18px;
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
  min-height: 360px;
  padding: 44px 36px;
  border-radius: var(--radius-xl);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 18px;
}

.prompt-hint {
  font-size: 12px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  font-weight: 600;
}

.big-zh {
  font-family: var(--font-serif);
  font-size: clamp(28px, 5vw, 38px);
  font-weight: 600;
  letter-spacing: -0.01em;
  color: var(--text-primary);
  text-align: center;
  line-height: 1.3;
  max-width: 580px;
}

.word-display {
  display: flex;
  align-items: center;
  gap: 12px;
}

.word-text {
  font-family: var(--font-serif);
  font-size: clamp(38px, 7vw, 50px);
  font-weight: 700;
  letter-spacing: -0.02em;
  color: var(--text-primary);
}

.word-text-small {
  font-family: var(--font-mono);
  font-weight: 600;
  color: var(--text-primary);
}

.word-hint {
  font-size: 13px;
}

.phonetic {
  font-family: var(--font-mono);
  font-size: 15px;
  color: var(--text-tertiary);
}

.pos {
  font-family: var(--font-serif);
  font-style: italic;
  display: inline-block;
  padding: 3px 10px;
  border-radius: 8px;
  background: var(--brand-soft);
  font-size: 12px;
  color: var(--brand);
}

.speaker, .speaker-small, .speaker-mini {
  appearance: none;
  border: none;
  cursor: pointer;
  transition: transform 200ms ease, background 200ms ease;
}

.speaker {
  background: var(--glass-bg-dim);
  width: 40px;
  height: 40px;
  border-radius: 50%;
  font-size: 18px;
}
.speaker:hover { background: var(--brand-soft); transform: scale(1.08); }

.speaker-small {
  background: var(--glass-bg-dim);
  width: 30px;
  height: 30px;
  border-radius: 50%;
  font-size: 14px;
}
.speaker-small:hover { background: var(--brand-soft); }

.speaker-mini {
  background: var(--brand-soft);
  padding: 6px 12px;
  border-radius: 999px;
  font-size: 13px;
  color: var(--brand);
}
.speaker-mini:hover { background: color-mix(in srgb, var(--brand) 28%, transparent); }

.big-speaker {
  appearance: none;
  border: none;
  background: var(--brand-soft);
  width: 104px;
  height: 104px;
  border-radius: 50%;
  font-size: 50px;
  color: var(--brand);
  cursor: pointer;
  transition: transform 200ms ease, background 200ms ease;
  animation: pulse 1.6s ease-in-out infinite;
}

.big-speaker:hover {
  background: color-mix(in srgb, var(--brand) 28%, transparent);
  transform: scale(1.06);
  animation: none;
}

@keyframes pulse {
  0%, 100% { box-shadow: 0 0 0 0 rgba(74, 110, 62, 0.4); }
  50% { box-shadow: 0 0 0 18px rgba(74, 110, 62, 0); }
}

.sentence-zh-prompt {
  font-family: var(--font-serif);
  font-size: clamp(22px, 4vw, 28px);
  font-weight: 600;
  letter-spacing: -0.01em;
  color: var(--text-primary);
  text-align: center;
  line-height: 1.4;
  max-width: 600px;
}

.sentence-en-prompt {
  font-family: var(--font-serif);
  font-size: clamp(20px, 3.5vw, 26px);
  font-weight: 500;
  font-style: italic;
  color: var(--text-primary);
  text-align: center;
  line-height: 1.45;
  max-width: 600px;
}

/* ─── Input ────────────────────────────────────────── */
.text-input-row {
  width: min(540px, 95%);
}

.answer-input {
  width: 100%;
  appearance: none;
  border: 2px solid var(--glass-border);
  background: var(--glass-bg);
  border-radius: var(--radius-card);
  padding: 14px 18px;
  font: inherit;
  font-size: 18px;
  font-weight: 500;
  text-align: center;
  color: var(--text-primary);
  outline: none;
  transition: border-color 200ms ease, box-shadow 200ms ease, background 200ms ease;
}

.answer-textarea {
  text-align: left;
  resize: vertical;
  min-height: 64px;
  font-size: 17px;
}

.answer-input::placeholder { color: var(--text-tertiary); font-weight: 400; }

.answer-input:focus {
  border-color: color-mix(in srgb, var(--brand) 50%, transparent);
  background: var(--glass-bg-strong);
  box-shadow: 0 0 0 4px var(--brand-soft);
}

.text-input-row.correct .answer-input {
  border-color: var(--success);
  background: color-mix(in srgb, var(--success) 12%, var(--glass-bg));
  box-shadow: 0 0 0 4px color-mix(in srgb, var(--success) 22%, transparent);
}

.text-input-row.wrong .answer-input {
  border-color: var(--danger);
  background: color-mix(in srgb, var(--danger) 10%, var(--glass-bg));
  animation: shake 380ms cubic-bezier(0.36, 0.07, 0.19, 0.97) both;
}

@keyframes shake {
  10%, 90% { transform: translateX(-1px); }
  20%, 80% { transform: translateX(2px); }
  30%, 50%, 70% { transform: translateX(-4px); }
  40%, 60% { transform: translateX(4px); }
}

/* ─── Reveal panel ─────────────────────────────────── */
.answer-panel {
  margin-top: 8px;
  padding-top: 16px;
  border-top: 1px solid rgba(0, 0, 0, 0.08);
  width: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}

.row-flex {
  display: flex;
  align-items: center;
  gap: 10px;
}

.answer-word {
  font-family: var(--font-serif);
  font-size: 28px;
  font-weight: 700;
  color: var(--brand);
  letter-spacing: -0.01em;
}

.answer-zh-big {
  font-size: 18px;
  color: var(--text-primary);
  text-align: center;
  font-weight: 500;
}

.sentence-full {
  font-size: 16px;
  color: var(--text-primary);
  text-align: center;
  line-height: 1.5;
  max-width: 580px;
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
  background: var(--glass-bg-dim);
  border: 1px solid var(--glass-border);
  font-family: var(--font-mono);
  font-size: 12px;
  font-weight: 500;
}

.kbd.small {
  margin: 0;
  padding: 0 6px;
  font-size: 11px;
  background: var(--glass-bg-dim);
  border-color: var(--hairline);
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

.btn.rating .label { font-size: 15px; }

.btn.rating:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 18px rgba(50, 60, 40, 0.12);
}

.btn.rating.again {
  background: color-mix(in srgb, var(--danger) 16%, transparent);
  color: var(--danger);
  border-color: color-mix(in srgb, var(--danger) 32%, transparent);
}
.btn.rating.again:hover {
  background: color-mix(in srgb, var(--danger) 26%, transparent);
}

.btn.rating.hard {
  background: color-mix(in srgb, var(--warn) 18%, transparent);
  color: var(--warn);
  border-color: color-mix(in srgb, var(--warn) 32%, transparent);
}
.btn.rating.hard:hover {
  background: color-mix(in srgb, var(--warn) 28%, transparent);
}

.btn.rating.good {
  background: var(--brand-soft);
  color: var(--brand);
  border-color: color-mix(in srgb, var(--brand) 32%, transparent);
}
.btn.rating.good:hover {
  background: color-mix(in srgb, var(--brand) 26%, transparent);
}

.btn.rating.easy {
  background: color-mix(in srgb, var(--success) 18%, transparent);
  color: var(--success);
  border-color: color-mix(in srgb, var(--success) 32%, transparent);
}
.btn.rating.easy:hover {
  background: color-mix(in srgb, var(--success) 28%, transparent);
}

.hint {
  font-size: 12px;
  text-align: center;
  letter-spacing: 0.01em;
}

.small { font-size: 13px; }

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

@media (max-width: 640px) {
  .tabs { flex-wrap: wrap; }
  .tab-label { font-size: 12px; }
  .progress { margin-left: auto; }
  .flash { padding: 32px 18px; }
  .answer-input { font-size: 16px; }
  .btn.rating { min-width: 70px; padding: 10px 14px; }
}

/* ─── Focus mode banner ─────────────────────────── */
.focus-banner {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 14px;
  border-radius: 999px;
  font-size: 13px;
  color: var(--accent);
  background: color-mix(in srgb, var(--accent) 12%, transparent);
  border: 1px solid color-mix(in srgb, var(--accent) 32%, transparent);
  align-self: flex-start;
}
.focus-icon { font-size: 14px; }
.focus-text { font-weight: 600; }
.exit-focus {
  appearance: none;
  background: transparent;
  border: none;
  color: var(--text-secondary);
  font: inherit;
  font-size: 11.5px;
  cursor: pointer;
  text-decoration: underline;
  padding: 0;
  margin-left: 4px;
}
.exit-focus:hover { color: var(--text-primary); }
</style>
