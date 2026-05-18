import { createRouter, createWebHistory } from "vue-router";
import type { RouteRecordRaw } from "vue-router";

const routes: RouteRecordRaw[] = [
  {
    path: "/login",
    name: "Login",
    component: () => import("@/views/LoginView.vue"),
    meta: { requiresAuth: false },
  },
  {
    path: "/",
    component: () => import("@/layouts/AdminLayout.vue"),
    meta: { requiresAuth: true },
    children: [
      {
        path: "",
        redirect: "/dashboard",
      },
      {
        path: "dashboard",
        name: "Dashboard",
        component: () => import("@/views/DashboardView.vue"),
      },
      {
        path: "plugins",
        name: "Plugins",
        component: () => import("@/views/PluginListView.vue"),
      },
    ],
  },
  {
    path: "/401",
    name: "Unauthorized",
    component: () => import("@/views/error/401.vue"),
    meta: { requiresAuth: false },
  },
  {
    path: "/403",
    name: "Forbidden",
    component: () => import("@/views/error/403.vue"),
    meta: { requiresAuth: false },
  },
  {
    path: "/500",
    name: "ServerError",
    component: () => import("@/views/error/500.vue"),
    meta: { requiresAuth: false },
  },
  {
    path: "/:pathMatch(.*)*",
    name: "NotFound",
    component: () => import("@/views/error/404.vue"),
    meta: { requiresAuth: false },
  },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

router.beforeEach(async (to, _from, next) => {
  // Pinia store 必须在 router guard 内惰性获取，避免在 app.use(pinia) 之前调用
  const { useAuthStore } = await import("@/stores/auth");
  const authStore = useAuthStore();

  if (to.meta.requiresAuth === false) {
    if (to.name === "Login" && authStore.isAuthenticated) {
      next({ name: "Dashboard" });
    } else {
      next();
    }
    return;
  }

  if (!authStore.isAuthenticated) {
    next({ name: "Login", query: { redirect: to.fullPath } });
    return;
  }

  if (!authStore.user) {
    await authStore.fetchUserInfo();
    if (!authStore.isAuthenticated) {
      next({ name: "Login", query: { redirect: to.fullPath } });
      return;
    }
  }

  next();
});

export default router;
