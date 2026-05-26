<script setup lang="ts">
import { onMounted } from 'vue'
import { storeToRefs } from 'pinia'
import { Plus, Delete } from '@element-plus/icons-vue'
import { useChatStore } from '@/stores/chatStore'

const emit = defineEmits<{
  newChat: []
}>()

const chat = useChatStore()
const {
  conversations,
  activeConversationId,
  loadingConversations,
  loadingMessages,
} = storeToRefs(chat)

onMounted(() => {
  void chat.loadConversations()
})

function formatTime(iso?: string): string {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  const now = new Date()
  const sameDay =
    d.getFullYear() === now.getFullYear()
    && d.getMonth() === now.getMonth()
    && d.getDate() === now.getDate()
  if (sameDay) {
    return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  }
  return d.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })
}

function onSelect(id: string) {
  void chat.selectConversation(id)
}

function onNewChat() {
  chat.startNewChat()
  emit('newChat')
}

async function onDelete(id: string, event: Event) {
  event.stopPropagation()
  try {
    await chat.deleteConversation(id)
  } catch (e) {
    console.error('[sidebar] 删除会话失败', e)
  }
}
</script>

<template>
  <aside class="conv-sidebar" :class="{ loading: loadingMessages }">
    <div class="sidebar-head">
      <span class="sidebar-title">历史会话</span>
      <el-button type="primary" size="small" :icon="Plus" @click="onNewChat">
        新对话
      </el-button>
    </div>

    <div class="sidebar-list" v-loading="loadingConversations">
      <button
        type="button"
        class="conv-item"
        :class="{ active: !activeConversationId }"
        @click="onNewChat"
      >
        <span class="conv-title">当前新对话</span>
      </button>

      <button
        v-for="conv in conversations"
        :key="conv.id"
        type="button"
        class="conv-item"
        :class="{ active: activeConversationId === conv.id }"
        @click="onSelect(conv.id)"
      >
        <span class="conv-title" :title="conv.title">{{ conv.title }}</span>
        <span class="conv-meta">
          <span class="conv-time">{{ formatTime(conv.updated_at) }}</span>
          <el-button
            class="conv-delete"
            type="danger"
            link
            :icon="Delete"
            aria-label="删除会话"
            @click="onDelete(conv.id, $event)"
          />
        </span>
      </button>

      <p v-if="!loadingConversations && !conversations.length" class="empty-tip">
        暂无历史会话
      </p>
    </div>
  </aside>
</template>

<style scoped>
.conv-sidebar {
  width: 260px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  border-right: 1px solid rgba(226, 232, 240, 0.9);
  background: rgba(255, 255, 255, 0.55);
  backdrop-filter: blur(6px);
  min-height: 0;
}

.conv-sidebar.loading {
  opacity: 0.92;
}

.sidebar-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 14px 12px 10px;
  border-bottom: 1px solid rgba(226, 232, 240, 0.7);
}

.sidebar-title {
  font-size: 13px;
  font-weight: 600;
  color: #475569;
}

.sidebar-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
  min-height: 0;
}

.conv-item {
  width: 100%;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 4px;
  padding: 10px 10px;
  margin-bottom: 4px;
  border: 1px solid transparent;
  border-radius: 10px;
  background: transparent;
  cursor: pointer;
  text-align: left;
  transition: background 0.15s ease, border-color 0.15s ease;
}

.conv-item:hover {
  background: rgba(109, 40, 217, 0.06);
}

.conv-item.active {
  background: rgba(109, 40, 217, 0.1);
  border-color: rgba(109, 40, 217, 0.25);
}

.conv-title {
  font-size: 13px;
  color: #334155;
  line-height: 1.35;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  word-break: break-word;
  width: 100%;
}

.conv-meta {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.conv-time {
  font-size: 11px;
  color: #94a3b8;
}

.conv-delete {
  opacity: 0;
  padding: 0;
  min-height: auto;
}

.conv-item:hover .conv-delete {
  opacity: 1;
}

.empty-tip {
  margin: 16px 8px;
  font-size: 12px;
  color: #94a3b8;
  text-align: center;
}
</style>
