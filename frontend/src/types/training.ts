export type TrainingDataType = 'sql' | 'ddl' | 'doc' | 'gen'

export interface TrainingListItem {
  id: string
  type: TrainingDataType
  question?: string
  content?: string
  table_name?: string
}

export interface TrainingSearchItem {
  id: string
  data_type: TrainingDataType
  content: string
  question?: string
  table_name?: string
  sql?: string
  ddl?: string
  doc?: string
  type?: string
}

export interface TrainingListResponse {
  data: TrainingListItem[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export interface TrainingSearchResponse {
  data: TrainingSearchItem[]
  total: number
}

export interface TrainPayload {
  question?: string
  sql?: string
  ddl?: string
  documentation?: string
  general?: string
  table_name?: string
  gen_type?: string
}

export interface UpdateTrainingPayload {
  id: string
  new_content?: string
  new_question?: string
  new_gen_type?: string
  table_name?: string
}
