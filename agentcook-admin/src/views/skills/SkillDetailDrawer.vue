<template>
  <el-drawer
    v-model="visible"
    title="Skill Detail"
    direction="rtl"
    size="640px"
    @close="reset"
  >
    <template #header>
      <div class="drawer-header">
        <span>Skill Detail</span>
        <el-tag v-if="source === 'backend'" type="success" size="small" effect="plain">
          live · backend
        </el-tag>
        <el-tag v-else-if="source === 'cached'" type="warning" size="small" effect="plain">
          cached · GET /api/v1/skills/{id} 404
        </el-tag>
      </div>
    </template>

    <el-skeleton v-if="loading" :rows="5" animated />

    <template v-else-if="skill">
      <el-descriptions :column="2" border>
        <el-descriptions-item label="Name">{{ skill.name }}</el-descriptions-item>
        <el-descriptions-item label="Version">{{ skill.version }}</el-descriptions-item>
        <el-descriptions-item label="Kind">
          <el-tag size="small" type="info" effect="plain">{{ skill.kind }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="Category">{{ skill.category }}</el-descriptions-item>
        <el-descriptions-item v-if="skill.author" label="Author">
          {{ skill.author }}
        </el-descriptions-item>
        <el-descriptions-item v-if="skill.tags && skill.tags.length" label="Tags">
          <el-tag
            v-for="tag in skill.tags"
            :key="tag"
            size="small"
            type="info"
            style="margin-right: 4px"
          >
            {{ tag }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="Description" :span="2">
          {{ skill.description }}
        </el-descriptions-item>
      </el-descriptions>

      <div class="manifest-section">
        <h4>skill manifest</h4>
        <vue-monaco-editor
          v-model:value="manifestYaml"
          language="yaml"
          theme="vs"
          :options="{
            readOnly: true,
            minimap: { enabled: false },
            fontSize: 12,
            scrollBeyondLastLine: false,
            automaticLayout: true,
            wordWrap: 'on',
          }"
          height="320px"
        />
      </div>
    </template>

    <template v-else>
      <el-empty description="No skill selected" />
    </template>
  </el-drawer>
</template>

<script setup lang="ts">
import { ref, computed, watch } from "vue";
import { VueMonacoEditor } from "@guolao/vue-monaco-editor";
import { pythonClient } from "@/api/client";
import type { SkillManifest } from "./skillTypes";

interface Props {
  modelValue: boolean;
  skillId?: string;
  fallback?: SkillManifest;
}
const props = defineProps<Props>();
const emit = defineEmits<{ "update:modelValue": [value: boolean] }>();

const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit("update:modelValue", v),
});

const skill = ref<SkillManifest | null>(null);
const loading = ref(false);
const source = ref<"backend" | "cached" | "empty">("empty");

const manifestYaml = computed(() => (skill.value ? toYaml(skill.value) : ""));

/**
 * Lightweight YAML emitter — admin doesn't ship a full yaml lib, so we render
 * the manifest with minimal handcraft formatting. Fine for read-only display;
 * Phase 5 swap to `js-yaml` if we ever need round-tripping.
 */
function toYaml(s: SkillManifest, indent = 0): string {
  const pad = " ".repeat(indent);
  const lines: string[] = [];
  for (const [key, value] of Object.entries(s)) {
    if (value === undefined || value === null) continue;
    if (Array.isArray(value)) {
      lines.push(`${pad}${key}:`);
      for (const item of value) {
        lines.push(`${pad}  - ${typeof item === "string" ? item : JSON.stringify(item)}`);
      }
    } else if (typeof value === "object") {
      lines.push(`${pad}${key}:`);
      for (const [k, v] of Object.entries(value as Record<string, unknown>)) {
        lines.push(`${pad}  ${k}: ${typeof v === "string" ? v : JSON.stringify(v)}`);
      }
    } else {
      const escaped =
        typeof value === "string" && /[:\n#]/.test(value)
          ? JSON.stringify(value)
          : value;
      lines.push(`${pad}${key}: ${escaped}`);
    }
  }
  return lines.join("\n");
}

function reset() {
  skill.value = null;
  loading.value = false;
  source.value = "empty";
}

async function load() {
  if (!props.skillId) {
    skill.value = props.fallback ?? null;
    source.value = props.fallback ? "cached" : "empty";
    return;
  }
  loading.value = true;
  try {
    skill.value = await pythonClient.get<SkillManifest>(
      `/api/v1/skills/${props.skillId}`,
    );
    source.value = "backend";
  } catch {
    if (props.fallback) {
      skill.value = props.fallback;
      source.value = "cached";
    } else {
      skill.value = null;
      source.value = "empty";
    }
  } finally {
    loading.value = false;
  }
}

watch(
  () => [props.modelValue, props.skillId],
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
.manifest-section {
  margin-top: 16px;
}
.manifest-section h4 {
  margin: 0 0 8px;
  font-size: 13px;
  color: var(--el-text-color-secondary);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
</style>
