import { getApiBase, requestJson } from '@/api/httpClient'
import type { KbDocument } from '@/types/kb'

export const kbApi = {
  list(): Promise<{ documents: KbDocument[] }> {
    return requestJson(`${getApiBase()}/api/kb/documents`)
  },

  createText(payload: { title: string; content: string }): Promise<KbDocument> {
    return requestJson(`${getApiBase()}/api/kb/documents`, {
      method: 'POST',
      body: JSON.stringify({
        title: payload.title,
        content: payload.content,
        filename: 'paste.txt',
      }),
    })
  },

  async uploadFile(file: File, title?: string): Promise<KbDocument> {
    const form = new FormData()
    form.append('file', file)
    if (title?.trim()) {
      form.append('title', title.trim())
    }
    const response = await fetch(`${getApiBase()}/api/kb/documents`, {
      method: 'POST',
      body: form,
    })
    const data = await response.json()
    if (!response.ok) {
      throw new Error(data?.error ?? `上传失败 HTTP ${response.status}`)
    }
    return data as KbDocument
  },

  remove(id: string): Promise<{ ok: boolean }> {
    return requestJson(`${getApiBase()}/api/kb/documents/${encodeURIComponent(id)}`, {
      method: 'DELETE',
    })
  },
}
