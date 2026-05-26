import { chatApi } from '@/api/chatApi'
import type { AskMode } from '@/stores/appStore'
import type { AskStreamResult, SseAskEvent } from '@/types/chat'
import type { KbSourceChunk } from '@/types/kb'
import type { QueryResult } from '@/types/api'

export interface StreamAskParams {
  question: string
  tableName: string
  mode?: AskMode
  conversationId?: string | null
  messages?: { role: 'user' | 'assistant'; content: string }[]
  onPhase?: (ev: SseAskEvent) => void
}

export async function streamAsk(params: StreamAskParams): Promise<AskStreamResult> {
  const {
    question,
    tableName,
    mode = 'chatbi',
    conversationId,
    messages,
    onPhase,
  } = params
  const llmMessages = messages?.length
    ? messages
    : [{ role: 'user' as const, content: question }]
  const response = await fetch(chatApi.askStreamUrl(), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      messages: llmMessages,
      table_name: tableName,
      mode,
      conversation_id: conversationId || undefined,
    }),
  })

  if (!response.ok) {
    throw new Error(`问数失败 HTTP ${response.status}`)
  }

  const reader = response.body?.getReader()
  if (!reader) {
    throw new Error('浏览器不支持流式响应')
  }

  const decoder = new TextDecoder()
  let buffer = ''
  let result: AskStreamResult = {
    sessionId: '',
    intent: 'chat',
  }
  let reportChunks = ''
  let answerChunks = ''

  try {
    while (true) {
      const { done, value } = await reader.read()
      buffer += decoder.decode(value ?? new Uint8Array(), { stream: !done })
      const lines = buffer.split('\n')
      buffer = lines.pop() ?? ''

      for (const line of lines) {
        const trimmed = line.trim()
        if (!trimmed.startsWith('data: ')) continue

        let payload: SseAskEvent
        try {
          payload = JSON.parse(trimmed.slice(6))
        } catch {
          continue
        }

        if (payload.error) {
          throw new Error(payload.error)
        }

        onPhase?.(payload)

        if (payload.id) {
          result.sessionId = payload.id
        }

        if (
          payload.intent === 'analysis'
          || payload.intent === 'query'
          || payload.intent === 'chat'
          || payload.intent === 'knowledge'
          || payload.intent === 'clarify'
          || payload.intent === 'doc_qa'
        ) {
          result.intent = payload.intent
        }

        if (payload.phase === 'report_chunk' && payload.chunk) {
          reportChunks += payload.chunk
        }

        if (payload.phase === 'answer_chunk' && payload.chunk) {
          answerChunks += payload.chunk
        }

        if (payload.done) {
          result.sessionId = payload.id ?? result.sessionId
          if (payload.intent === 'analysis') {
            result.intent = 'analysis'
          } else if (payload.intent === 'query') {
            result.intent = 'query'
          } else if (payload.intent === 'knowledge') {
            result.intent = 'knowledge'
          } else if (payload.intent === 'chat') {
            result.intent = 'chat'
          } else if (payload.intent === 'clarify') {
            result.intent = 'clarify'
          } else if (payload.intent === 'doc_qa') {
            result.intent = 'doc_qa'
          }
          result.answerText =
            payload.answer_text || answerChunks || undefined
          result.kbSources = payload.kb_sources as KbSourceChunk[] | undefined
          result.sql = payload.sql
          result.sqlSource = payload.sql_source
          result.queryResult = payload.query_result as QueryResult | undefined
          result.runError = payload.run_error
          result.errorRaw = payload.run_error_raw
          result.errorHint = payload.run_error_hint
          result.reportMd = payload.report_md ?? reportChunks
          result.facts = payload.facts
          result.subResults = payload.sub_results
          result.needsFallbackRun = Boolean(
            result.intent === 'query'
            && !result.queryResult
            && !result.runError
            && result.sql?.trim(),
          )
        }
      }

      if (done) break
    }
  } finally {
    reader.releaseLock()
  }

  if (!result.sessionId) {
    throw new Error('未收到会话 ID')
  }

  if (result.intent === 'analysis' && !result.reportMd) {
    result.reportMd = reportChunks || undefined
  }

  return result
}
