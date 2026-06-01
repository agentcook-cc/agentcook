<template>
  <div class="user-list-view">
    <div class="page-header">
      <h2>User Management</h2>
      <div class="header-right">
        <el-tag v-if="dataSource === 'mock'" type="warning" size="small" effect="plain">
          mock fallback (Java /api/v1/users 405)
        </el-tag>
        <el-tag v-else type="success" size="small" effect="plain">
          live · {{ JAVA_BASE }}
        </el-tag>
        <el-button :icon="Refresh" link @click="loadUsers">Reload</el-button>
      </div>
    </div>

    <div class="search-bar">
      <el-input
        v-model="searchQuery"
        placeholder="Search by email or nickname..."
        clearable
        :prefix-icon="Search"
        style="width: 320px"
        @input="handleSearch"
      />
      <el-select
        v-model="statusFilter"
        placeholder="Status"
        clearable
        style="width: 150px; margin-left: 12px"
        @change="handleSearch"
      >
        <el-option label="Active" value="ACTIVE" />
        <el-option label="Suspended" value="SUSPENDED" />
        <el-option label="Deleted" value="DELETED" />
      </el-select>
    </div>

    <ProTable
      :columns="columns"
      :data="filteredUsers"
      :loading="loading"
      :pagination="pagination"
      @page-change="handlePageChange"
    >
      <template #status="{ row }">
        <el-tag :type="statusTagType(row.status)" size="small">
          {{ row.status }}
        </el-tag>
      </template>
      <template #actions="{ row }">
        <el-button link type="primary" size="small" @click="handleDetail(row)">
          Detail
        </el-button>
        <el-button
          v-if="row.status === 'ACTIVE'"
          link
          type="warning"
          size="small"
          @click="handleSuspend(row)"
        >
          Suspend
        </el-button>
        <el-button
          v-if="row.status === 'SUSPENDED'"
          link
          type="success"
          size="small"
          @click="handleActivate(row)"
        >
          Activate
        </el-button>
        <el-button
          v-if="row.status !== 'DELETED'"
          link
          type="danger"
          size="small"
          @click="handleDelete(row)"
        >
          Delete
        </el-button>
      </template>
    </ProTable>

    <UserDetailDrawer
      v-model="detailOpen"
      :user-id="activeUser?.id"
      :fallback="activeUser ?? undefined"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from "vue";
import { Search, Refresh } from "@element-plus/icons-vue";
import { ElMessageBox, ElMessage } from "element-plus";
import axios from "axios";
import ProTable from "@/components/ProTable.vue";
import { javaClient } from "@/api/client";
import type { components } from "@/api/types.java.gen";
import UserDetailDrawer from "./users/UserDetailDrawer.vue";

type UserResponseDto = components["schemas"]["UserResponse"];
type UserStatus = "ACTIVE" | "SUSPENDED" | "DELETED";

interface UserRow extends UserResponseDto {
  status: UserStatus;
}

const JAVA_BASE =
  import.meta.env.VITE_JAVA_API_BASE_URL || "http://localhost:8080";

const loading = ref(false);
const searchQuery = ref("");
const statusFilter = ref<UserStatus | "">("");
const dataSource = ref<"live" | "mock">("mock");
const detailOpen = ref(false);
const activeUser = ref<UserRow | null>(null);

const columns = [
  { prop: "email", label: "Email", width: 240 },
  { prop: "nickname", label: "Nickname", width: 160 },
  { prop: "status", label: "Status", width: 120, slotName: "status" },
  { prop: "createdAt", label: "Created At", width: 180 },
  { prop: "actions", label: "Actions", width: 240, slotName: "actions" },
];

