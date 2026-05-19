import { onMounted, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { trainingApi } from '@/api/trainingApi'
import { DEFAULT_EXAMPLE_QUESTIONS } from '@/constants/exampleQuestions'
import { useAppStore } from '@/stores/appStore'

export function useExampleQuestions() {
  const app = useAppStore()
  const { tableName } = storeToRefs(app)
  const questions = ref<string[]>([...DEFAULT_EXAMPLE_QUESTIONS])
  const loading = ref(false)

  async function load() {
    loading.value = true
    try {
      const res = await trainingApi.exampleQuestions(tableName.value)
      if (res.questions?.length) {
        questions.value = res.questions.slice(0, 6)
      } else {
        questions.value = [...DEFAULT_EXAMPLE_QUESTIONS]
      }
    } catch {
      questions.value = [...DEFAULT_EXAMPLE_QUESTIONS]
    } finally {
      loading.value = false
    }
  }

  onMounted(() => void load())
  watch(tableName, () => void load())

  return { questions, loading, reload: load }
}
