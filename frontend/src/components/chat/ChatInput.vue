<script setup lang="ts">
import { ref } from 'vue'
import { storeToRefs } from 'pinia'
import { useChatStore } from '@/stores/chatStore'

const chat = useChatStore()
const { sending } = storeToRefs(chat)
const question = ref('')

async function submit() {
  const q = question.value
  question.value = ''
  await chat.sendQuestion(q)
}
</script>

<template>
  <div class="input-area">
    <el-input
      v-model="question"
      placeholder="输入你的问题…"
      :disabled="sending"
      clearable
      @keyup.enter="submit"
    />
    <el-button type="primary" :loading="sending" @click="submit">发送</el-button>
  </div>
</template>

<style scoped>
.input-area {
  display: flex;
  gap: 12px;
  padding: 16px 24px;
  background: #fff;
  border-top: 1px solid var(--color-border);
}

.input-area :deep(.el-input) {
  flex: 1;
}
</style>
