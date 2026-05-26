import { getApiBase, requestJson } from './httpClient'
import type { QueryResult } from '@/types/api'

export interface RunSqlResponse extends QueryResult {
  id: string
}

export interface PlotResponse {
  id: string
  figure: string
  error?: string
}

export interface FollowupResponse {
  id: string
  questions: string[]
  error?: string
}

export const chatApi = {
  askStreamUrl(): string {
    return `${getApiBase()}/api/ask/stream`
  },

  runSql(id: string, sql: string): Promise<RunSqlResponse> {
    return requestJson<RunSqlResponse>(`${getApiBase()}/api/run_sql`, {
      method: 'POST',
      body: JSON.stringify({ id, sql }),
      cache: 'no-store',
    })
  },

  generatePlot(sessionId: string): Promise<PlotResponse> {
    return requestJson<PlotResponse>(`${getApiBase()}/api/generate_plot`, {
      method: 'POST',
      body: JSON.stringify({ id: sessionId }),
    })
  },

  generateFollowup(sessionId: string): Promise<FollowupResponse> {
    return requestJson<FollowupResponse>(`${getApiBase()}/api/generate_followup`, {
      method: 'POST',
      body: JSON.stringify({ id: sessionId }),
    })
  },
}
