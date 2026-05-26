import { defineStore } from 'pinia'
import { ref } from 'vue'
import { chatApi } from '@/api/chatApi'
import { conversationsApi } from '@/api/conversationsApi'
import { streamAsk } from '@/composables/useAskStream'
import type { ChatMessage } from '@/types/chat'
import type { QueryResult } from '@/types/api'
import type { ConversationSummary } from '@/types/conversation'
import { createId } from '@/utils/id'
import {
  chatMessageToStored,
  storedToChatMessage,
  titleFromQuestion,
  toLlmMessages,
} from '@/utils/conversationMessages'
import { AUTO_PLOT_FOLLOWUP } from '@/constants/featureFlags'
import { CURRENT_USER } from '@/constants/user'
import { useAppStore } from './appStore'

export const useChatStore = defineStore('chat', () => {
  const conversations = ref<ConversationSummary[]>([])
  const activeConversationId = ref<string | null>(null)
  const messages = ref<ChatMessage[]>([])
  const currentSessionId = ref<string | null>(null)
  const sending = ref(false)
  const loadingConversations = ref(false)
  const loadingMessages = ref(false)

  function push(msg: ChatMessage) {
    messages.value.push(msg)
  }

  function removeById(id: string) {
    messages.value = messages.value.filter((m) => m.id !== id)
  }

  async function loadConversations() {
    loadingConversations.value = true
    try {
      const res = await conversationsApi.list(CURRENT_USER.username)
      conversations.value = res.items
    } catch (e) {
      console.error('[chat] 加载会话列表失败', e)
      conversations.value = []
    } finally {
      loadingConversations.value = false
    }
  }

  async function selectConversation(id: string) {
    if (activeConversationId.value === id && messages.value.length) return
    loadingMessages.value = true
    activeConversationId.value = id
    messages.value = []
    try {
      let conv = conversations.value.find((c) => c.id === id)
      if (!conv) {
        await loadConversations()
        conv = conversations.value.find((c) => c.id === id)
      }
      const msgRes = await conversationsApi.listMessages(id, CURRENT_USER.username)
      messages.value = msgRes.items.map(storedToChatMessage)
      if (conv) {
        const app = useAppStore()
        app.setAskMode(conv.mode)
        app.tableName = conv.table_name || ''
      }
    } catch (e) {
      console.error('[chat] 加载会话消息失败', e)
    } finally {
      loadingMessages.value = false
    }
  }

  async function createNewConversation(): Promise<string> {
    const app = useAppStore()
    const conv = await conversationsApi.create({
      user_id: CURRENT_USER.username,
      title: '新对话',
      mode: app.askMode,
      table_name: app.tableName,
    })
    conversations.value = [conv, ...conversations.value.filter((c) => c.id !== conv.id)]
    activeConversationId.value = conv.id
    messages.value = []
    return conv.id
  }

  function startNewChat() {
    activeConversationId.value = null
    messages.value = []
    currentSessionId.value = null
  }

  async function deleteConversation(id: string) {
    await conversationsApi.remove(id, CURRENT_USER.username)
    conversations.value = conversations.value.filter((c) => c.id !== id)
    if (activeConversationId.value === id) {
      startNewChat()
    }
  }

  async function ensureActiveConversation(question: string): Promise<string> {
    if (activeConversationId.value) return activeConversationId.value
    const app = useAppStore()
    const conv = await conversationsApi.create({
      user_id: CURRENT_USER.username,
      title: titleFromQuestion(question),
      mode: app.askMode,
      table_name: app.tableName,
    })
    conversations.value = [conv, ...conversations.value]
    activeConversationId.value = conv.id
    return conv.id
  }

  async function persistMessages(
    conversationId: string,
    turnId: string,
    batch: ChatMessage[],
    startSeq = 0,
  ) {
    if (!batch.length) return
    await conversationsApi.appendMessages(conversationId, {
      user_id: CURRENT_USER.username,
      messages: batch.map((m, i) => chatMessageToStored(m, turnId, startSeq + i)),
    })
    const idx = conversations.value.findIndex((c) => c.id === conversationId)
    if (idx >= 0) {
      conversations.value[idx] = {
        ...conversations.value[idx],
        updated_at: new Date().toISOString(),
      }
      const [updated] = conversations.value.splice(idx, 1)
      conversations.value.unshift(updated)
    }
  }

  async function appendPlotAndFollowup(sessionId: string, hasData: boolean, turnId: string) {
    if (!hasData || !activeConversationId.value) return
    const extras: ChatMessage[] = []

    try {
      const plot = await chatApi.generatePlot(sessionId)
      if (plot.figure && !plot.error) {
        extras.push({
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
        extras.push({
          id: createId('followup'),
          role: 'assistant',
          kind: 'followup',
          followupQuestions: follow.questions.filter((q) => q?.trim()),
        })
      }
    } catch (e) {
      console.error('[chat] 追问生成失败', e)
    }

    for (const msg of extras) {
      push(msg)
    }
    if (extras.length) {
      await persistMessages(activeConversationId.value, turnId, extras, 10)
    }
  }

  async function showQueryResult(
    sessionId: string,
    data: QueryResult,
    sql?: string,
    turnId?: string,
  ) {
    currentSessionId.value = sessionId
    const msg: ChatMessage = {
      id: createId('result'),
      role: 'assistant',
      kind: 'query-result',
      queryResult: data,
      sql: sql?.trim() || undefined,
    }
    push(msg)
    if (activeConversationId.value && turnId) {
      await persistMessages(activeConversationId.value, turnId, [msg], 1)
    }
    if (AUTO_PLOT_FOLLOWUP && turnId) {
      await appendPlotAndFollowup(sessionId, (data.data?.length ?? 0) > 0, turnId)
    }
  }

  async function fallbackRunSql(sessionId: string, sql: string, turnId: string) {
    const execId = createId('exec')
    push({ id: execId, role: 'assistant', kind: 'executing' })

    try {
      await new Promise((r) => setTimeout(r, 300))
      const data = await chatApi.runSql(sessionId, sql)
      removeById(execId)
      await showQueryResult(data.id, data, sql, turnId)
    } catch (e) {
      removeById(execId)
      const errMsg: ChatMessage = {
        id: createId('err'),
        role: 'assistant',
        kind: 'error',
        text: e instanceof Error ? e.message : String(e),
      }
      push(errMsg)
      if (activeConversationId.value) {
        await persistMessages(activeConversationId.value, turnId, [errMsg], 1)
      }
    }
  }

  async function sendQuestion(question: string) {
    const q = question.trim()
    if (!q || sending.value) return

    const app = useAppStore()
    sending.value = true
    const turnId = createId('turn')

    let conversationId: string
    try {
      conversationId = await ensureActiveConversation(q)
    } catch (e) {
      sending.value = false
      push({
        id: createId('err'),
        role: 'assistant',
        kind: 'error',
        text: e instanceof Error ? e.message : '创建会话失败',
      })
      return
    }

    const userMsg: ChatMessage = { id: createId('user'), role: 'user', kind: 'text', text: q }
    push(userMsg)

    try {
      await persistMessages(conversationId, turnId, [userMsg], 0)
      if (messages.value.filter((m) => m.role === 'user').length === 1) {
        await conversationsApi.update(conversationId, {
          user_id: CURRENT_USER.username,
          title: titleFromQuestion(q),
          mode: app.askMode,
          table_name: app.tableName,
        })
        const idx = conversations.value.findIndex((c) => c.id === conversationId)
        if (idx >= 0) {
          conversations.value[idx] = {
            ...conversations.value[idx],
            title: titleFromQuestion(q),
          }
        }
      }
    } catch (e) {
      console.error('[chat] 保存用户消息失败', e)
    }

    const loadingId = createId('loading')
    push({ id: loadingId, role: 'assistant', kind: 'loading', workflowStatus: '识别意图…' })

    const historyBefore = messages.value.filter((m) => m.id !== loadingId)
    const llmMessages = toLlmMessages(historyBefore)

    try {
      const isKb = app.askMode === 'kb'

      const stream = await streamAsk({
        question: q,
        tableName: app.tableName,
        mode: app.askMode,
        conversationId,
        messages: llmMessages,
        onPhase: (ev) => {
          const msg = messages.value.find((m) => m.id === loadingId)
          if (!msg || msg.kind !== 'loading') return
          if (ev.phase === 'intent') {
            const labels: Record<string, string> = {
              analysis: ev.report_mode ? '报告分析模式' : '归因分析模式',
              query: '智能查数模式',
              chat: '对话模式',
              knowledge: '智能问答',
              clarify: '澄清引导模式',
              doc_qa: '知识库问答',
            }
            msg.workflowStatus = labels[ev.intent ?? ''] ?? '处理中…'
            if (msg.workflowStatus) msg.kind = 'workflow'
          }
          if (ev.phase === 'retrieving') msg.workflowStatus = '检索知识库…'
          if (ev.phase === 'answer_chunk') msg.workflowStatus = '生成回答…'
          if (ev.phase === 'planning') msg.workflowStatus = '制定分析计划…'
          if (ev.phase === 'attributing') msg.workflowStatus = '归因计算中…'
          if (ev.phase === 'reporting') msg.workflowStatus = '生成报告…'
        },
      })

      removeById(loadingId)
      currentSessionId.value = stream.sessionId

      const assistantBatch: ChatMessage[] = []

      if (stream.intent === 'doc_qa' || isKb) {
        const msg: ChatMessage = {
          id: createId('kb'),
          role: 'assistant',
          kind: 'kb-answer',
          text: stream.answerText?.trim() || '（无回复内容）',
          kbSources: stream.kbSources,
        }
        push(msg)
        assistantBatch.push(msg)
      } else if (stream.intent === 'analysis') {
        const msg: ChatMessage = {
          id: createId('analysis'),
          role: 'assistant',
          kind: 'analysis-report',
          reportMd: stream.reportMd || '分析完成，暂无报告内容。',
          facts: stream.facts,
        }
        push(msg)
        assistantBatch.push(msg)
      } else if (
        stream.intent === 'chat'
        || stream.intent === 'knowledge'
        || stream.intent === 'clarify'
      ) {
        const msg: ChatMessage = {
          id: createId('answer'),
          role: 'assistant',
          kind: 'text',
          text: stream.answerText?.trim() || '（无回复内容）',
        }
        push(msg)
        assistantBatch.push(msg)
      } else if (stream.runError) {
        const msg: ChatMessage = {
          id: createId('err'),
          role: 'assistant',
          kind: 'error',
          text: stream.runError,
          errorRaw: stream.errorRaw,
          errorHint: stream.errorHint,
        }
        push(msg)
        assistantBatch.push(msg)
      } else if (stream.queryResult) {
        await showQueryResult(stream.sessionId, stream.queryResult, stream.sql, turnId)
      } else if (stream.needsFallbackRun && stream.sql) {
        await fallbackRunSql(stream.sessionId, stream.sql, turnId)
      }

      if (assistantBatch.length) {
        await persistMessages(conversationId, turnId, assistantBatch, 1)
      }
    } catch (e) {
      removeById(loadingId)
      const errMsg: ChatMessage = {
        id: createId('err'),
        role: 'assistant',
        kind: 'error',
        text: e instanceof Error ? e.message : String(e),
      }
      push(errMsg)
      try {
        await persistMessages(conversationId, turnId, [errMsg], 1)
      } catch {
        /* ignore persist error */
      }
    } finally {
      sending.value = false
    }
  }

  return {
    conversations,
    activeConversationId,
    messages,
    currentSessionId,
    sending,
    loadingConversations,
    loadingMessages,
    loadConversations,
    selectConversation,
    createNewConversation,
    startNewChat,
    deleteConversation,
    sendQuestion,
  }
})
