<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { api, type WordPreview } from "../api";

// ─── Persisted text + direction ────────────────────────────────────────────
type Direction = "en-to-zh" | "zh-to-en";

const STORAGE_KEY = "wordglass.reader";
const STORAGE_KEY_DIR = "wordglass.reader.dir";

function loadStored(): { en: string; zh: string } {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return { en: "", zh: "" };
    const data = JSON.parse(raw);
    return { en: data.en || "", zh: data.zh || "" };
  } catch {
    return { en: "", zh: "" };
  }
}

function loadDir(): Direction {
  const v = localStorage.getItem(STORAGE_KEY_DIR);
  return v === "zh-to-en" ? "zh-to-en" : "en-to-zh";
}

const stored = loadStored();
const english = ref(stored.en);
const chinese = ref(stored.zh);
const direction = ref<Direction>(loadDir());
const textareaRef = ref<HTMLTextAreaElement | null>(null);

watch([english, chinese], ([en, zh]) => {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ en, zh }));
  } catch { /* quota — ignore */ }
});

// ─── Direction-aware source / target ───────────────────────────────────────
const sourceText = computed({
  get: () => (direction.value === "en-to-zh" ? english.value : chinese.value),
  set: (v: string) => {
    if (direction.value === "en-to-zh") english.value = v;
    else chinese.value = v;
  },
});

const targetText = computed(() =>
  direction.value === "en-to-zh" ? chinese.value : english.value
);

function clearTarget() {
  if (direction.value === "en-to-zh") chinese.value = "";
  else english.value = "";
}

function setTarget(v: string) {
  if (direction.value === "en-to-zh") chinese.value = v;
  else english.value = v;
}

const sourceLabel = computed(() =>
  direction.value === "en-to-zh" ? "原文（English）" : "原文（中文）"
);
const targetLabel = computed(() =>
  direction.value === "en-to-zh" ? "译文（中文）" : "译文（English）"
);
const sourcePlaceholder = computed(() =>
  direction.value === "en-to-zh"
    ? "把英文粘进来——文章、新闻、邮件、字幕都行（最长 5000 字符）…"
    : "把中文粘进来——文章、邮件、想翻成英文的句子（最长 5000 字符）…"
);

// ─── Mode + selected word ──────────────────────────────────────────────────
type Mode = "edit" | "read";
const mode = ref<Mode>(sourceText.value ? "read" : "edit");
const loading = ref(false);
const error = ref("");
const addedCount = ref(0);

interface SelectedWord {
  text: string;
  loading: boolean;
  found: boolean;
  phonetic: string;
  pos: string;
  translation: string;
  alreadySaved: boolean;
  adding: boolean;
  addError: string;
}
const selected = ref<SelectedWord | null>(null);
const readContainer = ref<HTMLElement | null>(null);

// ─── Auto-translate debounce ───────────────────────────────────────────────
const DEBOUNCE_MS = 1200;
let debounceTimer: ReturnType<typeof setTimeout> | null = null;
let lastTranslatedText = sourceText.value;

function cancelDebounce() {
  if (debounceTimer) {
    clearTimeout(debounceTimer);
    debounceTimer = null;
  }
}

function scheduleTranslate(immediate = false) {
  cancelDebounce();
  const text = sourceText.value.trim();
  if (!text) {
    clearTarget();
    mode.value = "edit";
    lastTranslatedText = "";
    return;
  }
  if (text === lastTranslatedText.trim()) return;
  if (immediate) {
    doTranslate();
  } else {
    debounceTimer = setTimeout(doTranslate, DEBOUNCE_MS);
  }
}

watch(sourceText, () => scheduleTranslate(false));
watch(direction, (d) => {
  localStorage.setItem(STORAGE_KEY_DIR, d);
});

function onPaste() {
  setTimeout(() => scheduleTranslate(true), 0);
}

