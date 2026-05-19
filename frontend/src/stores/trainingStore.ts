import { defineStore } from 'pinia'
import { ref } from 'vue'
import { trainingApi } from '@/api/trainingApi'
import type {
  TrainPayload,
  TrainingDataType,
  TrainingListItem,
  TrainingSearchItem,
  UpdateTrainingPayload,
} from '@/types/training'
import { useAppStore } from './appStore'

export const useTrainingStore = defineStore('training', () => {
  const items = ref<(TrainingListItem | TrainingSearchItem)[]>([])
  const loading = ref(false)
  const keyword = ref('')

  async function loadList() {
    loading.value = true
    try {
      const res = await trainingApi.list(1, 50)
      items.value = res.data ?? []
    } catch (e) {
      console.error('[training] 加载失败', e)
      items.value = []
    } finally {
      loading.value = false
    }
  }

  async function search() {
    loading.value = true
    try {
      const res = await trainingApi.search({
        keyword: keyword.value || undefined,
      })
      items.value = res.data ?? []
    } catch (e) {
      console.error('[training] 搜索失败', e)
    } finally {
      loading.value = false
    }
  }

  async function add(payload: TrainPayload) {
    const app = useAppStore()
    const body = { ...payload, table_name: payload.table_name ?? app.tableName }
    await trainingApi.add(body)
    await loadList()
  }

  async function remove(id: string) {
    await trainingApi.remove(id)
    await loadList()
  }

  async function update(payload: UpdateTrainingPayload) {
    const app = useAppStore()
    await trainingApi.update({
      ...payload,
      table_name: payload.table_name ?? app.tableName,
    })
    await loadList()
  }

  function itemType(item: TrainingListItem | TrainingSearchItem): TrainingDataType {
    return ('data_type' in item ? item.data_type : item.type) as TrainingDataType
  }

  return {
    items,
    loading,
    keyword,
    loadList,
    search,
    add,
    remove,
    update,
    itemType,
  }
})
