<template>
  <el-dialog
    v-model="visible"
    :title="`Test connection — ${connector?.displayName ?? 'unknown'}`"
    width="480px"
    :close-on-click-modal="!pinging"
    @close="reset"
  >
    <div class="ping-section">
      <div v-if="pinging" class="state">
        <el-icon class="spinner"><Loading /></el-icon>
        <span>Pinging {{ connector?.displayName }}…</span>
      </div>
      <div v-else-if="result === 'success'" class="state success">
        <el-icon><SuccessFilled /></el-icon>
        <span>OK · round-trip {{ latencyMs }} ms</span>
      </div>
      <div v-else-if="result === 'error'" class="state error">
        <el-icon><CircleCloseFilled /></el-icon>
        <div>
          <strong>Ping failed</strong>
          <p>{{ errorMessage }}</p>
        </div>
      </div>
      <div v-else class="state idle">
        <el-icon><InfoFilled /></el-icon>
        <span>Click Ping to test the connection.</span>
      </div>
    </div>

    <template #footer>
      <el-button @click="visible = false" :disabled="pinging">Close</el-button>
      <el-button
        type="primary"
        :loading="pinging"
        :disabled="!connector"
        @click="runPing"
      >
        Ping
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, computed, watch } from "vue";
import {
  Loading,
  SuccessFilled,
  CircleCloseFilled,
  InfoFilled,
} from "@element-plus/icons-vue";
import axios from "axios";
import { javaClient } from "@/api/client";
import type { ConnectorRow } from "./connectorTypes";

interface Props {
  modelValue: boolean;
  connector?: ConnectorRow;
}
const props = defineProps<Props>();
const emit = defineEmits<{ "update:modelValue": [value: boolean] }>();

const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit("update:modelValue", v),
});

const pinging = ref(false);
const result = ref<"idle" | "success" | "error">("idle");
const latencyMs = ref(0);
const errorMessage = ref("");

async function runPing() {
  if (!props.connector) return;
  pinging.value = true;
  result.value = "idle";
  errorMessage.value = "";
  const start = performance.now();
  try {
    await javaClient.post(`/api/v1/connectors/${props.connector.id}/ping`, {});
    latencyMs.value = Math.round(performance.now() - start);
    result.value = "success";
  } catch (err) {
    latencyMs.value = Math.round(performance.now() - start);
    result.value = "error";
    if (axios.isAxiosError(err)) {
      const status = err.response?.status;
      if (status === 404) {
        errorMessage.value =
          "Backend POST /api/v1/connectors/{id}/ping not implemented yet (Day 29 reverse fact-check #3 to D)";
      } else {
        errorMessage.value =
          (err.response?.data as { message?: string } | undefined)?.message ??
          err.message;
      }
    } else {
      errorMessage.value = err instanceof Error ? err.message : "Network error";
    }
  } finally {
    pinging.value = false;
  }
}

function reset() {
  pinging.value = false;
  result.value = "idle";
  latencyMs.value = 0;
  errorMessage.value = "";
}

watch(
  () => props.modelValue,
  (open) => {
    if (!open) reset();
  },
);
</script>

<style scoped>
.ping-section {
  padding: 16px 4px;
  font-size: 14px;
}
.state {
  display: flex;
  align-items: center;
  gap: 12px;
}
.state .el-icon {
  font-size: 28px;
}
.state.success .el-icon {
  color: var(--el-color-success);
}
.state.error {
  align-items: flex-start;
}
.state.error .el-icon {
  color: var(--el-color-danger);
}
.state.error strong {
  display: block;
  color: var(--el-color-danger);
  margin-bottom: 4px;
}
.state.error p {
  margin: 0;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.state.idle .el-icon {
  color: var(--el-text-color-secondary);
}
.spinner {
  animation: spin 1s linear infinite;
  color: var(--el-color-primary);
}
@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
