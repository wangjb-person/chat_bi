<script setup lang="ts">
import { Grid } from '@element-plus/icons-vue'
import { storeToRefs } from 'pinia'
import { computed } from 'vue'
import { DATA_TABLE_OPTIONS } from '@/constants/dataTables'
import { useAppStore } from '@/stores/appStore'

const app = useAppStore()
const { tableName } = storeToRefs(app)

const currentLabel = computed(() => {
  const hit = DATA_TABLE_OPTIONS.find((o) => o.value === tableName.value)
  return hit?.label ?? (tableName.value || '数据表')
})

function onSelect(value: string) {
  tableName.value = value
}
</script>

<template>
  <el-dropdown trigger="click" @command="onSelect">
    <button type="button" class="table-chip" :title="tableName || '未限定数据表'">
      <el-icon :size="14"><Grid /></el-icon>
      <span>{{ currentLabel }}</span>
    </button>
    <template #dropdown>
      <el-dropdown-menu>
        <el-dropdown-item
          v-for="opt in DATA_TABLE_OPTIONS"
          :key="opt.value || '__all__'"
          :command="opt.value"
        >
          {{ opt.label }}
        </el-dropdown-item>
      </el-dropdown-menu>
    </template>
  </el-dropdown>
</template>

<style scoped>
.table-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #f8fafc;
  color: #475569;
  font-size: 12px;
  cursor: pointer;
  transition: border-color 0.15s, color 0.15s;
}

.table-chip:hover {
  border-color: #c4b5fd;
  color: #6d28d9;
}
</style>
