import { createRouter, createWebHistory } from "vue-router";

import { api } from "./api";
import { useAuth } from "./composables/auth";

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/", name: "dashboard", component: () => import("./views/Dashboard.vue"), meta: { auth: true } },
    { path: "/reader", name: "reader", component: () => import("./views/Reader.vue"), meta: { auth: true } },
    { path: "/library", name: "library", component: () => import("./views/Library.vue"), meta: { auth: true } },
    { path: "/practice", name: "practice", component: () => import("./views/Practice.vue"), meta: { auth: true } },
    { path: "/settings", name: "settings", component: () => import("./views/Settings.vue"), meta: { auth: true } },
    { path: "/login", name: "login", component: () => import("./views/Login.vue"), meta: { public: true } },
    { path: "/register", name: "register", component: () => import("./views/Register.vue"), meta: { public: true } },
    { path: "/setup", name: "setup", component: () => import("./views/Setup.vue"), meta: { public: true } },
  ],
});

let setupCache: { needs_setup: boolean; registration_enabled: boolean } | null = null;
async function checkSetup() {
  if (setupCache !== null) return setupCache;
  try {
    setupCache = await api.setupStatus();
  } catch {
    setupCache = { needs_setup: false, registration_enabled: true };
  }
  return setupCache;
}

router.beforeEach(async (to) => {
  if (to.meta.public) {
    const s = await checkSetup();
    if (s.needs_setup && to.name !== "setup") {
      return { name: "setup" };
    }
    return true;
  }

  const auth = useAuth();
  const s = await checkSetup();
  if (s.needs_setup) {
    return { name: "setup" };
  }
  if (!auth.isAuthed.value) {
    return { name: "login", query: { next: to.fullPath } };
  }
  return true;
});

window.addEventListener("wordglass:unauth", () => {
  const auth = useAuth();
  auth.clearSession();
  setupCache = null;
  if (router.currentRoute.value.name !== "login" && router.currentRoute.value.name !== "setup") {
    router.replace({ name: "login", query: { next: router.currentRoute.value.fullPath } });
  }
});
