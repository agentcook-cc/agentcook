<script setup lang="ts">
import { ref, computed } from "vue";
import { useRouter, useRoute } from "vue-router";
import { useAuthStore } from "@/stores/auth";
import { useThemeStore } from "@/stores/theme";
import { menuConfig, type MenuItem } from "@/config/menu";

const authStore = useAuthStore();
const themeStore = useThemeStore();
const router = useRouter();
const route = useRoute();
const isCollapsed = ref(false);

const visibleMenuItems = computed<MenuItem[]>(() =>
  menuConfig.filter((item) => {
    if (!item.roles || item.roles.length === 0) return true;
    return item.roles.some((role) => authStore.hasRole(role));
  }),
);

const activeMenu = computed(() => route.path);
const isDark = computed(() => themeStore.mode === "dark");

async function handleLogout() {
  authStore.logout();
  router.push({ name: "Login" });
}
</script>

<template>
  <el-container class="admin-layout">
    <el-aside :width="isCollapsed ? '64px' : '220px'" class="admin-aside">
      <div class="logo-area">
        <span v-if="!isCollapsed" class="logo-text">AgentCook</span>
        <span v-else class="logo-icon">AC</span>
      </div>
      <el-menu
        router
        :default-active="activeMenu"
        :collapse="isCollapsed"
        class="admin-menu"
      >
        <template v-for="item in visibleMenuItems" :key="item.path">
          <el-sub-menu v-if="item.children?.length" :index="item.path">
            <template #title>
              <el-icon><component :is="item.icon" /></el-icon>
              <span>{{ item.title }}</span>
            </template>
            <el-menu-item
              v-for="child in item.children"
              :key="child.path"
              :index="child.path"
            >
              <el-icon><component :is="child.icon" /></el-icon>
              <template #title>{{ child.title }}</template>
            </el-menu-item>
          </el-sub-menu>
          <el-menu-item v-else :index="item.path">
            <el-icon><component :is="item.icon" /></el-icon>
            <template #title>{{ item.title }}</template>
          </el-menu-item>
        </template>
      </el-menu>
    </el-aside>

    <el-container>
      <el-header class="admin-header">
        <el-button text @click="isCollapsed = !isCollapsed">
          <el-icon size="18">
            <component :is="isCollapsed ? 'Expand' : 'Fold'" />
          </el-icon>
        </el-button>
        <div class="header-right">
          <el-button text @click="themeStore.toggle()">
            <el-icon size="18">
              <component :is="isDark ? 'Sunny' : 'Moon'" />
            </el-icon>
          </el-button>
          <span class="user-name">{{ authStore.user?.displayName }}</span>
          <el-button text @click="handleLogout">Logout</el-button>
        </div>
      </el-header>

      <el-main class="admin-main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<style scoped>
.admin-layout {
  height: 100vh;
}
.admin-aside {
  background: var(--el-bg-color);
  border-right: 1px solid var(--el-border-color-lighter);
  transition: width 0.3s;
}
.logo-area {
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-bottom: 1px solid var(--el-border-color-lighter);
}
.logo-text {
  font-size: 18px;
  font-weight: 700;
}
.logo-icon {
  font-size: 16px;
  font-weight: 700;
}
.admin-menu {
  border-right: none;
}
.admin-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid var(--el-border-color-lighter);
  height: 56px;
}
.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}
.user-name {
  font-size: 14px;
  color: var(--el-text-color-regular);
}
.admin-main {
  background: var(--el-fill-color-lighter);
  min-height: 0;
}
</style>
