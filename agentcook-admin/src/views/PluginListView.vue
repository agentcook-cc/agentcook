<template>
  <div class="plugin-list-view">
    <div class="header">
      <h2>Plugin Management</h2>
      <el-button type="primary" @click="handleCreate">Create Plugin</el-button>
    </div>

    <ProTable
      :columns="columns"
      :data="plugins"
      :loading="loading"
      :pagination="pagination"
      @page-change="handlePageChange"
    >
      <template #status="{ row }">
        <el-tag :type="getStatusType(row.status)">
          {{ row.status }}
        </el-tag>
      </template>
      <template #kind="{ row }">
        <el-tag type="info" effect="plain">
          {{ row.kind }}
        </el-tag>
      </template>
    </ProTable>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import ProTable from '@/components/ProTable.vue'

interface Plugin {
  id: string
  name: string
  version: string
  kind: 'MCP' | 'HTTP' | 'OAUTH' | 'WEBHOOK'
  status: 'DRAFT' | 'PUBLISHED' | 'DEPRECATED'
  updatedAt: string
}

const columns = [
  { prop: 'name', label: 'Name', width: 200 },
  { prop: 'version', label: 'Version', width: 120 },
  { prop: 'kind', label: 'Kind', width: 120, slotName: 'kind' },
  { prop: 'status', label: 'Status', width: 140, slotName: 'status' },
  { prop: 'updatedAt', label: 'Updated At' },
]

const plugins = ref<Plugin[]>([])
const loading = ref(false)
const pagination = ref({
  page: 1,
  size: 10,
  total: 7,
})

const mockPlugins: Plugin[] = [
  {
    id: '1',
    name: 'GitHub Connector',
    version: '1.2.0',
    kind: 'HTTP',
    status: 'PUBLISHED',
    updatedAt: '2026-05-15 10:30:00',
  },
  {
    id: '2',
    name: 'Slack Integration',
    version: '2.0.1',
    kind: 'WEBHOOK',
    status: 'PUBLISHED',
    updatedAt: '2026-05-14 14:20:00',
  },
  {
    id: '3',
    name: 'OAuth2 Provider',
    version: '0.9.0',
    kind: 'OAUTH',
    status: 'DRAFT',
    updatedAt: '2026-05-13 09:15:00',
  },
  {
    id: '4',
    name: 'Model Context Protocol',
    version: '1.0.0',
    kind: 'MCP',
    status: 'PUBLISHED',
    updatedAt: '2026-05-12 16:45:00',
  },
  {
    id: '5',
    name: 'Legacy API Bridge',
    version: '0.5.3',
    kind: 'HTTP',
    status: 'DEPRECATED',
    updatedAt: '2026-05-10 11:00:00',
  },
  {
    id: '6',
    name: 'Custom Webhook Handler',
    version: '1.1.0',
    kind: 'WEBHOOK',
    status: 'DRAFT',
    updatedAt: '2026-05-08 13:30:00',
  },
  {
    id: '7',
    name: 'Advanced MCP Server',
    version: '0.3.0',
    kind: 'MCP',
    status: 'DRAFT',
    updatedAt: '2026-05-05 08:00:00',
  },
]

const getStatusType = (status: string) => {
  switch (status) {
    case 'PUBLISHED':
      return 'success'
    case 'DRAFT':
      return 'info'
    case 'DEPRECATED':
      return 'warning'
    default:
      return 'info'
  }
}

const loadPlugins = () => {
  loading.value = true
  setTimeout(() => {
    plugins.value = mockPlugins
    loading.value = false
  }, 300)
}

const handlePageChange = (page: number) => {
  pagination.value.page = page
  loadPlugins()
}

const handleCreate = () => {
  console.log('Create plugin clicked')
}

onMounted(() => {
  loadPlugins()
})
</script>

<style scoped>
.plugin-list-view {
  padding: 24px;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.header h2 {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  color: #303133;
}
</style>
