// @vitest-environment jsdom

import '@testing-library/jest-dom/vitest';
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  AiChatIntegrationProvider,
  type AiChatIntegrationValue,
} from '../contexts/AiChatIntegrationContext';
import { getLastThreadId, setLastThreadId } from '../storage/aiChatStorage';
import type { Thread, ThreadSummary } from '../model/threadModel';
import type { WorkspaceCapabilities } from '../model/threadCapabilitiesModel';
import { CompanionChatPanel } from './CompanionChatPanel';

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

vi.mock('@/shared/components/slash-command-picker', () => ({
  SlashCommandPickerDialog: () => null,
}));

vi.mock('./messages/ThreadTimeline', () => ({
  ThreadTimeline: () => <div data-testid="thread-timeline" />,
}));

vi.mock('@/shared/api/slashCommandApi', () => ({
  slashCommandApi: {
    listPickerItems: vi.fn(async () => []),
  },
}));

const toastMock = vi.hoisted(() => vi.fn());

vi.mock('@/shared/components/ui/use-toast', () => ({
  useToast: () => ({ toast: toastMock }),
}));

const createDraftMock = vi.fn();
const submitMock = vi.fn();
const postMessageMock = vi.fn();
const removeQueuedMessageMock = vi.fn();
const answerQuestionMock = vi.fn();
const patchDraftMock = vi.fn();
const cancelMock = vi.fn();
const retryMock = vi.fn();
const archiveMock = vi.fn();
const deleteThreadMock = vi.fn();

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

const buildSummary = (id: string, updatedAt: string, archived = false): ThreadSummary => ({
  id,
  workspaceId: 'workspace-companion',
  userId: 'user-companion',
  title: `aiChat.mock.threadTitles.${id}`,
  agenticTool: 'claude',
  model: 'sonnet-5',
  claudeMode: 'execute',
  status: 'complete',
  archived,
  errorCode: null,
  errorInfo: null,
  errorMessage: null,
  contextTokens: null,
  contextWindow: null,
  createdAt: updatedAt,
  updatedAt,
});

const buildThread = (id: string): Thread => ({
  ...buildSummary(id, '2026-07-09T03:00:00.000Z'),
  messages: [],
  queuedMessages: [],
  draftMessage: null,
});

let summaries: ThreadSummary[];
let selectedThread: Thread | null;

vi.mock('../hooks/useCapabilities', () => ({
  useCapabilities: () => ({
    data: capabilities,
    isLoading: false,
  }),
}));

vi.mock('../hooks/useThreads', () => ({
  useThreads: () => ({
    query: {
      data: summaries,
      isLoading: false,
    },
    createDraft: {
      mutateAsync: createDraftMock,
    },
    patchDraft: {
      mutate: patchDraftMock,
    },
  }),
}));

vi.mock('../hooks/useThread', () => ({
  questionAnswerErrorKey: () => null,
  useThread: () => ({
    query: {
      data: selectedThread,
      isLoading: false,
    },
    submit: {
      mutate: submitMock,
      mutateAsync: submitMock,
    },
    postMessage: {
      mutate: postMessageMock,
      mutateAsync: postMessageMock,
    },
    removeQueuedMessage: {
      mutate: removeQueuedMessageMock,
    },
    answerQuestion: {
      mutate: answerQuestionMock,
      variables: undefined,
      isPending: false,
      error: null,
    },
    cancel: {
      mutate: cancelMock,
    },
    retry: {
      mutate: retryMock,
    },
    archive: {
      mutate: archiveMock,
    },
    deleteThread: {
      mutate: deleteThreadMock,
    },
  }),
}));

const renderCompanion = (integrationOverrides: Partial<AiChatIntegrationValue> = {}) => {
  const integrationValue: AiChatIntegrationValue = {
    workspaceId: 'workspace-companion',
    runtimeBaseUrl: 'http://runtime.test',
    fileChooser: null,
    openCanvas: null,
    codeReference: null,
    clearCodeReference: null,
    pendingHandoff: null,
    handoffToAiChat: null,
    completeHandoff: null,
    failHandoff: null,
    ...integrationOverrides,
  };
  render(
    <MemoryRouter>
      <AiChatIntegrationProvider value={integrationValue}>
        <CompanionChatPanel workspaceId="workspace-companion" userId="user-companion" />
      </AiChatIntegrationProvider>
    </MemoryRouter>,
  );
};

