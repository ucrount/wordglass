<script setup lang="ts">
import { computed } from "vue";
import { useRoute } from "vue-router";
import GlobalGuards from "./components/GlobalGuards.vue";
import SideBar from "./components/SideBar.vue";

const route = useRoute();
// Only the dashboard locks to one viewport. Settings/Library/Practice/Reader flow naturally.
const lockHeight = computed(() => route.name === "dashboard");
</script>

<template>
  <div class="app-shell" :class="{ locked: lockHeight }">
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
  padding: 28px 32px 40px;
}

/* Locked: dashboard fills exactly one viewport, no page scroll */
.app-shell.locked .main {
  height: 100vh;
  min-height: 0;
  overflow: hidden;
}

.app-shell.locked .main-inner {
  height: 100vh;
  overflow: hidden;
  padding: 20px 28px;
  display: flex;
  flex-direction: column;
}

@media (max-width: 860px) {
  .main { margin-left: 0; }
  .main-inner { padding: 72px 20px 40px; }
  /* Drop the lock on narrow screens — phones can't fit it */
  .app-shell.locked .main,
  .app-shell.locked .main-inner {
    height: auto;
    overflow: visible;
  }
}

@media (max-height: 640px) {
  /* Drop lock on shorter screens (landscape phones, small laptops) */
  .app-shell.locked .main,
  .app-shell.locked .main-inner {
    height: auto;
    overflow: visible;
  }
}
</style>