const MOCK_USERS: UserRow[] = [
  { id: "u1", email: "alice@example.com", nickname: "Alice", status: "ACTIVE", createdAt: "2026-05-10 08:00" },
  { id: "u2", email: "bob@example.com", nickname: "Bob", status: "ACTIVE", createdAt: "2026-05-11 09:30" },
  { id: "u3", email: "charlie@test.io", nickname: "Charlie", status: "SUSPENDED", createdAt: "2026-05-12 11:00" },
  { id: "u4", email: "diana@company.com", nickname: "Diana", status: "ACTIVE", createdAt: "2026-05-13 14:20" },
  { id: "u5", email: "eve@dev.org", nickname: "Eve", status: "DELETED", createdAt: "2026-05-14 16:45" },
  { id: "u6", email: "frank@mail.com", nickname: "Frank", status: "ACTIVE", createdAt: "2026-05-15 10:00" },
  { id: "u7", email: "grace@startup.io", nickname: "Grace", status: "SUSPENDED", createdAt: "2026-05-16 13:15" },
  { id: "u8", email: "henry@corp.net", nickname: "Henry", status: "ACTIVE", createdAt: "2026-05-17 07:30" },
  { id: "u9", email: "iris@cloud.dev", nickname: "Iris", status: "ACTIVE", createdAt: "2026-05-18 09:00" },
  { id: "u10", email: "jack@platform.ai", nickname: "Jack", status: "ACTIVE", createdAt: "2026-05-19 11:30" },
];

const users = ref<UserRow[]>([]);

const filteredUsers = computed(() => {
  let result = users.value;
  if (searchQuery.value) {
    const query = searchQuery.value.toLowerCase();
    result = result.filter(
      (user) =>
        (user.email ?? "").toLowerCase().includes(query) ||
        (user.nickname ?? "").toLowerCase().includes(query),
    );
  }
  if (statusFilter.value) {
    result = result.filter((user) => user.status === statusFilter.value);
  }
  return result;
});

const pagination = ref({ page: 1, size: 10, total: 10 });

function statusTagType(status: UserStatus) {
  const map: Record<UserStatus, string> = {
    ACTIVE: "success",
    SUSPENDED: "warning",
    DELETED: "danger",
  };
  return map[status] || "info";
}

async function loadUsers() {
  loading.value = true;
  try {
    const data = await javaClient.get<UserResponseDto[]>("/api/v1/users");
    users.value = (Array.isArray(data) ? data : []).map((u) => ({
      ...u,
      status: (u.status ?? "ACTIVE") as UserStatus,
    }));
    pagination.value.total = users.value.length;
    dataSource.value = "live";
    if (users.value.length === 0) {
      ElMessage.info("Java backend returned 0 users");
    }
  } catch {
    users.value = MOCK_USERS;
    pagination.value.total = MOCK_USERS.length;
    dataSource.value = "mock";
  } finally {
    loading.value = false;
  }
}

function handlePageChange(page: number) {
  pagination.value.page = page;
}

function handleSearch() {
  pagination.value.page = 1;
}

function handleDetail(row: UserRow) {
  activeUser.value = row;
  detailOpen.value = true;
}

async function handleSuspend(row: UserRow) {
  await ElMessageBox.confirm(`Suspend user "${row.nickname}"?`, "Confirm", { type: "warning" });
  await invokeStatusChange(row, "SUSPENDED", "suspend");
}

async function handleActivate(row: UserRow) {
  await ElMessageBox.confirm(`Activate user "${row.nickname}"?`, "Confirm", { type: "info" });
  await invokeStatusChange(row, "ACTIVE", "activate");
}

async function handleDelete(row: UserRow) {
  await ElMessageBox.confirm(
    `Delete user "${row.nickname}"? This cannot be undone.`,
    "Confirm",
    { type: "error" },
  );
  await invokeStatusChange(row, "DELETED", "delete");
}

async function invokeStatusChange(row: UserRow, target: UserStatus, action: string) {
  try {
    // D Day 28 added SuspendUserUseCase + ActivateUserUseCase; controller
    // endpoints not yet confirmed wired — try then fall back to local.
    await javaClient.post(`/api/v1/users/${row.id}/${action}`, {});
    row.status = target;
    ElMessage.success(`User ${row.nickname} ${action}d`);
  } catch (err) {
    row.status = target;
    const status = axios.isAxiosError(err) ? err.response?.status : undefined;
    ElMessage.warning(
      status === 404
        ? `User ${row.nickname} ${action}d locally — POST /api/v1/users/{id}/${action} not wired (reverse fact-check #4 to D)`
        : `User ${row.nickname} ${action}d locally — backend ${status ?? "network"} failure`,
    );
  }
}

onMounted(loadUsers);
</script>

<style scoped>
.user-list-view {
  padding: 24px;
}
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}
.page-header h2 {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  color: #303133;
}
.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}
.search-bar {
  display: flex;
  align-items: center;
  margin-bottom: 16px;
}
</style>
