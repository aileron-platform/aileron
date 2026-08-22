import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiClient, registerExecutionGrantProvider } from '@/shared/api/apiClient';
import type { Thread, ThreadSummary } from '../model/threadModel';
import type { ThreadTimelinePage, TimelineItems } from '../model/threadTimelineModel';
import type { WorkspaceCapabilities } from '../model/threadCapabilitiesModel';
import { ThreadApiError } from './threadApi';
import { createThreadApiHttp } from './threadApiHttp';

const summary: ThreadSummary = {
  id: 'thread-1',
  workspaceId: 'workspace-1',
  userId: 'user-1',
  title: 'Inspect workspace',
  agenticTool: 'claude',
  model: 'claude-alpha',
  claudeMode: 'execute',
  status: 'draft',
  archived: false,
  errorCode: null,
  errorInfo: null,
  errorMessage: null,
  contextTokens: null,
  contextWindow: 200000,
  createdAt: '2026-07-10T00:00:00Z',
  updatedAt: '2026-07-10T00:00:00Z',
};

const detail: Thread = {
  ...summary,
  queuedMessages: [],
  draftMessage: null,
};

const timelinePage: ThreadTimelinePage = {
  items: [],
  turns: [],
  executions: [],
  pageInfo: { oldestSequence: null, newestSequence: null, nextBeforeSequence: null, hasMoreBefore: false },
};
const timelineItems: TimelineItems = { items: [], turns: [], executions: [] };

const capabilities: WorkspaceCapabilities = {
  defaultTool: 'claude',
  tools: [{
    id: 'claude',
    models: ['claude-alpha'],
    defaultModel: 'claude-alpha',
    modes: ['execute', 'plan'],
    defaultMode: 'execute',
    contextWindow: 200000,
  }],
};

const jsonResponse = (body: unknown, status = 200): Response =>
  new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });

const blobTextResponse = (body: string): Response => {
  const response = new Response(null);
  vi.spyOn(response, 'blob').mockResolvedValue({
    text: async () => body,
  } as Blob);
  return response;
};

