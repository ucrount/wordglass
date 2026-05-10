<script setup lang="ts">
import type { WordBrief } from "../api";

defineProps<{ word: WordBrief }>();
</script>

<template>
  <div class="word glass">
    <div class="header">
      <div class="text">{{ word.text }}</div>
      <div class="mastery" :title="`掌握度 ${word.mastery}/5`">
        <span
          v-for="i in 5"
          :key="i"
          class="pip"
          :class="{ on: i <= word.mastery }"
        />
      </div>
    </div>
    <div class="phonetic tertiary">{{ word.phonetic || "—" }}</div>
    <div class="translation">{{ word.translation || "（无翻译）" }}</div>
  </div>
</template>

<style scoped>
.word {
  padding: 18px 20px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  cursor: pointer;
  transition: transform 200ms ease, box-shadow 200ms ease, background 200ms ease;
}

.word:hover {
  transform: translateY(-2px);
  box-shadow: var(--glass-shadow-lg);
  background: var(--glass-bg-strong);
}

.header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
}

.text {
  font-size: 22px;
  font-weight: 600;
  letter-spacing: -0.01em;
  color: var(--text-primary);
}

.phonetic {
  font-size: 13px;
  font-family: ui-monospace, "SF Mono", Menlo, monospace;
}

.translation {
  margin-top: 4px;
  font-size: 14px;
  color: var(--text-secondary);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.mastery {
  display: flex;
  gap: 3px;
}

.pip {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: rgba(0, 0, 0, 0.12);
}

.pip.on {
  background: var(--accent);
}
</style>
