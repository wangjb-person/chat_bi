<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { storeToRefs } from 'pinia'
import { useAppStore } from '@/stores/appStore'
import { useChatStore } from '@/stores/chatStore'
import { useTrainingStore } from '@/stores/trainingStore'
import { trainingPreview, trainingTypeLabel } from '@/utils/trainingLabel'
import type { TrainingListItem } from '@/types/training'
import TrainingFormModal from './TrainingFormModal.vue'

const app = useAppStore()
const training = useTrainingStore()
const chat = useChatStore()
const { items, loading, keyword } = storeToRefs(training)

const modalVisible = ref(false)
const modalMode = ref<'add' | 'edit'>('add')
const editingItem = ref<TrainingListItem | null>(null)

onMounted(() => {
  void training.loadList()
})

function openAdd() {
  modalMode.value = 'add'
  editingItem.value = null
  modalVisible.value = true
}

function openEdit(item: TrainingListItem | (typeof items.value)[number]) {
  modalMode.value = 'edit'
  const type = training.itemType(item)
  const content =
    'content' in item && item.content
      ? item.content
      : 'content' in item
        ? String((item as { content?: string }).content ?? '')
        : ''
  editingItem.value = {
    id: item.id,
    type,
    question: 'question' in item ? item.question : undefined,
    content,
    table_name: item.table_name,
  }
  modalVisible.value = true
}

async function onRemove(id: string) {
  try {
    await ElMessageBox.confirm('确定删除该语料？', '确认', { type: 'warning' })
    await training.remove(id)
    ElMessage.success('已删除')
  } catch {
    /* cancelled */
  }
}

function askFromItem(item: { question?: string; content?: string }) {
  const q = item.question || item.content || ''
  if (q) void chat.sendQuestion(q)
}
</script>

<template>
  <aside class="sidebar">
    <header class="sidebar-header">
      <h1>🤖 ChatBI 助手</h1>
      <p>智能问数平台</p>
    </header>

    <section class="sidebar-section">
      <h3>📊 选择数据表</h3>
      <el-input v-model="app.tableName" placeholder="输入表名（可选）" />
    </section>

    <section class="sidebar-section flex-grow">
      <h3>📚 语料训练</h3>
      <el-button type="primary" plain class="w-full" @click="openAdd">+ 添加语料</el-button>

      <div class="search-row">
        <el-input
          v-model="keyword"
          placeholder="关键词搜索"
          clearable
          @keyup.enter="training.search()"
        />
        <el-button @click="training.search()">搜索</el-button>
      </div>
      <el-button text type="primary" size="small" @click="training.loadList()">刷新列表</el-button>

      <el-scrollbar v-loading="loading" class="training-list">
        <el-empty v-if="!items.length" description="暂无语料" :image-size="64" />
        <div v-for="item in items" :key="item.id" class="training-card">
          <div class="card-head">
            <el-tag size="small" type="info">{{ trainingTypeLabel(training.itemType(item)) }}</el-tag>
            <span class="item-id">{{ item.id }}</span>
          </div>
          <p class="preview" @click="askFromItem(item)">{{ trainingPreview(item) }}</p>
          <div class="card-actions">
            <el-button size="small" text type="primary" @click="askFromItem(item)">提问</el-button>
            <el-button size="small" text @click="openEdit(item as TrainingListItem)">编辑</el-button>
            <el-button size="small" text type="danger" @click="onRemove(item.id)">删除</el-button>
          </div>
        </div>
      </el-scrollbar>
    </section>

    <TrainingFormModal
      v-model:visible="modalVisible"
      :mode="modalMode"
      :item="editingItem"
    />
  </aside>
</template>

<style scoped>
.sidebar {
  width: var(--sidebar-width);
  background: #fff;
  border-right: 1px solid var(--color-border);
  display: flex;
  flex-direction: column;
  box-shadow: 2px 0 12px rgba(0, 0, 0, 0.05);
}

.sidebar-header {
  padding: 20px;
  background: var(--color-accent);
  text-align: center;
}

.sidebar-header h1 {
  font-size: 20px;
  margin-bottom: 4px;
}

.sidebar-header p {
  font-size: 12px;
  opacity: 0.85;
}

.sidebar-section {
  padding: 16px 20px;
  border-bottom: 1px solid #eef2f6;
}

.sidebar-section h3 {
  font-size: 14px;
  margin-bottom: 12px;
  font-weight: 600;
}

.flex-grow {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.w-full {
  width: 100%;
}

.search-row {
  display: flex;
  gap: 8px;
  margin-top: 12px;
}

.training-list {
  flex: 1;
  margin-top: 12px;
}

.training-card {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: 10px;
  margin-bottom: 8px;
  background: #f8fafc;
}

.card-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.item-id {
  font-size: 10px;
  color: var(--color-text-muted);
  overflow: hidden;
  text-overflow: ellipsis;
}

.preview {
  font-size: 12px;
  cursor: pointer;
  color: #334155;
  line-height: 1.4;
}

.preview:hover {
  color: var(--color-primary);
}

.card-actions {
  display: flex;
  gap: 4px;
  margin-top: 8px;
}
</style>
