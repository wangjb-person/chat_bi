import { getApiBase, requestJson } from './httpClient'
import type {
  TrainPayload,
  TrainingListResponse,
  TrainingSearchResponse,
  UpdateTrainingPayload,
} from '@/types/training'

export const trainingApi = {
  add(payload: TrainPayload): Promise<{ id: string; success: boolean }> {
    return requestJson(`${getApiBase()}/api/train`, {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },

  list(page = 1, pageSize = 50): Promise<TrainingListResponse> {
    return requestJson(
      `${getApiBase()}/api/get_training_data?page=${page}&page_size=${pageSize}`,
    )
  },

  search(params: {
    keyword?: string
    data_type?: string
    table_name?: string
    gen_type?: string
  }): Promise<TrainingSearchResponse> {
    return requestJson(`${getApiBase()}/api/search_training_data`, {
      method: 'POST',
      body: JSON.stringify(params),
    })
  },

  remove(id: string): Promise<{ success: boolean }> {
    return requestJson(`${getApiBase()}/api/remove_training_data`, {
      method: 'POST',
      body: JSON.stringify({ id }),
    })
  },

  update(payload: UpdateTrainingPayload): Promise<{
    success: boolean
    message?: string
  }> {
    return requestJson(`${getApiBase()}/api/update_training_data`, {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },

  exampleQuestions(tableName = ''): Promise<{ questions: string[] }> {
    return requestJson(`${getApiBase()}/api/generate_example_questions`, {
      method: 'POST',
      body: JSON.stringify({ table_name: tableName }),
    })
  },
}