describe('createThreadApiHttp', () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    fetchMock.mockReset();
    registerExecutionGrantProvider(async () => 'signed-grant');
    vi.stubGlobal('fetch', fetchMock);
  });

  afterEach(() => {
    registerExecutionGrantProvider(null);
    vi.unstubAllGlobals();
    MockXMLHttpRequest.instances = [];
    MockXMLHttpRequest.responseStatus = 200;
    MockXMLHttpRequest.responseText = JSON.stringify({
      attachmentId: 'att-1',
      kind: 'image',
      name: 'screen.png',
      mimeType: 'image/png',
      size: 4,
    });
    MockXMLHttpRequest.autoComplete = true;
  });

  it('maps every ThreadApi method to the runtime or manager endpoint', async () => {
    fetchMock
      .mockResolvedValueOnce(jsonResponse({ items: [summary], total: 1 }))
      .mockResolvedValueOnce(jsonResponse(detail))
      .mockResolvedValueOnce(jsonResponse(timelinePage))
      .mockResolvedValueOnce(jsonResponse(timelineItems))
      .mockResolvedValueOnce(blobTextResponse('full output'))
      .mockResolvedValueOnce(jsonResponse(detail))
      .mockResolvedValueOnce(jsonResponse(detail))
      .mockResolvedValueOnce(jsonResponse(detail))
      .mockResolvedValueOnce(jsonResponse(detail))
      .mockResolvedValueOnce(jsonResponse(detail))
      .mockResolvedValueOnce(jsonResponse(detail))
      .mockResolvedValueOnce(jsonResponse(detail))
      .mockResolvedValueOnce(jsonResponse(detail))
      .mockResolvedValueOnce(jsonResponse(detail))
      .mockResolvedValueOnce(new Response(null, { status: 204 }))
      .mockResolvedValueOnce(jsonResponse(capabilities));
    const api = createThreadApiHttp(
      'http://runtime.test',
      new ApiClient({ baseUrl: 'http://manager.test/api/v1' }),
    );

    await expect(api.listThreads('workspace-1', { archived: true })).resolves.toEqual([summary]);
    await api.getThread('thread-1');
    await api.getTimeline('thread-1', 51, 100);
    await api.getTimelineItems('thread-1', ['41', '42']);
    await expect(api.getToolResultContent('thread-1', '42')).resolves.toBe('full output');
    await api.createDraft('workspace-1', {
      agenticTool: 'claude',
      model: 'claude-alpha',
      claudeMode: 'execute',
    });
    await api.patchDraft('thread-1', {
      model: 'claude-alpha',
      draftMessage: {
        text: 'draft',
        attachments: [{ attachmentId: 'att-image-1' }],
      },
    });
    await api.submit('thread-1', { text: 'submit', attachments: [] });
    await api.postMessage('thread-1', {
      text: 'follow up',
      attachments: [{ attachmentId: 'att-image-2' }],
    });
    await api.removeQueuedMessage('thread-1', 'queued-1');
    await api.answerQuestion('thread-1', '42', {
      answers: { 'Favorite color': 'red' },
      text: '[form answers — color]\nFavorite color: red',
    });
    await api.stop('thread-1');
    await api.retry('thread-1');
    await api.archive('thread-1');
    await api.deleteThread('thread-1');
    await expect(api.getCapabilities('workspace-1')).resolves.toEqual(capabilities);

    expect(fetchMock.mock.calls.map(([url, init]) => [url, init.method, init.body])).toEqual([
      ['http://runtime.test/api/v1/threads?archived=true', 'GET', undefined],
      ['http://runtime.test/api/v1/threads/thread-1', 'GET', undefined],
      ['http://runtime.test/api/v1/threads/thread-1/timeline?limit=100&beforeSequence=51', 'GET', undefined],
      ['http://runtime.test/api/v1/threads/thread-1/timeline/items/batch-get', 'POST', JSON.stringify({ ids: ['41', '42'] })],
      ['http://runtime.test/api/v1/threads/thread-1/messages/42/tool-result', 'GET', undefined],
      ['http://runtime.test/api/v1/threads/draft', 'POST', JSON.stringify({
        agenticTool: 'claude', model: 'claude-alpha', claudeMode: 'execute',
      })],
      ['http://runtime.test/api/v1/threads/thread-1/draft', 'PATCH', JSON.stringify({
        model: 'claude-alpha',
        draftMessage: {
          text: 'draft',
          attachments: [{ attachmentId: 'att-image-1' }],
        },
      })],
      ['http://runtime.test/api/v1/threads/thread-1/submit', 'POST', JSON.stringify({ text: 'submit', attachments: [] })],
      ['http://runtime.test/api/v1/threads/thread-1/messages', 'POST', JSON.stringify({
        text: 'follow up',
        attachments: [{ attachmentId: 'att-image-2' }],
      })],
      ['http://runtime.test/api/v1/threads/thread-1/queued-messages/queued-1', 'DELETE', undefined],
      ['http://runtime.test/api/v1/threads/thread-1/questions/42/answer', 'POST', JSON.stringify({
        answers: { 'Favorite color': 'red' },
        text: '[form answers — color]\nFavorite color: red',
      })],
      ['http://runtime.test/api/v1/threads/thread-1/stop', 'POST', undefined],
      ['http://runtime.test/api/v1/threads/thread-1/retry', 'POST', undefined],
      ['http://runtime.test/api/v1/threads/thread-1/archive', 'POST', undefined],
      ['http://runtime.test/api/v1/threads/thread-1', 'DELETE', undefined],
      ['http://manager.test/api/v1/workspaces/workspace-1/capabilities', 'GET', undefined],
    ]);
  });

  it('preserves nullable metadata fields without adding the removed message history', async () => {
    const response = {
      ...detail,
      draftMessage: { text: 'continue', attachments: [] },
      contextTokens: 168500,
      contextWindow: null,
    };
    fetchMock.mockResolvedValueOnce(jsonResponse(response));
    const api = createThreadApiHttp(
      'http://runtime.test',
      new ApiClient({ baseUrl: 'http://manager.test/api/v1' }),
    );

    const result = await api.getThread('thread-1');

    expect(result).toEqual(response);
    expect(result).not.toHaveProperty('messages');
  });

  it('loads a complete thread by encoded automation execution id', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(detail));
    const api = createThreadApiHttp(
      'http://runtime.test',
      new ApiClient({ baseUrl: 'http://manager.test/api/v1' }),
    );

    await expect(api.getThreadByAutomationExecution('execution /1')).resolves.toEqual(detail);
    expect(fetchMock).toHaveBeenCalledWith(
      'http://runtime.test/api/v1/threads/by-automation-execution/execution%20%2F1',
      expect.objectContaining({ method: 'GET' }),
    );
  });

  it('preserves the stable not-found code and HTTP status for automation thread lookup', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({
      error_code: 'automation_thread_not_found',
      error_info: { automation_execution_id: 'execution-1' },
    }, 404));
    const api = createThreadApiHttp(
      'http://runtime.test',
      new ApiClient({ baseUrl: 'http://manager.test/api/v1' }),
    );

    await expect(api.getThreadByAutomationExecution('execution-1')).rejects.toMatchObject({
      code: 'automation_thread_not_found',
      status: 404,
      info: { automation_execution_id: 'execution-1' },
    });
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it('throws ThreadApiError with backend code and info', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({
      error_code: 'thread_locked',
      error_info: { thread_id: 'thread-1' },
    }, 409));
    const api = createThreadApiHttp(
      'http://runtime.test',
      new ApiClient({ baseUrl: 'http://manager.test/api/v1' }),
    );

    const request = api.patchDraft('thread-1', { draftMessage: null });

    await expect(request).rejects.toBeInstanceOf(ThreadApiError);
    await expect(request).rejects.toMatchObject({
      code: 'thread_locked',
      info: { thread_id: 'thread-1' },
    });
  });

  it('uploads chat attachments with XHR progress and runtime auth headers', async () => {
    vi.stubGlobal('XMLHttpRequest', MockXMLHttpRequest);
    const api = createThreadApiHttp(
      'http://runtime.test',
      new ApiClient({ baseUrl: 'http://manager.test/api/v1' }),
    );
    const progressValues: number[] = [];

    const operation = api.uploadAttachment(
      'thread-1',
      new File(['test'], 'screen.png', { type: 'image/png' }),
      (progress) => progressValues.push(progress),
    );
    const result = await operation.promise;
    const request = MockXMLHttpRequest.instances[0];

    expect(result).toEqual({
      attachmentId: 'att-1',
      kind: 'image',
      name: 'screen.png',
      mimeType: 'image/png',
      size: 4,
    });
    expect(progressValues).toEqual([50]);
    expect(request.method).toBe('POST');
    expect(request.url).toBe('http://runtime.test/api/v1/threads/thread-1/attachments');
    expect(request.headers.Authorization).toBe('Bearer signed-grant');
    expect(request.headers['Content-Type']).toBeUndefined();
    expect(request.body).toBeInstanceOf(FormData);
  });

  it('aborts an in-flight chat attachment upload', async () => {
    MockXMLHttpRequest.autoComplete = false;
    vi.stubGlobal('XMLHttpRequest', MockXMLHttpRequest);
    const api = createThreadApiHttp(
      'http://runtime.test',
      new ApiClient({ baseUrl: 'http://manager.test/api/v1' }),
    );

    const operation = api.uploadAttachment(
      'thread-1',
      new File(['test'], 'screen.png', { type: 'image/png' }),
      vi.fn(),
    );
    operation.abort();

    await expect(operation.promise).rejects.toMatchObject({ name: 'AbortError' });
    expect(MockXMLHttpRequest.instances).toHaveLength(0);
  });

  it('deletes uploaded chat attachments through the runtime API', async () => {
    fetchMock.mockResolvedValueOnce(new Response(null, { status: 204 }));
    const api = createThreadApiHttp(
      'http://runtime.test',
      new ApiClient({ baseUrl: 'http://manager.test/api/v1' }),
    );

    await api.deleteAttachment('thread-1', 'att-1');

    expect(fetchMock).toHaveBeenCalledWith(
      'http://runtime.test/api/v1/threads/thread-1/attachments/att-1',
      expect.objectContaining({ method: 'DELETE' }),
    );
  });
});

