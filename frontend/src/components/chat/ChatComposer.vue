<script setup lang="ts">
import { Promotion } from '@element-plus/icons-vue'
import { ref } from 'vue'
import { storeToRefs } from 'pinia'
import { useChatStore } from '@/stores/chatStore'
import TableSelectButton from './TableSelectButton.vue'

const emit = defineEmits<{
  submit: [question: string]
}>()

const chat = useChatStore()
const { sending } = storeToRefs(chat)
const question = ref('')

function submit() {
  const q = question.value.trim()
  if (!q || sending.value) return
  question.value = ''
  emit('submit', q)
}

function fill(text: string) {
  question.value = text
}

defineExpose({ fill })
</script>

<template>
  <div class="composer-card">
    <el-input
      v-model="question"
      type="textarea"
      :autosize="{ minRows: 3, maxRows: 6 }"
      placeholder="请输入您想问的问题"
      :disabled="sending"
      resize="none"
      class="composer-input"
      @keydown.enter.exact.prevent="submit"
    />
    <div class="composer-toolbar">
      <div class="toolbar-left">
        <TableSelectButton />
      </div>
      <button
        type="button"
        class="send-btn"
        :disabled="sending || !question.trim()"
        title="发送"
        @click="submit"
      >
        <el-icon :size="18"><Promotion /></el-icon>
      </button>
    </div>
  </div>
</template>

<style scoped>
.composer-card {
  width: 100%;
  max-width: 880px;
  background: #fff;
  border-radius: 16px;
  border: 1px solid #e8ecf4;
  box-shadow: 0 12px 40px rgba(15, 23, 42, 0.06);
  padding: 16px 16px 12px;
}

.composer-input :deep(.el-textarea__inner) {
  border: none;
  box-shadow: none;
  padding: 0 4px;
  font-size: 15px;
  line-height: 1.6;
  color: #1e293b;
}

.composer-input :deep(.el-textarea__inner:focus) {
  box-shadow: none;
}

.composer-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 12px;
  padding-top: 8px;
  border-top: 1px solid #f1f5f9;
}

.toolbar-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.send-btn {
  width: 40px;
  height: 40px;
  border: none;
  border-radius: 50%;
  background: linear-gradient(135deg, #8b5cf6 0%, #6d28d9 100%);
  color: #fff;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  transition: opacity 0.15s, transform 0.15s;
}

.send-btn:hover:not(:disabled) {
  transform: scale(1.04);
}

.send-btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}
</style>
