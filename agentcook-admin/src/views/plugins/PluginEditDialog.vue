<template>
  <el-dialog
    v-model="visible"
    title="Edit plugin.json"
    width="780px"
    :close-on-click-modal="false"
    @close="reset"
  >
    <el-alert
      v-if="errorMessage"
      :title="errorMessage"
      type="error"
      show-icon
      closable
      style="margin-bottom: 12px"
      @close="errorMessage = ''"
    />

    <div class="validation-bar">
      <el-tag v-if="isValid" type="success" size="small" effect="dark">
        ✓ schema valid
      </el-tag>
      <el-tag v-else type="danger" size="small" effect="dark">
        ✗ {{ validationErrors.length }} error{{ validationErrors.length === 1 ? "" : "s" }}
      </el-tag>
      <span class="hint">Live validation against <code>agent-plugin-spec v1</code></span>
    </div>

    <vue-monaco-editor
      v-model:value="editorValue"
      language="json"
      theme="vs"
      :options="{
        readOnly: false,
        minimap: { enabled: false },
        fontSize: 13,
        scrollBeyondLastLine: false,
        automaticLayout: true,
        formatOnPaste: true,
      }"
      height="380px"
    />

    <div v-if="!isValid && validationErrors.length" class="error-list">
      <div v-for="(err, idx) in validationErrors.slice(0, 5)" :key="idx" class="error-row">
        <code>{{ err.path }}</code> — {{ err.message }}
      </div>
      <div v-if="validationErrors.length > 5" class="error-row truncated">
        ...and {{ validationErrors.length - 5 }} more
      </div>
    </div>

    <template #footer>
      <el-button @click="visible = false" :disabled="saving">Cancel</el-button>
      <el-button
        type="primary"
        :loading="saving"
        :disabled="!isValid || saving"
        @click="handleSave"
      >
        Save
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, computed, watch } from "vue";
import { VueMonacoEditor } from "@guolao/vue-monaco-editor";
import { ElMessage } from "element-plus";
import axios from "axios";
import Ajv, { type ErrorObject } from "ajv";
import { javaClient } from "@/api/client";
import type { components } from "@/api/types.java.gen";
import { PLUGIN_JSON_SCHEMA } from "./pluginJsonSchema";

type PluginResponseDto = components["schemas"]["PluginResponse"];

interface Props {
  modelValue: boolean;
  pluginId?: string;
  initialJson?: string;
}
const props = defineProps<Props>();
const emit = defineEmits<{
  "update:modelValue": [value: boolean];
  saved: [plugin: PluginResponseDto];
}>();

const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit("update:modelValue", v),
});

const editorValue = ref<string>("");
const saving = ref(false);
const errorMessage = ref("");

const ajv = new Ajv({ allErrors: true, strict: false });
const validate = ajv.compile(PLUGIN_JSON_SCHEMA);

interface ValidationIssue {
  path: string;
  message: string;
}

const validationState = ref<{ valid: boolean; errors: ValidationIssue[] }>({
  valid: true,
  errors: [],
});
const isValid = computed(() => validationState.value.valid);
const validationErrors = computed(() => validationState.value.errors);

function ajvErrorToIssue(err: ErrorObject): ValidationIssue {
  const path = err.instancePath || "(root)";
  return { path, message: err.message ?? "invalid" };
}

function runValidation() {
  let parsed: unknown;
  try {
    parsed = JSON.parse(editorValue.value || "{}");
  } catch (e) {
    validationState.value = {
      valid: false,
      errors: [{ path: "(json)", message: e instanceof Error ? e.message : "invalid JSON" }],
    };
    return;
  }
  const ok = validate(parsed);
  if (ok) {
    validationState.value = { valid: true, errors: [] };
  } else {
    validationState.value = {
      valid: false,
      errors: (validate.errors ?? []).map(ajvErrorToIssue),
    };
  }
}

watch(editorValue, runValidation);

watch(
  () => [props.modelValue, props.initialJson],
  ([open, initialJson]) => {
    if (open) {
      editorValue.value =
        (initialJson as string | undefined) ??
        JSON.stringify(
          { name: "my-plugin", version: "0.1.0", kind: "HTTP", description: "" },
          null,
          2,
        );
      runValidation();
    } else {
      reset();
    }
  },
  { immediate: true },
);

function reset() {
  saving.value = false;
  errorMessage.value = "";
}

async function handleSave() {
  if (!props.pluginId) {
    errorMessage.value = "Plugin id missing — cannot save without a target";
    return;
  }
  saving.value = true;
  errorMessage.value = "";
  try {
    const body = JSON.parse(editorValue.value);
    const updated = await javaClient.put<PluginResponseDto>(
      `/api/v1/plugins/${props.pluginId}`,
      body,
    );
    ElMessage.success(`Plugin "${updated.name ?? props.pluginId}" saved`);
    emit("saved", updated);
    visible.value = false;
  } catch (err) {
    if (axios.isAxiosError(err) && (err.response?.status === 404 || err.response?.status === 405)) {
      errorMessage.value =
        "Backend PUT /api/v1/plugins/{id} not implemented yet (Day 27 reverse fact-check #3 to D). Schema is valid locally — change preserved in editor.";
    } else {
      errorMessage.value = err instanceof Error ? err.message : "Save failed";
    }
  } finally {
    saving.value = false;
  }
}
</script>

<style scoped>
.validation-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 8px;
}
.hint {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.hint code {
  background: var(--el-fill-color-light);
  padding: 1px 4px;
  border-radius: 3px;
  font-family: "JetBrains Mono", monospace;
  font-size: 11px;
}
.error-list {
  margin-top: 8px;
  max-height: 140px;
  overflow-y: auto;
  padding: 8px 12px;
  background: var(--el-color-danger-light-9);
  border-radius: 4px;
  font-size: 12px;
}
.error-row {
  padding: 2px 0;
  color: var(--el-color-danger-dark-2);
}
.error-row code {
  font-family: "JetBrains Mono", monospace;
  color: var(--el-text-color-primary);
  margin-right: 6px;
}
.error-row.truncated {
  font-style: italic;
  color: var(--el-text-color-secondary);
}
</style>
