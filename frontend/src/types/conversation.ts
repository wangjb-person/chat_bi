import type { AskMode } from '@/stores/appStore'

export interface ConversationSummary {
  id: string
  user_id: string
  title: string
  mode: AskMode
  table_name: string
  created_at?: string
  updated_at?: string
}

export interface StoredMessage {
  id: string
  conversation_id: string
  turn_id: string
  seq: number
  role: 'user' | 'assistant'
  kind: string
  content: Record<string, unknown>
  created_at?: string
}

export interface AppendMessagePayload {
  id: string
  turn_id: string
  seq: number
  role: 'user' | 'assistant'
  kind: string
  content: Record<string, unknown>
}
