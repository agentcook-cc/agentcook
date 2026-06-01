<template>
  <div class="connector-list-view">
    <div class="page-header">
      <h2>Connectors</h2>
      <div class="header-right">
        <el-tag v-if="dataSource === 'mock'" type="warning" size="small" effect="plain">
          mock fallback (Java /api/v1/connectors unreachable)
        </el-tag>
        <el-tag v-else-if="dataSource === 'live'" type="success" size="small" effect="plain">
          live · {{ JAVA_BASE }}
        </el-tag>
        <el-button :icon="Refresh" link @click="loadConnectors">Reload</el-button>
        <el-button type="primary" @click="openOAuth">+ Connect provider</el-button>
      </div>
    </div>

    <div class="search-bar">
      <el-input
        v-model="searchQuery"
        placeholder="Search by name..."
        clearable
        :prefix-icon="Search"
        style="width: 320px"
      />
      <el-select
        v-model="providerFilter"
        placeholder="Provider"
        clearable
        style="width: 160px; margin-left: 12px"
      >
        <el-option v-for="p in PROVIDERS" :key="p" :label="PROVIDER_META[p].label" :value="p" />
      </el-select>
      <el-select
        v-model="statusFilter"
        placeholder="Status"
        clearable
        style="width: 150px; margin-left: 12px"
      >
        <el-option label="Connected" value="CONNECTED" />
        <el-option label="Disconnected" value="DISCONNECTED" />
        <el-option label="Error" value="ERROR" />
      </el-select>
    </div>

    <ProTable
      :columns="columns"
      :data="filteredConnectors"
      :loading="loading"
      :pagination="pagination"
      @page-change="handlePageChange"
    >
      <template #provider="{ row }">
        <span class="provider-cell">
          <span class="provider-icon">{{ providerMeta(row).icon }}</span>
          <span>{{ providerMeta(row).label }}</span>
        </span>
      </template>
      <template #status="{ row }">
        <el-tag :type="statusTagType(row.status)" size="small">{{ row.status }}</el-tag>
      </template>
      <template #lastConnectedAt="{ row }">
        <span class="muted">{{ formatDate(row.lastConnectedAt) }}</span>
      </template>
      <template #actions="{ row }">
        <el-button link type="primary" size="small" @click="handlePing(row)">Test</el-button>
        <el-button link type="warning" size="small" @click="handleReauth(row)">
          Re-auth
        </el-button>
        <el-popconfirm
          :title="`Delete connector '${row.displayName}'?`"
          confirm-button-type="danger"
          @confirm="handleDelete(row)"
        >
          <template #reference>
            <el-button link type="danger" size="small">Delete</el-button>
          </template>
        </el-popconfirm>
      </template>
    </ProTable>

    <ConnectorOAuthFlow v-model="oauthOpen" @connected="onConnected" />
    <ConnectorPingDialog v-model="pingOpen" :connector="activeConnector ?? undefined" />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from "vue";
import { Search, Refresh } from "@element-plus/icons-vue";
import { ElMessage } from "element-plus";
import axios from "axios";
import ProTable from "@/components/ProTable.vue";
import { javaClient } from "@/api/client";
import {
  PROVIDER_META,
  PROVIDERS,
  fromJavaDto,
  type ConnectorRow,
  type ConnectorProvider,
  type ConnectorStatus,
  type JavaConnectorResponseDto,
} from "./connectors/connectorTypes";
import ConnectorOAuthFlow from "./connectors/ConnectorOAuthFlow.vue";
import ConnectorPingDialog from "./connectors/ConnectorPingDialog.vue";

const JAVA_BASE =
  import.meta.env.VITE_JAVA_API_BASE_URL || "http://localhost:8080";

const connectors = ref<ConnectorRow[]>([]);
const loading = ref(false);
const dataSource = ref<"live" | "mock" | "loading">("loading");
const searchQuery = ref("");
const providerFilter = ref<ConnectorProvider | "">("");
const statusFilter = ref<ConnectorStatus | "">("");
const oauthOpen = ref(false);
const pingOpen = ref(false);
const activeConnector = ref<ConnectorRow | null>(null);

const columns = [
  { prop: "displayName", label: "Name", width: 200 },
  { prop: "provider", label: "Provider", width: 160, slotName: "provider" },
  { prop: "status", label: "Status", width: 130, slotName: "status" },
  { prop: "lastConnectedAt", label: "Last connected", width: 200, slotName: "lastConnectedAt" },
  { prop: "actions", label: "Actions", width: 240, slotName: "actions" },
];

