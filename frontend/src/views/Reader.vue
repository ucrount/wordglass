<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { api, type WordPreview } from "../api";

// ─── Persisted text ────────────────────────────────────────────────────────
const STORAGE_KEY = "wordglass.reader";

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

const stored = loadStored();
const english = ref(stored.en);
const chinese = ref(stored.zh);
const textareaRef = ref<HTMLTextAreaElement | null>(null);

watch([english, chinese], ([en, zh]) => {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ en, zh }));
  } catch { /* quota — ignore */ }
});

// ─── State ─────────────────────────────────────────────────────────────────
type Mode = "edit" | "read";
const mode = ref<Mode>(chinese.value ? "read" : "edit");
const loading = ref(false);
const error = ref("");
const addedCount = ref(0);

// Auto-translate debounce. Fires 1200ms after the last keystroke or right
// away on paste — so the user never thinks about a "translate" button.
const DEBOUNCE_MS = 1200;
let debounceTimer: ReturnType<typeof setTimeout> | null = null;
let lastTranslatedText = stored.en;

function cancelDebounce() {
  if (debounceTimer) {
    clearTimeout(debounceTimer);
    debounceTimer = null;
  }
}

function scheduleTranslate(immediate = false) {
  cancelDebounce();
  const text = english.value.trim();
  if (!text) {
    chinese.value = "";
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

watch(english, () => scheduleTranslate(false));

function onPaste() {
  setTimeout(() => scheduleTranslate(true), 0);
}

interface Popup {
  word: string;
  loading: boolean;
  found: boolean;
  phonetic: string;
  pos: string;
  translation: string;
  alreadySaved: boolean;
  adding: boolean;
  addError: string;
  x: number;
  y: number;
  flipAbove: boolean;
}
const popup = ref<Popup | null>(null);
const readContainer = ref<HTMLElement | null>(null);

type Token = { kind: "word" | "gap"; text: string };
const tokens = computed<Token[]>(() => {
  const out: Token[] = [];
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

const wordCount = computed(
  () => (english.value.match(/[A-Za-z][A-Za-z'-]*/g) || []).length
);
const charCount = computed(() => english.value.length);

// ─── Actions ───────────────────────────────────────────────────────────────
async function doTranslate() {
  cancelDebounce();
  const text = english.value.trim();
  if (!text || loading.value) return;
  // If the textarea is focused, the user is actively typing — translate but
  // DON'T snap to read mode (it'd lose focus mid-edit).
  const textareaFocused = document.activeElement === textareaRef.value;
  loading.value = true;
  error.value = "";
  try {
    const res = await api.translateText(text);
    chinese.value = res.translation;
    lastTranslatedText = text;
    if (english.value.trim() === text && !textareaFocused) {
      mode.value = "read";
    }
  } catch (e: any) {
    error.value = e.message || "翻译失败";
  } finally {
    loading.value = false;
    if (english.value.trim() && english.value.trim() !== lastTranslatedText.trim()) {
      scheduleTranslate(false);
    }
  }
}

function enterEditMode() {
  mode.value = "edit";
  popup.value = null;
  nextTick(() => {
    textareaRef.value?.focus();
    // Put cursor at the end so the user can keep typing naturally
    if (textareaRef.value) {
      const len = textareaRef.value.value.length;
      textareaRef.value.setSelectionRange(len, len);
    }
  });
}

function pasteExample() {
  english.value = `The morning light slipped through the cracked blinds, painting thin stripes across the wooden floor. Lena sat by the window, cradling a cup of tea, watching the city wake up. Somewhere in the distance, a tram bell rang. She thought about all the things she had meant to do this week, and how a quiet Saturday could rearrange her priorities entirely.`;
  mode.value = "edit";
  scheduleTranslate(true);
}

// ─── Popup ─────────────────────────────────────────────────────────────────
async function onWordClick(event: MouseEvent, word: string) {
  event.stopPropagation();
  const rect = (event.currentTarget as HTMLElement).getBoundingClientRect();
  const containerRect = readContainer.value?.getBoundingClientRect();
  if (!containerRect) return;
  const POPUP_WIDTH = 300;
  const POPUP_HEIGHT_ESTIMATE = 180;

  const spaceBelow = window.innerHeight - rect.bottom;
  const flipAbove = spaceBelow < POPUP_HEIGHT_ESTIMATE + 20;
  let x = rect.left - containerRect.left;
  const maxX = containerRect.width - POPUP_WIDTH - 8;
  if (x > maxX) x = Math.max(8, maxX);
  const y = flipAbove
    ? rect.top - containerRect.top - 8
    : rect.bottom - containerRect.top + 8;

  popup.value = {
    word,
    loading: true,
    found: false,
    phonetic: "",
    pos: "",
    translation: "",
    alreadySaved: false,
    adding: false,
    addError: "",
    x,
    y,
    flipAbove,
  };

  try {
    const data: WordPreview = await api.previewWord(word);
    if (!popup.value || popup.value.word !== word) return;
    if (data.found) {
      popup.value = {
        ...popup.value,
        loading: false,
        found: true,
        phonetic: data.phonetic,
        pos: data.pos,
        translation: data.translation,
        alreadySaved: data.already_saved,
      };
    } else {
      popup.value = { ...popup.value, loading: false, found: false };
    }
  } catch {
    if (popup.value) popup.value = { ...popup.value, loading: false, found: false };
  }
}

async function addWord() {
  if (!popup.value || popup.value.adding) return;
  popup.value.adding = true;
  popup.value.addError = "";
  try {
    await api.addWord(popup.value.word);
    if (popup.value) {
      popup.value = { ...popup.value, adding: false, alreadySaved: true };
      addedCount.value++;
    }
  } catch (e: any) {
    if (popup.value) {
      popup.value = { ...popup.value, adding: false, addError: e.message || "添加失败" };
    }
  }
}

function closePopup() {
  popup.value = null;
}

function onKey(e: KeyboardEvent) {
  if (e.key === "Escape") closePopup();
}

onMounted(() => {
  document.addEventListener("keydown", onKey);
  document.addEventListener("click", closePopup);
});
onBeforeUnmount(() => {
  cancelDebounce();
  document.removeEventListener("keydown", onKey);
  document.removeEventListener("click", closePopup);
});
</script>

<template>
  <div class="reader-page">
    <!-- Top progress bar — shows during translation, very visible -->
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
          粘段英文，自动翻译；翻译完成后点任意单词加入单词库
          <span v-if="addedCount > 0" class="status-chip saved">
            本次已加入 {{ addedCount }} 个 ✓
          </span>
        </p>
      </div>
    </header>

    <div v-if="error" class="error glass-dim">{{ error }}</div>

    <!-- Two panes -->
    <div class="panes">
      <!-- Left: original text -->
      <section class="pane glass">
        <div class="pane-head">
          <span class="pane-label">原文（English）</span>
          <span class="pane-meta tertiary">
            <template v-if="wordCount">{{ wordCount }} 词 · </template>{{ charCount }} 字
            <span v-if="mode === 'read'" class="hint-tag">点词加入 · 点空白处编辑</span>
          </span>
        </div>

        <textarea
          v-if="mode === 'edit'"
          ref="textareaRef"
          v-model="english"
          class="textarea"
          placeholder="把英文粘进来——文章、新闻、邮件、字幕都行（最长 5000 字符）…"
          spellcheck="false"
          @paste="onPaste"
        />

        <div
          v-else
          ref="readContainer"
          class="reading"
          @click="enterEditMode"
        >
          <template v-for="(t, i) in tokens" :key="i">
            <span
              v-if="t.kind === 'word'"
              class="w"
              :class="{ active: popup?.word === t.text }"
              @click.stop="onWordClick($event, t.text)"
            >{{ t.text }}</span>
            <span v-else class="gap">{{ t.text }}</span>
          </template>

          <!-- Word popup -->
          <div
            v-if="popup"
            class="popup glass-strong"
            :class="{ above: popup.flipAbove }"
            :style="{ left: popup.x + 'px', top: popup.y + 'px' }"
            @click.stop
          >
            <div class="popup-head">
              <span class="popup-word">{{ popup.word }}</span>
              <button class="popup-close" @click="closePopup" title="关闭 (Esc)">×</button>
            </div>

            <div v-if="popup.loading" class="popup-loading muted">查询中…</div>
            <template v-else-if="popup.found">
              <div class="popup-meta">
                <span v-if="popup.phonetic" class="popup-phonetic">{{ popup.phonetic }}</span>
                <span v-if="popup.pos" class="popup-pos">{{ popup.pos }}</span>
              </div>
              <div class="popup-trans">{{ popup.translation }}</div>
            </template>
            <div v-else class="popup-empty muted small">
              本地词典未收录这个词。可以点击加入单词库，配置了 AI 的话会自动兜底翻译。
            </div>

            <div class="popup-actions">
              <span v-if="popup.alreadySaved" class="popup-saved">✓ 已在单词库</span>
              <button
                v-else
                class="btn btn-primary tiny"
                :disabled="popup.adding"
                @click="addWord"
              >
                {{ popup.adding ? "添加中…" : "+ 加入单词库" }}
              </button>
            </div>
            <div v-if="popup.addError" class="popup-error">{{ popup.addError }}</div>
          </div>
        </div>
      </section>

      <!-- Right: translation -->
      <section class="pane glass">
        <div class="pane-head">
          <span class="pane-label">译文（中文）</span>
          <span v-if="chinese" class="pane-meta tertiary">{{ chinese.length }} 字</span>
        </div>

        <div v-if="loading && !chinese" class="skeleton">
          <div class="skeleton-line" style="width: 92%"></div>
          <div class="skeleton-line" style="width: 86%"></div>
          <div class="skeleton-line" style="width: 78%"></div>
          <div class="skeleton-line" style="width: 90%"></div>
          <div class="skeleton-line" style="width: 64%"></div>
        </div>

        <div v-else-if="chinese" class="chinese" :class="{ stale: loading }">{{ chinese }}</div>

        <div v-else class="empty">
          <div class="empty-emoji">🌐</div>
          <p class="muted">粘段英文，几秒后这里会出现中文</p>
          <p v-if="!english" class="tertiary small">
            或者
            <button class="link-btn" @click="pasteExample">塞个示例进来</button>
          </p>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.reader-page {
  display: flex;
  flex-direction: column;
  gap: 18px;
  min-height: 0;
}

/* ─── Top progress bar (very prominent) ──────────────── */
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

/* ─── Loading banner — prominent inline beside title ──── */
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
  min-height: 520px;
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
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC",
               "Hiragino Sans GB", "Microsoft YaHei", sans-serif;
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
  color: #fff;
}

.gap {
  white-space: pre-wrap;
  user-select: text;
}

/* ─── Popup ──────────────────────────────────────── */
.popup {
  position: absolute;
  z-index: 30;
  width: 300px;
  padding: 14px 16px;
  border-radius: 14px;
  box-shadow: var(--glass-shadow-lg);
  font-size: 13px;
  line-height: 1.5;
  display: flex;
  flex-direction: column;
  gap: 10px;
  animation: pop-in 180ms cubic-bezier(0.16, 1, 0.3, 1);
}

.popup.above {
  transform: translateY(-100%);
}

@keyframes pop-in {
  from { opacity: 0; transform: translateY(-4px) scale(0.96); }
  to   { opacity: 1; transform: translateY(0) scale(1); }
}
.popup.above {
  animation-name: pop-in-above;
}
@keyframes pop-in-above {
  from { opacity: 0; transform: translateY(calc(-100% - 4px)) scale(0.96); }
  to   { opacity: 1; transform: translateY(-100%) scale(1); }
}

.popup-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.popup-word {
  font-family: var(--font-serif);
  font-size: 17px;
  font-weight: 700;
  color: var(--text-primary);
}
.popup-close {
  border: none;
  background: transparent;
  font-size: 18px;
  cursor: pointer;
  color: var(--text-tertiary);
  width: 24px;
  height: 24px;
  border-radius: 6px;
  line-height: 1;
}
.popup-close:hover { background: var(--glass-bg-dim); color: var(--text-primary); }

.popup-meta {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  font-size: 12px;
  align-items: center;
}

.popup-phonetic {
  font-family: ui-monospace, "SF Mono", Menlo, monospace;
  color: var(--text-tertiary);
}

.popup-pos {
  font-family: var(--font-serif);
  font-style: italic;
  background: var(--brand-soft);
  padding: 2px 8px;
  border-radius: 999px;
  color: var(--brand);
}

.popup-trans {
  font-size: 14px;
  color: var(--accent);
  font-weight: 500;
  line-height: 1.55;
}

.popup-empty { padding: 2px 0; }
.popup-loading {
  padding: 12px 0;
  text-align: center;
  font-size: 12px;
}

.popup-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
  padding-top: 8px;
  border-top: 1px solid var(--hairline);
}

.popup-saved {
  font-size: 12px;
  color: var(--brand);
  font-weight: 600;
}

.popup-error {
  font-size: 12px;
  color: var(--danger);
}

.btn.tiny {
  padding: 5px 12px;
  font-size: 12px;
  font-weight: 600;
}

/* ─── Right pane: translation / skeleton / empty ──── */
.chinese {
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

.chinese.stale {
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

/* ─── Responsive ─────────────────────────────────── */
@media (max-width: 1000px) {
  .panes { grid-template-columns: 1fr; }
  .pane { min-height: 360px; }
  .page-head { flex-direction: column; align-items: stretch; }
}
</style>