// ─── Token splitting (only used in en→zh mode) ─────────────────────────────
type Token = { kind: "word" | "gap"; text: string };
const tokens = computed<Token[]>(() => {
  const out: Token[] = [];
  if (direction.value !== "en-to-zh") return out;
  const re = /[A-Za-z][A-Za-z'-]*/g;
  let last = 0;
  const text = english.value;
  for (const m of text.matchAll(re)) {
    if (m.index! > last) out.push({ kind: "gap", text: text.slice(last, m.index) });
    out.push({ kind: "word", text: m[0] });
    last = m.index! + m[0].length;
  }
  if (last < text.length) out.push({ kind: "gap", text: text.slice(last) });
  return out;
});

const wordCount = computed(() => {
  if (direction.value === "en-to-zh") {
    return (english.value.match(/[A-Za-z][A-Za-z'-]*/g) || []).length;
  }
  return (chinese.value.match(/[一-鿿]/g) || []).length;
});
const charCount = computed(() => sourceText.value.length);

// ─── Direction toggle ──────────────────────────────────────────────────────
function setDirection(d: Direction) {
  if (d === direction.value) return;
  cancelDebounce();
  direction.value = d;
  english.value = "";
  chinese.value = "";
  selected.value = null;
  mode.value = "edit";
  lastTranslatedText = "";
  error.value = "";
  nextTick(() => textareaRef.value?.focus());
}

// ─── Actions ───────────────────────────────────────────────────────────────
async function doTranslate() {
  cancelDebounce();
  const text = sourceText.value.trim();
  if (!text || loading.value) return;
  const textareaFocused = document.activeElement === textareaRef.value;
  const targetLang = direction.value === "en-to-zh" ? "zh" : "en";
  loading.value = true;
  error.value = "";
  try {
    const res = await api.translateText(text, targetLang);
    setTarget(res.translation);
    lastTranslatedText = text;
    if (sourceText.value.trim() === text && !textareaFocused) {
      mode.value = "read";
    }
  } catch (e: any) {
    error.value = e.message || "翻译失败";
  } finally {
    loading.value = false;
    if (sourceText.value.trim() && sourceText.value.trim() !== lastTranslatedText.trim()) {
      scheduleTranslate(false);
    }
  }
}

function enterEditMode() {
  mode.value = "edit";
  nextTick(() => {
    textareaRef.value?.focus();
    if (textareaRef.value) {
      const len = textareaRef.value.value.length;
      textareaRef.value.setSelectionRange(len, len);
    }
  });
}

function pasteExample() {
  if (direction.value === "en-to-zh") {
    english.value = `The morning light slipped through the cracked blinds, painting thin stripes across the wooden floor. Lena sat by the window, cradling a cup of tea, watching the city wake up. Somewhere in the distance, a tram bell rang. She thought about all the things she had meant to do this week, and how a quiet Saturday could rearrange her priorities entirely.`;
  } else {
    chinese.value = `清晨的阳光从百叶窗的缝隙里溜进来，在木地板上画出细细的条纹。莉娜坐在窗边，捧着一杯茶，看着城市慢慢醒来。远处某个地方，有轨电车的铃声响起。她想着这周本来要做的所有事，又想到一个安静的周六，可以把她的优先级完全重新排列一遍。`;
  }
  mode.value = "edit";
  scheduleTranslate(true);
}

// ─── Word selection (en→zh only) ───────────────────────────────────────────
async function onWordClick(event: MouseEvent, word: string) {
  if (direction.value !== "en-to-zh") return;
  event.stopPropagation();
  selected.value = {
    text: word, loading: true, found: false,
    phonetic: "", pos: "", translation: "",
    alreadySaved: false, adding: false, addError: "",
  };
  try {
    const data: WordPreview = await api.previewWord(word);
    if (!selected.value || selected.value.text !== word) return;
    if (data.found) {
      selected.value = {
        ...selected.value, loading: false, found: true,
        phonetic: data.phonetic, pos: data.pos,
        translation: data.translation, alreadySaved: data.already_saved,
      };
    } else {
      selected.value = { ...selected.value, loading: false, found: false };
    }
  } catch {
    if (selected.value) selected.value = { ...selected.value, loading: false, found: false };
  }
}

async function addSelectedWord() {
  if (!selected.value || selected.value.adding) return;
  selected.value.adding = true;
  selected.value.addError = "";
  try {
    await api.addWord(selected.value.text);
    if (selected.value) {
      selected.value = { ...selected.value, adding: false, alreadySaved: true };
      addedCount.value++;
    }
  } catch (e: any) {
    if (selected.value) {
      selected.value = { ...selected.value, adding: false, addError: e.message || "添加失败" };
    }
  }
}

function closeSelected() {
  selected.value = null;
}

function onKey(e: KeyboardEvent) {
  if (e.key === "Escape" && selected.value) closeSelected();
}

onMounted(() => {
  document.addEventListener("keydown", onKey);
});
onBeforeUnmount(() => {
  cancelDebounce();
  document.removeEventListener("keydown", onKey);
});
</script>

<template>
  <div class="reader-page">
    <!-- Top progress bar — shows during translation -->
    <div v-if="loading" class="top-progress" aria-hidden="true" />

    <!-- Header -->
    <header class="page-head">
      <div class="title-block">
        <h1>
          <span class="emoji">📖</span> 阅读 &amp; 翻译
          <span v-if="loading" class="loading-banner">
            <span class="loading-dot" />
            <span class="loading-dot" style="animation-delay: 0.15s" />
            <span class="loading-dot" style="animation-delay: 0.3s" />
            <span class="loading-label">AI 翻译中…</span>
          </span>
        </h1>
        <p class="muted small">
          粘段文字，自动翻译；翻译完成后点任意英文单词加入单词库
          <span v-if="addedCount > 0" class="status-chip saved">
            本次已加入 {{ addedCount }} 个 ✓
          </span>
        </p>
      </div>

      <div class="dir-toggle" role="tablist" aria-label="翻译方向">
        <button
          role="tab"
          :aria-selected="direction === 'en-to-zh'"
          :class="{ active: direction === 'en-to-zh' }"
          @click="setDirection('en-to-zh')"
        >英 → 中</button>
        <button
          role="tab"
          :aria-selected="direction === 'zh-to-en'"
          :class="{ active: direction === 'zh-to-en' }"
          @click="setDirection('zh-to-en')"
        >中 → 英</button>
      </div>
    </header>

    <div v-if="error" class="error glass-dim">{{ error }}</div>

    <!-- Two panes -->
    <div class="panes">
      <!-- Source pane -->
      <section class="pane glass">
        <div class="pane-head">
          <span class="pane-label">{{ sourceLabel }}</span>
          <span class="pane-meta tertiary">
            <template v-if="wordCount">{{ wordCount }} {{ direction === 'en-to-zh' ? '词' : '字' }} · </template>{{ charCount }} 字符
            <span v-if="mode === 'read' && direction === 'en-to-zh'" class="hint-tag">点词加入 · 点空白处编辑</span>
            <span v-else-if="mode === 'read'" class="hint-tag">点任意位置编辑</span>
          </span>
        </div>

        <textarea
          v-if="mode === 'edit'"
          ref="textareaRef"
          v-model="sourceText"
          class="textarea"
          :placeholder="sourcePlaceholder"
          spellcheck="false"
          @paste="onPaste"
        />

        <!-- en→zh: clickable word reading -->
        <div
          v-else-if="direction === 'en-to-zh'"
          ref="readContainer"
          class="reading"
          @click="enterEditMode"
        >
          <template v-for="(t, i) in tokens" :key="i">
            <span
              v-if="t.kind === 'word'"
              class="w"
              :class="{ active: selected?.text === t.text }"
              @click.stop="onWordClick($event, t.text)"
            >{{ t.text }}</span>
            <span v-else class="gap">{{ t.text }}</span>
          </template>
        </div>

        <!-- zh→en: plain text reading, no spans -->
        <div
          v-else
          class="reading reading-plain"
          @click="enterEditMode"
        >{{ chinese }}</div>
      </section>

      <!-- Target pane -->
      <section class="pane glass">
        <div class="pane-head">
          <span class="pane-label">{{ targetLabel }}</span>
          <span v-if="targetText" class="pane-meta tertiary">{{ targetText.length }} 字符</span>
        </div>

        <div v-if="loading && !targetText" class="skeleton">
          <div class="skeleton-line" style="width: 92%"></div>
          <div class="skeleton-line" style="width: 86%"></div>
          <div class="skeleton-line" style="width: 78%"></div>
          <div class="skeleton-line" style="width: 90%"></div>
          <div class="skeleton-line" style="width: 64%"></div>
        </div>

        <div v-else-if="targetText" class="target" :class="{ stale: loading }">{{ targetText }}</div>

        <div v-else class="empty">
          <div class="empty-emoji">🌐</div>
          <p class="muted">
            {{ direction === 'en-to-zh' ? '粘段英文，几秒后这里会出现中文' : '粘段中文，几秒后这里会出现英文' }}
          </p>
          <p v-if="!sourceText" class="tertiary small">
            或者
            <button class="link-btn" @click="pasteExample">塞个示例进来</button>
          </p>
        </div>
      </section>
    </div>

    <!-- Bottom word panel — en→zh only -->
    <section v-if="direction === 'en-to-zh'" class="word-panel glass">
      <div v-if="!selected" class="wp-empty tertiary">
        <span class="wp-hint-emoji">🔎</span>
        点任意英文单词查看读法和释义
      </div>

      <div v-else-if="selected.loading" class="wp-loading muted">
        查询「{{ selected.text }}」…
      </div>

      <div v-else-if="selected.found" class="wp-detail">
        <div class="wp-head">
          <span class="wp-word">{{ selected.text }}</span>
          <span v-if="selected.phonetic" class="wp-phon">{{ selected.phonetic }}</span>
          <span v-if="selected.pos" class="wp-pos">{{ selected.pos }}</span>
        </div>
        <div class="wp-trans">{{ selected.translation }}</div>
        <div class="wp-actions">
          <span v-if="selected.alreadySaved" class="wp-saved">✓ 已在单词库</span>
          <button
            v-else
            class="btn btn-primary"
            :disabled="selected.adding"
            @click="addSelectedWord"
          >
            {{ selected.adding ? "添加中…" : "+ 加入单词库" }}
          </button>
          <button class="btn btn-ghost wp-close-btn" @click="closeSelected">关闭</button>
        </div>
        <div v-if="selected.addError" class="wp-error">{{ selected.addError }}</div>
      </div>

      <div v-else class="wp-not-found">
        <div class="wp-head">
          <span class="wp-word">{{ selected.text }}</span>
        </div>
        <div class="muted small">
          本地词典没收录这个词。配置了 AI 的话可以直接「加入单词库」让 AI 兜底翻译。
        </div>
        <div class="wp-actions">
          <button
            class="btn btn-primary"
            :disabled="selected.adding"
            @click="addSelectedWord"
          >
            {{ selected.adding ? "添加中…" : "+ 加入单词库" }}
          </button>
          <button class="btn btn-ghost wp-close-btn" @click="closeSelected">关闭</button>
        </div>
        <div v-if="selected.addError" class="wp-error">{{ selected.addError }}</div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.reader-page {
  display: flex;
  flex-direction: column;
  gap: 18px;
  min-height: 0;
}

/* ─── Top progress bar ──────────────────────────────────── */
.top-progress {
  position: fixed;
  top: 0;
  left: 220px;
  right: 0;
  height: 3px;
  z-index: 1000;
  background: var(--brand-soft);
  overflow: hidden;
  pointer-events: none;
}
.top-progress::after {
  content: "";
  position: absolute;
  inset: 0;
  background: linear-gradient(
    90deg,
    transparent 0%,
    var(--brand) 50%,
    transparent 100%
  );
  background-size: 40% 100%;
  background-repeat: no-repeat;
  animation: top-progress-slide 1.1s linear infinite;
}
@keyframes top-progress-slide {
  0%   { background-position: -50% 0; }
  100% { background-position: 150% 0; }
}

@media (max-width: 860px) {
  .top-progress { left: 0; }
}

/* ─── Header ─────────────────────────────────────── */
.page-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20px;
  flex-wrap: wrap;
}

.title-block h1 {
  font-family: var(--font-serif);
  margin: 0 0 4px;
  font-size: 22px;
  font-weight: 700;
  letter-spacing: -0.02em;
  display: flex;
  align-items: center;
  gap: 14px;
  flex-wrap: wrap;
}
.emoji { font-size: 22px; }

.loading-banner {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 14px 4px 12px;
  border-radius: 999px;
  background: linear-gradient(135deg, var(--brand) 0%, var(--accent) 100%);
  color: var(--brand-strong-text);
  font-size: 13px;
  font-weight: 600;
  letter-spacing: 0.01em;
  box-shadow: 0 4px 16px rgba(74, 110, 62, 0.35);
  animation: banner-pulse 1.8s ease-in-out infinite;
}
.loading-label { margin-left: 4px; }

.loading-dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: #fff;
  display: inline-block;
  animation: dot-bounce 1.1s ease-in-out infinite;
}
@keyframes dot-bounce {
  0%, 80%, 100% { transform: scale(0.6); opacity: 0.6; }
  40%           { transform: scale(1.1); opacity: 1; }
}
@keyframes banner-pulse {
  0%, 100% { box-shadow: 0 4px 16px rgba(74, 110, 62, 0.35); }
  50%      { box-shadow: 0 4px 24px rgba(184, 145, 101, 0.55); }
}

.title-block p {
  margin: 0;
  font-size: 13px;
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.small { font-size: 13px; }

.status-chip {
  font-weight: 600;
  padding: 2px 10px;
  border-radius: 999px;
  font-size: 12px;
}
.status-chip.saved {
  background: var(--brand-soft);
  color: var(--brand);
}

/* ─── Direction toggle ──────────────────────────── */
.dir-toggle {
  display: inline-flex;
  align-self: center;
  gap: 4px;
  padding: 4px;
  background: var(--glass-bg-dim);
  border-radius: 999px;
  border: 1px solid var(--glass-border);
  flex-shrink: 0;
}

.dir-toggle button {
  appearance: none;
  background: transparent;
  border: none;
  padding: 7px 18px;
  border-radius: 999px;
  font: inherit;
  font-size: 13px;
  font-weight: 500;
  color: var(--text-secondary);
  cursor: pointer;
  transition: background 150ms ease, color 150ms ease;
}

.dir-toggle button:hover:not(.active) {
  color: var(--text-primary);
}

.dir-toggle button.active {
  background: var(--brand-soft);
  color: var(--brand);
  font-weight: 600;
}

.error {
  padding: 10px 16px;
  border-radius: 12px;
  color: var(--danger);
  font-size: 14px;
}

/* ─── Panes ──────────────────────────────────────── */
.panes {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 18px;
  min-height: 0;
}

.pane {
  padding: 18px 20px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-width: 0;
  min-height: 380px;
}

.pane-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--hairline);
  gap: 10px;
  flex-wrap: wrap;
}

.pane-label {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--text-secondary);
}

