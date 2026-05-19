import type { QueryResult } from './api'

export type ChatRole = 'user' | 'assistant'

export type MessageKind =
  | 'text'
  | 'loading'
  | 'executing'
  | 'query-result'
  | 'plot'
  | 'followup'
  | 'error'

export interface ChatMessage {
  id: string
  role: ChatRole
  kind: MessageKind
  text?: string
  sql?: string
  queryResult?: QueryResult
  figureJson?: string
  followupQuestions?: string[]
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
}

export interface SseErrorPayload {
  error: string
}
