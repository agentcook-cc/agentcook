<template>
  <el-dialog
    v-model="visible"
    title="Edit permissions"
    width="640px"
    :close-on-click-modal="!saving"
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

    <p class="hint">
      Click a cell to cycle:
      <el-tag size="small" type="info">unset</el-tag> →
      <el-tag size="small" type="success">ALLOW</el-tag> →
      <el-tag size="small" type="danger">DENY</el-tag> →
      <el-tag size="small" type="info">unset</el-tag>
    </p>

    <table class="perm-matrix">
      <thead>
        <tr>
          <th class="corner">resource ＼ action</th>
          <th v-for="action in MOCK_PERMISSION_ACTIONS" :key="action">{{ action }}</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="resource in MOCK_PERMISSION_RESOURCES" :key="resource">
          <th class="row-label">{{ resource }}</th>
          <td v-for="action in MOCK_PERMISSION_ACTIONS" :key="action">
            <button
              type="button"
              class="cell-btn"
              :class="cellClass(resource, action)"
              :title="`${resource}.${action} = ${cellLabel(resource, action)}`"
              @click="cycle(resource, action)"
            >
              {{ cellGlyph(resource, action) }}
            </button>
          </td>
        </tr>
      </tbody>
    </table>

    <template #footer>
      <el-button @click="visible = false" :disabled="saving">Cancel</el-button>
      <el-button type="primary" :loading="saving" @click="handleSave">Save</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, computed, watch } from "vue";
import { ElMessage } from "element-plus";
import axios from "axios";
import { javaClient } from "@/api/client";
import {
  MOCK_PERMISSION_ACTIONS,
  MOCK_PERMISSION_RESOURCES,
  type PermissionDto,
  type PermissionEffect,
} from "./permissionTypes";

interface Props {
  modelValue: boolean;
  userId?: string;
  initialPermissions?: PermissionDto[];
}
const props = defineProps<Props>();
const emit = defineEmits<{
  "update:modelValue": [value: boolean];
  saved: [permissions: PermissionDto[]];
}>();

const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit("update:modelValue", v),
});

const matrix = ref<Map<string, PermissionEffect>>(new Map());
const saving = ref(false);
const errorMessage = ref("");

function key(resource: string, action: string) {
  return `${resource}#${action}`;
}

function cellEffect(resource: string, action: string): PermissionEffect | undefined {
  return matrix.value.get(key(resource, action));
}

function cellClass(resource: string, action: string) {
  const e = cellEffect(resource, action);
  if (e === "ALLOW") return "allow";
  if (e === "DENY") return "deny";
  return "unset";
}

function cellLabel(resource: string, action: string) {
  return cellEffect(resource, action) ?? "unset";
}

function cellGlyph(resource: string, action: string) {
  const e = cellEffect(resource, action);
  if (e === "ALLOW") return "✓";
  if (e === "DENY") return "✕";
  return "—";
}

function cycle(resource: string, action: string) {
  const k = key(resource, action);
  const current = matrix.value.get(k);
  const next = new Map(matrix.value);
  if (current === undefined) next.set(k, "ALLOW");
  else if (current === "ALLOW") next.set(k, "DENY");
  else next.delete(k);
  matrix.value = next;
}

function reset() {
  errorMessage.value = "";
  saving.value = false;
}

function rebuildFromInitial() {
  const map = new Map<string, PermissionEffect>();
  for (const p of props.initialPermissions ?? []) {
    map.set(key(p.resource, p.action), p.effect);
  }
  matrix.value = map;
}

watch(
  () => [props.modelValue, props.initialPermissions],
  ([open]) => {
    if (open) rebuildFromInitial();
  },
  { immediate: true },
);

function flatten(): PermissionDto[] {
  const list: PermissionDto[] = [];
  let i = 0;
  for (const [k, effect] of matrix.value.entries()) {
    const [resource, action] = k.split("#");
    list.push({
      id: `pending-${i++}`,
      resource,
      action,
      effect,
      userId: props.userId,
    });
  }
  return list;
}

async function handleSave() {
  if (!props.userId) {
    errorMessage.value = "User id missing — cannot save";
    return;
  }
  saving.value = true;
  errorMessage.value = "";
  const next = flatten();
  try {
    await javaClient.put(`/api/v1/users/${props.userId}/permissions`, {
      permissions: next.map((p) => ({
        resource: p.resource,
        action: p.action,
        effect: p.effect,
      })),
    });
    ElMessage.success(`Saved ${next.length} permission${next.length === 1 ? "" : "s"}`);
    emit("saved", next);
    visible.value = false;
  } catch (err) {
    if (axios.isAxiosError(err) && err.response?.status === 404) {
      // Day 30 reverse fact-check #3 — PUT not wired; optimistic save so the
      // drawer reflects the user's intent until D ships the endpoint.
      ElMessage.warning(
        "Saved locally — PUT /api/v1/users/{id}/permissions 404 (reverse fact-check #3 to D)",
      );
      emit("saved", next);
      visible.value = false;
    } else {
      errorMessage.value = err instanceof Error ? err.message : "Save failed";
    }
  } finally {
    saving.value = false;
  }
}
</script>

<style scoped>
.hint {
  margin: 0 0 16px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.perm-matrix {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}
.perm-matrix th,
.perm-matrix td {
  border: 1px solid var(--el-border-color);
  padding: 6px;
  text-align: center;
}
.perm-matrix thead th {
  background: var(--el-fill-color-light);
  font-weight: 600;
}
.perm-matrix .row-label {
  background: var(--el-fill-color-light);
  text-align: left;
  padding-left: 10px;
  font-weight: 500;
  font-family: "JetBrains Mono", monospace;
  font-size: 12px;
}
.cell-btn {
  width: 32px;
  height: 28px;
  border: 1px solid transparent;
  border-radius: 4px;
  cursor: pointer;
  font-weight: 700;
  transition: all 0.1s;
}
.cell-btn.unset {
  background: transparent;
  color: var(--el-text-color-disabled);
}
.cell-btn.allow {
  background: var(--el-color-success-light-8);
  color: var(--el-color-success-dark-2);
}
.cell-btn.deny {
  background: var(--el-color-danger-light-8);
  color: var(--el-color-danger-dark-2);
}
.cell-btn:hover {
  border-color: var(--el-color-primary);
}
</style>
