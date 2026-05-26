import type { ChatMessage } from '@/types/chat'
import type { AppendMessagePayload, StoredMessage } from '@/types/conversation'

/** 与后端 conversation_context 对齐 */
export const MAX_LLM_MESSAGE_CHARS = 2000
export const MAX_LLM_CONTEXT_MESSAGES = 20

const SKIP_LLM_KINDS = new Set(['loading', 'workflow', 'executing'])

export function chatMessageToContent(msg: ChatMessage): Record<string, unknown> {
  const content: Record<string, unknown> = {}
  if (msg.text !== undefined) content.text = msg.text
  if (msg.sql !== undefined) content.sql = msg.sql
  if (msg.queryResult !== undefined) content.queryResult = msg.queryResult
  if (msg.figureJson !== undefined) content.figureJson = msg.figureJson
  if (msg.followupQuestions !== undefined) content.followupQuestions = msg.followupQuestions
  if (msg.reportMd !== undefined) content.reportMd = msg.reportMd
  if (msg.facts !== undefined) content.facts = msg.facts
  if (msg.workflowStatus !== undefined) content.workflowStatus = msg.workflowStatus
  if (msg.errorRaw !== undefined) content.errorRaw = msg.errorRaw
  if (msg.errorHint !== undefined) content.errorHint = msg.errorHint
  if (msg.kbSources !== undefined) content.kbSources = msg.kbSources
  return content
}

export function chatMessageToStored(msg: ChatMessage, turnId: string, seq: number): AppendMessagePayload {
  return {
    id: msg.id,
    turn_id: turnId,
    seq,
    role: msg.role,
    kind: msg.kind,
    content: chatMessageToContent(msg),
  }
}

export function storedToChatMessage(row: StoredMessage): ChatMessage {
  const c = row.content || {}
  return {
    id: row.id,
    role: row.role,
    kind: row.kind as ChatMessage['kind'],
    text: c.text as string | undefined,
    sql: c.sql as string | undefined,
    queryResult: c.queryResult as ChatMessage['queryResult'],
    figureJson: c.figureJson as string | undefined,
    followupQuestions: c.followupQuestions as string[] | undefined,
    reportMd: c.reportMd as string | undefined,
    facts: c.facts as ChatMessage['facts'],
    workflowStatus: c.workflowStatus as string | undefined,
    errorRaw: c.errorRaw as string | undefined,
    errorHint: c.errorHint as string | undefined,
    kbSources: c.kbSources as ChatMessage['kbSources'],
  }
}

function truncateForLlm(text: string, maxLen = MAX_LLM_MESSAGE_CHARS): string {
  const t = text.trim()
  if (t.length <= maxLen) return t
  return `${t.slice(0, maxLen - 1)}…`
}

function messageToLlmText(msg: ChatMessage): string {
  if (msg.kind === 'text' || msg.kind === 'kb-answer' || msg.kind === 'error') {
    return msg.text?.trim() || ''
  }
  if (msg.kind === 'analysis-report') {
    const report = msg.reportMd?.trim() || msg.text?.trim() || ''
    return truncateForLlm(report)
  }
  if (msg.kind === 'query-result') {
    const rows = msg.queryResult?.data ?? []
    const preview = rows.slice(0, 5)
    const parts = [`查询结果（共 ${msg.queryResult?.row_count ?? rows.length} 行）`]
    if (msg.sql) parts.push(`SQL: ${msg.sql}`)
    if (preview.length) parts.push(`数据预览: ${JSON.stringify(preview)}`)
    return parts.join('\n')
  }
  return msg.text?.trim() || ''
}

export function toLlmMessages(messages: ChatMessage[]): { role: 'user' | 'assistant'; content: string }[] {
  const out: { role: 'user' | 'assistant'; content: string }[] = []
  for (const msg of messages) {
    if (SKIP_LLM_KINDS.has(msg.kind)) continue
    const text = truncateForLlm(messageToLlmText(msg))
    if (!text) continue
    out.push({ role: msg.role, content: text })
  }
  return out.slice(-MAX_LLM_CONTEXT_MESSAGES)
}

export function titleFromQuestion(question: string, maxLen = 48): string {
  const text = question.trim().replace(/\s+/g, ' ')
  if (!text) return '新对话'
  return text.length <= maxLen ? text : `${text.slice(0, maxLen - 1)}…`
}
