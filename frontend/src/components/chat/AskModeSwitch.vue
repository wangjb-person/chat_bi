<script setup lang="ts">
import { storeToRefs } from 'pinia'
import { useAppStore, type AskMode } from '@/stores/appStore'

const app = useAppStore()
const { askMode } = storeToRefs(app)

function select(mode: AskMode) {
  if (askMode.value !== mode) {
    app.setAskMode(mode)
  }
}
</script>

<template>
  <div class="mode-switch" role="tablist" aria-label="问答模式">
    <button
      type="button"
      role="tab"
      class="mode-btn"
      :class="{ active: askMode === 'chatbi' }"
      :aria-selected="askMode === 'chatbi'"
      @click="select('chatbi')"
    >
      ChatBI
    </button>
    <button
      type="button"
      role="tab"
      class="mode-btn"
      :class="{ active: askMode === 'kb' }"
      :aria-selected="askMode === 'kb'"
      @click="select('kb')"
    >
      知识库问答
    </button>
  </div>
</template>

<style scoped>
.mode-switch {
  display: inline-flex;
  padding: 4px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.85);
  border: 1px solid #e8ecf4;
  box-shadow: 0 4px 16px rgba(109, 40, 217, 0.06);
}

.mode-btn {
  border: none;
  background: transparent;
  padding: 8px 20px;
  font-size: 14px;
  font-weight: 500;
  color: #64748b;
  border-radius: 8px;
  cursor: pointer;
  transition:
    background 0.15s,
    color 0.15s;
}

.mode-btn:hover:not(.active) {
  color: #5b21b6;
  background: rgba(109, 40, 217, 0.06);
}

.mode-btn.active {
  color: #fff;
  background: linear-gradient(135deg, #8b5cf6 0%, #6d28d9 100%);
  box-shadow: 0 2px 8px rgba(109, 40, 217, 0.25);
}
</style>
