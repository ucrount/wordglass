<script setup lang="ts">
import GlobalGuards from "./components/GlobalGuards.vue";
import SideBar from "./components/SideBar.vue";
</script>

<template>
  <div class="app-shell">
    <SideBar />
    <main class="main">
      <div class="main-inner">
        <GlobalGuards />
        <RouterView v-slot="{ Component }">
          <Transition name="fade" mode="out-in">
            <component :is="Component" />
          </Transition>
        </RouterView>
      </div>
    </main>
  </div>
</template>

<style>
.app-shell {
  min-height: 100vh;
  display: flex;
}

.main {
  flex: 1;
  margin-left: 220px;
  min-width: 0;
  min-height: 100vh;
}

.main-inner {
  max-width: 1500px;
  margin: 0 auto;
  padding: 32px 36px 64px;
}

@media (max-width: 860px) {
  .main { margin-left: 0; }
  .main-inner { padding: 72px 20px 64px; }
}
</style>
