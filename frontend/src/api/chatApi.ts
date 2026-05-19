import { getApiBase, requestJson } from './httpClient'
import type { QueryResult } from '@/types/api'

export interface GenerateSqlStreamParams {
  messages: { role: string; content: string }[]
  table_name?: string
}

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
  generateSqlStreamUrl(): string {
    return `${getApiBase()}/api/generate_sql_stream`
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
