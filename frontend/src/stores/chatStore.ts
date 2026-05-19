import { defineStore } from 'pinia'
import { ref } from 'vue'
import { chatApi } from '@/api/chatApi'
import { streamAskSql } from '@/composables/useSqlStream'
import type { ChatMessage } from '@/types/chat'
import type { QueryResult } from '@/types/api'
import { createId } from '@/utils/id'
import { useAppStore } from './appStore'

const WELCOME: ChatMessage = {
  id: 'welcome',
  role: 'assistant',
  kind: 'welcome',
  text: `👋 你好！我是 ChatBI 助手。
你可以直接输入自然语言问题，我会帮你生成 SQL、执行查询并展示结果。

📌 例如：
• 贵阳金阳第一中学排名第一的总分比排名第二的高多少分
• 贵阳金阳第一中学总分在 700 分以上的有多少人`,
}

export const useChatStore = defineStore('chat', () => {
  const messages = ref<ChatMessage[]>([{ ...WELCOME }])
  const currentSessionId = ref<string | null>(null)
  const sending = ref(false)

  function push(msg: ChatMessage) {
    messages.value.push(msg)
  }

  function removeById(id: string) {
    messages.value = messages.value.filter((m) => m.id !== id)
  }

  function updateSqlMessage(id: string, sql: string) {
    const msg = messages.value.find((m) => m.id === id)
    if (msg) msg.sql = sql
  }

  async function appendPlotAndFollowup(sessionId: string, hasData: boolean) {
    if (!hasData) return

    try {
      const plot = await chatApi.generatePlot(sessionId)
      if (plot.figure && !plot.error) {
        push({
          id: createId('plot'),
          role: 'assistant',
          kind: 'plot',
          figureJson: plot.figure,
        })
      }
    } catch (e) {
      console.error('[chat] 图表生成失败', e)
    }

    try {
      const follow = await chatApi.generateFollowup(sessionId)
      if (follow.questions?.length) {
        push({
          id: createId('followup'),
          role: 'assistant',
          kind: 'followup',
          followupQuestions: follow.questions.filter((q) => q?.trim()),
        })
      }
    } catch (e) {
      console.error('[chat] 追问生成失败', e)
    }
  }

  async function showQueryResult(sessionId: string, data: QueryResult) {
    currentSessionId.value = sessionId
    push({
      id: createId('result'),
      role: 'assistant',
      kind: 'query-result',
      queryResult: data,
    })
    await appendPlotAndFollowup(sessionId, (data.data?.length ?? 0) > 0)
  }

  async function fallbackRunSql(sessionId: string, sql: string) {
    const execId = createId('exec')
    push({ id: execId, role: 'assistant', kind: 'executing' })

    try {
      await new Promise((r) => setTimeout(r, 300))
      const data = await chatApi.runSql(sessionId, sql)
      removeById(execId)
      await showQueryResult(data.id, data)
    } catch (e) {
      removeById(execId)
      push({
        id: createId('err'),
        role: 'assistant',
        kind: 'error',
        text: e instanceof Error ? e.message : String(e),
      })
    }
  }

  async function sendQuestion(question: string) {
    const q = question.trim()
    if (!q || sending.value) return

    const app = useAppStore()
    sending.value = true

    push({ id: createId('user'), role: 'user', kind: 'text', text: q })

    const loadingId = createId('loading')
    push({ id: loadingId, role: 'assistant', kind: 'loading' })

    const sqlMsgId = createId('sql')
    let sqlMsgCreated = false

    try {
      const stream = await streamAskSql({
        question: q,
        tableName: app.tableName,
        onSqlChunk: (_chunk, full) => {
          if (!sqlMsgCreated) {
            removeById(loadingId)
            push({ id: sqlMsgId, role: 'assistant', kind: 'sql-stream', sql: full })
            sqlMsgCreated = true
          } else {
            updateSqlMessage(sqlMsgId, full)
          }
        },
      })

      if (!sqlMsgCreated && stream.sql) {
        removeById(loadingId)
        push({ id: sqlMsgId, role: 'assistant', kind: 'sql-stream', sql: stream.sql })
      } else if (!sqlMsgCreated) {
        removeById(loadingId)
      } else {
        updateSqlMessage(sqlMsgId, stream.sql)
      }

      currentSessionId.value = stream.sessionId

      if (stream.runError) {
        push({
          id: createId('err'),
          role: 'assistant',
          kind: 'error',
          text: `SQL 执行失败: ${stream.runError}`,
        })
      } else if (stream.queryResult) {
        await showQueryResult(stream.sessionId, stream.queryResult)
      } else if (stream.needsFallbackRun) {
        await fallbackRunSql(stream.sessionId, stream.sql)
      }
    } catch (e) {
      removeById(loadingId)
      push({
        id: createId('err'),
        role: 'assistant',
        kind: 'error',
        text: e instanceof Error ? e.message : String(e),
      })
    } finally {
      sending.value = false
    }
  }

  return {
    messages,
    currentSessionId,
    sending,
    sendQuestion,
  }
})
