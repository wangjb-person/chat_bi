import type { TrainingDataType } from '@/types/training'

const LABELS: Record<TrainingDataType, string> = {
  sql: 'SQL',
  ddl: 'DDL',
  doc: '文档',
  gen: '通用',
}

export function trainingTypeLabel(type: TrainingDataType): string {
  return LABELS[type] ?? type
}

export function trainingPreview(item: {
  question?: string
  content?: string
}): string {
  const text = item.question || item.content || ''
  return text.length > 50 ? `${text.slice(0, 50)}…` : text
}
