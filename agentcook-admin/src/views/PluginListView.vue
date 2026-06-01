<template>
  <div class="plugin-list-view">
    <div class="page-header">
      <h2>Plugin Management</h2>
      <div class="header-right">
        <el-tag v-if="dataSource === 'mock'" type="warning" size="small" effect="plain">
          mock fallback (Java backend unreachable)
        </el-tag>
        <el-tag v-else-if="dataSource === 'java'" type="success" size="small" effect="plain">
          live · {{ JAVA_BASE_URL }}
        </el-tag>
        <el-button type="primary" @click="handleCreate">Create Plugin</el-button>
      </div>
    </div>

    <div class="search-bar">
      <el-input
        v-model="searchQuery"
        placeholder="Search by name..."
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
        <el-option label="Published" value="PUBLISHED" />
        <el-option label="Draft" value="DRAFT" />
        <el-option label="Disabled" value="DISABLED" />
      </el-select>
      <el-select
        v-model="kindFilter"
        placeholder="Kind"
        clearable
        style="width: 130px; margin-left: 12px"
        @change="handleSearch"
      >
        <el-option label="MCP" value="MCP" />
        <el-option label="HTTP" value="HTTP" />
        <el-option label="OAUTH" value="OAUTH" />
        <el-option label="WEBHOOK" value="WEBHOOK" />
      </el-select>
      <el-button :icon="Refresh" link @click="loadPlugins">Reload</el-button>
    </div>

    <ProTable
      :columns="columns"
      :data="filteredPlugins"
      :loading="loading"
      :pagination="pagination"
      @page-change="handlePageChange"
    >
      <template #kind="{ row }">
        <el-tag type="info" effect="plain" size="small">
          {{ row.kind }}
        </el-tag>
      </template>
      <template #status="{ row }">
        <el-tag :type="statusTagType(row.status)" size="small">
          {{ row.status }}
        </el-tag>
      </template>
      <template #actions="{ row }">
        <el-button link type="primary" size="small" @click="handleDetail(row)">
          Detail
        </el-button>
        <el-button link type="primary" size="small" @click="handleEdit(row)">
          Edit
        </el-button>
        <el-button
          v-if="row.status === 'DISABLED' || row.status === 'DRAFT'"
          link
          type="success"
          size="small"
          @click="handleEnable(row)"
        >
          Enable
        </el-button>
        <el-button
          v-if="row.status === 'PUBLISHED'"
          link
          type="warning"
          size="small"
          @click="handleDisable(row)"
        >
          Disable
        </el-button>
      </template>
    </ProTable>

    <PluginCreateDialog v-model="createOpen" @created="onPluginCreated" />
    <PluginDetailDrawer
      v-model="detailOpen"
      :plugin-id="activeRow?.id"
      :fallback="activeDto ?? undefined"
    />
    <PluginEditDialog
      v-model="editOpen"
      :plugin-id="activeRow?.id"
      :initial-json="
        activeDto
          ? JSON.stringify(
              {
                name: activeDto.name,
                version: activeDto.version,
                kind: activeDto.kind,
                description: activeDto.description,
              },
              null,
              2,
            )
          : undefined
      "
      @saved="onPluginSaved"
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
import PluginCreateDialog from "./plugins/PluginCreateDialog.vue";
import PluginDetailDrawer from "./plugins/PluginDetailDrawer.vue";
import PluginEditDialog from "./plugins/PluginEditDialog.vue";

type PluginKind = "MCP" | "HTTP" | "OAUTH" | "WEBHOOK";
type PluginStatus = "PUBLISHED" | "DRAFT" | "DISABLED";

/** Real Java backend response shape (auto-generated from springdoc). */
type PluginResponseDto = components["schemas"]["PluginResponse"];

/** Internal row shape consumed by the table (display layer). */
interface PluginRow {
  id: string;
  name: string;
  version: string;
  kind: PluginKind;
  status: PluginStatus;
  updatedAt: string;
  description?: string;
}

