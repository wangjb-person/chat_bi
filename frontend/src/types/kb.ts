export interface KbDocument {
  id: string
  title: string
  filename: string
  chunk_count: number
  created_at: string
  file_kind?: string
  chunk_profile?: string
}

export const KB_FILE_KIND_LABEL: Record<string, string> = {
  txt: '文本',
  markdown: 'Markdown',
  csv: 'CSV',
  pdf: 'PDF',
  excel: 'Excel',
  word: 'Word',
}

export const KB_CHUNK_PROFILE_LABEL: Record<string, string> = {
  general: '通用段落',
  markdown: '标题分段',
  faq: '问答对',
  csv: '表格行组',
  excel: '工作表行组',
}

export interface KbSourceChunk {
  text?: string
  doc_title?: string
  doc_id?: string
  chunk_index?: number
  score?: number
}
