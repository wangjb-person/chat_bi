import { chatApi } from '@/api/chatApi'
import type { QueryResult } from '@/types/api'
import type { SseDonePayload, SseErrorPayload, SseSqlChunk } from '@/types/chat'

export interface StreamAskParams {
  question: string
  tableName: string
  /** 不传则不在界面流式展示 SQL（业务场景推荐） */
  onSqlChunk?: (chunk: string, fullSql: string) => void
}

export interface StreamAskResult {
  sessionId: string
  sql: string
  queryResult?: QueryResult
  runError?: string
  needsFallbackRun: boolean
}

/**
 * 解析 SSE 流式生成 SQL，并在 done 时返回会话 ID 与可选内联查询结果。
 */
export async function streamAskSql(params: StreamAskParams): Promise<StreamAskResult> {
  const { question, tableName, onSqlChunk } = params
  const response = await fetch(chatApi.generateSqlStreamUrl(), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      messages: [{ role: 'user', content: question }],
      table_name: tableName,
    }),
  })

  if (!response.ok) {
    throw new Error(`生成 SQL 失败 HTTP ${response.status}`)
  }

  const reader = response.body?.getReader()
  if (!reader) {
    throw new Error('浏览器不支持流式响应')
  }

  const decoder = new TextDecoder()
  let buffer = ''
  let fullSql = ''
  let result: StreamAskResult | null = null

  try {
    while (true) {
      const { done, value } = await reader.read()
      buffer += decoder.decode(value ?? new Uint8Array(), { stream: !done })
      const lines = buffer.split('\n')
      buffer = lines.pop() ?? ''

      for (const line of lines) {
        const trimmed = line.trim()
        if (!trimmed.startsWith('data: ')) continue

        let payload: SseSqlChunk & Partial<SseDonePayload> & Partial<SseErrorPayload>
        try {
          payload = JSON.parse(trimmed.slice(6))
        } catch {
          continue
        }

        if (payload.error) {
          throw new Error(payload.error)
        }

        if (payload.sql && !payload.done) {
          fullSql += payload.sql
          onSqlChunk?.(payload.sql, fullSql)
        }

        if (payload.done) {
          const done = payload as SseDonePayload
          const sql = (done.sql?.trim() || fullSql.trim())
          result = {
            sessionId: done.id,
            sql,
            queryResult: done.query_result,
            runError: done.run_error,
            needsFallbackRun: Boolean(sql && !done.query_result && !done.run_error),
          }
          break
        }
      }

      if (result) break
      if (done) break
    }
  } finally {
    try {
      await reader.cancel()
    } catch {
      /* ignore */
    }
  }

  if (!result) {
    throw new Error('流式响应未返回完成标记')
  }

  return result
}
