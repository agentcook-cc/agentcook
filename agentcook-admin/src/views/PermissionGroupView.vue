<template>
  <div class="permission-view">
    <div class="page-header">
      <h2>Permissions</h2>
      <div class="header-right">
        <el-tag v-if="dataSource === 'mock'" type="warning" size="small" effect="plain">
          mock fallback (Java /users 405, /permissions 404)
        </el-tag>
        <el-tag v-else type="success" size="small" effect="plain">
          live · {{ JAVA_BASE }}
        </el-tag>
        <el-button :icon="Refresh" link @click="loadUsers">Reload</el-button>
      </div>
    </div>

    <p class="hint">
      Permissions are managed per user (no Role aggregate in Day 30 backend).
      Pick a user on the left, edit the resource × action matrix on the right.
    </p>

    <div class="split">
      <aside class="user-pane">
        <el-input
          v-model="searchQuery"
          placeholder="Filter users..."
          clearable
          :prefix-icon="Search"
          size="small"
        />
        <el-skeleton v-if="loading" :rows="6" animated />
        <ul v-else class="user-list">
          <li
            v-for="u in filteredUsers"
            :key="u.id"
            :class="{ active: u.id === selectedUserId }"
            @click="selectUser(u.id ?? '')"
          >
            <div class="user-row">
              <strong>{{ u.nickname || "(no name)" }}</strong>
              <el-tag :type="userStatusType(u.status)" size="small" effect="plain">
                {{ u.status }}
              </el-tag>
            </div>
            <div class="user-email">{{ u.email }}</div>
          </li>
          <el-empty
            v-if="filteredUsers.length === 0"
            description="No users"
            :image-size="48"
          />
        </ul>
      </aside>

      <section class="matrix-pane">
        <div v-if="!selectedUserId" class="placeholder">
          Select a user to see their permission matrix.
        </div>
        <template v-else>
          <div class="matrix-header">
            <h3>{{ selectedUser?.nickname }} <small>· {{ selectedUser?.email }}</small></h3>
            <el-button type="primary" size="small" @click="openEdit">Edit permissions</el-button>
          </div>

          <el-tag v-if="permSource === 'mock'" type="warning" size="small" effect="plain">
            mock · GET /users/{{ '{id}' }}/permissions 404
          </el-tag>

          <table v-if="matrix.actions.length" class="perm-matrix">
            <thead>
              <tr>
                <th class="corner">resource ＼ action</th>
                <th v-for="a in matrix.actions" :key="a">{{ a }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="r in matrix.resources" :key="r">
                <th class="row-label">{{ r }}</th>
                <td v-for="a in matrix.actions" :key="a">
                  <span class="cell" :class="cellClass(r, a)">{{ cellGlyph(r, a) }}</span>
                </td>
              </tr>
            </tbody>
          </table>
          <el-empty v-else description="No permissions assigned" :image-size="60" />
        </template>
      </section>
    </div>

    <PermissionEditDialog
      v-model="editOpen"
      :user-id="selectedUserId ?? undefined"
      :initial-permissions="permissions"
      @saved="onSaved"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from "vue";
import { Search, Refresh } from "@element-plus/icons-vue";
import { javaClient } from "@/api/client";
import type { components } from "@/api/types.java.gen";
import {
  buildMatrix,
  makeMockPermissions,
  type PermissionDto,
} from "./users/permissionTypes";
import PermissionEditDialog from "./users/PermissionEditDialog.vue";

type UserResponseDto = components["schemas"]["UserResponse"];
interface UserRow extends UserResponseDto {
  status: "ACTIVE" | "SUSPENDED" | "DELETED";
}

const JAVA_BASE =
  import.meta.env.VITE_JAVA_API_BASE_URL || "http://localhost:8080";

const users = ref<UserRow[]>([]);
const permissions = ref<PermissionDto[]>([]);
const loading = ref(false);
const dataSource = ref<"live" | "mock">("mock");
const permSource = ref<"backend" | "mock">("mock");
const searchQuery = ref("");
const selectedUserId = ref<string | null>(null);
const editOpen = ref(false);

const MOCK_USERS: UserRow[] = [
  { id: "u1", email: "alice@example.com", nickname: "Alice", status: "ACTIVE", createdAt: "2026-05-10 08:00" },
  { id: "u2", email: "bob@example.com", nickname: "Bob", status: "ACTIVE", createdAt: "2026-05-11 09:30" },
  { id: "u3", email: "charlie@test.io", nickname: "Charlie", status: "SUSPENDED", createdAt: "2026-05-12 11:00" },
  { id: "u4", email: "diana@company.com", nickname: "Diana", status: "ACTIVE", createdAt: "2026-05-13 14:20" },
  { id: "u5", email: "henry@corp.net", nickname: "Henry", status: "ACTIVE", createdAt: "2026-05-17 07:30" },
];

const filteredUsers = computed(() => {
  if (!searchQuery.value) return users.value;
  const q = searchQuery.value.toLowerCase();
  return users.value.filter(
    (u) => u.email?.toLowerCase().includes(q) || u.nickname?.toLowerCase().includes(q),
  );
});

const selectedUser = computed(() =>
  users.value.find((u) => u.id === selectedUserId.value) ?? null,
);

const matrix = computed(() => buildMatrix(permissions.value));

function cellClass(resource: string, action: string) {
  const eff = matrix.value.cells.get(`${resource}#${action}`);
  if (eff === "ALLOW") return "allow";
  if (eff === "DENY") return "deny";
  return "unset";
}
function cellGlyph(resource: string, action: string) {
  const eff = matrix.value.cells.get(`${resource}#${action}`);
  if (eff === "ALLOW") return "✓";
  if (eff === "DENY") return "✕";
  return "—";
}

function userStatusType(s?: string) {
  if (s === "ACTIVE") return "success";
  if (s === "SUSPENDED") return "warning";
  if (s === "DELETED") return "danger";
  return "info";
}

async function loadUsers() {
  loading.value = true;
  try {
    const data = await javaClient.get<UserResponseDto[]>("/api/v1/users");
    users.value = (Array.isArray(data) ? data : []).map((u) => ({
      ...u,
      status: (u.status ?? "ACTIVE") as UserRow["status"],
    }));
    dataSource.value = "live";
  } catch {
    users.value = MOCK_USERS;
    dataSource.value = "mock";
  } finally {
    loading.value = false;
    if (users.value.length && !selectedUserId.value) {
      selectUser(users.value[0].id ?? "");
    }
  }
}

async function loadPermissionsFor(userId: string) {
  try {
    permissions.value = await javaClient.get<PermissionDto[]>(
      `/api/v1/users/${userId}/permissions`,
    );
    permSource.value = "backend";
  } catch {
    permissions.value = makeMockPermissions(userId);
    permSource.value = "mock";
  }
}

function selectUser(id: string) {
  selectedUserId.value = id;
  loadPermissionsFor(id);
}

function openEdit() {
  editOpen.value = true;
}

function onSaved(next: PermissionDto[]) {
  permissions.value = next;
}

watch(selectedUserId, (id) => {
  if (id) loadPermissionsFor(id);
});

onMounted(loadUsers);
</script>

<style scoped>
.permission-view {
  padding: 24px;
}
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}
.page-header h2 {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
}
.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}
.hint {
  margin: 0 0 16px;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}
