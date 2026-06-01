<template>
  <el-drawer
    v-model="visible"
    title="Plugin Detail"
    direction="rtl"
    size="640px"
    @close="reset"
  >
    <template #header>
      <div class="drawer-header">
        <span>Plugin Detail</span>
        <el-tag v-if="source === 'backend'" type="success" size="small" effect="plain">
          live · backend
        </el-tag>
        <el-tag v-else-if="source === 'cached'" type="warning" size="small" effect="plain">
          cached · GET /api/v1/plugins/{id} 404
        </el-tag>
      </div>
    </template>

    <el-skeleton v-if="loading" :rows="6" animated />

    <template v-else-if="plugin">
      <el-descriptions :column="2" border>
        <el-descriptions-item label="Name">{{ plugin.name }}</el-descriptions-item>
        <el-descriptions-item label="Version">{{ plugin.version }}</el-descriptions-item>
        <el-descriptions-item label="Kind">
          <el-tag size="small" type="info" effect="plain">{{ plugin.kind }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="Status">
          <el-tag size="small" :type="statusType(plugin.status)">{{ plugin.status }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="Created At" :span="2">
          {{ formatDate(plugin.createdAt) }}
        </el-descriptions-item>
        <el-descriptions-item label="Updated At" :span="2">
          {{ formatDate(plugin.updatedAt) }}
        </el-descriptions-item>
      </el-descriptions>

      <div class="json-section">
        <h4>plugin.json</h4>
        <vue-monaco-editor
          v-model:value="jsonString"
          language="json"
          theme="vs"
          :options="{
            readOnly: true,
            minimap: { enabled: false },
            fontSize: 12,
            scrollBeyondLastLine: false,
            automaticLayout: true,
          }"
          height="320px"
        />
      </div>
    </template>

    <template v-else>
      <el-empty description="No plugin selected" />
    </template>
  </el-drawer>
</template>

<script setup lang="ts">
import { ref, computed, watch } from "vue";
import { VueMonacoEditor } from "@guolao/vue-monaco-editor";
import { javaClient } from "@/api/client";
import type { components } from "@/api/types.java.gen";

type PluginResponseDto = components["schemas"]["PluginResponse"];

interface Props {
  modelValue: boolean;
  pluginId?: string;
  fallback?: PluginResponseDto;
}
const props = defineProps<Props>();
const emit = defineEmits<{ "update:modelValue": [value: boolean] }>();

const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit("update:modelValue", v),
});

const plugin = ref<PluginResponseDto | null>(null);
const loading = ref(false);
const source = ref<"backend" | "cached" | "empty">("empty");

const jsonString = computed(() => (plugin.value ? JSON.stringify(plugin.value, null, 2) : ""));

function statusType(s?: string) {
  if (s === "PUBLISHED") return "success";
  if (s === "DEPRECATED" || s === "DISABLED") return "warning";
  return "info";
}

function formatDate(iso?: string) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString("zh-CN", { hour12: false });
  } catch {
    return iso;
  }
}

function reset() {
  plugin.value = null;
  loading.value = false;
  source.value = "empty";
}

async function load() {
  if (!props.pluginId) {
    plugin.value = props.fallback ?? null;
    source.value = props.fallback ? "cached" : "empty";
    return;
  }
  loading.value = true;
  try {
    plugin.value = await javaClient.get<PluginResponseDto>(
      `/api/v1/plugins/${props.pluginId}`,
    );
    source.value = "backend";
  } catch {
    // GET /api/v1/plugins/{id} not yet implemented by D (Day 27 reverse
    // fact-check #2). Fall back to the row data already on the list page.
    if (props.fallback) {
      plugin.value = props.fallback;
      source.value = "cached";
    } else {
      plugin.value = null;
      source.value = "empty";
    }
  } finally {
    loading.value = false;
  }
}

watch(
  () => [props.modelValue, props.pluginId],
  ([open]) => {
    if (open) load();
    else reset();
  },
  { immediate: true },
);
</script>

<style scoped>
.drawer-header {
  display: flex;
  align-items: center;
  gap: 12px;
}
.json-section {
  margin-top: 16px;
}
.json-section h4 {
  margin: 0 0 8px;
  font-size: 13px;
  color: var(--el-text-color-secondary);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
</style>