class MockXMLHttpRequest {
  static instances: MockXMLHttpRequest[] = [];
  static responseStatus = 200;
  static responseText = JSON.stringify({
    attachmentId: 'att-1',
    kind: 'image',
    name: 'screen.png',
    mimeType: 'image/png',
    size: 4,
  });
  static autoComplete = true;

  method = '';
  url = '';
  headers: Record<string, string> = {};
  body: Document | XMLHttpRequestBodyInit | null = null;
  status = 0;
  responseText = '';
  aborted = false;
  upload: XMLHttpRequestUpload = {
    onprogress: null,
  } as XMLHttpRequestUpload;
  onload: (() => void) | null = null;
  onerror: (() => void) | null = null;
  onabort: (() => void) | null = null;

  constructor() {
    MockXMLHttpRequest.instances.push(this);
  }

  open(method: string, url: string) {
    this.method = method;
    this.url = url;
  }

  setRequestHeader(name: string, value: string) {
    this.headers[name] = value;
  }

  send(body: Document | XMLHttpRequestBodyInit | null) {
    this.body = body;
    const onProgress = this.upload.onprogress as ((event: ProgressEvent) => void) | null;
    onProgress?.({ lengthComputable: true, loaded: 2, total: 4 } as ProgressEvent);
    if (!MockXMLHttpRequest.autoComplete) return;
    this.status = MockXMLHttpRequest.responseStatus;
    this.responseText = MockXMLHttpRequest.responseText;
    this.onload?.();
  }

  abort() {
    this.aborted = true;
    this.onabort?.();
  }
}
