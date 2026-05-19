/**
 * 统一 HTTP 客户端：封装 fetch、JSON 解析与错误处理。
 */

export class HttpError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly body?: unknown,
  ) {
    super(message)
    this.name = 'HttpError'
  }
}

async function parseJson<T>(response: Response): Promise<T> {
  const text = await response.text()
  if (!text) return {} as T
  try {
    return JSON.parse(text) as T
  } catch {
    throw new HttpError('响应不是合法 JSON', response.status, text)
  }
}

export async function requestJson<T>(
  url: string,
  init?: RequestInit,
): Promise<T> {
  const response = await fetch(url, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...init?.headers,
    },
  })

  const data = await parseJson<T & ApiErrorBody>(response)

  if (!response.ok) {
    const err = (data as ApiErrorBody)?.error ?? `HTTP ${response.status}`
    throw new HttpError(err, response.status, data)
  }

  return data as T
}

interface ApiErrorBody {
  error?: string
}

export function getApiBase(): string {
  return import.meta.env.VITE_API_BASE ?? ''
}