.split {
  display: grid;
  grid-template-columns: 280px 1fr;
  gap: 16px;
  min-height: 420px;
}
.user-pane {
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  padding: 12px;
  background: white;
  display: flex;
  flex-direction: column;
  gap: 10px;
  max-height: 600px;
  overflow-y: auto;
}
.user-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.user-list li {
  padding: 8px 10px;
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.1s;
}
.user-list li:hover {
  background: var(--el-fill-color-lighter);
}
.user-list li.active {
  background: var(--el-color-primary-light-9);
  border: 1px solid var(--el-color-primary);
}
.user-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 6px;
  font-size: 13px;
}
.user-email {
  font-size: 11px;
  color: var(--el-text-color-secondary);
  margin-top: 2px;
}
.matrix-pane {
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  padding: 16px;
  background: white;
}
.matrix-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}
.matrix-header h3 {
  margin: 0;
  font-size: 16px;
}
.matrix-header small {
  color: var(--el-text-color-secondary);
  font-weight: 400;
  font-size: 13px;
}
.placeholder {
  text-align: center;
  color: var(--el-text-color-secondary);
  padding: 60px 0;
}
.perm-matrix {
  width: 100%;
  border-collapse: collapse;
  margin-top: 12px;
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
}
.perm-matrix .row-label {
  background: var(--el-fill-color-light);
  text-align: left;
  padding-left: 10px;
  font-family: "JetBrains Mono", monospace;
  font-size: 12px;
}
.cell {
  display: inline-block;
  width: 28px;
  text-align: center;
  font-weight: 700;
}
.cell.allow {
  color: var(--el-color-success);
}
.cell.deny {
  color: var(--el-color-danger);
}
.cell.unset {
  color: var(--el-text-color-disabled);
}
</style>
