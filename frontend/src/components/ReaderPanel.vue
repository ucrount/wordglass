<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref } from "vue";
import { api, type WordPreview } from "../api";

const mode = ref<"edit" | "view">("edit");
const english = ref("");
const chinese = ref("");
const loading = ref(false);
const error = ref("");

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
}

const popup = ref<Popup | null>(null);
const viewContainer = ref<HTMLElement | null>(null);

// Split text into clickable word tokens and inert filler (whitespace, punctuation,
// numbers). Words are A-Za-z runs that may include ' or - (don't, mother-in-law).
type Token = { kind: "word" | "gap"; text: string };
const tokens = computed<Token[]>(() => {
  const out: Token[] = [];
  const re = /[A-Za-z][A-Za-z'-]*/g;
  let last = 0;
  for (const m of english.value.matchAll(re)) {
    if (m.index! > last) out.push({ kind: "gap", text: english.value.slice(last, m.index) });
    out.push({ kind: "word", text: m[0] });
    last = m.index! + m[0].length;
  }
  if (last < english.value.length) out.push({ kind: "gap", text: english.value.slice(last) });
  return out;
});

async function doTranslate() {
  const text = english.value.trim();
  if (!text || loading.value) return;
  loading.value = true;
  error.value = "";
  try {
    const res = await api.translateText(text);
    chinese.value = res.translation;
    mode.value = "view";
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
  english.value = "";
  chinese.value = "";
  error.value = "";
  mode.value = "edit";
  popup.value = null;
}

async function onWordClick(event: MouseEvent, word: string) {
  event.stopPropagation();
  const rect = (event.currentTarget as HTMLElement).getBoundingClientRect();
  const containerRect = viewContainer.value?.getBoundingClientRect();
  const x = rect.left - (containerRect?.left ?? 0);
  const y = rect.bottom - (containerRect?.top ?? 0) + 6;

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
    popup.value = { ...popup.value, adding: false, alreadySaved: true };
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
onUnmounted(() => {
  document.removeEventListener("keydown", onKey);
  document.removeEventListener("click", closePopup);
});

const canTranslate = computed(() => english.value.trim().length > 0 && !loading.value);
</script>

<template>
  <section class="reader glass">
    <header class="head">
      <h2><span class="emoji">📖</span> 阅读 &amp; 翻译</h2>
      <div class="actions">
        <button v-if="mode === 'view'" class="btn btn-ghost small" @click="backToEdit">编辑</button>
        <button class="btn btn-ghost small" :disabled="!english && !chinese" @click="clearAll">清空</button>
        <button class="btn btn-primary small" :disabled="!canTranslate" @click="doTranslate">
          {{ loading ? "翻译中…" : "🤖 翻译" }}
        </button>
      </div>
    </header>

    <p class="muted small intro">
      粘一段英文文本 → 点 <b>🤖 翻译</b> 得到中文译文 → 点任意单词加入单词库，反复练习。
    </p>

    <div v-if="error" class="error glass-dim">{{ error }}</div>

    <div class="panes">
      <div class="pane left">
        <div class="pane-label tertiary">原文（English）</div>
        <textarea
          v-if="mode === 'edit'"
          v-model="english"
          class="input textarea"
          placeholder="粘一段英文文本（最长 5000 字符）…"
          spellcheck="false"
        />
        <div
          v-else
          ref="viewContainer"
          class="tokens"
          @click.stop
        >
          <template v-for="(t, i) in tokens" :key="i">
            <span
              v-if="t.kind === 'word'"
              class="word"
              @click="onWordClick($event, t.text)"
            >{{ t.text }}</span>
            <span v-else class="gap">{{ t.text }}</span>
          </template>

          <!-- Popup -->
          <div
            v-if="popup"
            class="popup glass-strong"
            :style="{ left: popup.x + 'px', top: popup.y + 'px' }"
            @click.stop
          >
            <div class="popup-head">
              <span class="popup-word">{{ popup.word }}</span>
              <button class="popup-close" @click="closePopup" title="关闭 (Esc)">×</button>
            </div>
            <div v-if="popup.loading" class="popup-loading muted small">查询中…</div>
            <template v-else-if="popup.found">
              <div class="popup-meta">
                <span v-if="popup.phonetic" class="popup-phonetic">{{ popup.phonetic }}</span>
                <span v-if="popup.pos" class="popup-pos">{{ popup.pos }}</span>
              </div>
              <div class="popup-trans">{{ popup.translation }}</div>
            </template>
            <div v-else class="popup-empty muted small">
              本地词典未收录，加入后会用 AI 兜底（需要配置 AI）。
            </div>

            <div class="popup-actions">
              <span v-if="popup.alreadySaved" class="popup-saved">✓ 已在单词库</span>
              <button
                v-else
                class="btn btn-primary tiny"
                :disabled="popup.adding"
                @click="addWord"
              >
                {{ popup.adding ? "添加中…" : "加入单词库" }}
              </button>
            </div>
            <div v-if="popup.addError" class="popup-error">{{ popup.addError }}</div>
          </div>
        </div>
      </div>

      <div class="pane right">
        <div class="pane-label tertiary">译文（中文）</div>
        <div v-if="chinese" class="chinese">{{ chinese }}</div>
        <div v-else-if="loading" class="empty muted small">AI 翻译中，可能要 2-5 秒…</div>
        <div v-else class="empty muted small">点 🤖 翻译 后这里显示中文译文</div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.reader {
  padding: 20px 24px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.head h2 {
  margin: 0;
  font-size: 16px;
  font-weight: 700;
  letter-spacing: -0.01em;
  display: flex;
  align-items: center;
  gap: 8px;
}
.emoji { font-size: 18px; }

.actions {
  display: flex;
  gap: 6px;
}

.btn.small {
  padding: 6px 14px;
  font-size: 13px;
}
.btn.tiny {
  padding: 4px 10px;
  font-size: 12px;
}

.intro {
  margin: 0;
  font-size: 12px;
  line-height: 1.5;
}
.intro b { color: var(--brand); }

.error {
  padding: 8px 14px;
  border-radius: 10px;
  color: var(--danger);
  font-size: 13px;
}

.panes {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
  min-height: 0;
}

.pane {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
  min-height: 220px;
}

.pane-label {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

.textarea {
  flex: 1;
  min-height: 220px;
  resize: vertical;
  font-size: 14px;
  font-family: ui-monospace, "SF Mono", Menlo, monospace;
  line-height: 1.6;
  padding: 14px 16px;
}

.tokens {
  position: relative;
  flex: 1;
  padding: 14px 16px;
  border-radius: var(--radius-md);
  border: 1px solid var(--hairline);
  background: var(--glass-bg-dim);
  font-size: 15px;
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-word;
  cursor: text;
  user-select: text;
}

.word {
  cursor: pointer;
  border-radius: 4px;
  padding: 0 1px;
  transition: background 120ms ease, color 120ms ease;
}
.word:hover {
  background: var(--brand-soft);
  color: var(--brand);
}

.gap {
  white-space: pre-wrap;
}

/* Popup */
.popup {
  position: absolute;
  z-index: 50;
  width: 280px;
  padding: 12px 14px;
  border-radius: 12px;
  box-shadow: var(--glass-shadow-lg);
  font-size: 13px;
  line-height: 1.5;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.popup-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.popup-word {
  font-size: 16px;
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
  background: rgba(0,0,0,0.05);
  padding: 1px 8px;
  border-radius: 999px;
  color: var(--text-secondary);
}
[data-theme="dark"] .popup-pos { background: rgba(255,255,255,0.08); }

.popup-trans {
  font-size: 14px;
  color: var(--brand);
  font-weight: 500;
}

.popup-empty { padding: 4px 0; }
.popup-loading { padding: 8px 0; text-align: center; }

.popup-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
  padding-top: 4px;
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

/* Right pane */
.chinese {
  flex: 1;
  padding: 14px 16px;
  border-radius: var(--radius-md);
  border: 1px solid var(--hairline);
  background: var(--glass-bg-dim);
  font-size: 15px;
  line-height: 1.7;
  color: var(--text-primary);
  white-space: pre-wrap;
  word-break: break-word;
  overflow-y: auto;
}

.empty {
  flex: 1;
  padding: 14px 16px;
  border-radius: var(--radius-md);
  border: 1px dashed var(--hairline);
  display: flex;
  align-items: center;
  justify-content: center;
  text-align: center;
}

@media (max-width: 900px) {
  .panes { grid-template-columns: 1fr; }
}
</style>
