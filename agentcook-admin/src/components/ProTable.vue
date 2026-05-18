<template>
  <div class="pro-table">
    <el-table
      :data="data"
      v-loading="loading"
      border
      style="width: 100%"
    >
      <el-table-column
        v-for="column in columns"
        :key="column.prop"
        :prop="column.prop"
        :label="column.label"
        :width="column.width"
        :sortable="column.sortable"
      >
        <template #default="scope" v-if="column.slotName">
          <slot :name="column.slotName" :row="scope.row" :index="scope.$index" />
        </template>
      </el-table-column>
    </el-table>

    <div class="pagination-container" v-if="pagination">
      <el-pagination
        :current-page="pagination.page"
        :page-size="pagination.size"
        :total="pagination.total"
        @current-change="handlePageChange"
        layout="total, prev, pager, next"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { defineProps, defineEmits } from 'vue'

interface Column {
  prop: string
  label: string
  width?: number
  slotName?: string
  sortable?: boolean
}

interface Pagination {
  page: number
  size: number
  total: number
}

const props = defineProps<{
  columns: Column[]
  data: any[]
  loading?: boolean
  pagination?: Pagination
}>()

const emit = defineEmits<{
  (e: 'page-change', page: number): void
}>()

const handlePageChange = (page: number) => {
  emit('page-change', page)
}
</script>

<style scoped>
.pro-table {
  width: 100%;
}

.pagination-container {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}
</style>
