<script setup lang="ts">
import { ref } from "vue";
import { useRouter, useRoute } from "vue-router";
import { useAuthStore } from "@/stores/auth";
import axios from "axios";

const router = useRouter();
const route = useRoute();
const authStore = useAuthStore();

const form = ref({ username: "", password: "" });
const loading = ref(false);
const errorMessage = ref("");

function describeError(err: unknown): string {
  if (axios.isAxiosError(err)) {
    const status = err.response?.status;
    const serverMessage =
      (err.response?.data as { message?: string } | undefined)?.message;
    if (status === 401) return serverMessage || "Invalid username or password.";
    if (status === 403) return serverMessage || "Account disabled. Contact admin.";
    if (status === 400) return serverMessage || "Bad request. Check your inputs.";
    if (status && status >= 500) return `Server error (${status}). Try again later.`;
    if (err.code === "ERR_NETWORK" || !err.response) {
      return "Cannot reach Java backend. Is it running on http://localhost:8080?";
    }
    return serverMessage || err.message;
  }
  return err instanceof Error ? err.message : "Unknown error during login.";
}

async function handleLogin() {
  if (!form.value.username || !form.value.password) {
    errorMessage.value = "Please enter username and password";
    return;
  }
  loading.value = true;
  errorMessage.value = "";
  try {
    await authStore.login(form.value.username, form.value.password);
    const redirect = (route.query.redirect as string) || "/dashboard";
    router.push(redirect);
  } catch (err) {
    errorMessage.value = describeError(err);
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <div class="login-container">
    <div class="login-card">
      <h1 class="login-title">AgentCook Admin</h1>
      <p class="login-subtitle">Sign in to continue</p>

      <el-alert
        v-if="errorMessage"
        :title="errorMessage"
        type="error"
        show-icon
        closable
        style="margin-bottom: 16px"
        @close="errorMessage = ''"
      />

      <el-form @submit.prevent="handleLogin" label-position="top">
        <el-form-item label="Username">
          <el-input
            v-model="form.username"
            placeholder="Enter username"
            size="large"
            :disabled="loading"
            autocomplete="username"
          />
        </el-form-item>
        <el-form-item label="Password">
          <el-input
            v-model="form.password"
            type="password"
            placeholder="Enter password"
            size="large"
            show-password
            :disabled="loading"
            autocomplete="current-password"
          />
        </el-form-item>
        <el-button
          type="primary"
          size="large"
          native-type="submit"
          :loading="loading"
          style="width: 100%; margin-top: 8px"
        >
          Sign In
        </el-button>
      </el-form>
    </div>
  </div>
</template>

<style scoped>
.login-container {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--el-fill-color-lighter);
}
.login-card {
  width: 400px;
  padding: 40px;
  background: white;
  border-radius: 12px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
}
.login-title {
  margin: 0 0 4px;
  font-size: 24px;
  font-weight: 700;
}
.login-subtitle {
  margin: 0 0 24px;
  color: var(--el-text-color-secondary);
  font-size: 14px;
}
</style>
