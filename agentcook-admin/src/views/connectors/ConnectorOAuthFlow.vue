<template>
  <el-dialog
    v-model="visible"
    :title="step === 'choose' ? 'Connect a provider' : 'Authorising…'"
    width="540px"
    :close-on-click-modal="!busy"
    @close="reset"
  >
    <el-alert
      v-if="error"
      :title="error"
      type="error"
      show-icon
      closable
      style="margin-bottom: 12px"
      @close="error = ''"
    />

    <!-- Step 1: choose provider -->
    <template v-if="step === 'choose'">
      <p class="hint">
        Pick a provider. Dev profile uses a dummy callback that returns a fake
        <code>access_token</code> immediately — no browser redirect.
      </p>
      <div class="provider-grid">
        <button
          v-for="p in PROVIDERS"
          :key="p"
          type="button"
          class="provider-card"
          :style="{ borderColor: selected === p ? PROVIDER_META[p].brandColor : undefined }"
          :aria-pressed="selected === p"
          @click="selected = p"
        >
          <span class="icon">{{ PROVIDER_META[p].icon }}</span>
          <span class="label">{{ PROVIDER_META[p].label }}</span>
        </button>
      </div>
    </template>

    <!-- Step 2: authorising / done -->
    <template v-else>
      <div class="auth-state">
        <el-progress
          v-if="step === 'authorising'"
          type="circle"
          :percentage="80"
          status="warning"
          :width="80"
        />
        <el-icon v-else-if="step === 'done'" class="big-check"><CircleCheckFilled /></el-icon>
        <div class="auth-text">
          <strong>{{ PROVIDER_META[selected!].label }}</strong>
          <p>{{ statusText }}</p>
        </div>
      </div>
    </template>

    <template #footer>
      <el-button @click="visible = false" :disabled="busy">Cancel</el-button>
      <el-button
        v-if="step === 'choose'"
        type="primary"
        :disabled="!selected"
        @click="startAuth"
      >
        Authorize
      </el-button>
      <el-button
        v-else-if="step === 'done'"
        type="primary"
        @click="visible = false"
      >
        Done
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, computed } from "vue";
import { CircleCheckFilled } from "@element-plus/icons-vue";
import axios from "axios";
import { javaClient } from "@/api/client";
import {
  PROVIDER_META,
  PROVIDERS,
  type ConnectorProvider,
  type JavaConnectorResponseDto,
} from "./connectorTypes";

interface Props {
  modelValue: boolean;
}
const props = defineProps<Props>();
const emit = defineEmits<{
  "update:modelValue": [value: boolean];
  connected: [connector: JavaConnectorResponseDto];
}>();

const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit("update:modelValue", v),
});

type Step = "choose" | "authorising" | "done";

const step = ref<Step>("choose");
const selected = ref<ConnectorProvider | null>(null);
const error = ref("");
const busy = computed(() => step.value === "authorising");

const statusText = computed(() => {
  if (step.value === "authorising") return "Exchanging code for access token...";
  if (step.value === "done") return "Connector established — you can close this dialog.";
  return "";
});

async function startAuth() {
  if (!selected.value) return;
  step.value = "authorising";
  error.value = "";
  try {
    // Dev profile: pretend we already came back from the provider with a code.
    // Phase 4 will replace this with a real window.open(...) + postMessage callback.
    const dummyCode = `dev-code-${Math.random().toString(36).slice(2, 10)}`;
    const dummyState = `state-${Date.now()}`;
    const connector = await javaClient.post<JavaConnectorResponseDto>(
      "/api/v1/connectors/oauth/callback",
      { provider: selected.value, code: dummyCode, state: dummyState },
    );
    step.value = "done";
    emit("connected", connector);
  } catch (err) {
    step.value = "choose";
    if (axios.isAxiosError(err) && err.response?.status === 404) {
      error.value =
        "Backend POST /api/v1/connectors/oauth/callback not implemented yet (Day 29 reverse fact-check #2 to D)";
    } else {
      error.value = err instanceof Error ? err.message : "OAuth callback failed";
    }
  }
}

function reset() {
  step.value = "choose";
  selected.value = null;
  error.value = "";
}
</script>

<style scoped>
.hint {
  margin: 0 0 12px;
  font-size: 13px;
  color: var(--el-text-color-secondary);
  line-height: 1.5;
}
.hint code {
  background: var(--el-fill-color-light);
  padding: 1px 4px;
  border-radius: 3px;
  font-family: "JetBrains Mono", monospace;
  font-size: 11px;
}
.provider-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 10px;
}
.provider-card {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 14px;
  border: 2px solid var(--el-border-color);
  border-radius: 8px;
  background: white;
  cursor: pointer;
  transition: all 0.15s;
  font-size: 14px;
  text-align: left;
}
.provider-card:hover {
  border-color: var(--el-color-primary);
  background: var(--el-fill-color-lighter);
}
.provider-card[aria-pressed="true"] {
  background: var(--el-color-primary-light-9);
  font-weight: 600;
}
.provider-card .icon {
  font-size: 22px;
}
.auth-state {
  display: flex;
  align-items: center;
  gap: 20px;
  padding: 16px 0;
}
.auth-text strong {
  display: block;
  margin-bottom: 4px;
  font-size: 15px;
}
.auth-text p {
  margin: 0;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}
.big-check {
  font-size: 64px;
  color: var(--el-color-success);
}
</style>
