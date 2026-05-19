<script setup lang="ts">
import { computed } from 'vue'
import type { QueryResult } from '@/types/api'
import SqlBlock from './SqlBlock.vue'

const props = defineProps<{
  result: QueryResult
  sql?: string
}>()

const maxRows = 100

const displayRows = computed(() => props.result.data?.slice(0, maxRows) ?? [])

function isNumericValue(val: unknown): boolean {
  if (val === null || val === undefined || val === '') return false
  if (typeof val === 'number') return true
  if (typeof val === 'string' && /^-?\d+(\.\d+)?$/.test(val.trim())) return true
  return false
}

function formatCell(val: unknown): string {
  if (val === null || val === undefined) return '—'
  if (typeof val === 'number') {
    return Number.isInteger(val) ? String(val) : val.toFixed(2).replace(/\.?0+$/, '')
  }
  return String(val)
}

const isSingleMetric = computed(
  () =>
    props.result.row_count === 1
    && props.result.columns.length === 1
    && displayRows.value.length === 1,
)

const singleMetric = computed(() => {
  if (!isSingleMetric.value) return null
  const col = props.result.columns[0]
  const row = displayRows.value[0]
  return {
    label: col,
    value: formatCell(row[col]),
  }
})
</script>

<template>
  <div class="query-result">
    <header class="result-header">
      <span v-if="result.data?.length" class="result-status success">
        <span class="status-dot" />
        共 {{ result.row_count }} 条结果
      </span>
      <span v-else class="result-status empty">暂无数据</span>
    </header>

    <!-- 单值聚合：大数字卡片 -->
    <div v-if="isSingleMetric && singleMetric" class="metric-card">
      <span class="metric-label">{{ singleMetric.label }}</span>
      <span class="metric-value">{{ singleMetric.value }}</span>
    </div>

    <!-- 多行多列：标准表格 -->
    <div v-else-if="displayRows.length" class="data-table-wrap">
      <table class="data-table">
        <thead>
          <tr>
            <th v-for="col in result.columns" :key="col" scope="col">
              {{ col }}
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(row, ri) in displayRows" :key="ri">
            <td
              v-for="col in result.columns"
              :key="col"
              :class="{ 'cell-num': isNumericValue(row[col]) }"
            >
              {{ formatCell(row[col]) }}
            </td>
          </tr>
        </tbody>
      </table>
      <p v-if="result.row_count > maxRows" class="more-hint">
        仅展示前 {{ maxRows }} 行，共 {{ result.row_count }} 行
      </p>
    </div>

    <SqlBlock v-if="sql?.trim()" :sql="sql" />
  </div>
</template>

<style scoped>
.query-result {
  width: 100%;
  min-width: 0;
}

.result-header {
  margin-bottom: 12px;
}

.result-status {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  font-weight: 500;
}

.result-status.success {
  color: #5b21b6;
}

.result-status.empty {
  color: #94a3b8;
}

.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #22c55e;
}

.metric-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 20px 16px;
  border-radius: 12px;
  background: linear-gradient(135deg, #faf5ff 0%, #f5f3ff 100%);
  border: 1px solid #e9d5ff;
}

.metric-label {
  font-size: 13px;
  color: #6b7280;
}

.metric-value {
  font-size: 32px;
  font-weight: 700;
  color: #5b21b6;
  letter-spacing: 0.02em;
}

.data-table-wrap {
  overflow-x: auto;
  border-radius: 12px;
  border: 1px solid #e9d5ff;
  background: #fff;
  box-shadow: 0 1px 3px rgba(109, 40, 217, 0.06);
}

.data-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.data-table thead {
  background: linear-gradient(180deg, #f5f3ff 0%, #ede9fe 100%);
}

.data-table th {
  padding: 10px 14px;
  text-align: left;
  font-weight: 600;
  font-size: 12px;
  color: #5b21b6;
  border-bottom: 1px solid #ddd6fe;
  white-space: nowrap;
}

.data-table td {
  padding: 10px 14px;
  color: #334155;
  border-bottom: 1px solid #f1f5f9;
}

.data-table tbody tr:nth-child(even) td {
  background: #fafafa;
}

.data-table tbody tr:hover td {
  background: #f5f3ff;
}

.data-table tbody tr:last-child td {
  border-bottom: none;
}

.cell-num {
  text-align: right;
  font-variant-numeric: tabular-nums;
  font-family: ui-monospace, 'SF Mono', Monaco, monospace;
}

.more-hint {
  font-size: 12px;
  color: #7c3aed;
  margin: 0;
  padding: 10px 14px;
  background: #faf5ff;
  border-top: 1px solid #ede9fe;
}

.query-result:hover :deep(.sql-link),
.query-result:focus-within :deep(.sql-link) {
  opacity: 1;
}

.query-result :deep(.sql-link) {
  opacity: 0;
  transition: opacity 0.2s ease;
}
</style>
