<script setup lang="ts">
import type { QueryResult } from '@/types/api'
import SqlBlock from './SqlBlock.vue'

defineProps<{
  result: QueryResult
  /** 可选：挂在结果底部的技术向 SQL 详情 */
  sql?: string
}>()

const maxRows = 100
</script>

<template>
  <div class="query-result">
    <div class="result-badge">
      <span v-if="result.data?.length">📊 查询成功，共 {{ result.row_count }} 条记录</span>
      <span v-else>📭 查询结果为空</span>
    </div>

    <div v-if="result.data?.length" class="data-table-wrap">
      <table>
        <tbody>
          <tr v-for="(row, ri) in result.data.slice(0, maxRows)" :key="ri">
            <td v-for="col in result.columns" :key="col">
              {{ row[col] ?? '' }}
            </td>
          </tr>
        </tbody>
      </table>
      <p v-if="result.row_count > maxRows" class="more-hint">
        仅显示前 {{ maxRows }} 行，共 {{ result.row_count }} 行
      </p>
    </div>

    <SqlBlock v-if="sql?.trim()" :sql="sql" />
  </div>
</template>

<style scoped>
.query-result {
  margin-top: 8px;
}

.result-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: #f1f5f9;
  padding: 4px 12px;
  border-radius: 16px;
  font-size: 11px;
  color: #475569;
  margin-bottom: 8px;
}

.data-table-wrap {
  overflow-x: auto;
  border-radius: 10px;
  border: 1px solid var(--color-border);
  background: #fff;
}

table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}

td {
  padding: 8px 12px;
  border-bottom: 1px solid #f1f5f9;
}

tr:hover td {
  background: #f8fafc;
}

.more-hint {
  font-size: 12px;
  color: var(--color-accent);
  margin-top: 8px;
  padding: 0 4px;
}

/* 默认几乎不可见，鼠标悬停结果区时才露出（供内部技术同事使用） */
.query-result:hover :deep(.sql-link),
.query-result:focus-within :deep(.sql-link) {
  opacity: 1;
}

.query-result :deep(.sql-link) {
  opacity: 0;
  transition: opacity 0.2s ease;
}
</style>
