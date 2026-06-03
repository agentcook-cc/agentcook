<script setup lang="ts">
import { onMounted, onUnmounted, ref, computed } from "vue";
import { javaClient } from "@/api/client";

interface QuotaResponse {
  free_questions_used: number;
  free_questions_quota: number;
}

const used = ref(0);
const quota = ref(2);
const loaded = ref(false);
const errored = ref(false);

const remaining = computed(() => Math.max(0, quota.value - used.value));
const tagType = computed<"info" | "warning" | "danger">(() => {
  if (remaining.value === 0) return "danger";
  if (remaining.value === 1) return "warning";
  return "info";
});
const label = computed(() => {
  if (errored.value) return "Quota n/a";
  if (!loaded.value) return "Quota …";
  if (remaining.value === 0) return `Quota 0/${quota.value} — downgraded`;
  return `Quota ${remaining.value}/${quota.value}`;
});

const POLL_INTERVAL_MS = 30_000;
let timer: ReturnType<typeof setInterval> | null = null;

async function refresh() {
  try {
    const data = await javaClient.get<QuotaResponse>("/api/v1/quota");
    used.value = data.free_questions_used;
    quota.value = data.free_questions_quota;
    loaded.value = true;
    errored.value = false;
  } catch {
    errored.value = true;
    loaded.value = true;
  }
}

onMounted(() => {
  refresh();
  timer = setInterval(refresh, POLL_INTERVAL_MS);
});

onUnmounted(() => {
  if (timer) clearInterval(timer);
});
</script>

<template>
  <el-tooltip
    :content="
      errored ? 'Failed to fetch /api/v1/quota' : 'Free chat quota — ADR-018'
    "
  >
    <el-tag :type="tagType" size="small" data-testid="quota-badge">
      {{ label }}
    </el-tag>
  </el-tooltip>
</template>