/**
 * Day 24 contract reconciliation:
 * - Day 22 brief required the UI to show status=DISABLED.
 * - Java spec (java-v1.yaml @ 2026-05-31) ships status=DEPRECATED.
 * Until the author rules on which side moves, normalise here so the table
 * keeps its Day 22 contract and the divergence is contained to one mapper.
 * Tracked in progress-agent-b-day-24.md (reverse fact-check #2 to D).
 */
function fromJavaDto(dto: PluginResponseDto): PluginRow {
  const rawStatus = dto.status;
  const status: PluginStatus =
    rawStatus === "DEPRECATED" ? "DISABLED" : (rawStatus as PluginStatus);
  return {
    id: dto.id ?? crypto.randomUUID(),
    name: dto.name ?? "(unnamed)",
    version: dto.version ?? "—",
    kind: (dto.kind ?? "HTTP") as PluginKind,
    status,
    description: dto.description,
    updatedAt: dto.updatedAt
      ? new Date(dto.updatedAt).toLocaleString("zh-CN", { hour12: false })
      : "—",
  };
}

const JAVA_BASE_URL =
  import.meta.env.VITE_JAVA_API_BASE_URL || "http://localhost:8080";

const loading = ref(false);
const searchQuery = ref("");
const statusFilter = ref("");
const kindFilter = ref("");
const dataSource = ref<"java" | "mock" | "loading">("loading");

const columns = [
  { prop: "name", label: "Name", width: 220 },
  { prop: "version", label: "Version", width: 100 },
  { prop: "kind", label: "Kind", width: 110, slotName: "kind" },
  { prop: "status", label: "Status", width: 120, slotName: "status" },
  { prop: "updatedAt", label: "Updated At", width: 180 },
  { prop: "actions", label: "Actions", width: 200, slotName: "actions" },
];

const MOCK_PLUGINS: PluginRow[] = [
  { id: "p1", name: "GitHub Connector", version: "1.2.0", kind: "HTTP", status: "PUBLISHED", updatedAt: "2026-05-15 10:30" },
  { id: "p2", name: "Slack Integration", version: "2.0.1", kind: "WEBHOOK", status: "PUBLISHED", updatedAt: "2026-05-14 14:20" },
  { id: "p3", name: "OAuth2 Provider", version: "0.9.0", kind: "OAUTH", status: "DRAFT", updatedAt: "2026-05-13 09:15" },
  { id: "p4", name: "Model Context Protocol", version: "1.0.0", kind: "MCP", status: "PUBLISHED", updatedAt: "2026-05-12 16:45" },
  { id: "p5", name: "Legacy API Bridge", version: "0.5.3", kind: "HTTP", status: "DISABLED", updatedAt: "2026-05-10 11:00" },
  { id: "p6", name: "Custom Webhook Handler", version: "1.1.0", kind: "WEBHOOK", status: "DRAFT", updatedAt: "2026-05-08 13:30" },
  { id: "p7", name: "Advanced MCP Server", version: "0.3.0", kind: "MCP", status: "DRAFT", updatedAt: "2026-05-05 08:00" },
  { id: "p8", name: "Web Search", version: "1.0.4", kind: "HTTP", status: "PUBLISHED", updatedAt: "2026-05-03 17:20" },
];

const plugins = ref<PluginRow[]>([]);

const filteredPlugins = computed(() => {
  let result = plugins.value;
  if (searchQuery.value) {
    const query = searchQuery.value.toLowerCase();
    result = result.filter((p) => p.name.toLowerCase().includes(query));
  }
  if (statusFilter.value) {
    result = result.filter((p) => p.status === statusFilter.value);
  }
  if (kindFilter.value) {
    result = result.filter((p) => p.kind === kindFilter.value);
  }
  return result;
});

const pagination = ref({ page: 1, size: 10, total: 0 });

