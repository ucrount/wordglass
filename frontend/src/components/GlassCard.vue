<script setup lang="ts">
defineProps<{
  variant?: "default" | "strong" | "dim";
  padding?: string;
}>();
</script>

<template>
  <div
    class="card"
    :class="{
      glass: !variant || variant === 'default',
      'glass-strong': variant === 'strong',
      'glass-dim': variant === 'dim',
    }"
    :style="padding ? { padding } : undefined"
  >
    <slot />
  </div>
</template>

<style scoped>
.card {
  padding: 24px;
}
</style>
