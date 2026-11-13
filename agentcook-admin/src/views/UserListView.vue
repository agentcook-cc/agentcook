<template>
  <div class="user-list-view">
    <div class="page-header">
      <h2>User Management</h2>
      <div class="header-right">
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

    <el-alert v-if="loadError" :title="loadError" type="error" :closable="false" show-icon />

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
        <el-button link type="primary" size="small" @click="handleDetail(row)"> Detail </el-button>
        <el-button v-if="row.status === 'ACTIVE'" link type="warning" size="small" @click="handleSuspend(row)">
          Suspend
        </el-button>
        <el-button v-if="row.status === 'SUSPENDED'" link type="success" size="small" @click="handleActivate(row)">
          Activate
        </el-button>
      </template>
    </ProTable>

    <UserDetailDrawer v-model="detailOpen" :user-id="activeUser?.id" :fallback="activeUser ?? undefined" />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from "vue";
import { Search, Refresh } from "@element-plus/icons-vue";
import { ElMessageBox, ElMessage } from "element-plus";
import ProTable from "@/components/ProTable.vue";
import { javaClient } from "@/api/client";
import type { components } from "@/api/types.java.gen";
import UserDetailDrawer from "./users/UserDetailDrawer.vue";

type UserResponseDto = components["schemas"]["UserResponse"];
type UserStatus = "ACTIVE" | "SUSPENDED" | "DELETED";

interface UserRow extends UserResponseDto {
  status: UserStatus;
}

const loading = ref(false);
const searchQuery = ref("");
const statusFilter = ref<UserStatus | "">("");
const loadError = ref("");
const detailOpen = ref(false);
const activeUser = ref<UserRow | null>(null);

const columns = [
  { prop: "email", label: "Email", width: 240 },
  { prop: "nickname", label: "Nickname", width: 160 },
  { prop: "status", label: "Status", width: 120, slotName: "status" },
  { prop: "createdAt", label: "Created At", width: 180 },
  { prop: "actions", label: "Actions", width: 240, slotName: "actions" },
];

const users = ref<UserRow[]>([]);

const filteredUsers = computed(() => {
  let result = users.value;
  if (searchQuery.value) {
    const query = searchQuery.value.toLowerCase();
    result = result.filter(
      (user) => (user.email ?? "").toLowerCase().includes(query) || (user.nickname ?? "").toLowerCase().includes(query),
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
  loadError.value = "";
  try {
    const data = await javaClient.get<UserResponseDto[]>("/api/v1/users");
    users.value = (Array.isArray(data) ? data : []).map((u) => ({
      ...u,
      status: (u.status ?? "ACTIVE") as UserStatus,
    }));
    pagination.value.total = users.value.length;
    if (users.value.length === 0) {
      ElMessage.info("Java backend returned 0 users");
    }
  } catch {
    users.value = [];
    pagination.value.total = 0;
    loadError.value = "无法加载用户，请稍后重试。";
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

async function invokeStatusChange(row: UserRow, target: UserStatus, action: "suspend" | "activate") {
  try {
    await javaClient.put(`/api/v1/users/${row.id}/${action}`);
    row.status = target;
    ElMessage.success("用户状态已更新");
  } catch {
    ElMessage.error("操作失败，用户状态未更改，请重试。");
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
