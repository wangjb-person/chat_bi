<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { storeToRefs } from 'pinia'
import { useAppStore } from '@/stores/appStore'
import { useTrainingStore } from '@/stores/trainingStore'
import { trainingPreview, trainingTypeLabel } from '@/utils/trainingLabel'
import type { TrainingListItem } from '@/types/training'
import TrainingFormModal from '@/components/training/TrainingFormModal.vue'

const app = useAppStore()
const training = useTrainingStore()
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
</script>

<template>
  <div class="training-page">
    <header class="page-header">
      <div>
        <RouterLink to="/" class="back-link">← 返回问数</RouterLink>
        <h1>语料训练管理</h1>
        <p>维护 SQL 问答、DDL、业务文档与通用规则，供问数检索使用</p>
      </div>
      <el-button type="primary" @click="openAdd">+ 添加语料</el-button>
    </header>

    <section class="toolbar card">
      <el-form inline label-width="80px">
        <el-form-item label="关联表">
          <el-input v-model="app.tableName" placeholder="表名（筛选/新增时默认）" style="width: 220px" />
        </el-form-item>
        <el-form-item label="关键词">
          <el-input
            v-model="keyword"
            placeholder="搜索语料"
            clearable
            style="width: 240px"
            @keyup.enter="training.search()"
          />
        </el-form-item>
        <el-form-item>
          <el-button @click="training.search()">搜索</el-button>
          <el-button @click="training.loadList()">刷新</el-button>
        </el-form-item>
      </el-form>
    </section>

    <section v-loading="loading" class="list card">
      <el-empty v-if="!items.length" description="暂无语料" />
      <div v-for="item in items" :key="item.id" class="training-card">
        <div class="card-head">
          <el-tag size="small" type="info">{{ trainingTypeLabel(training.itemType(item)) }}</el-tag>
          <span class="item-id">{{ item.id }}</span>
        </div>
        <p class="preview">{{ trainingPreview(item) }}</p>
        <div class="card-actions">
          <el-button size="small" text @click="openEdit(item as TrainingListItem)">编辑</el-button>
          <el-button size="small" text type="danger" @click="onRemove(item.id)">删除</el-button>
        </div>
      </div>
    </section>

    <TrainingFormModal
      v-model:visible="modalVisible"
      :mode="modalMode"
      :item="editingItem"
    />
  </div>
</template>

<style scoped>
.training-page {
  min-height: 100%;
  background: #f8fafc;
  padding: 24px;
  max-width: 960px;
  margin: 0 auto;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  margin-bottom: 20px;
}

.back-link {
  font-size: 13px;
  color: #6d28d9;
  text-decoration: none;
  display: inline-block;
  margin-bottom: 8px;
}

.page-header h1 {
  font-size: 22px;
  color: #1e293b;
  margin-bottom: 6px;
}

.page-header p {
  font-size: 13px;
  color: #64748b;
}

.card {
  background: #fff;
  border: 1px solid var(--color-border);
  border-radius: 12px;
  padding: 16px;
  margin-bottom: 16px;
}

.training-card {
  border: 1px solid #eef2f6;
  border-radius: 8px;
  padding: 12px;
  margin-bottom: 10px;
  background: #f8fafc;
}

.card-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.item-id {
  font-size: 10px;
  color: var(--color-text-muted);
}

.preview {
  font-size: 13px;
  line-height: 1.5;
  color: #334155;
}

.card-actions {
  margin-top: 8px;
}
</style>
