// @vitest-environment jsdom

import '@testing-library/jest-dom/vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { CreateDraftPayload } from '../api/threadApi';
import type { OutgoingMessage, Thread } from '../model/threadModel';
import type { WorkspaceCapabilities } from '../model/threadCapabilitiesModel';
import { ChatWorkbench } from './ChatWorkbench';

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string, params?: Record<string, unknown>) => (
      params?.progress === undefined ? key : `${key} ${params.progress}%`
    ),
  }),
}));

vi.mock('../contexts/AiChatIntegrationContext', () => ({
  useAiChatIntegration: () => ({
    workspaceId: 'workspace-workbench',
    runtimeBaseUrl: 'http://runtime.test',
    fileChooser: null,
    openCanvas: null,
  }),
}));

vi.mock('@/shared/components/prompt-invocation-picker', () => ({
  PromptInvocationPickerDialog: () => null,
}));

vi.mock('@/shared/api/promptInvocationApi', () => ({
  promptInvocationApi: {
    list: vi.fn(),
  },
}));

const createDraftMock = vi.fn();
const submitMock = vi.fn();
const postMessageMock = vi.fn();
const removeQueuedMessageMock = vi.fn();
const patchDraftMock = vi.fn();
const stopMock = vi.fn();
const retryMock = vi.fn();
const selectMock = vi.fn();
const threadApiMock = vi.hoisted(() => ({
  uploadAttachment: vi.fn(),
  deleteAttachment: vi.fn(),
}));

vi.mock('../api/threadApi', async () => {
  const actual = await vi.importActual<typeof import('../api/threadApi')>('../api/threadApi');
  return {
    ...actual,
    getThreadApi: () => threadApiMock,
  };
});

vi.mock('../hooks/useCapabilities', () => ({
  useCapabilities: () => ({
    data: capabilities,
    isLoading: false,
  }),
}));

vi.mock('../hooks/useThreads', () => ({
  useThreads: () => ({
    createDraft: {
      mutateAsync: createDraftMock,
    },
    patchDraft: {
      mutate: patchDraftMock,
    },
  }),
}));

vi.mock('../hooks/useThread', () => ({
  useThread: () => ({
    query: {
      data: selectedThread,
      isLoading: selectedThreadLoading,
    },
    submit: {
      mutateAsync: submitMock,
    },
    postMessage: {
      mutate: postMessageMock,
    },
    removeQueuedMessage: {
      mutate: removeQueuedMessageMock,
    },
    stop: {
      mutate: stopMock,
      isPending: false,
    },
    retry: {
      mutate: retryMock,
    },
  }),
}));

const capabilities: WorkspaceCapabilities = {
  defaultTool: 'claude',
  tools: [
    {
      id: 'claude',
      models: ['sonnet-5'],
      defaultModel: 'sonnet-5',
      modes: ['execute', 'plan'],
      defaultMode: 'execute',
      contextWindow: 200000,
    },
  ],
};

let selectedThread: Thread | null = null;
let selectedThreadLoading = false;

const buildThread = (overrides: Partial<Thread> = {}): Thread => ({
  id: 'thread-workbench',
  workspaceId: 'workspace-workbench',
  userId: 'user-workbench',
  title: 'aiChat.mock.threadTitles.complete',
  agenticTool: 'claude',
  model: 'sonnet-5',
  claudeMode: 'execute',
  status: 'complete',
  archived: false,
  errorCode: null,
  errorInfo: null,
  errorMessage: null,
  contextTokens: null,
  contextWindow: null,
  createdAt: '2026-07-09T01:00:00.000Z',
  updatedAt: '2026-07-09T01:00:00.000Z',
  messages: [],
  queuedMessages: [],
  draftMessage: null,
  ...overrides,
});

