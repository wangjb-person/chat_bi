<script setup lang="ts">
import { useBackendHealth } from '@/composables/useBackendHealth'
import MessageList from './MessageList.vue'
import ChatInput from './ChatInput.vue'

const { statusText, statusTitle, connected, check } = useBackendHealth()

defineExpose({ check, connected })
</script>

<template>
  <section class="chat-panel">
    <header class="chat-header">
      <h2>💬 智能问数</h2>
      <span
        class="status-badge"
        :class="{ error: !connected && statusText.includes('未连接') }"
        :title="statusTitle"
      >
        {{ statusText }}
      </span>
    </header>
    <MessageList />
    <ChatInput />
  </section>
</template>

<style scoped>
.chat-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: var(--color-bg);
  min-width: 0;
}

.chat-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 24px;
  background: #fff;
  border-bottom: 1px solid var(--color-border);
}

.chat-header h2 {
  font-size: 18px;
  font-weight: 600;
}

.status-badge {
  font-size: 12px;
  color: #059669;
  background: #d1fae5;
  padding: 4px 10px;
  border-radius: 20px;
  max-width: 280px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.status-badge.error {
  color: #b91c1c;
  background: #fee2e2;
}
</style>
