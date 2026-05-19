import { getApiBase, requestJson } from './httpClient'
import type { PingResponse } from '@/types/api'

export const healthApi = {
  ping(): Promise<PingResponse> {
    return requestJson<PingResponse>(`${getApiBase()}/api/ping`, {
      cache: 'no-store',
    })
  },
}
