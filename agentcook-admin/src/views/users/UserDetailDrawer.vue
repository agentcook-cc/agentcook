<template>
  <el-drawer
    v-model="visible"
    title="User Detail"
    direction="rtl"
    size="640px"
    @close="reset"
  >
    <template #header>
      <div class="drawer-header">
        <span>{{ user?.nickname ?? "User Detail" }}</span>
        <el-tag v-if="userSource === 'backend'" type="success" size="small" effect="plain">
          live · /users/{{ '{id}' }}
        </el-tag>
        <el-tag v-else-if="userSource === 'cached'" type="warning" size="small" effect="plain">
          cached · row fallback
        </el-tag>
      </div>
    </template>

    <el-skeleton v-if="loading" :rows="6" animated />

    <template v-else-if="user">
      <el-descriptions :column="2" border>
        <el-descriptions-item label="ID">
          <code class="muted-code">{{ user.id }}</code>
        </el-descriptions-item>
        <el-descriptions-item label="Status">
          <el-tag :type="statusType(user.status)" size="small">{{ user.status }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="Email">{{ user.email }}</el-descriptions-item>
        <el-descriptions-item label="Nickname">{{ user.nickname }}</el-descriptions-item>
        <el-descriptions-item label="Created" :span="2">
          {{ formatDate(user.createdAt) }}
        </el-descriptions-item>
        <el-descriptions-item label="Updated" :span="2">
          {{ formatDate(user.updatedAt) }}
        </el-descriptions-item>
      </el-descriptions>

      <el-tabs v-model="activeTab" class="detail-tabs">
        <el-tab-pane label="Permissions" name="permissions">
          <div class="tab-header">
            <el-tag v-if="permSource === 'backend'" type="success" size="small" effect="plain">
              live
            </el-tag>
            <el-tag v-else type="warning" size="small" effect="plain">
              mock · GET /users/{{ '{id}' }}/permissions 404
            </el-tag>
            <el-button link type="primary" size="small" @click="openEdit">Edit</el-button>
          </div>
          <el-table
            v-if="permissions.length"
            :data="permissions"
            size="small"
            style="width: 100%"
          >
            <el-table-column prop="resource" label="Resource" width="140" />
            <el-table-column prop="action" label="Action" width="120" />
            <el-table-column prop="effect" label="Effect" width="100">
              <template #default="{ row }">
                <el-tag :type="row.effect === 'ALLOW' ? 'success' : 'danger'" size="small">
                  {{ row.effect }}
                </el-tag>
              </template>
            </el-table-column>
          </el-table>
          <el-empty v-else description="No permissions assigned" :image-size="60" />
        </el-tab-pane>
        <el-tab-pane label="Activity" name="activity">
          <el-empty description="Activity log Phase 5" :image-size="60" />
        </el-tab-pane>
      </el-tabs>
    </template>

    <template v-else>
      <el-empty description="No user selected" />
    </template>

    <PermissionEditDialog
      v-model="editOpen"
      :user-id="user?.id"
      :initial-permissions="permissions"
      @saved="onPermissionsSaved"
    />
  </el-drawer>
</template>

<script setup lang="ts">
import { ref, computed, watch } from "vue";
import { javaClient } from "@/api/client";
import type { components } from "@/api/types.java.gen";
import {
  makeMockPermissions,
  type PermissionDto,
} from "./permissionTypes";
import PermissionEditDialog from "./PermissionEditDialog.vue";

type UserResponseDto = components["schemas"]["UserResponse"];

interface UserRow extends UserResponseDto {
  status: "ACTIVE" | "SUSPENDED" | "DELETED";
}

interface Props {
  modelValue: boolean;
  userId?: string;
  fallback?: UserRow;
}
const props = defineProps<Props>();
const emit = defineEmits<{ "update:modelValue": [value: boolean] }>();

const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit("update:modelValue", v),
});

const user = ref<UserRow | null>(null);
const permissions = ref<PermissionDto[]>([]);
const loading = ref(false);
const userSource = ref<"backend" | "cached" | "empty">("empty");
const permSource = ref<"backend" | "mock" | "empty">("empty");
const activeTab = ref("permissions");
const editOpen = ref(false);

function statusType(s?: string) {
  if (s === "ACTIVE") return "success";
  if (s === "SUSPENDED") return "warning";
  if (s === "DELETED") return "danger";
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
  user.value = null;
  permissions.value = [];
  loading.value = false;
  userSource.value = "empty";
  permSource.value = "empty";
  activeTab.value = "permissions";
}

async function loadUser() {
  if (!props.userId) {
    user.value = props.fallback ?? null;
    userSource.value = props.fallback ? "cached" : "empty";
    return;
  }
  loading.value = true;
  try {
    const dto = await javaClient.get<UserResponseDto>(`/api/v1/users/${props.userId}`);
    user.value = { ...dto, status: (dto.status ?? "ACTIVE") as UserRow["status"] };
    userSource.value = "backend";
  } catch {
    if (props.fallback) {
      user.value = props.fallback;
      userSource.value = "cached";
    } else {
      user.value = null;
      userSource.value = "empty";
    }
  } finally {
    loading.value = false;
  }
}

async function loadPermissions() {
  if (!props.userId) return;
  try {
    permissions.value = await javaClient.get<PermissionDto[]>(
      `/api/v1/users/${props.userId}/permissions`,
    );
    permSource.value = "backend";
  } catch {
    // Day 30 reverse fact-check #2 — D's PermissionController not shipped.
    permissions.value = makeMockPermissions(props.userId);
    permSource.value = "mock";
  }
}

function openEdit() {
  editOpen.value = true;
}

function onPermissionsSaved(next: PermissionDto[]) {
  permissions.value = next;
}

watch(
  () => [props.modelValue, props.userId],
  ([open]) => {
    if (open) {
      loadUser();
      loadPermissions();
    } else {
      reset();
    }
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
.detail-tabs {
  margin-top: 16px;
}
.tab-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}
.muted-code {
  font-family: "JetBrains Mono", monospace;
  font-size: 11px;
  color: var(--el-text-color-secondary);
}
</style>
