<script setup lang="ts">
import { nextTick, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useChatStore } from '@/stores/chatStore'
import ChatMessageItem from './ChatMessageItem.vue'

const chat = useChatStore()
const { messages } = storeToRefs(chat)
const listRef = ref<HTMLElement | null>(null)

async function scrollToBottom() {
  await nextTick()
  if (listRef.value) {
    listRef.value.scrollTop = listRef.value.scrollHeight
  }
}

watch(messages, () => void scrollToBottom(), { deep: true })

function onFollowup(q: string) {
  void chat.sendQuestion(q)
}
</script>

<template>
  <div ref="listRef" class="messages">
    <ChatMessageItem
      v-for="msg in messages"
      :key="msg.id"
      :message="msg"
      @followup-click="onFollowup"
    />
  </div>
</template>

<style scoped>
.messages {
  flex: 1;
  overflow-y: auto;
  padding: 20px 24px;
}
</style>