function statusTagType(status: PluginStatus) {
  const map: Record<PluginStatus, string> = {
    PUBLISHED: "success",
    DRAFT: "info",
    DISABLED: "warning",
  };
  return map[status] || "info";
}

async function loadPlugins() {
  loading.value = true;
  try {
    const data = await javaClient.get<PluginResponseDto[]>("/api/v1/plugins");
    plugins.value = (Array.isArray(data) ? data : []).map(fromJavaDto);
    pagination.value.total = plugins.value.length;
    dataSource.value = "java";
    if (plugins.value.length === 0) {
      ElMessage.info("Java backend returned 0 plugins");
    }
  } catch (err) {
    plugins.value = MOCK_PLUGINS;
    pagination.value.total = MOCK_PLUGINS.length;
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

// --- Day 27 Plugin CRUD dialogs ---

const createOpen = ref(false);
const detailOpen = ref(false);
const editOpen = ref(false);
const activeRow = ref<PluginRow | null>(null);
const activeDto = ref<PluginResponseDto | null>(null);

function handleCreate() {
  createOpen.value = true;
}

function handleDetail(row: PluginRow) {
  activeRow.value = row;
  // Project the row back to the Java DTO shape for the drawer fallback path.
  activeDto.value = {
    id: row.id,
    name: row.name,
    version: row.version,
    kind: row.kind,
    status: row.status === "DISABLED" ? "DEPRECATED" : row.status,
    description: row.description,
    updatedAt: row.updatedAt,
  } as PluginResponseDto;
  detailOpen.value = true;
}

function handleEdit(row: PluginRow) {
  activeRow.value = row;
  editOpen.value = true;
}

function onPluginCreated(dto: PluginResponseDto) {
  const created = fromJavaDto(dto);
  plugins.value = [created, ...plugins.value];
  pagination.value.total = plugins.value.length;
  ElMessage.success("Plugin list refreshed");
}

function onPluginSaved(dto: PluginResponseDto) {
  const idx = plugins.value.findIndex((p) => p.id === (dto.id ?? ""));
  if (idx !== -1) {
    plugins.value[idx] = fromJavaDto(dto);
  }
}

async function handleEnable(row: PluginRow) {
  await ElMessageBox.confirm(`Enable plugin "${row.name}"?`, "Confirm", { type: "info" });
  try {
    await javaClient.post(`/api/v1/plugins/${row.id}/activate`, {});
    row.status = "PUBLISHED";
    ElMessage.success(`Plugin ${row.name} activated`);
  } catch (err) {
    // Day 26 D added ActivatePluginUseCase, controller responds 400 to empty
    // body — still optimistically flip the row but tell the user it's local.
    row.status = "PUBLISHED";
    const status = axios.isAxiosError(err) ? err.response?.status : undefined;
    ElMessage.warning(
      status === 400
        ? `Plugin ${row.name} enabled locally — backend expects an activation body (reverse fact-check to D)`
        : `Plugin ${row.name} enabled locally — backend call failed (${status ?? "network"})`,
    );
  }
}

async function handleDisable(row: PluginRow) {
  await ElMessageBox.confirm(`Disable plugin "${row.name}"?`, "Confirm", { type: "warning" });
  try {
    await javaClient.post(`/api/v1/plugins/${row.id}/deactivate`, {});
    row.status = "DISABLED";
    ElMessage.success(`Plugin ${row.name} deactivated`);
  } catch (err) {
    row.status = "DISABLED";
    const status = axios.isAxiosError(err) ? err.response?.status : undefined;
    ElMessage.warning(
      status === 404
        ? `Plugin ${row.name} disabled locally — D hasn't exposed POST /plugins/{id}/deactivate yet (reverse fact-check #4)`
        : `Plugin ${row.name} disabled locally — backend call failed (${status ?? "network"})`,
    );
  }
}

onMounted(loadPlugins);
</script>

<style scoped>
.plugin-list-view {
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
  gap: 8px;
}
</style>
