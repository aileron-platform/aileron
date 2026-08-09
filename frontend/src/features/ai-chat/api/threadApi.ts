import { apiClient, type ApiClient } from '@/shared/api/apiClient';
import { createThreadApiHttp } from './threadApiHttp';
import type { ThreadApi } from './threadApiContract';

export { ThreadApiError } from './threadApiContract';
export type {
  CreateDraftPayload,
  ListThreadsQuery,
  PatchDraftPayload,
  QuestionAnswerPayload,
  ThreadApi,
} from './threadApiContract';

export const getThreadApi = (
  runtimeBaseUrl: string,
  managerClient: ApiClient = apiClient,
): ThreadApi => createThreadApiHttp(runtimeBaseUrl, managerClient);
