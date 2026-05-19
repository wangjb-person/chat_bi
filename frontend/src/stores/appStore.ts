import { defineStore } from 'pinia'
import { ref } from 'vue'

/** 全局 UI 上下文：表名筛选等跨模块共享状态 */
export const useAppStore = defineStore('app', () => {
  const tableName = ref('')

  return { tableName }
})
