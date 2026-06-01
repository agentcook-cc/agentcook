<template>
  <el-dialog
    v-model="visible"
    :title="`Test skill — ${skillName ?? 'unknown'}`"
    width="780px"
    :close-on-click-modal="false"
    @close="onClose"
  >
    <el-alert
      v-if="error"
      :title="error"
      type="error"
      show-icon
      closable
      style="margin-bottom: 12px"
      @close="resetError"
    />

    <div class="test-section">
      <div class="section-label">Input</div>
      <el-input
        v-model="inputText"
        type="textarea"
        :rows="3"
        spellcheck="false"
        placeholder="e.g. summarise the last meeting transcript"
        :disabled="running"
      />
      <div class="section-label" style="margin-top: 12px">
        Args (optional JSON · Phase 5)
      </div>
      <el-input
        v-model="argsJson"
        type="textarea"
        :rows="2"
        spellcheck="false"
        placeholder='{ "max_tokens": 512 }  — leave blank for now'
        :disabled="running"
      />
      <div class="hint">
        Posted to <code>POST {{ PYTHON_BASE }}/api/v1/skills/{{ skillId }}/test/stream</code>
        (SSE / Accept: text/event-stream)
      </div>
    </div>

    <div class="output-section">
      <div class="output-header">
        <span class="section-label">Output</span>
        <el-tag v-if="running" type="primary" size="small" effect="dark">
          streaming · {{ chunks.length }} chunks
        </el-tag>
        <el-tag v-else-if="hasOutput" type="success" size="small" effect="plain">
          done · {{ chunks.length }} chunks
        </el-tag>
      </div>
      <div ref="outputBoxRef" class="output-box">
        <pre v-if="accumulated">{{ accumulated }}</pre>
        <el-empty v-else description="(no output yet — click Run)" :image-size="60" />
      </div>
    </div>

    <template #footer>
      <el-button @click="visible = false" :disabled="running">Close</el-button>
      <el-button v-if="running" type="warning" @click="cancel">Cancel</el-button>
      <el-button
        v-else
        type="primary"
        :disabled="!skillId || !argsValid"
        @click="handleRun"
      >
        Run
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick } from "vue";
import { useSseStream } from "@/composables/useSseStream";

interface Props {
  modelValue: boolean;
  skillId?: string;
  skillName?: string;
}
const props = defineProps<Props>();
const emit = defineEmits<{ "update:modelValue": [value: boolean] }>();

const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit("update:modelValue", v),
});

const PYTHON_BASE =
  import.meta.env.VITE_PYTHON_API_BASE_URL || "http://localhost:8000";

const inputText = ref("");
const argsJson = ref("");
const outputBoxRef = ref<HTMLDivElement | null>(null);

const { accumulated, running, error, start, cancel, reset } = useSseStream();

const chunks = computed(() => {
  if (!accumulated.value) return [];
  return accumulated.value.split(/\n+/).filter(Boolean);
});
const hasOutput = computed(() => !!accumulated.value);

const argsValid = computed(() => {
  if (!argsJson.value.trim()) return true;
  try {
    JSON.parse(argsJson.value);
    return true;
  } catch {
    return false;
  }
});

watch(accumulated, () => {
  nextTick(() => {
    if (outputBoxRef.value) {
      outputBoxRef.value.scrollTop = outputBoxRef.value.scrollHeight;
    }
  });
});

async function handleRun() {
  if (!props.skillId) return;
  if (!inputText.value.trim()) {
    error.value = "Input is required (Python SkillTestRequest schema)";
    return;
  }
  let args: Record<string, unknown> | undefined;
  if (argsJson.value.trim()) {
    try {
      args = JSON.parse(argsJson.value);
    } catch {
      error.value = "Args is not valid JSON";
      return;
    }
  }
  await start({
    url: `${PYTHON_BASE}/api/v1/skills/${props.skillId}/test/stream`,
    body: { input: inputText.value, args },
  });
}

function onClose() {
  cancel();
  reset();
}

function resetError() {
  error.value = null;
}
</script>

<style scoped>
.test-section,
.output-section {
  margin-bottom: 12px;
}
.section-label {
  font-size: 12px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--el-text-color-secondary);
  margin-bottom: 6px;
  display: block;
}
.hint {
  margin-top: 4px;
  font-size: 11px;
  color: var(--el-text-color-secondary);
}
.hint code {
  background: var(--el-fill-color-light);
  padding: 1px 4px;
  border-radius: 3px;
  font-family: "JetBrains Mono", monospace;
  font-size: 11px;
}
.output-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}
.output-box {
  height: 280px;
  overflow-y: auto;
  padding: 12px;
  background: var(--el-fill-color-lighter);
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 4px;
  font-family: "JetBrains Mono", monospace;
  font-size: 12px;
  line-height: 1.5;
}
.output-box pre {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  color: var(--el-text-color-primary);
}
</style>
