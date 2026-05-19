<script setup lang="ts">
import type { ChatMessage } from '@/types/chat'
import QueryResultTable from './QueryResultTable.vue'
import PlotlyChart from './PlotlyChart.vue'

defineProps<{
  message: ChatMessage
}>()

const emit = defineEmits<{
  followupClick: [question: string]
}>()
</script>

<template>
  <div class="message" :class="message.role">
    <div
      class="message-content"
      :class="{
        'message-content--wide':
          message.kind === 'query-result' || message.kind === 'followup',
      }"
    >
      <p v-if="message.kind === 'text'" class="whitespace-pre">
        {{ message.text }}
      </p>

      <p v-else-if="message.kind === 'loading' || message.kind === 'executing'" class="status-line">
        <span class="spinner" /> 正在为您查询…
      </p>

      <QueryResultTable
        v-else-if="message.kind === 'query-result' && message.queryResult"
        :result="message.queryResult"
        :sql="message.sql"
      />

      <PlotlyChart
        v-else-if="message.kind === 'plot' && message.figureJson"
        :figure-json="message.figureJson"
      />

      <div v-else-if="message.kind === 'followup' && message.followupQuestions?.length" class="followup">
        <p class="followup-title">您可以继续问</p>
        <div class="followup-list">
          <button
            v-for="(q, i) in message.followupQuestions"
            :key="i"
            type="button"
            class="followup-chip"
            @click="emit('followupClick', q)"
          >
            {{ q }}
          </button>
        </div>
      </div>

      <p v-else-if="message.kind === 'error'" class="error-text">❌ {{ message.text }}</p>
    </div>
  </div>
</template>

<style scoped>
.message {
  margin-bottom: 20px;
  display: flex;
}

.message.user {
  justify-content: flex-end;
}

.message-content {
  max-width: 75%;
  padding: 12px 18px;
  border-radius: 20px;
  font-size: 14px;
  line-height: 1.5;
}

.message-content--wide {
  max-width: min(920px, 92vw);
  padding: 14px 16px;
  border-radius: 16px;
}

.message.user .message-content {
  background: linear-gradient(135deg, #8b5cf6 0%, #6d28d9 100%);
  color: #fff;
  border-bottom-right-radius: 4px;
}

.message.assistant .message-content {
  background: #fff;
  color: var(--color-text);
  border: 1px solid var(--color-border);
  border-bottom-left-radius: 4px;
  box-shadow: var(--shadow-sm);
}

.status-line {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--color-primary);
}

.spinner {
  width: 16px;
  height: 16px;
  border: 2px solid #e2e8f0;
  border-top-color: var(--color-primary);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.followup-title {
  font-size: 13px;
  font-weight: 600;
  color: #5b21b6;
  margin-bottom: 10px;
}

.followup-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.followup-chip {
  padding: 8px 14px;
  border: 1px solid #e9d5ff;
  border-radius: 999px;
  background: #faf5ff;
  color: #4c1d95;
  font-size: 13px;
  line-height: 1.4;
  cursor: pointer;
  text-align: left;
  transition: background 0.15s, border-color 0.15s;
}

.followup-chip:hover {
  background: #f3e8ff;
  border-color: #c4b5fd;
}

.error-text {
  color: #b91c1c;
}
</style>
