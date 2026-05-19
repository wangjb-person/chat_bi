import { defineStore } from 'pinia'
import { ref } from 'vue'
import { chatApi } from '@/api/chatApi'
import { streamAskSql } from '@/composables/useSqlStream'
import type { ChatMessage } from '@/types/chat'
import type { QueryResult } from '@/types/api'
import { createId } from '@/utils/id'
import { useAppStore } from './appStore'

export const useChatStore = defineStore('chat', () => {
  const messages = ref<ChatMessage[]>([])
  const currentSessionId = ref<string | null>(null)
  const sending = ref(false)

  function push(msg: ChatMessage) {
    messages.value.push(msg)
  }

  function removeById(id: string) {
    messages.value = messages.value.filter((m) => m.id !== id)
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

  async function showQueryResult(
    sessionId: string,
    data: QueryResult,
    sql?: string,
  ) {
    currentSessionId.value = sessionId
    push({
      id: createId('result'),
      role: 'assistant',
      kind: 'query-result',
      queryResult: data,
      sql: sql?.trim() || undefined,
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
      await showQueryResult(data.id, data, sql)
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

    try {
      const stream = await streamAskSql({
        question: q,
        tableName: app.tableName,
      })

      removeById(loadingId)
      currentSessionId.value = stream.sessionId

      if (stream.runError) {
        push({
          id: createId('err'),
          role: 'assistant',
          kind: 'error',
          text: `查询失败：${stream.runError}`,
        })
      } else if (stream.queryResult) {
        await showQueryResult(stream.sessionId, stream.queryResult, stream.sql)
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