beforeEach(() => {
  localStorage.clear();
  toastMock.mockReset();
  createDraftMock.mockReset();
  submitMock.mockReset();
  submitMock.mockResolvedValue(undefined);
  postMessageMock.mockReset();
  postMessageMock.mockResolvedValue(undefined);
  patchDraftMock.mockReset();
  cancelMock.mockReset();
  retryMock.mockReset();
  archiveMock.mockReset();
  deleteThreadMock.mockReset();
  summaries = [
    buildSummary('older-thread', '2026-07-09T01:00:00.000Z'),
    buildSummary('latest-thread', '2026-07-09T03:00:00.000Z'),
  ];
  selectedThread = buildThread('latest-thread');
});

afterEach(() => {
  cleanup();
});

describe('CompanionChatPanel', () => {
  it('renders the AI Chat second layer and view slot', () => {
    renderCompanion();

    expect(screen.getByTestId('ai-chat-companion-switcher-row')).toHaveClass('border-b');
    expect(screen.getByTestId('ai-chat-companion-view-slot')).toHaveClass(
      'flex',
      'min-h-0',
      'flex-1',
      'flex-col',
      'overflow-hidden',
    );
    expect(screen.queryByRole('button', { name: 'aiChat.companion.openInHome' })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'aiChat.threadActions.menu' })).toHaveClass('hover:bg-sidebar-accent');
    expect(screen.getByRole('textbox')).toBeInTheDocument();
  });

  it('does not render an open-in-home button in the companion second layer', async () => {
    setLastThreadId('user-companion', 'workspace-companion', 'latest-thread');
    renderCompanion();

    expect(screen.queryByRole('button', { name: 'aiChat.companion.openInHome' })).not.toBeInTheDocument();
  });

  it('persists switcher selection through the companion owner', async () => {
    const user = userEvent.setup();
    renderCompanion();

    await user.click(screen.getByRole('combobox', { name: 'aiChat.companion.switchThread' }));
    await user.click(screen.getByRole('button', { name: 'aiChat.mock.threadTitles.older-thread' }));

    expect(getLastThreadId('user-companion', 'workspace-companion')).toBe('older-thread');
  });

  it('applies a pending Canvas draft handoff after the companion mounts', async () => {
    const completeHandoff = vi.fn();
    renderCompanion({
      pendingHandoff: {
        id: 'handoff-1',
        workspaceId: 'workspace-companion',
        delivery: 'draft',
        content: '#1 spacing',
        mode: 'replace',
        skillName: 'aileron-web-canvas-review',
      },
      completeHandoff,
    });

    await waitFor(() => {
      expect(screen.getByRole('textbox')).toHaveValue('/aileron-web-canvas-review\n\n#1 spacing');
      expect(completeHandoff).toHaveBeenCalledWith('handoff-1');
    });
  });

  it('submits a pending Canvas handoff directly through the selected thread', async () => {
    selectedThread = { ...buildThread('latest-thread'), status: 'draft' };
    const completeHandoff = vi.fn();
    renderCompanion({
      pendingHandoff: {
        id: 'handoff-submit',
        workspaceId: 'workspace-companion',
        delivery: 'submit',
        content: '#1 spacing',
        mode: 'replace',
        skillName: 'aileron-web-canvas-review',
      },
      completeHandoff,
    });

    await waitFor(() => {
      expect(submitMock).toHaveBeenCalledWith({
        targetThreadId: 'latest-thread',
        message: {
          text: '/aileron-web-canvas-review\n\n#1 spacing',
          attachments: [],
        },
      });
      expect(completeHandoff).toHaveBeenCalledWith('handoff-submit');
    });
  });

  it('posts a pending Canvas handoff when the selected thread has already started', async () => {
    selectedThread = { ...buildThread('latest-thread'), status: 'working' };
    const completeHandoff = vi.fn();
    renderCompanion({
      pendingHandoff: {
        id: 'handoff-post',
        workspaceId: 'workspace-companion',
        delivery: 'submit',
        content: '#1 spacing',
        mode: 'replace',
        skillName: 'aileron-web-canvas-review',
      },
      completeHandoff,
    });

    await waitFor(() => {
      expect(postMessageMock).toHaveBeenCalledWith({
        targetThreadId: 'latest-thread',
        message: {
          text: '/aileron-web-canvas-review\n\n#1 spacing',
          attachments: [],
        },
      });
      expect(completeHandoff).toHaveBeenCalledWith('handoff-post');
    });
  });

  it('creates a default draft before submitting when no thread exists', async () => {
    summaries = [];
    selectedThread = null;
    createDraftMock.mockImplementation(async () => {
      const draft = { ...buildThread('created-thread'), status: 'draft' as const };
      selectedThread = draft;
      summaries = [buildSummary('created-thread', '2026-07-09T04:00:00.000Z')];
      return draft;
    });
    const completeHandoff = vi.fn();
    renderCompanion({
      pendingHandoff: {
        id: 'handoff-create',
        workspaceId: 'workspace-companion',
        delivery: 'submit',
        content: '#1 spacing',
        mode: 'replace',
        skillName: 'aileron-web-canvas-review',
      },
      completeHandoff,
    });

    await waitFor(() => {
      expect(createDraftMock).toHaveBeenCalledWith({
        agenticTool: 'claude',
        model: 'sonnet-5',
        claudeMode: 'execute',
      });
      expect(submitMock).toHaveBeenCalledWith(expect.objectContaining({
        targetThreadId: 'created-thread',
      }));
      expect(completeHandoff).toHaveBeenCalledWith('handoff-create');
    });
  });

  it('persists input changes through the thread-list draft mutation', async () => {
    selectedThread = { ...buildThread('latest-thread'), status: 'draft' };
    renderCompanion();

    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'Updated draft' } });

    expect(patchDraftMock).toHaveBeenCalledWith({
      threadId: 'latest-thread',
      input: { draftMessage: { text: 'Updated draft', attachments: [] } },
    });
  });

  it('shows an empty state when there is no active thread', () => {
    summaries = [];
    selectedThread = null;

    renderCompanion();

    expect(screen.getByText('aiChat.companion.empty')).toBeInTheDocument();
    expect(screen.queryByRole('textbox')).not.toBeInTheDocument();
  });

  it('shows archive, delete, and secondary copy Thread ID actions for the selected summary', async () => {
    const user = userEvent.setup();
    const writeText = vi.fn(async () => undefined);
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: { writeText },
    });

    selectedThread = null;
    renderCompanion();

    await user.click(screen.getByRole('button', { name: 'aiChat.threadActions.menu' }));

    expect(screen.getByRole('menuitem', { name: 'aiChat.threadActions.archive' })).toBeInTheDocument();
    expect(screen.getByRole('menuitem', { name: 'aiChat.threadActions.delete' })).toBeInTheDocument();
    await user.click(screen.getByRole('menuitem', { name: 'aiChat.threadActions.copyThreadId' }));
    expect(writeText).toHaveBeenCalledWith('latest-thread');
    await waitFor(() => {
      expect(toastMock).toHaveBeenCalledWith({
        title: 'aiChat.threadActions.copyThreadIdSuccess.title',
        description: 'aiChat.threadActions.copyThreadIdSuccess.description',
        variant: 'success',
      });
    });
  });

  it('renders the init message visibility toggle in the shared action menu', async () => {
    const user = userEvent.setup();

    selectedThread = null;
    renderCompanion();

    await user.click(screen.getByRole('button', { name: 'aiChat.threadActions.menu' }));

    expect(
      screen.getByRole('menuitemcheckbox', { name: 'aiChat.threadActions.showInitMessages' }),
    ).toBeInTheDocument();
  });

  it('selects the next active thread after archiving the selected thread', async () => {
    const user = userEvent.setup();
    archiveMock.mockImplementation((_threadId: string, options?: { onSuccess?: () => void }) => {
      options?.onSuccess?.();
    });

    renderCompanion();

    await user.click(screen.getByRole('button', { name: 'aiChat.threadActions.menu' }));
    await user.click(screen.getByRole('menuitem', { name: 'aiChat.threadActions.archive' }));

    expect(archiveMock).toHaveBeenCalledWith(
      'latest-thread',
      expect.objectContaining({ onSuccess: expect.any(Function) }),
    );
    expect(screen.getByRole('combobox', { name: 'aiChat.companion.switchThread' }))
      .toHaveTextContent('aiChat.mock.threadTitles.older-thread');
  });

  it('clears selected thread after deleting the only active thread', async () => {
    const user = userEvent.setup();
    summaries = [buildSummary('only-thread', '2026-07-09T03:00:00.000Z')];
    selectedThread = buildThread('only-thread');
    deleteThreadMock.mockImplementation((_threadId: string, options?: { onSuccess?: () => void }) => {
      summaries = [];
      selectedThread = null;
      options?.onSuccess?.();
    });

    renderCompanion();

    await user.click(screen.getByRole('button', { name: 'aiChat.threadActions.menu' }));
    await user.click(screen.getByRole('menuitem', { name: 'aiChat.threadActions.delete' }));

    expect(deleteThreadMock).toHaveBeenCalledWith(
      'only-thread',
      expect.objectContaining({ onSuccess: expect.any(Function) }),
    );
    await waitFor(() => {
      expect(screen.getByText('aiChat.companion.empty')).toBeInTheDocument();
    });
  });
});
