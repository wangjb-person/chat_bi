import { getApiBase, requestJson } from './httpClient'

export interface MetricDto {
  code: string
  name: string
  dataset_id: string
  base_table: string
  expression: string
  format: string
  description: string
  synonyms: string[]
  dimensions: string[]
  status: string
}

export interface MetricUpsertPayload {
  code: string
  name: string
  base_table: string
  expression: string
  dataset_id?: string
  format?: string
  description?: string
  synonyms?: string[]
  dimensions?: string[]
  status?: string
}

export const metricsApi = {
  list(): Promise<{ metrics: MetricDto[] }> {
    return requestJson(`${getApiBase()}/api/metrics`)
  },

  upsert(payload: MetricUpsertPayload): Promise<{ ok: boolean; code: string }> {
    return requestJson(`${getApiBase()}/api/metrics`, {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },

  remove(code: string): Promise<{ ok: boolean }> {
    return requestJson(`${getApiBase()}/api/metrics/${encodeURIComponent(code)}`, {
      method: 'DELETE',
    })
  },

  resolve(question: string): Promise<Record<string, unknown>> {
    return requestJson(`${getApiBase()}/api/metrics/resolve`, {
      method: 'POST',
      body: JSON.stringify({ question }),
    })
  },
}