const MOCK_CONNECTORS: ConnectorRow[] = [
  { id: "c1", provider: "dingtalk", displayName: "DingTalk · Team Bot", status: "CONNECTED", lastConnectedAt: "2026-06-04 14:00" },
  { id: "c2", provider: "feishu", displayName: "Feishu · Engineering", status: "CONNECTED", lastConnectedAt: "2026-06-04 09:30" },
  { id: "c3", provider: "telegram", displayName: "Telegram · Personal", status: "DISCONNECTED" },
  { id: "c4", provider: "discord", displayName: "Discord · OSS Server", status: "ERROR", lastConnectedAt: "2026-06-03 22:15" },
  { id: "c5", provider: "slack", displayName: "Slack · Customer Success", status: "CONNECTED", lastConnectedAt: "2026-06-04 11:45" },
];

const filteredConnectors = computed(() => {
  let result = connectors.value;
  if (searchQuery.value) {
    const q = searchQuery.value.toLowerCase();
    result = result.filter((c) => c.displayName.toLowerCase().includes(q));
  }
  if (providerFilter.value) {
    result = result.filter((c) => c.provider === providerFilter.value);
  }
  if (statusFilter.value) {
    result = result.filter((c) => c.status === statusFilter.value);
  }
  return result;
});

const pagination = ref({ page: 1, size: 10, total: 0 });

function providerMeta(row: ConnectorRow) {
  return PROVIDER_META[row.provider] ?? PROVIDER_META.dingtalk;
}

function statusTagType(status: ConnectorStatus) {
  if (status === "CONNECTED") return "success";
  if (status === "ERROR") return "danger";
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

async function loadConnectors() {
  loading.value = true;
  try {
    const data = await javaClient.get<JavaConnectorResponseDto[]>("/api/v1/connectors");
    connectors.value = (Array.isArray(data) ? data : []).map(fromJavaDto);
    pagination.value.total = connectors.value.length;
    dataSource.value = "live";
    if (connectors.value.length === 0) {
      ElMessage.info("Java backend returned 0 connectors");
    }
  } catch {
    connectors.value = MOCK_CONNECTORS;
    pagination.value.total = MOCK_CONNECTORS.length;
    dataSource.value = "mock";
  } finally {
    loading.value = false;
  }
}

function handlePageChange(page: number) {
  pagination.value.page = page;
}

function openOAuth() {
  oauthOpen.value = true;
}

function onConnected(dto: JavaConnectorResponseDto) {
  const row = fromJavaDto(dto);
  connectors.value = [row, ...connectors.value];
  pagination.value.total = connectors.value.length;
  ElMessage.success(`${PROVIDER_META[row.provider].label} connector created`);
}

function handlePing(row: ConnectorRow) {
  activeConnector.value = row;
  pingOpen.value = true;
}

function handleReauth(row: ConnectorRow) {
  // Day 29 stub: re-running OAuth would re-establish the connector; for now
  // we just re-open the chooser so the user can pick the same provider again.
  activeConnector.value = row;
  oauthOpen.value = true;
}

async function handleDelete(row: ConnectorRow) {
  try {
    await javaClient.del(`/api/v1/connectors/${row.id}`);
    connectors.value = connectors.value.filter((c) => c.id !== row.id);
    pagination.value.total = connectors.value.length;
    ElMessage.success(`Connector ${row.displayName} deleted`);
  } catch (err) {
    const status = axios.isAxiosError(err) ? err.response?.status : undefined;
    // Optimistic UI when backend hasn't shipped the endpoint yet.
    connectors.value = connectors.value.filter((c) => c.id !== row.id);
    pagination.value.total = connectors.value.length;
    ElMessage.warning(
      status === 404
        ? `${row.displayName} removed locally — DELETE /api/v1/connectors/{id} not wired (reverse fact-check #4 to D)`
        : `${row.displayName} removed locally — backend ${status ?? "network"} failure`,
    );
  }
}

onMounted(loadConnectors);
</script>

<style scoped>
.connector-list-view {
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
  color: var(--el-text-color-primary);
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
.provider-cell {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.provider-icon {
  font-size: 16px;
}
.muted {
  color: var(--el-text-color-secondary);
  font-size: 13px;
}
</style>
