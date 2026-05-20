import { defineStore } from 'pinia'
import { ref } from 'vue'
import { DEFAULT_BUSINESS_SECTOR } from '@/constants/dataTables'

/** 全局 UI 上下文：表名筛选等跨模块共享状态 */
export const useAppStore = defineStore('app', () => {
  /** 传给后端的表名筛选，空表示不限制 */
  const tableName = ref('')
  /** 业务方向（仅展示，默认教育；暂不参与 API） */
  const businessSector = ref(DEFAULT_BUSINESS_SECTOR)

  return { tableName, businessSector }
})
