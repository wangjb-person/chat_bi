<script setup lang="ts">
defineProps<{ sql: string }>()
</script>

<template>
  <pre class="sql-block">{{ sql }}</pre>
</template>

<style scoped>
.sql-block {
  background: #1e293b;
  color: #e2e8f0;
  padding: 12px 16px;
  border-radius: 10px;
  font-family: Monaco, Menlo, 'Courier New', monospace;
  font-size: 12px;
  overflow-x: auto;
  margin: 8px 0 0;
  white-space: pre-wrap;
  word-break: break-word;
}
</style>
