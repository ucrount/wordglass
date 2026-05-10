<script setup lang="ts">
import { ref } from "vue";
import { api } from "../api";

const emit = defineEmits<{ (e: "added"): void }>();

const text = ref("");
const loading = ref(false);
const error = ref("");
const flash = ref(""); // last successfully added word

async function submit() {
  const value = text.value.trim();
  if (!value || loading.value) return;
  loading.value = true;
  error.value = "";
  try {
    const w = await api.addWord(value);
    flash.value = w.text;
    text.value = "";
    emit("added");
    setTimeout(() => (flash.value = ""), 2400);
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
      <span class="plus">＋</span>
      <input
        v-model="text"
        class="bare-input"
        type="text"
        :disabled="loading"
        placeholder="输入要保存的英文单词或短语，回车添加…"
        @keyup.enter="submit"
      />
      <button class="btn btn-primary" :disabled="loading || !text.trim()" @click="submit">
        {{ loading ? "翻译中…" : "保存" }}
      </button>
    </div>
    <Transition name="fade">
      <div v-if="flash" class="hint success">已添加：{{ flash }}</div>
    </Transition>
    <Transition name="fade">
      <div v-if="error" class="hint error">{{ error }}</div>
    </Transition>
  </div>
</template>

<style scoped>
.add-bar {
  padding: 12px 12px 12px 20px;
  border-radius: var(--radius-xl);
}

.row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.plus {
  font-size: 22px;
  color: var(--text-tertiary);
  width: 24px;
  text-align: center;
  user-select: none;
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

.hint.success {
  color: var(--success);
}
.hint.error {
  color: var(--danger);
}
</style>
