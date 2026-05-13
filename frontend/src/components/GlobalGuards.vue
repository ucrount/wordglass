<script setup lang="ts">
import { onMounted, ref } from "vue";
import { RouterLink, useRoute } from "vue-router";
import { api } from "../api";

const aiConfigured = ref<boolean | null>(null);
const route = useRoute();

async function checkConfig() {
  try {
    const s = await api.getSettings();
    aiConfigured.value = s.configured;
  } catch {
    aiConfigured.value = false;
  }
}

onMounted(checkConfig);
</script>

<template>
  <Transition name="fade">
    <div
      v-if="aiConfigured === false && route.name !== 'settings'"
      class="banner glass-strong"
    >
      <div>
        <strong>👋 还差一步</strong> · AI 服务还没配置，去
        <RouterLink to="/settings" class="link">设置</RouterLink>
        填一下，就能开始添加单词了。
      </div>
    </div>
  </Transition>
</template>

<style scoped>
.banner {
  position: sticky;
  top: 80px;
  z-index: 40;
  padding: 12px 18px;
  border-radius: var(--radius-md);
  margin: 8px 0 20px;
  font-size: 14px;
}
.banner .link {
  color: var(--accent);
  font-weight: 600;
  text-decoration: none;
}
.banner .link:hover { text-decoration: underline; }
</style>
