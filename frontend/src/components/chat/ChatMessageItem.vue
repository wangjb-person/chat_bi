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
    <div class="message-content">
      <p v-if="message.kind === 'welcome' || message.kind === 'text'" class="whitespace-pre">
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
        <strong>📌 您可以继续问：</strong>
        <div class="followup-list">
          <el-button
            v-for="(q, i) in message.followupQuestions"
            :key="i"
            size="small"
            round
            @click="emit('followupClick', q)"
          >
            {{ q }}
          </el-button>
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

.message.user .message-content {
  background: linear-gradient(135deg, var(--color-primary) 0%, var(--color-primary-dark) 100%);
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

.followup {
  margin-top: 8px;
}

.followup-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 10px;
}

.error-text {
  color: #b91c1c;
}
</style>
