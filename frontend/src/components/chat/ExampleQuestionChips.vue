<script setup lang="ts">
import { computed } from 'vue'
import { Refresh } from '@element-plus/icons-vue'
import { storeToRefs } from 'pinia'
import { useExampleQuestions } from '@/composables/useExampleQuestions'
import { KB_EXAMPLE_QUESTIONS } from '@/constants/kbExampleQuestions'
import { useAppStore } from '@/stores/appStore'

const emit = defineEmits<{
  select: [question: string]
}>()

const app = useAppStore()
const { askMode } = storeToRefs(app)
const chatbiExamples = useExampleQuestions()

const questions = computed(() =>
  askMode.value === 'kb'
    ? [...KB_EXAMPLE_QUESTIONS]
    : chatbiExamples.questions.value,
)
const loading = computed(() =>
  askMode.value === 'kb' ? false : chatbiExamples.loading.value,
)

function reload() {
  if (askMode.value === 'chatbi') {
    void chatbiExamples.reload()
  }
}
</script>

<template>
  <div class="example-row">
    <button
      v-for="(q, i) in questions"
      :key="`${i}-${q.slice(0, 12)}`"
      type="button"
      class="example-chip"
      :disabled="loading"
      @click="emit('select', q)"
    >
      {{ q }}
    </button>
    <button
      v-if="askMode === 'chatbi'"
      type="button"
      class="icon-btn"
      title="换一批示例问题"
      :disabled="loading"
      @click="reload"
    >
      <el-icon :class="{ spin: loading }"><Refresh /></el-icon>
    </button>
  </div>
</template>

<style scoped>
.example-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  margin-top: 16px;
  max-width: 880px;
  width: 100%;
}

.example-chip {
  padding: 8px 14px;
  border: 1px solid #e8ecf4;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.85);
  color: #334155;
  font-size: 13px;
  line-height: 1.4;
  cursor: pointer;
  transition: border-color 0.15s, box-shadow 0.15s;
  text-align: left;
}

.example-chip:hover:not(:disabled) {
  border-color: #c4b5fd;
  box-shadow: 0 2px 8px rgba(109, 40, 217, 0.08);
  color: #5b21b6;
}

.example-chip:disabled {
  opacity: 0.6;
  cursor: wait;
}

.icon-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border: 1px solid #e8ecf4;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.9);
  color: #64748b;
  cursor: pointer;
}

.icon-btn:hover:not(:disabled) {
  color: #6d28d9;
  border-color: #ddd6fe;
}

.spin {
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
