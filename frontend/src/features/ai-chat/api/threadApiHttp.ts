import { ApiClient, ApiError } from '@/shared/api/apiClient';
import { isRecord } from '@/shared/utils/typeGuards';
import { uploadChatAttachment } from '../attachments/uploadChatAttachment';
import type {
  Thread,
  ThreadMutation,
  ThreadSummary,
} from '../model/threadModel';
import type {
  ThreadTimelinePage,
  TimelineItems,
} from '../model/threadTimelineModel';
import type {
  WorkspaceCapabilities,
} from '../model/threadCapabilitiesModel';
import {
  ThreadApiError,
  type CreateDraftPayload,
  type ListThreadsQuery,
  type PatchDraftPayload,
  type QuestionAnswerPayload,
  type ThreadApi,
} from './threadApiContract';

interface ThreadListResponse {
  items: ThreadSummary[];
  total: number;
}

const getErrorInfo = (responseData: unknown): Record<string, unknown> => {
  if (!isRecord(responseData) || !isRecord(responseData.error_info)) {
    return {};
  }
  return responseData.error_info;
};

const normalizeError = (error: unknown): never => {
  if (error instanceof ThreadApiError) {
    throw error;
  }
  if (error instanceof ApiError) {
    throw new ThreadApiError(
      error.errorCode ?? 'generic',
      getErrorInfo(error.responseData),
      error.status,
    );
  }
  throw error;
};

const request = async <T>(operation: () => Promise<T>): Promise<T> => {
  try {
    return await operation();
  } catch (error) {
    return normalizeError(error);
  }
};

export const createThreadApiHttp = (
  runtimeBaseUrl: string,
  managerClient: ApiClient,
): ThreadApi => {
  const runtimeClient = new ApiClient({
    baseUrl: runtimeBaseUrl,
    unauthorizedBehavior: 'propagate',
    executionAudience: 'workspace-runtime',
  });
  const threadPath = (threadId: string): string =>
    `/api/v1/threads/${encodeURIComponent(threadId)}`;

  return {
    async listThreads(_workspaceId: string, filters: ListThreadsQuery = {}) {
      const query = new URLSearchParams({ archived: String(filters.archived ?? false) });
      const response = await request(() =>
        runtimeClient.get<ThreadListResponse>(`/api/v1/threads?${query.toString()}`),
      );
      return response.items;
    },
    getThread: (threadId) => request(() => runtimeClient.get<Thread>(threadPath(threadId))),
    getThreadByAutomationExecution: (automationExecutionId) => request(() =>
      runtimeClient.get<Thread>(
        `/api/v1/threads/by-automation-execution/${encodeURIComponent(automationExecutionId)}`,
      ),
    ),
    getTimeline: (threadId, beforeSequence, limit = 100) => {
      const query = new URLSearchParams({ limit: String(limit) });
      if (beforeSequence !== undefined) query.set('beforeSequence', String(beforeSequence));
      return request(() => runtimeClient.get<ThreadTimelinePage>(
        `${threadPath(threadId)}/timeline?${query.toString()}`,
      ));
    },
    getTimelineItems: (threadId, itemIds) => request(() =>
      runtimeClient.post<TimelineItems>(`${threadPath(threadId)}/timeline/items/batch-get`, {
        ids: itemIds,
      })),
    getToolResultContent: (threadId, messageId) => request(async () => {
      const blob = await runtimeClient.getBlob(
        `${threadPath(threadId)}/messages/${encodeURIComponent(messageId)}/tool-result`,
      );
      return blob.text();
    }),
    createDraft: (_workspaceId: string, input: CreateDraftPayload) =>
      request(() => runtimeClient.post<Thread>('/api/v1/threads/draft', input)),
    patchDraft: (threadId: string, input: PatchDraftPayload) =>
      request(() => runtimeClient.patch<Thread>(`${threadPath(threadId)}/draft`, input)),
    submit: (threadId, message) =>
      request(() => runtimeClient.post<ThreadMutation>(`${threadPath(threadId)}/submit`, message)),
    postMessage: (threadId, message) =>
      request(() => runtimeClient.post<ThreadMutation>(`${threadPath(threadId)}/messages`, message)),
    removeQueuedMessage: (threadId, queuedMessageId) =>
      request(() =>
        runtimeClient.delete<Thread>(
          `${threadPath(threadId)}/queued-messages/${encodeURIComponent(queuedMessageId)}`,
        ),
      ),
    answerQuestion: (threadId: string, messageId: string, payload: QuestionAnswerPayload) =>
      request(() =>
        runtimeClient.post<ThreadMutation>(
          `${threadPath(threadId)}/questions/${encodeURIComponent(messageId)}/answer`,
          payload,
        ),
      ),
    stop: (threadId) =>
      request(() => runtimeClient.post<Thread>(`${threadPath(threadId)}/stop`)),
    retry: (threadId) =>
      request(() => runtimeClient.post<Thread>(`${threadPath(threadId)}/retry`)),
    archive: (threadId) =>
      request(() => runtimeClient.post<Thread>(`${threadPath(threadId)}/archive`)),
    deleteThread: (threadId) =>
      request(() => runtimeClient.delete<void>(threadPath(threadId))),
    getCapabilities: (workspaceId) =>
      request(() => managerClient.get<WorkspaceCapabilities>(
        `/workspaces/${encodeURIComponent(workspaceId)}/capabilities`,
      )),
    uploadAttachment: (threadId, file, onProgress) =>
      uploadChatAttachment({
        url: runtimeClient.buildUrl(`${threadPath(threadId)}/attachments`),
        headers: runtimeClient.getRequestHeaders({
          omitContentType: true,
          method: 'POST',
          path: `${threadPath(threadId)}/attachments`,
        }),
        file,
        onProgress,
      }),
    deleteAttachment: (threadId, attachmentId) =>
      request(() =>
        runtimeClient.delete<void>(
          `${threadPath(threadId)}/attachments/${encodeURIComponent(attachmentId)}`,
        ),
      ),
    transcribeAudio: (file) => {
      const formData = new FormData();
      formData.append('file', file);
      return request(() =>
        runtimeClient.post<{ text: string }>(
          '/api/v1/audio/transcriptions',
          formData,
        ),
      );
    },
  };
};
