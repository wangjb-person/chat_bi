import { getApiBase, requestJson } from './httpClient'
import type { AskMode } from '@/stores/appStore'
import type {
  AppendMessagePayload,
  ConversationSummary,
  StoredMessage,
} from '@/types/conversation'

function userQuery(userId: string): string {
  return `user_id=${encodeURIComponent(userId)}`
}

export const conversationsApi = {
  list(userId: string): Promise<{ items: ConversationSummary[] }> {
    return requestJson(`${getApiBase()}/api/conversations?${userQuery(userId)}`)
  },

  create(payload: {
    id?: string
    user_id: string
    title?: string
    mode?: AskMode
    table_name?: string
  }): Promise<ConversationSummary> {
    return requestJson(`${getApiBase()}/api/conversations`, {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },

  update(
    id: string,
    payload: { user_id: string; title?: string; mode?: AskMode; table_name?: string },
  ): Promise<ConversationSummary> {
    return requestJson(`${getApiBase()}/api/conversations/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    })
  },

  remove(id: string, userId: string): Promise<{ ok: boolean }> {
    return requestJson(`${getApiBase()}/api/conversations/${id}?${userQuery(userId)}`, {
      method: 'DELETE',
    })
  },

  listMessages(id: string, userId: string): Promise<{ items: StoredMessage[] }> {
    return requestJson(
      `${getApiBase()}/api/conversations/${id}/messages?${userQuery(userId)}`,
    )
  },

  appendMessages(
    id: string,
    payload: { user_id: string; messages: AppendMessagePayload[] },
  ): Promise<{ items: StoredMessage[] }> {
    return requestJson(`${getApiBase()}/api/conversations/${id}/messages`, {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },
}
