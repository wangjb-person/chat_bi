import type { QueryResult } from './api'
import type { KbSourceChunk } from './kb'

export type ChatRole = 'user' | 'assistant'

export type MessageKind =
  | 'text'
  | 'loading'
  | 'workflow'
  | 'executing'
  | 'query-result'
  | 'analysis-report'
  | 'plot'
  | 'followup'
  | 'error'
  | 'kb-answer'

export interface ChatMessage {
  id: string
  role: ChatRole
  kind: MessageKind
  text?: string
  sql?: string
  queryResult?: QueryResult
  figureJson?: string
  followupQuestions?: string[]
  reportMd?: string
  workflowStatus?: string
  facts?: AnalysisFacts
  errorRaw?: string
  errorHint?: string
  kbSources?: KbSourceChunk[]
}

export interface AnalysisFacts {
  summary?: string
  top_dimensions?: { dimension?: string; value?: number | null }[]
  comparisons?: Record<string, unknown>[]
  raw_notes?: string[]
}

export interface AskStreamResult {
  sessionId: string
  intent: 'query' | 'analysis' | 'chat' | 'knowledge' | 'clarify' | 'doc_qa'
  sql?: string
  queryResult?: QueryResult
  runError?: string
  needsFallbackRun?: boolean
  sqlSource?: string
  reportMd?: string
  facts?: AnalysisFacts
  subResults?: Record<string, unknown>[]
  workflowStatus?: string
  answerText?: string
  errorRaw?: string
  errorHint?: string
  kbSources?: KbSourceChunk[]
}

export interface SseAskEvent {
  phase?: string
  intent?: string
  reason?: string
  sql?: string
  done?: boolean
  id?: string
  error?: string
  query_result?: QueryResult
  run_error?: string
  run_error_raw?: string
  run_error_hint?: string
  report_mode?: boolean
  sql_source?: string
  report_md?: string
  facts?: AnalysisFacts
  sub_results?: Record<string, unknown>[]
  chunk?: string
  answer_text?: string
  task_id?: string
  plan?: Record<string, unknown>
  kb_sources?: KbSourceChunk[]
}

export interface SseSqlChunk {
  sql?: string
}

export interface SseDonePayload {
  done: true
  id: string
  sql: string
  query_result?: QueryResult
  run_error?: string
  run_error_raw?: string
  run_error_hint?: string
  report_mode?: boolean
}

export interface SseErrorPayload {
  error: string
}
