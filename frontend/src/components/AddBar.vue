<script setup lang="ts">
import { ref } from "vue";
import { api, type WordOut } from "../api";

const emit = defineEmits<{
  (e: "added", word: WordOut): void;
}>();

const text = ref("");
const loading = ref(false);
const error = ref("");

async function submit() {
  const value = text.value.trim();
  if (!value || loading.value) return;
  loading.value = true;
  error.value = "";
  try {
    const w = await api.addWord(value);
    text.value = "";
    emit("added", w);
  } catch (e: any) {
    error.value = e.message || "添加失败";
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <div class="add-bar glass-strong">
    <div class="row">
      <span class="plus">{{ loading ? "⏳" : "+" }}</span>
      <input
        v-model="text"
        class="bare-input"
        type="text"
        :disabled="loading"
        placeholder="粘个英文单词或短语，回车 AI 自动给翻译 + 例句…"
        autocomplete="off"
        autocapitalize="off"
        @keyup.enter="submit"
      />
      <button class="btn btn-primary" :disabled="loading || !text.trim()" @click="submit">
        {{ loading ? "翻译中…" : "保存" }}
      </button>
    </div>
    <Transition name="fade">
      <div v-if="error" class="hint error">{{ error }}</div>
    </Transition>
  </div>
</template>

<style scoped>
.add-bar {
  padding: 14px 14px 14px 22px;
  border-radius: var(--radius-xl);
}

.row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.plus {
  font-size: 26px;
  color: var(--brand);
  width: 28px;
  text-align: center;
  font-weight: 300;
  user-select: none;
  line-height: 1;
}

.bare-input {
  flex: 1;
  border: none;
  outline: none;
  background: transparent;
  font: inherit;
  font-size: 17px;
  color: var(--text-primary);
  padding: 12px 0;
  min-width: 0;
}

.bare-input::placeholder {
  color: var(--text-tertiary);
}

.btn {
  white-space: nowrap;
}

.hint {
  margin: 8px 4px 0;
  font-size: 13px;
}

.hint.error {
  color: var(--danger);
}
</style>
