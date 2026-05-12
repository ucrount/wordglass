<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
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

// Split English into clickable word tokens + inert gaps (whitespace/punct/digits)
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
const canTranslate = computed(() => english.value.trim().length > 0 && !loading.value);

// ─── Actions ───────────────────────────────────────────────────────────────
async function doTranslate() {
  const text = english.value.trim();
  if (!text || loading.value) return;
  loading.value = true;
  error.value = "";
  try {
    const res = await api.translateText(text);
    chinese.value = res.translation;
    mode.value = "read";
  } catch (e: any) {
    error.value = e.message || "翻译失败";
  } finally {
    loading.value = false;
  }
}

function backToEdit() {
  mode.value = "edit";
  popup.value = null;
}

function clearAll() {
  if (!english.value && !chinese.value) return;
  if (!confirm("清空原文和译文？")) return;
  english.value = "";
  chinese.value = "";
  error.value = "";
  mode.value = "edit";
  popup.value = null;
  addedCount.value = 0;
}

function pasteExample() {
  english.value = `The morning light slipped through the cracked blinds, painting thin stripes across the wooden floor. Lena sat by the window, cradling a cup of tea, watching the city wake up. Somewhere in the distance, a tram bell rang. She thought about all the things she had meant to do this week, and how a quiet Saturday could rearrange her priorities entirely.`;
  mode.value = "edit";
}

// ─── Popup ─────────────────────────────────────────────────────────────────
async function onWordClick(event: MouseEvent, word: string) {
  event.stopPropagation();
  const rect = (event.currentTarget as HTMLElement).getBoundingClientRect();
  const containerRect = readContainer.value?.getBoundingClientRect();
  if (!containerRect) return;
  const POPUP_WIDTH = 300;
  const POPUP_HEIGHT_ESTIMATE = 180;

  // Position the popup near the clicked word; flip above if it would overflow.
  const spaceBelow = window.innerHeight - rect.bottom;
  const flipAbove = spaceBelow < POPUP_HEIGHT_ESTIMATE + 20;
  let x = rect.left - containerRect.left;
  // Don't let the popup overflow the right edge of the container
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
  document.removeEventListener("keydown", onKey);
  document.removeEventListener("click", closePopup);
});
</script>

<template>
  <div class="reader-page">
    <!-- Header -->
    <header class="page-head">
      <div class="title-block">
        <h1><span class="emoji">📖</span> 阅读 &amp; 翻译</h1>
        <p class="muted small">
          粘一段英文 → AI 翻译成中文 → 点任意单词加入单词库
          <span v-if="addedCount > 0" class="added-chip">
            本次已加入 {{ addedCount }} 个 ✓
          </span>
        </p>
      </div>
      <div class="actions">
        <button
          v-if="mode === 'read'"
          class="btn btn-ghost"
          @click="backToEdit"
        >✎ 编辑原文</button>
        <button
          class="btn btn-ghost"
          :disabled="!english && !chinese"
          @click="clearAll"
        >清空</button>
        <button
          class="btn btn-primary"
          :disabled="!canTranslate"
          @click="doTranslate"
        >
          {{ loading ? "翻译中…" : "🤖 翻译整段" }}
        </button>
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
          </span>
        </div>

        <textarea
          v-if="mode === 'edit'"
          v-model="english"
          class="textarea"
          placeholder="把英文粘进来——文章、新闻、邮件、字幕都行（最长 5000 字符）…"
          spellcheck="false"
        />

        <div v-else ref="readContainer" class="reading" @click.stop>
          <template v-for="(t, i) in tokens" :key="i">
            <span
              v-if="t.kind === 'word'"
              class="w"
              :class="{ active: popup?.word === t.text }"
              @click="onWordClick($event, t.text)"
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

        <div v-if="loading" class="skeleton">
          <div class="skeleton-line" style="width: 92%"></div>
          <div class="skeleton-line" style="width: 86%"></div>
          <div class="skeleton-line" style="width: 78%"></div>
          <div class="skeleton-line" style="width: 90%"></div>
          <div class="skeleton-line" style="width: 64%"></div>
        </div>

        <div v-else-if="chinese" class="chinese">{{ chinese }}</div>

        <div v-else class="empty">
          <div class="empty-emoji">🌐</div>
          <p class="muted">这里会显示中文译文</p>
          <p v-if="!english" class="tertiary small">
            先在左边粘段英文，或者
            <button class="link-btn" @click="pasteExample">塞个示例进来</button>
          </p>
          <p v-else class="tertiary small">点 🤖 翻译整段 开始</p>
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

/* ─── Header ─────────────────────────────────────── */
.page-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20px;
  flex-wrap: wrap;
}

.title-block h1 {
  margin: 0 0 4px;
  font-size: 22px;
  font-weight: 700;
  letter-spacing: -0.02em;
  display: flex;
  align-items: center;
  gap: 10px;
}
.emoji { font-size: 22px; }

.title-block p {
  margin: 0;
  font-size: 13px;
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.small { font-size: 13px; }

.added-chip {
  background: var(--brand-soft);
  color: var(--brand);
  font-weight: 600;
  padding: 2px 10px;
  border-radius: 999px;
  font-size: 12px;
}

.actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
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
  background: rgba(0, 0, 0, 0.05);
  padding: 2px 8px;
  border-radius: 999px;
  color: var(--text-secondary);
}
[data-theme="dark"] .popup-pos { background: rgba(255, 255, 255, 0.08); }

.popup-trans {
  font-size: 14px;
  color: var(--brand);
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
  .actions { justify-content: flex-end; }
}
</style>
