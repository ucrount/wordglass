<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import { api, type WordOut } from "../api";
import { isSpeechSupported, speak } from "../composables/tts";

const props = defineProps<{ wordId: number | null }>();
const emit = defineEmits<{
  (e: "close"): void;
  (e: "deleted", wordId: number): void;
  (e: "starred-changed", wordId: number, starred: boolean): void;
}>();

const word = ref<WordOut | null>(null);
const loading = ref(false);
const error = ref("");
const deleting = ref(false);
const ttsSupported = isSpeechSupported();

async function load() {
  if (props.wordId == null) {
    word.value = null;
    return;
  }
  loading.value = true;
  error.value = "";
  word.value = null;
  try {
    word.value = await api.getWord(props.wordId);
  } catch (e: any) {
    error.value = e.message || "加载失败";
  } finally {
    loading.value = false;
  }
}

watch(() => props.wordId, load, { immediate: true });

async function handleDelete() {
  if (!word.value) return;
  if (!confirm(`确认删除「${word.value.text}」？此操作不可恢复。`)) return;
  deleting.value = true;
  try {
    await api.deleteWord(word.value.id);
    emit("deleted", word.value.id);
  } catch (e: any) {
    error.value = e.message || "删除失败";
  } finally {
    deleting.value = false;
  }
}

async function toggleStar() {
  if (!word.value) return;
  const target = !word.value.starred;
  word.value.starred = target;
  try {
    await api.setStarred(word.value.id, target);
    emit("starred-changed", word.value.id, target);
  } catch (e: any) {
    if (word.value) word.value.starred = !target;
    error.value = e.message || "操作失败";
    setTimeout(() => { error.value = ""; }, 4000);
  }
}

function handleKey(e: KeyboardEvent) {
  if (e.key === "Escape") emit("close");
}

const masteryLabel = computed(() => {
  if (!word.value) return "";
  const m = word.value.mastery;
  if (m === 0) return "未学";
  if (m <= 2) return "学习中";
  if (m <= 4) return "熟悉";
  return "已掌握";
});

const accuracy = computed(() => {
  if (!word.value || word.value.review_count === 0) return null;
  return Math.round((word.value.correct_count / word.value.review_count) * 100);
});

onMounted(() => window.addEventListener("keydown", handleKey));
onUnmounted(() => window.removeEventListener("keydown", handleKey));
</script>

<template>
  <Teleport to="body">
    <Transition name="fade">
      <div v-if="wordId != null" class="drawer-mask" @click.self="$emit('close')">
        <Transition name="slide">
          <aside v-if="wordId != null" class="drawer glass-strong">
            <button class="close" @click="$emit('close')" title="关闭 (Esc)">×</button>

            <div v-if="loading" class="loading muted">加载中…</div>

            <div v-else-if="error" class="error">
              <p>{{ error }}</p>
              <button class="btn" @click="load">重试</button>
            </div>

            <template v-else-if="word">
              <!-- Header -->
              <div class="head">
                <div class="word-row">
                  <span class="word-text">{{ word.text }}</span>
                  <button
                    v-if="ttsSupported"
                    class="speaker"
                    @click="speak(word.text)"
                    title="朗读"
                  >🔊</button>
                </div>
                <div class="head-actions">
                  <button
                    class="star-btn"
                    :class="{ on: word.starred }"
                    @click="toggleStar"
                  >{{ word.starred ? '★ 已重点' : '☆ 标重点' }}</button>
                </div>
                <div class="meta">
                  <span v-if="word.phonetic" class="phonetic">{{ word.phonetic }}</span>
                  <span v-if="word.pos" class="chip">{{ word.pos }}</span>
                  <span v-if="word.category" class="chip category-chip">📁 {{ word.category }}</span>
                </div>
                <div class="translation">{{ word.translation || "（无翻译）" }}</div>
              </div>

              <!-- Stats panel -->
              <div class="stats">
                <div class="stat-item">
                  <div class="stat-num">{{ word.mastery }} / 5</div>
                  <div class="stat-label muted">{{ masteryLabel }}</div>
                </div>
                <div class="stat-divider" />
                <div class="stat-item">
                  <div class="stat-num">{{ word.review_count }}</div>
                  <div class="stat-label muted">已复习</div>
                </div>
                <div class="stat-divider" />
                <div class="stat-item">
                  <div class="stat-num">{{ accuracy != null ? `${accuracy}%` : "—" }}</div>
                  <div class="stat-label muted">正确率</div>
                </div>
              </div>

              <!-- Examples -->
              <section class="examples-section">
                <h3>
                  <span class="dot" />
                  例句（由易到难）
                </h3>
                <div v-if="word.examples.length === 0" class="muted small">
                  这个词暂无例句
                </div>
                <div
                  v-for="(ex, i) in word.examples"
                  :key="ex.id"
                  class="example"
                >
                  <div class="example-num">{{ i + 1 }}</div>
                  <div class="example-body">
                    <div class="example-en">{{ ex.en }}</div>
                    <div v-if="ex.zh" class="example-zh muted">{{ ex.zh }}</div>
                  </div>
                </div>
              </section>

              <!-- Footer actions -->
              <div class="footer-actions">
                <button
                  class="btn btn-danger"
                  :disabled="deleting"
                  @click="handleDelete"
                >
                  {{ deleting ? "删除中…" : "🗑 删除单词" }}
                </button>
              </div>
            </template>
          </aside>
        </Transition>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.drawer-mask {
  position: fixed;
  inset: 0;
  z-index: 90;
  background: rgba(0, 0, 0, 0.32);
  backdrop-filter: blur(6px);
  -webkit-backdrop-filter: blur(6px);
  display: flex;
  justify-content: flex-end;
}

