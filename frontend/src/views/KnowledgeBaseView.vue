<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { storeToRefs } from 'pinia'
import { useKbStore } from '@/stores/kbStore'
import { KB_CHUNK_PROFILE_LABEL, KB_FILE_KIND_LABEL } from '@/types/kb'

const kb = useKbStore()
const { documents, loading } = storeToRefs(kb)

const pasteVisible = ref(false)
const pasteTitle = ref('')
const pasteContent = ref('')
const submitting = ref(false)

onMounted(() => {
  void kb.loadList()
})

function onFileChange(ev: Event) {
  const input = ev.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  submitting.value = true
  void kb
    .uploadFile(file, file.name.replace(/\.[^.]+$/, ''))
    .then(() => {
      ElMessage.success('文档已入库')
      input.value = ''
    })
    .catch((e: unknown) => {
      ElMessage.error(e instanceof Error ? e.message : String(e))
    })
    .finally(() => {
      submitting.value = false
    })
}

async function submitPaste() {
  const content = pasteContent.value.trim()
  if (!content) {
    ElMessage.warning('请输入文档正文')
    return
  }
  submitting.value = true
  try {
    await kb.addText(pasteTitle.value.trim() || '粘贴文档', content)
    ElMessage.success('文档已入库')
    pasteVisible.value = false
    pasteTitle.value = ''
    pasteContent.value = ''
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : String(e))
  } finally {
    submitting.value = false
  }
}

async function onRemove(id: string, title: string) {
  try {
    await ElMessageBox.confirm(`确定删除「${title}」？`, '确认', { type: 'warning' })
    await kb.remove(id)
    ElMessage.success('已删除')
  } catch {
    /* cancelled */
  }
}

function formatTime(iso: string) {
  try {
    return new Date(iso).toLocaleString('zh-CN')
  } catch {
    return iso
  }
}
</script>

<template>
  <div class="kb-page">
    <header class="page-header">
      <div>
        <RouterLink to="/" class="back-link">← 返回问数</RouterLink>
        <h1>知识库管理</h1>
        <p>
          支持 txt、md、csv、pdf、xlsx/xls、docx；后台将自动解析并按类型选择切块策略（通用 / 标题 / 问答 / 表格等）
        </p>
      </div>
      <div class="header-actions">
        <el-button @click="pasteVisible = true">粘贴文本入库</el-button>
        <label class="upload-btn">
          <input
            type="file"
            accept=".txt,.md,.markdown,.csv,.pdf,.xlsx,.xls,.docx"
            :disabled="submitting"
            @change="onFileChange"
          >
          上传文件
        </label>
      </div>
    </header>

    <section class="card list-card" v-loading="loading">
      <el-table :data="documents" empty-text="暂无文档，请上传或粘贴文本">
        <el-table-column prop="title" label="标题" min-width="180" />
        <el-table-column prop="filename" label="文件名" min-width="120" />
        <el-table-column label="类型" width="88">
          <template #default="{ row }">
            {{ KB_FILE_KIND_LABEL[row.file_kind ?? ''] ?? row.file_kind ?? '—' }}
          </template>
        </el-table-column>
        <el-table-column label="切块" width="100">
          <template #default="{ row }">
            {{ KB_CHUNK_PROFILE_LABEL[row.chunk_profile ?? ''] ?? row.chunk_profile ?? '—' }}
          </template>
        </el-table-column>
        <el-table-column prop="chunk_count" label="切片数" width="90" />
        <el-table-column label="入库时间" min-width="160">
          <template #default="{ row }">
            {{ formatTime(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100" fixed="right">
          <template #default="{ row }">
            <el-button
              type="danger"
              link
              @click="onRemove(row.id, row.title)"
            >
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </section>

    <el-dialog v-model="pasteVisible" title="粘贴文本入库" width="560px" destroy-on-close>
      <el-form label-width="72px">
        <el-form-item label="标题">
          <el-input v-model="pasteTitle" placeholder="例如：差旅报销制度" />
        </el-form-item>
        <el-form-item label="正文">
          <el-input
            v-model="pasteContent"
            type="textarea"
            :rows="12"
            placeholder="粘贴制度、FAQ 全文（UTF-8）"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="pasteVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitPaste">
          入库
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.kb-page {
  min-height: 100%;
  padding: 24px 32px 48px;
  background: #f8fafc;
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
  margin: 0 0 8px;
  color: #1e293b;
}

.page-header p {
  margin: 0;
  font-size: 14px;
  color: #64748b;
  max-width: 640px;
}

.header-actions {
  display: flex;
  gap: 10px;
  flex-shrink: 0;
}

.upload-btn {
  display: inline-flex;
  align-items: center;
  padding: 8px 16px;
  font-size: 14px;
  color: #fff;
  background: #7c3aed;
  border-radius: 4px;
  cursor: pointer;
}

.upload-btn input {
  display: none;
}

.upload-btn:has(input:disabled) {
  opacity: 0.6;
  cursor: not-allowed;
}

.card {
  background: #fff;
  border-radius: 12px;
  border: 1px solid #e2e8f0;
  padding: 16px;
}
</style>
