<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { storeToRefs } from 'pinia'
import { useAppStore } from '@/stores/appStore'
import { useTrainingStore } from '@/stores/trainingStore'
import type { TrainingDataType, TrainingListItem } from '@/types/training'

const visible = defineModel<boolean>('visible', { default: false })
const props = defineProps<{
  mode: 'add' | 'edit'
  item?: TrainingListItem | null
}>()

const training = useTrainingStore()
const app = useAppStore()
const { tableName } = storeToRefs(app)

const trainType = ref<TrainingDataType>('sql')
const form = reactive({
  question: '',
  sql: '',
  ddl: '',
  doc: '',
  gen: '',
  genType: '',
})

const title = computed(() => (props.mode === 'add' ? '添加训练数据' : '编辑训练数据'))

watch(visible, (v) => {
  if (!v) return
  if (props.mode === 'edit' && props.item) {
    trainType.value = props.item.type
    form.question = props.item.question ?? ''
    form.sql = props.item.type === 'sql' ? props.item.content ?? '' : ''
    form.ddl = props.item.type === 'ddl' ? props.item.content ?? '' : ''
    form.doc = props.item.type === 'doc' ? props.item.content ?? '' : ''
    form.gen = props.item.type === 'gen' ? props.item.content ?? '' : ''
    form.genType = props.item.table_name ?? ''
  } else {
    trainType.value = 'sql'
    form.question = ''
    form.sql = ''
    form.ddl = ''
    form.doc = ''
    form.gen = ''
    form.genType = ''
  }
})

async function submit() {
  try {
    if (props.mode === 'add') {
      if (trainType.value === 'sql') {
        await training.add({
          question: form.question,
          sql: form.sql,
          table_name: tableName.value,
        })
      } else if (trainType.value === 'ddl') {
        await training.add({ ddl: form.ddl, table_name: tableName.value })
      } else if (trainType.value === 'doc') {
        await training.add({ documentation: form.doc, table_name: tableName.value })
      } else {
        await training.add({ general: form.gen, gen_type: form.genType })
      }
      ElMessage.success('添加成功')
    } else if (props.item) {
      const id = props.item.id
      if (trainType.value === 'sql') {
        await training.update({
          id,
          new_question: form.question,
          new_content: form.sql,
          table_name: tableName.value,
        })
      } else if (trainType.value === 'gen') {
        await training.update({
          id,
          new_content: form.gen,
          new_gen_type: form.genType,
        })
      } else {
        const content =
          trainType.value === 'ddl' ? form.ddl : form.doc
        await training.update({
          id,
          new_content: content,
          table_name: tableName.value,
        })
      }
      ElMessage.success('更新成功')
    }
    visible.value = false
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '操作失败')
  }
}
</script>

<template>
  <el-dialog v-model="visible" :title="title" width="520px" destroy-on-close>
    <el-form label-position="top">
      <el-form-item label="语料类型">
        <el-select v-model="trainType" :disabled="mode === 'edit'" style="width: 100%">
          <el-option label="SQL 问答对" value="sql" />
          <el-option label="DDL 语句" value="ddl" />
          <el-option label="文档说明" value="doc" />
          <el-option label="通用知识" value="gen" />
        </el-select>
      </el-form-item>

      <template v-if="trainType === 'sql'">
        <el-form-item label="问题">
          <el-input v-model="form.question" />
        </el-form-item>
        <el-form-item label="SQL">
          <el-input v-model="form.sql" type="textarea" :rows="4" />
        </el-form-item>
      </template>

      <template v-else-if="trainType === 'ddl'">
        <el-form-item label="DDL">
          <el-input v-model="form.ddl" type="textarea" :rows="4" />
        </el-form-item>
      </template>

      <template v-else-if="trainType === 'doc'">
        <el-form-item label="文档">
          <el-input v-model="form.doc" type="textarea" :rows="4" />
        </el-form-item>
      </template>

      <template v-else>
        <el-form-item label="通用知识">
          <el-input v-model="form.gen" type="textarea" :rows="4" />
        </el-form-item>
        <el-form-item label="类型标签 (gen_type)">
          <el-input v-model="form.genType" />
        </el-form-item>
      </template>
    </el-form>

    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" @click="submit">确定</el-button>
    </template>
  </el-dialog>
</template>
