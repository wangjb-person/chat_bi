<script setup lang="ts">
import { ref } from 'vue'

defineProps<{ sql: string }>()

const expanded = ref(false)

function toggle() {
  expanded.value = !expanded.value
}
</script>

<template>
  <div class="sql-disclosure">
    <button
      type="button"
      class="sql-link"
      :aria-expanded="expanded"
      :title="expanded ? '收起技术详情' : '查看技术详情（仅运维/开发使用）'"
      @click="toggle"
    >
      {{ expanded ? '收起' : '技术详情' }}
    </button>
    <pre v-show="expanded" class="sql-block">{{ sql }}</pre>
  </div>
</template>

<style scoped>
.sql-disclosure {
  margin-top: 10px;
  text-align: right;
}

.sql-link {
  padding: 0;
  border: none;
  background: none;
  font-size: 10px;
  line-height: 1.4;
  color: #cbd5e1;
  cursor: pointer;
  letter-spacing: 0.02em;
  transition: color 0.15s;
}

.sql-link:hover {
  color: #94a3b8;
  text-decoration: underline;
}

.sql-block {
  margin-top: 8px;
  text-align: left;
  background: #1e293b;
  color: #e2e8f0;
  padding: 10px 12px;
  border-radius: 8px;
  font-family: Monaco, Menlo, 'Courier New', monospace;
  font-size: 11px;
  overflow-x: auto;
  white-space: pre-wrap;
  word-break: break-word;
}
</style>
