<script setup lang="ts">
import { computed } from "vue";
import { useRoute } from "vue-router";
import GlobalGuards from "./components/GlobalGuards.vue";
import SideBar from "./components/SideBar.vue";

const route = useRoute();
// Dashboard wants to fit one viewport (no page scroll). Other pages scroll
// normally because their content (settings, library) can grow long.
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
  padding: 32px 36px 80px;
}

/* Lock-height mode: main + inner take exactly the viewport, no page scroll */
.app-shell.locked .main {
  height: 100vh;
  min-height: 0;
  overflow: hidden;
}

.app-shell.locked .main-inner {
  height: 100vh;
  padding: 20px 32px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

@media (max-width: 860px) {
  .main { margin-left: 0; }
  .main-inner { padding: 72px 20px 80px; }
  /* On narrow / short screens, drop the lock — phone keyboards eat too
     much height to fit a dashboard in 1 viewport. */
  .app-shell.locked .main,
  .app-shell.locked .main-inner {
    height: auto;
    overflow: visible;
  }
}

@media (max-height: 680px) {
  /* Phones in landscape, very small laptops — also unlock so user can scroll */
  .app-shell.locked .main,
  .app-shell.locked .main-inner {
    height: auto;
    overflow: visible;
  }
}
</style>
