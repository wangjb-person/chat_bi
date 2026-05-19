/** 通用 API 错误响应 */
export interface ApiErrorBody {
  error?: string
}

/** 查询结果（与后端 _query_result_payload 一致） */
export interface QueryResult {
  data: Record<string, unknown>[]
  columns: string[]
  row_count: number
}

export interface PingResponse {
  status: string
  pid: number
  cwd: string
}
