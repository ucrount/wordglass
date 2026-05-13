<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from "vue";

const props = withDefaults(
  defineProps<{
    target: string;
    disabled?: boolean;
    showHint?: boolean; // when true, fills remaining slots with the correct answer
  }>(),
  { disabled: false, showHint: false }
);

const emit = defineEmits<{
  (e: "complete"): void;
  (e: "wrong", key: string): void;
}>();

const chars = computed(() => Array.from(props.target));

function isEditable(c: string): boolean {
  return /[a-zA-Z0-9]/.test(c);
}

const typed = ref<string[]>([]);
const currentIndex = ref(0);
const shakeIndex = ref(-1);

function nextEditable(from: number): number {
  for (let i = from; i < chars.value.length; i++) {
    if (isEditable(chars.value[i])) return i;
  }
  return chars.value.length;
}

function prevEditable(from: number): number {
  for (let i = from - 1; i >= 0; i--) {
    if (isEditable(chars.value[i])) return i;
  }
  return -1;
}

function init() {
  typed.value = chars.value.map((c) => (isEditable(c) ? "" : c));
  currentIndex.value = nextEditable(0);
}

function reset() {
  init();
}

defineExpose({ reset });

watch(
  () => props.target,
  () => init(),
  { immediate: true }
);

// When asked to show hint, fill in remaining slots with target letters
watch(
  () => props.showHint,
  (val) => {
    if (val) {
      typed.value = chars.value.map((c) => c);
      currentIndex.value = chars.value.length;
    }
  }
);

function handleKey(e: KeyboardEvent) {
  if (props.disabled || props.showHint) return;
  if (e.metaKey || e.ctrlKey || e.altKey) return;

  // Allow shortcut keys to pass through (S, Tab, 1-4 handled at parent)
  if (e.key === "Tab" || (e.key === "s" && currentIndex.value >= chars.value.length)) return;

  if (e.key === "Backspace") {
    e.preventDefault();
    const prev = prevEditable(currentIndex.value);
    if (prev >= 0) {
      typed.value[prev] = "";
      currentIndex.value = prev;
    }
    return;
  }

  if (e.key.length !== 1) return;
  const idx = currentIndex.value;
  if (idx >= chars.value.length) return;

  const expected = chars.value[idx];
  if (e.key.toLowerCase() === expected.toLowerCase()) {
    e.preventDefault();
    typed.value[idx] = e.key;
    const next = nextEditable(idx + 1);
    currentIndex.value = next;
    if (next === chars.value.length) {
      emit("complete");
    }
  } else if (isEditable(e.key)) {
    e.preventDefault();
    shakeIndex.value = idx;
    setTimeout(() => (shakeIndex.value = -1), 380);
    emit("wrong", e.key);
  }
}

onMounted(() => {
  window.addEventListener("keydown", handleKey);
});

onUnmounted(() => {
  window.removeEventListener("keydown", handleKey);
});
</script>

<template>
  <div class="slots">
    <template v-for="(c, i) in chars" :key="i + '-' + target">
      <span
        v-if="isEditable(c)"
        class="slot"
        :class="{
          active: i === currentIndex && !disabled && !showHint,
          filled: !!typed[i],
          shake: shakeIndex === i,
          hint: showHint,
        }"
      >{{ typed[i] || ' ' }}</span>
      <span v-else class="punct">{{ c === ' ' ? ' ' : c }}</span>
    </template>
  </div>
</template>

<style scoped>
.slots {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: center;
  align-items: center;
  font-family: var(--font-mono);
}

.slot {
  position: relative;
  width: 40px;
  height: 52px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: var(--font-serif);
  font-size: 28px;
  font-weight: 700;
  border: 2px solid var(--hairline-strong);
  border-radius: 10px;
  background: var(--glass-bg);
  color: var(--text-primary);
  text-transform: lowercase;
  transition: all 200ms ease;
  user-select: none;
}

.slot.active {
  border-color: var(--brand);
  background: var(--brand-soft);
  box-shadow: 0 0 0 4px color-mix(in srgb, var(--brand) 15%, transparent);
}

.slot.active::after {
  content: "";
  position: absolute;
  bottom: 6px;
  left: 25%;
  right: 25%;
  height: 2px;
  background: var(--brand);
  border-radius: 1px;
  animation: blink 1s ease-in-out infinite;
}

.slot.filled:not(.active) {
  background: var(--glass-bg-strong);
  border-color: color-mix(in srgb, var(--success) 40%, transparent);
  color: var(--success);
}

.slot.shake {
  background: color-mix(in srgb, var(--danger) 15%, transparent);
  border-color: var(--danger);
  animation: shake 380ms cubic-bezier(0.36, 0.07, 0.19, 0.97) both;
}

.slot.hint {
  background: color-mix(in srgb, var(--warn) 18%, transparent);
  border-color: color-mix(in srgb, var(--warn) 40%, transparent);
  color: var(--warn);
}

.punct {
  display: flex;
  align-items: center;
  font-size: 26px;
  color: var(--text-tertiary);
  min-width: 14px;
}

@keyframes blink {
  50% { opacity: 0.25; }
}

@keyframes shake {
  10%, 90% { transform: translateX(-1px); }
  20%, 80% { transform: translateX(2px); }
  30%, 50%, 70% { transform: translateX(-4px); }
  40%, 60% { transform: translateX(4px); }
}

@media (max-width: 640px) {
  .slot {
    width: 32px;
    height: 44px;
    font-size: 22px;
  }
  .slots { gap: 6px; }
}
</style>
