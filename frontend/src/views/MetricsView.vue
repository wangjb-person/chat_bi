<script setup lang="ts">
import { onMounted, ref } from 'vue'
import AppNavBar from '@/components/layout/AppNavBar.vue'
import { metricsApi, type MetricDto, type MetricUpsertPayload } from '@/api/metricsApi'
import { ElMessage } from 'element-plus'

const loading = ref(false)
const metrics = ref<MetricDto[]>([])
const dialogVisible = ref(false)
const editingCode = ref<string | null>(null)
const resolveQuestion = ref('')
const resolveResult = ref('')

const form = ref<MetricUpsertPayload>({
  code: '',
  name: '',
  base_table: '',
  expression: '',
  dataset_id: '',
  format: 'number',
  description: '',
  synonyms: [],
  dimensions: [],
  status: 'published',
})

async function load() {
  loading.value = true
  try {
    const res = await metricsApi.list()
    metrics.value = res.metrics ?? []
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : String(e))
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editingCode.value = null
  form.value = {
    code: '',
    name: '',
    base_table: '',
    expression: '',
    dataset_id: '',
    format: 'number',
    description: '',
    synonyms: [],
    dimensions: [],
    status: 'published',
  }
  dialogVisible.value = true
}

function openEdit(row: MetricDto) {
  editingCode.value = row.code
  form.value = {
    code: row.code,
    name: row.name,
    base_table: row.base_table,
    expression: row.expression,
    dataset_id: row.dataset_id,
    format: row.format,
    description: row.description,
    synonyms: [...row.synonyms],
    dimensions: [...row.dimensions],
    status: row.status,
  }
  dialogVisible.value = true
}

async function save() {
  try {
    const synonyms = String((form.value as { synonymsText?: string }).synonymsText ?? '')
      .split(/[,，]/)
      .map((s) => s.trim())
      .filter(Boolean)
    const dimensions = String((form.value as { dimensionsText?: string }).dimensionsText ?? '')
      .split(/[,，]/)
      .map((s) => s.trim())
      .filter(Boolean)
    await metricsApi.upsert({
      ...form.value,
      synonyms: synonyms.length ? synonyms : form.value.synonyms,
      dimensions: dimensions.length ? dimensions : form.value.dimensions,
    })
    ElMessage.success('已保存')
    dialogVisible.value = false
    await load()
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : String(e))
  }
}

async function remove(row: MetricDto) {
  try {
    await metricsApi.remove(row.code)
    ElMessage.success('已删除')
    await load()
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : String(e))
  }
}

async function testResolve() {
  if (!resolveQuestion.value.trim()) return
  try {
    const res = await metricsApi.resolve(resolveQuestion.value.trim())
    resolveResult.value = JSON.stringify(res, null, 2)
  } catch (e) {
    resolveResult.value = e instanceof Error ? e.message : String(e)
  }
}

onMounted(() => {
  void load()
})
</script>

<template>
  <div class="metrics-page">
    <AppNavBar />
    <main class="metrics-main">
      <header class="page-header">
        <h1>指标管理</h1>
        <p class="subtitle">结构化口径配置，查数优先命中指标 SQL，分析任务引用同一套定义。</p>
        <el-button type="primary" @click="openCreate">新建指标</el-button>
      </header>

      <el-table v-loading="loading" :data="metrics" stripe class="metric-table">
        <el-table-column prop="code" label="编码" width="140" />
        <el-table-column prop="name" label="名称" width="120" />
        <el-table-column prop="base_table" label="表" width="160" />
        <el-table-column prop="expression" label="公式" min-width="200" show-overflow-tooltip />
        <el-table-column prop="status" label="状态" width="90" />
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
            <el-button link type="danger" @click="remove(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <section class="resolve-box">
        <h2>解析试跑</h2>
        <div class="resolve-row">
          <el-input
            v-model="resolveQuestion"
            placeholder="例如：A产品本月毛利率是多少"
            clearable
          />
          <el-button @click="testResolve">解析</el-button>
        </div>
        <pre v-if="resolveResult" class="resolve-pre">{{ resolveResult }}</pre>
      </section>
    </main>

    <el-dialog v-model="dialogVisible" title="指标配置" width="560px">
      <el-form label-width="100px">
        <el-form-item label="编码" required>
          <el-input v-model="form.code" :disabled="!!editingCode" />
        </el-form-item>
        <el-form-item label="名称" required>
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="数据表" required>
          <el-input v-model="form.base_table" />
        </el-form-item>
        <el-form-item label="表达式" required>
          <el-input v-model="form.expression" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="同义词">
          <el-input
            v-model="(form as MetricUpsertPayload & { synonymsText?: string }).synonymsText"
            placeholder="逗号分隔，如 毛利,毛利率"
          />
        </el-form-item>
        <el-form-item label="维度">
          <el-input
            v-model="(form as MetricUpsertPayload & { dimensionsText?: string }).dimensionsText"
            placeholder="逗号分隔，如 region,product_name"
          />
        </el-form-item>
        <el-form-item label="说明">
          <el-input v-model="form.description" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="save">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.metrics-page {
  min-height: 100%;
  display: flex;
  flex-direction: column;
  background: #f8fafc;
}

.metrics-main {
  flex: 1;
  max-width: 1100px;
  margin: 0 auto;
  padding: 24px;
  width: 100%;
}

.page-header {
  margin-bottom: 20px;
}

.page-header h1 {
  font-size: 22px;
  color: #1e293b;
  margin: 0 0 8px;
}

.subtitle {
  color: #64748b;
  font-size: 14px;
  margin: 0 0 16px;
}

.metric-table {
  background: #fff;
  border-radius: 12px;
}

.resolve-box {
  margin-top: 32px;
  padding: 20px;
  background: #fff;
  border-radius: 12px;
  border: 1px solid #e2e8f0;
}

.resolve-box h2 {
  font-size: 16px;
  margin: 0 0 12px;
}

.resolve-row {
  display: flex;
  gap: 12px;
}

.resolve-pre {
  margin-top: 12px;
  padding: 12px;
  background: #f1f5f9;
  border-radius: 8px;
  font-size: 12px;
  overflow: auto;
}
</style>
