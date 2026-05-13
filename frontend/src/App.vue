<script setup lang="ts">
import GlobalGuards from "./components/GlobalGuards.vue";
import SideBar from "./components/SideBar.vue";
import { useAuth } from "./composables/auth";

const { isAuthed } = useAuth();
</script>

<template>
  <div class="app-shell">
    <SideBar v-if="isAuthed" />
    <main class="main" :class="{ 'no-sidebar': !isAuthed }">
      <div class="main-inner" :class="{ 'full-page': !isAuthed }">
        <GlobalGuards v-if="isAuthed" />
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

.main.no-sidebar {
  margin-left: 0;
}

.main-inner {
  max-width: 1500px;
  margin: 0 auto;
  padding: 28px 32px 40px;
}

.main-inner.full-page {
  max-width: none;
  padding: 0;
}

@media (max-width: 860px) {
  .main { margin-left: 0; }
  .main-inner { padding: 72px 20px 40px; }
  .main-inner.full-page { padding: 0; }
}
</style>