.drawer {
  width: min(520px, 100%);
  height: 100%;
  padding: 32px 32px 24px;
  border-radius: 0;
  border-top: none;
  border-bottom: none;
  border-right: none;
  border-left: 1px solid var(--glass-border);
  display: flex;
  flex-direction: column;
  gap: 18px;
  overflow-y: auto;
  position: relative;
}

.close {
  position: absolute;
  top: 12px;
  right: 12px;
  width: 36px;
  height: 36px;
  border: none;
  background: transparent;
  font-size: 22px;
  color: var(--text-secondary);
  cursor: pointer;
  border-radius: 10px;
  transition: background 200ms ease, color 200ms ease;
}
.close:hover {
  background: var(--glass-bg-dim);
  color: var(--text-primary);
}

.loading,
.error {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 12px;
  align-items: center;
  justify-content: center;
}
.error { color: var(--danger); }

/* ─── Head ─────────────────────────────────────────── */
.head {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.word-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.word-text {
  font-family: var(--font-serif);
  font-size: clamp(32px, 4vw, 40px);
  font-weight: 700;
  letter-spacing: -0.02em;
  color: var(--text-primary);
  line-height: 1.1;
}

.speaker {
  appearance: none;
  border: none;
  background: var(--brand-soft);
  width: 36px;
  height: 36px;
  border-radius: 50%;
  font-size: 16px;
  cursor: pointer;
  transition: background 200ms ease, transform 200ms ease;
}
.speaker:hover { transform: scale(1.08); background: color-mix(in srgb, var(--brand) 28%, transparent); }

.meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.head-actions {
  display: flex;
  gap: 8px;
  margin: 4px 0 2px;
}
.star-btn {
  appearance: none;
  border: 1px solid var(--glass-border);
  background: var(--glass-bg-dim);
  padding: 6px 14px;
  border-radius: 999px;
  font: inherit;
  font-size: 12.5px;
  color: var(--text-secondary);
  cursor: pointer;
  transition: background 150ms ease, color 150ms ease, border-color 150ms ease;
}
.star-btn:hover {
  border-color: color-mix(in srgb, var(--accent) 30%, var(--glass-border));
  color: var(--text-primary);
}
.star-btn.on {
  background: color-mix(in srgb, var(--accent) 15%, transparent);
  border-color: color-mix(in srgb, var(--accent) 40%, var(--glass-border));
  color: var(--accent);
  font-weight: 600;
}

.phonetic {
  font-family: var(--font-mono);
  font-size: 14px;
  color: var(--text-tertiary);
}

.chip {
  padding: 3px 10px;
  border-radius: 999px;
  background: var(--glass-bg-dim);
  font-size: 12px;
  color: var(--text-secondary);
}

.category-chip {
  background: var(--brand-soft);
  color: var(--brand);
  font-weight: 600;
}

.translation {
  margin-top: 4px;
  font-size: 18px;
  font-weight: 500;
  color: var(--accent);
  line-height: 1.45;
}

/* ─── Stats panel ──────────────────────────────────── */
.stats {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 14px 18px;
  border-radius: var(--radius-md);
  background: var(--glass-bg-dim);
  border: 1px solid var(--hairline);
}

.stat-item {
  flex: 1;
  text-align: center;
}

.stat-num {
  font-family: var(--font-serif);
  font-size: 22px;
  font-weight: 700;
  letter-spacing: -0.02em;
  color: var(--text-primary);
}

.stat-label {
  font-size: 11px;
  margin-top: 2px;
}

.stat-divider {
  width: 1px;
  height: 30px;
  background: var(--hairline-strong);
}

/* ─── Examples ─────────────────────────────────────── */
.examples-section {
  display: flex;
  flex-direction: column;
  gap: 10px;
  flex: 1;
}

.examples-section h3 {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0 0 4px;
  font-size: 14px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-secondary);
}

.examples-section h3 .dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--brand);
}

.example {
  display: flex;
  gap: 12px;
  padding: 12px 14px;
  border-radius: 12px;
  background: var(--glass-bg-dim);
  border: 1px solid var(--hairline);
}

.example-num {
  flex-shrink: 0;
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: var(--brand-soft);
  color: var(--brand);
  font-size: 11px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
}

.example-body { min-width: 0; flex: 1; }

.example-en {
  font-family: var(--font-serif);
  font-style: italic;
  font-size: 15px;
  color: var(--text-primary);
  line-height: 1.55;
}

.example-zh {
  margin-top: 4px;
  font-size: 13px;
  line-height: 1.55;
  color: var(--text-secondary);
}

.small { font-size: 13px; }

/* ─── Footer ───────────────────────────────────────── */
.footer-actions {
  padding-top: 14px;
  border-top: 1px solid var(--hairline);
  display: flex;
  justify-content: flex-end;
}

.btn-danger {
  background: color-mix(in srgb, var(--danger) 14%, transparent);
  color: var(--danger);
  border-color: color-mix(in srgb, var(--danger) 28%, transparent);
}

.btn-danger:hover {
  background: color-mix(in srgb, var(--danger) 22%, transparent);
}

/* ─── Transitions ──────────────────────────────────── */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 200ms ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

.slide-enter-active,
.slide-leave-active {
  transition: transform 280ms cubic-bezier(0.16, 1, 0.3, 1);
}
.slide-enter-from,
.slide-leave-to {
  transform: translateX(100%);
}
</style>