const renderWorkbench = (selectedThreadId = selectedThread?.id ?? null) => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  render(
    <QueryClientProvider client={queryClient}>
        <ChatWorkbench
        workspaceId="workspace-workbench"
        userId="user-workbench"
        selectedThreadId={selectedThreadId}
        onThreadSelected={selectMock}
      />
    </QueryClientProvider>,
  );
};

beforeEach(() => {
  selectedThread = null;
  selectedThreadLoading = false;
  createDraftMock.mockReset();
  submitMock.mockReset();
  postMessageMock.mockReset();
  patchDraftMock.mockReset();
  stopMock.mockReset();
  retryMock.mockReset();
  selectMock.mockReset();
  URL.createObjectURL = vi.fn(() => 'blob:preview');
  URL.revokeObjectURL = vi.fn();
  threadApiMock.uploadAttachment.mockImplementation((_threadId: string, file: File, onProgress: (progress: number) => void) => {
    onProgress(100);
    return {
      promise: Promise.resolve({
        attachmentId: `att-${file.name}`,
        kind: file.type.startsWith('image/') ? 'image' : 'text-file',
        name: file.name,
        mimeType: file.type,
        size: file.size,
      }),
      abort: vi.fn(),
    };
  });
  threadApiMock.deleteAttachment.mockResolvedValue(undefined);
});

afterEach(() => {
  cleanup();
});

describe('ChatWorkbench', () => {
  it('waits for a selected draft thread before rendering the new task composer', () => {
    selectedThreadLoading = true;

    renderWorkbench('draft-loading');

    expect(screen.queryByTestId('ai-chat-file-input')).not.toBeInTheDocument();
  });

  it('creates a draft, submits it, and switches to ChatView after new prompt submission', async () => {
    const createdDraft = buildThread({ id: 'draft-created', status: 'draft' });
    createDraftMock.mockResolvedValue(createdDraft);
    submitMock.mockResolvedValue(buildThread({ id: 'draft-created', status: 'queued' }));

    renderWorkbench();

    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'ship the homepage' } });
    fireEvent.click(screen.getByRole('button', { name: 'aiChat.input.send' }));

    await waitFor(() => {
      expect(createDraftMock).toHaveBeenCalledWith({
        agenticTool: 'claude',
        model: 'sonnet-5',
        claudeMode: 'execute',
      } satisfies CreateDraftPayload);
    });
    expect(submitMock).toHaveBeenCalledWith({
      targetThreadId: 'draft-created',
      message: {
        text: 'ship the homepage',
        attachments: [],
      } satisfies OutgoingMessage,
    });
    expect(selectMock).toHaveBeenCalledWith('draft-created');
  });

  it('creates a draft before uploading a new-task attachment and reuses it on submit', async () => {
    const user = userEvent.setup();
    const createdDraft = buildThread({ id: 'draft-for-attachment', status: 'draft' });
    createDraftMock.mockResolvedValue(createdDraft);
    submitMock.mockResolvedValue(buildThread({ id: 'draft-for-attachment', status: 'queued' }));

    renderWorkbench();

    await user.upload(
      screen.getByTestId('ai-chat-file-input'),
      new File(['notes'], 'notes.txt', { type: 'text/plain' }),
    );

    await waitFor(() => {
      expect(createDraftMock).toHaveBeenCalledTimes(1);
    });
    expect(threadApiMock.uploadAttachment).toHaveBeenCalledWith(
      'draft-for-attachment',
      expect.any(File),
      expect.any(Function),
    );
    expect(await screen.findByText('aiChat.input.attachmentReady')).toBeInTheDocument();

    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'review this file' } });
    fireEvent.click(screen.getByRole('button', { name: 'aiChat.input.send' }));

    await waitFor(() => {
      expect(submitMock).toHaveBeenCalledWith({
        targetThreadId: 'draft-for-attachment',
        message: {
          text: 'review this file',
          attachments: [{ attachmentId: 'att-notes.txt' }],
        },
      });
    });
    expect(createDraftMock).toHaveBeenCalledTimes(1);
  });
});
