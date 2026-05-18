<script setup lang="ts">
import { useRouter } from "vue-router";

const router = useRouter();
</script>

<template>
  <div class="error-page">
    <h1 class="error-code">500</h1>
    <p class="error-message">Internal Server Error — Something went wrong on our end.</p>
    <el-button type="primary" @click="router.push('/dashboard')">Back to Dashboard</el-button>
  </div>
</template>

<style scoped>
.error-page {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
}
.error-code {
  font-size: 72px;
  font-weight: 800;
  margin: 0;
  color: var(--el-color-danger);
}
.error-message {
  font-size: 16px;
  color: var(--el-text-color-secondary);
  margin: 8px 0 24px;
}
</style>
