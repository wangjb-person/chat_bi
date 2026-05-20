/**
 * 业务方向展示选项（仅 UI，不参与问数 / 检索逻辑）。
 * 后续可按方向切换语料与数据表时再接入 tableName 等。
 */
export const BUSINESS_SECTOR_OPTIONS: { label: string; value: string }[] = [
  { label: '教育', value: 'education' },
  { label: '销售', value: 'sales' },
  { label: '采购', value: 'procurement' },
]

export const DEFAULT_BUSINESS_SECTOR = 'education'