.pane-meta {
  font-size: 11px;
  font-variant-numeric: tabular-nums;
  display: flex;
  align-items: center;
  gap: 10px;
}

.hint-tag {
  font-size: 11px;
  color: var(--brand);
  background: var(--brand-soft);
  padding: 2px 8px;
  border-radius: 999px;
  font-weight: 600;
  letter-spacing: 0;
  text-transform: none;
}

/* ─── Textarea ────────────────────────────────────── */
.textarea {
  flex: 1;
  appearance: none;
  border: none;
  outline: none;
  background: transparent;
  resize: none;
  padding: 4px 2px;
  font: inherit;
  font-size: 15px;
  line-height: 1.7;
  color: var(--text-primary);
  font-family: var(--font-ui);
}

.textarea::placeholder {
  color: var(--text-tertiary);
}

/* ─── Reading mode ────────────────────────────────── */
.reading {
  position: relative;
  flex: 1;
  padding: 4px 2px;
  font-size: 16px;
  line-height: 1.8;
  white-space: pre-wrap;
  word-break: break-word;
  color: var(--text-primary);
  cursor: text;
  user-select: text;
}

.w {
  cursor: pointer;
  border-radius: 4px;
  padding: 0 1px;
  margin: 0 -1px;
  transition: background 100ms ease, color 100ms ease;
}
.w:hover {
  background: var(--brand-soft);
  color: var(--brand);
}
.w.active {
  background: var(--brand);
  color: var(--brand-strong-text);
}

