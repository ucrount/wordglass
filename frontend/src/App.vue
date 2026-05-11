<script setup lang="ts">
import GlobalGuards from "./components/GlobalGuards.vue";
import NavBar from "./components/NavBar.vue";
</script>

<template>
  <NavBar />
  <main class="container content">
    <GlobalGuards />
    <RouterView v-slot="{ Component }">
      <Transition name="fade" mode="out-in">
        <component :is="Component" />
      </Transition>
    </RouterView>
  </main>
</template>

<style>
.content {
  padding-bottom: 120px;
}
</style>
