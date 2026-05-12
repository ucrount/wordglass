import { createRouter, createWebHistory } from "vue-router";

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/", name: "dashboard", component: () => import("./views/Dashboard.vue") },
    { path: "/reader", name: "reader", component: () => import("./views/Reader.vue") },
    { path: "/library", name: "library", component: () => import("./views/Library.vue") },
    { path: "/practice", name: "practice", component: () => import("./views/Practice.vue") },
    { path: "/settings", name: "settings", component: () => import("./views/Settings.vue") },
  ],
});
