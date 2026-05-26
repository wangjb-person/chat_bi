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
          message.kind === 'query-result'
          || message.kind === 'followup'
          || message.kind === 'analysis-report',
      }"
    >
      <p v-if="message.kind === 'text'" class="whitespace-pre">
        {{ message.text }}
      </p>

      <div v-else-if="message.kind === 'kb-answer'" class="kb-answer">
        <p class="kb-badge">知识库回答</p>
        <p class="whitespace-pre kb-body">{{ message.text }}</p>
        <details v-if="message.kbSources?.length" class="kb-sources-details">
          <summary class="kb-sources-summary">
            查看引文出处（{{ message.kbSources.length }}）
          </summary>
          <ul class="kb-sources">
            <li v-for="(s, i) in message.kbSources" :key="i">
              <span class="src-title">{{ s.doc_title || '文档' }}</span>
              <span v-if="s.score != null" class="src-score">
                相关度 {{ (s.score * 100).toFixed(0) }}%
              </span>
              <p class="src-snippet">{{ s.text }}</p>
            </li>
          </ul>
        </details>
      </div>

      <p
        v-else-if="message.kind === 'loading' || message.kind === 'executing' || message.kind === 'workflow'"
        class="status-line"
      >
        <span class="spinner" />
        {{ message.workflowStatus || '正在为您处理…' }}
      </p>

      <div
        v-else-if="message.kind === 'analysis-report'"
        class="analysis-report"
      >
        <p class="analysis-badge">归因分析报告</p>
        <pre class="report-body">{{ message.reportMd }}</pre>
        <ul v-if="message.facts?.raw_notes?.length" class="facts-notes">
          <li v-for="(n, i) in message.facts.raw_notes" :key="i">{{ n }}</li>
        </ul>
      </div>

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

      <div v-else-if="message.kind === 'error'" class="error-box">
        <p class="error-title">未能完成查询</p>
        <template v-if="message.errorRaw">
          <p class="error-section-label">原始错误</p>
          <pre class="error-raw">{{ message.errorRaw }}</pre>
        </template>
        <template v-if="message.errorHint">
          <p class="error-section-label">中文说明</p>
          <pre class="error-text">{{ message.errorHint }}</pre>
        </template>
        <pre v-else class="error-text">{{ message.text }}</pre>
      </div>
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

.error-box {
  color: #991b1b;
}

.error-title {
  font-weight: 600;
  margin: 0 0 8px;
  font-size: 14px;
}

.error-section-label {
  font-size: 12px;
  font-weight: 600;
  margin: 8px 0 4px;
  color: #b91c1c;
}

.error-raw {
  margin: 0 0 4px;
  white-space: pre-wrap;
  font-family: ui-monospace, Consolas, monospace;
  font-size: 12px;
  line-height: 1.45;
  background: #fef2f2;
  padding: 8px;
  border-radius: 6px;
  color: #7f1d1d;
}

.error-text {
  margin: 0;
  white-space: pre-wrap;
  font-family: inherit;
  font-size: 13px;
  line-height: 1.55;
  color: #b91c1c;
}

.analysis-badge {
  font-size: 12px;
  font-weight: 600;
  color: #6d28d9;
  margin-bottom: 10px;
}

.report-body {
  white-space: pre-wrap;
  font-family: inherit;
  font-size: 14px;
  line-height: 1.6;
  margin: 0;
}

.facts-notes {
  margin: 12px 0 0;
  padding-left: 18px;
  font-size: 13px;
  color: #475569;
}

.kb-badge {
  font-size: 12px;
  font-weight: 600;
  color: #0f766e;
  margin: 0 0 10px;
}

.kb-body {
  margin: 0;
}

.kb-sources-details {
  margin-top: 14px;
  border-top: 1px solid #e2e8f0;
}

.kb-sources-summary {
  padding: 10px 0 0;
  font-size: 13px;
  font-weight: 500;
  color: #0f766e;
  cursor: pointer;
  list-style: none;
  user-select: none;
}

.kb-sources-summary::-webkit-details-marker {
  display: none;
}

.kb-sources-summary::before {
  content: '▸ ';
  display: inline-block;
  transition: transform 0.15s ease;
}

.kb-sources-details[open] .kb-sources-summary::before {
  transform: rotate(90deg);
}

.kb-sources-summary:hover {
  color: #0d9488;
}

.kb-sources {
  margin: 8px 0 0;
  padding: 0;
  list-style: none;
}

.kb-sources li {
  margin-bottom: 10px;
  font-size: 12px;
}

.src-title {
  font-weight: 600;
  color: #334155;
  margin-right: 8px;
}

.src-score {
  color: #64748b;
}

.src-snippet {
  margin: 4px 0 0;
  color: #64748b;
  line-height: 1.45;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