.gap {
  white-space: pre-wrap;
  user-select: text;
}

/* ─── Target pane content ────────────────────────── */
.target {
  flex: 1;
  padding: 4px 2px;
  font-size: 16px;
  line-height: 1.85;
  color: var(--text-primary);
  white-space: pre-wrap;
  word-break: break-word;
  overflow-y: auto;
  transition: opacity 200ms ease;
}

.target.stale {
  opacity: 0.45;
}

.skeleton {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 10px 2px;
}

.skeleton-line {
  height: 14px;
  border-radius: 7px;
  background: linear-gradient(
    90deg,
    var(--glass-bg-dim) 0%,
    var(--brand-soft) 50%,
    var(--glass-bg-dim) 100%
  );
  background-size: 200% 100%;
  animation: shimmer 1.4s ease-in-out infinite;
}

@keyframes shimmer {
  0%   { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

.empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  gap: 6px;
  padding: 20px;
}

.empty-emoji {
  font-size: 40px;
  line-height: 1;
  margin-bottom: 4px;
  opacity: 0.7;
}

.empty p { margin: 0; }

.link-btn {
  appearance: none;
  border: none;
  background: transparent;
  color: var(--brand);
  cursor: pointer;
  font: inherit;
  font-size: inherit;
  padding: 0;
  text-decoration: underline;
  text-decoration-color: var(--brand-soft);
  text-underline-offset: 3px;
}
.link-btn:hover { text-decoration-color: var(--brand); }

/* ─── Bottom word panel ──────────────────────────── */
.word-panel {
  padding: 14px 20px;
  border-left: 3px solid var(--brand);
  min-height: 76px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  justify-content: center;
}

.wp-empty {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 13px;
  padding: 6px 0;
}
.wp-hint-emoji { font-size: 18px; opacity: 0.7; }

.wp-loading {
  padding: 8px 0;
  font-size: 13px;
}

.wp-detail, .wp-not-found {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.wp-head {
  display: flex;
  align-items: baseline;
  gap: 12px;
  flex-wrap: wrap;
}

.wp-word {
  font-family: var(--font-serif);
  font-size: 26px;
  font-weight: 700;
  letter-spacing: -0.01em;
  color: var(--text-primary);
}

.wp-phon {
  font-family: var(--font-mono);
  font-size: 13px;
  color: var(--text-tertiary);
}

.wp-pos {
  font-family: var(--font-serif);
  font-style: italic;
  font-size: 12px;
  padding: 2px 8px;
  border-radius: 999px;
  background: var(--brand-soft);
  color: var(--brand);
}

.wp-trans {
  font-size: 15px;
  color: var(--accent);
  font-weight: 500;
  line-height: 1.55;
  word-wrap: break-word;
}

.wp-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  padding-top: 4px;
}

.wp-saved {
  font-size: 13px;
  color: var(--brand);
  font-weight: 600;
}

.wp-close-btn {
  padding: 6px 14px;
  font-size: 13px;
}

.btn-primary {
  padding: 6px 16px;
  font-size: 13px;
  font-weight: 600;
}

.wp-error {
  font-size: 12px;
  color: var(--danger);
}

/* ─── Responsive ─────────────────────────────────── */
@media (max-width: 1000px) {
  .panes { grid-template-columns: 1fr; }
  .pane { min-height: 260px; }
  .page-head { flex-direction: column; align-items: stretch; }
  .dir-toggle { align-self: flex-start; }
}
</style>
