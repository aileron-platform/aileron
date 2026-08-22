// @vitest-environment jsdom

import '@testing-library/jest-dom/vitest';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { getLastThreadId, setLastThreadId } from './storage/aiChatStorage';
import type { ThreadSummary } from './model/threadModel';
import { AiChatPage } from './AiChatPage';

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

vi.mock('./components/ThreadListSidebar', () => ({
  ThreadListSidebar: ({ selectedThreadId, threads, isLoading, onSelect, onArchive, onDelete }: {
    selectedThreadId: string | null;
    threads: ThreadSummary[];
    isLoading: boolean;
    onSelect: (threadId: string) => void;
    onArchive: (threadId: string) => void;
    onDelete: (threadId: string) => void;
  }) => (
    <div data-testid="thread-list-sidebar">
      {`${selectedThreadId ?? 'none'}:${isLoading ? 'loading' : threads.map((thread) => thread.id).join(',')}`}
      {threads.some((thread) => thread.archived) && (
        <button type="button" onClick={() => onSelect(threads[0].id)}>select archived</button>
      )}
      {threads.length > 0 && (
        <button type="button" onClick={() => onSelect(threads[threads.length - 1].id)}>select last visible</button>
      )}
      {selectedThreadId && (
        <>
          <button type="button" onClick={() => onArchive(selectedThreadId)}>archive selected</button>
          <button type="button" onClick={() => onDelete(selectedThreadId)}>delete selected</button>
        </>
      )}
    </div>
  ),
}));

vi.mock('./components/ChatWorkbench', () => ({
  ChatWorkbench: ({ selectedThreadId }: { selectedThreadId: string | null }) => (
    <div data-testid="chat-workbench">{selectedThreadId ?? 'none'}</div>
  ),
}));

const useThreadsMock = vi.hoisted(() => vi.fn());
const stopThreadMock = vi.hoisted(() => vi.fn());
const retryThreadMock = vi.hoisted(() => vi.fn());
const archiveThreadMock = vi.hoisted(() => vi.fn());
const deleteThreadMock = vi.hoisted(() => vi.fn());
const toastMock = vi.hoisted(() => vi.fn());

vi.mock('./hooks/useThreads', () => ({
  useThreads: (...args: unknown[]) => useThreadsMock(...args),
}));

vi.mock('./hooks/useThread', () => ({
  useThread: (threadId: string | null) => ({
    query: {
      data: threadId === 'archived-thread'
        ? buildSummary('archived-thread', '2026-07-08T01:00:00.000Z', { archived: true })
        : activeThreads.find((thread) => thread.id === threadId) ?? null,
    },
    stop: {
      mutate: stopThreadMock,
    },
    retry: {
      mutate: retryThreadMock,
    },
    archive: {
      mutate: archiveThreadMock,
    },
    deleteThread: {
      mutate: deleteThreadMock,
    },
  }),
}));

vi.mock('./hooks/useCapabilities', () => ({
  useCapabilities: () => ({
    data: {
      defaultTool: 'claude',
      tools: [
        {
          id: 'claude',
          models: ['claude-beta'],
          defaultModel: 'claude-beta',
          modes: ['execute', 'plan'],
          defaultMode: 'execute',
          contextWindow: 200000,
        },
        {
          id: 'codex',
          models: ['codex-alpha'],
          defaultModel: 'codex-alpha',
          modes: null,
          defaultMode: null,
          contextWindow: 200000,
        },
      ],
    },
  }),
}));

vi.mock('@/shared/components/ui/use-toast', () => ({
  useToast: () => ({ toast: toastMock }),
}));

const buildSummary = (
  id: string,
  updatedAt: string,
  overrides: Partial<ThreadSummary> = {},
): ThreadSummary => ({
  id,
  workspaceId: 'workspace-home',
  userId: 'user-home',
  title: `aiChat.mock.threadTitles.${id}`,
  agenticTool: 'claude',
  model: 'claude-beta',
  claudeMode: 'execute',
  status: 'complete',
  archived: false,
  errorCode: null,
  errorInfo: null,
  errorMessage: null,
  contextTokens: null,
  contextWindow: null,
  createdAt: updatedAt,
  updatedAt,
  ...overrides,
});

const activeThreads = [
  buildSummary('older-thread', '2026-07-09T01:00:00.000Z'),
  buildSummary('latest-thread', '2026-07-09T03:00:00.000Z', {
    status: 'working',
    contextTokens: 168500,
    contextWindow: 200000,
  }),
  buildSummary('middle-thread', '2026-07-09T02:00:00.000Z'),
];

const createHomeUi = (initialPath = '/workspaces/workspace-home/home') => (
  <MemoryRouter initialEntries={[initialPath]}>
    <Routes>
      <Route
        path="/workspaces/:workspaceId/home"
        element={<AiChatPage workspaceId="workspace-home" userId="user-home" />}
      />
    </Routes>
  </MemoryRouter>
);

const renderHome = (initialPath = '/workspaces/workspace-home/home') => {
  const view = render(createHomeUi(initialPath));
  return {
    ...view,
    rerenderHome: () => view.rerender(createHomeUi(initialPath)),
  };
};

beforeEach(() => {
  localStorage.clear();
  stopThreadMock.mockReset();
  retryThreadMock.mockReset();
  archiveThreadMock.mockReset();
  deleteThreadMock.mockReset();
  archiveThreadMock.mockImplementation((_threadId: string, options?: { onSuccess?: () => void }) => {
    options?.onSuccess?.();
  });
  deleteThreadMock.mockImplementation((_threadId: string, options?: { onSuccess?: () => void }) => {
    options?.onSuccess?.();
  });
  toastMock.mockReset();
  useThreadsMock.mockReset();
  useThreadsMock.mockImplementation((_workspaceId: string, filters?: { archived?: boolean }) => ({
    query: {
      data: filters?.archived
        ? [buildSummary('archived-thread', '2026-07-08T01:00:00.000Z', { archived: true })]
        : activeThreads,
      isLoading: false,
    },
    createDraft: {
      mutateAsync: vi.fn(),
    },
  }));
});

afterEach(() => {
  cleanup();
});

describe('AiChatPage', () => {
  it('prioritizes the thread query parameter over saved and fallback selection', async () => {
    setLastThreadId('user-home', 'workspace-home', 'older-thread');

    renderHome('/workspaces/workspace-home/home?thread=middle-thread');

    await waitFor(() => {
      expect(screen.getByTestId('chat-workbench')).toHaveTextContent('middle-thread');
    });
    expect(screen.getByTestId('thread-list-sidebar')).toHaveTextContent('middle-thread');
  });

  it('uses the saved active thread when no query parameter is present', async () => {
    setLastThreadId('user-home', 'workspace-home', 'older-thread');

    renderHome();

    await waitFor(() => {
      expect(screen.getByTestId('chat-workbench')).toHaveTextContent('older-thread');
    });
  });

  it('falls back to the newest updated active thread when saved thread is unavailable', async () => {
    setLastThreadId('user-home', 'workspace-home', 'archived-thread');

    renderHome();

    await waitFor(() => {
      expect(screen.getByTestId('chat-workbench')).toHaveTextContent('latest-thread');
    });
  });

  it('persists sidebar selection through the page owner', async () => {
    const user = userEvent.setup();
    renderHome();

    await waitFor(() => {
      expect(screen.getByTestId('chat-workbench')).toHaveTextContent('latest-thread');
    });
    await user.click(screen.getByRole('button', { name: 'select last visible' }));

    expect(getLastThreadId('user-home', 'workspace-home')).toBe('older-thread');
    expect(screen.getByTestId('chat-workbench')).toHaveTextContent('older-thread');
  });

  it('passes filtered and sorted thread data to the sidebar', async () => {
    const user = userEvent.setup();
    useThreadsMock.mockImplementation((_workspaceId: string, filters?: { archived?: boolean }) => ({
      query: {
        data: filters?.archived
          ? [
            buildSummary('archived-zeta', '2026-07-09T03:00:00.000Z', { archived: true, title: 'Zeta' }),
            buildSummary('archived-alpha', '2026-07-09T01:00:00.000Z', { archived: true, title: 'Alpha' }),
          ]
          : activeThreads,
        isLoading: false,
      },
      createDraft: {
        mutateAsync: vi.fn(),
      },
    }));

    renderHome();

    await waitFor(() => {
      expect(screen.getByTestId('thread-list-sidebar'))
        .toHaveTextContent('latest-thread,middle-thread,older-thread');
    });
    await user.click(screen.getByRole('button', { name: 'aiChat.threadList.filter.label' }));
    await user.click(screen.getByText('aiChat.threadList.filter.archived'));
    await waitFor(() => {
      expect(screen.getByTestId('thread-list-sidebar'))
        .toHaveTextContent('archived-zeta,archived-alpha');
    });

    await user.click(screen.getByRole('button', { name: 'aiChat.threadList.sort.label' }));
    await user.click(screen.getByText('aiChat.threadList.sort.title'));

    expect(screen.getByTestId('thread-list-sidebar'))
      .toHaveTextContent('archived-alpha,archived-zeta');
  });

  it('renders feature headers and allows resizing the thread column', async () => {
    const user = userEvent.setup();
    renderHome();

    expect(screen.getByText('aiChat.threadList.title')).toBeInTheDocument();
    const featureHeader = screen.getByTestId('ai-chat-thread-feature-header');
    expect(featureHeader).toBeInTheDocument();
    expect(within(featureHeader).getByTestId('ai-chat-thread-feature-header-icon')).toBeInTheDocument();
    expect(within(featureHeader).queryByTestId('status-active')).not.toBeInTheDocument();
    expect(featureHeader).not.toContainHTML('mt-0.5');
    expect(screen.getByRole('heading', { name: 'aiChat.mock.threadTitles.latest-thread' })).toBeInTheDocument();
    expect(screen.getByText('claude')).toBeInTheDocument();
    expect(screen.getByText('claude-beta')).toBeInTheDocument();
    const headerActionMenu = within(featureHeader).getByRole('button', { name: 'aiChat.threadActions.menu' });
    expect(headerActionMenu).toHaveClass('hover:bg-sidebar-accent');
    expect(headerActionMenu).not.toHaveClass('h-8');
    expect(screen.getByRole('button', { name: 'aiChat.threadList.filter.label' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'aiChat.threadList.sort.label' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'aiChat.threadList.newThread' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'aiChat.threadList.filter.label' })).toHaveClass('hover:bg-sidebar-accent');
    expect(screen.getByRole('button', { name: 'aiChat.threadList.filter.label' })).not.toHaveClass('h-8');
    expect(screen.getByRole('button', { name: 'aiChat.threadList.newThread' })).toHaveClass('hover:bg-sidebar-accent');
    expect(screen.getByRole('button', { name: 'aiChat.threadList.newThread' })).not.toHaveClass('h-8');

    const column = screen.getByTestId('ai-chat-home-thread-column');
    expect(column).toHaveStyle({ width: '320px' });

    await user.click(screen.getByRole('button', { name: 'aiChat.threadList.filter.label' }));
    expect((await screen.findByText('aiChat.threadList.filter.active')).closest('[role="menuitem"]')).toContainHTML('svg');
    await user.click(screen.getByText('aiChat.threadList.filter.archived'));
    await waitFor(() => {
      expect(screen.getByTestId('thread-list-sidebar')).toHaveTextContent('latest-thread:archived-thread');
    });
    expect(useThreadsMock).toHaveBeenLastCalledWith('workspace-home', { archived: true });
    await user.click(screen.getByRole('button', { name: 'aiChat.threadList.sort.label' }));
    await user.click(screen.getByText('aiChat.threadList.sort.title'));
    expect(screen.getByTestId('thread-list-sidebar')).toHaveTextContent('latest-thread:archived-thread');
    expect(localStorage.getItem('aichat.threadListSort.user-home.workspace-home')).toBe('title');

    fireEvent.mouseDown(screen.getByTestId('ai-chat-home-resize-handle'), { clientX: 320 });
    fireEvent.mouseMove(document, { clientX: 420 });
    fireEvent.mouseUp(document);

    await waitFor(() => {
      expect(column).toHaveStyle({ width: '420px' });
    });

    fireEvent.click(screen.getByRole('button', { name: 'shared.shell.collapseSidebar' }));

    expect(column).toHaveStyle({ width: '64px' });
    expect(screen.queryByTestId('thread-list-sidebar')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'aiChat.threadList.filter.label' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'aiChat.threadList.sort.label' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'aiChat.threadList.newThread' })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'shared.shell.expandSidebar' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'shared.shell.expandSidebar' })).toHaveClass('hover:bg-sidebar-accent');
    const collapsedIcon = screen.getByTestId('ai-chat-home-thread-column-collapsed-icon');
    expect(collapsedIcon).toBeInTheDocument();
    expect(collapsedIcon).toHaveClass('hover:bg-sidebar-accent');
    expect(collapsedIcon).not.toHaveClass('h-8');
  });

  it('archives the selected thread from the feature header action menu', async () => {
    const user = userEvent.setup();
    renderHome();

    await waitFor(() => {
      expect(screen.getByTestId('chat-workbench')).toHaveTextContent('latest-thread');
    });
    await user.click(within(screen.getByTestId('ai-chat-thread-feature-header')).getByRole('button', {
      name: 'aiChat.threadActions.menu',
    }));
    await user.click(screen.getByRole('menuitem', { name: 'aiChat.threadActions.archive' }));

    expect(archiveThreadMock.mock.calls[0][0]).toBe('latest-thread');
  });

  it('falls back to the next visible sorted thread after deleting the selected thread', async () => {
    const user = userEvent.setup();
    renderHome();

    await waitFor(() => {
      expect(screen.getByTestId('chat-workbench')).toHaveTextContent('latest-thread');
    });
    await user.click(screen.getByRole('button', { name: 'delete selected' }));

    expect(deleteThreadMock.mock.calls[0][0]).toBe('latest-thread');
    expect(screen.getByTestId('chat-workbench')).toHaveTextContent('middle-thread');
  });

  it('creates new threads with the preferred settings from the previous selection', async () => {
    const user = userEvent.setup();
    const createDraft = vi.fn(async () => buildSummary('preferred-draft', '2026-07-09T04:00:00.000Z', {
      status: 'draft',
      agenticTool: 'codex',
      model: 'codex-alpha',
      claudeMode: null,
    }));
    useThreadsMock.mockReturnValue({
      query: {
        data: activeThreads,
        isLoading: false,
      },
      createDraft: {
        mutateAsync: createDraft,
      },
    });
    localStorage.setItem(
      'aichat.preferredSettings',
      JSON.stringify({ agenticTool: 'codex', model: 'codex-alpha', claudeMode: null }),
    );

    renderHome();

    await user.click(screen.getByRole('button', { name: 'aiChat.threadList.newThread' }));

    await waitFor(() => {
      expect(createDraft).toHaveBeenCalledWith({
        agenticTool: 'codex',
        model: 'codex-alpha',
        claudeMode: null,
      });
    });
    expect(screen.getByTestId('chat-workbench')).toHaveTextContent('preferred-draft');
  });

  it('keeps a newly selected draft while the thread list refetch is still missing it', async () => {
    const user = userEvent.setup();
    let threadList = activeThreads;
    const createDraft = vi.fn(async () => buildSummary('preferred-draft', '2026-07-09T04:00:00.000Z', {
      status: 'draft',
      agenticTool: 'codex',
      model: 'codex-alpha',
      claudeMode: null,
    }));
    useThreadsMock.mockImplementation(() => ({
      query: {
        data: threadList,
        isLoading: false,
      },
      createDraft: {
        mutateAsync: createDraft,
      },
    }));
    localStorage.setItem(
      'aichat.preferredSettings',
      JSON.stringify({ agenticTool: 'codex', model: 'codex-alpha', claudeMode: null }),
    );

    const view = renderHome();

    await user.click(screen.getByRole('button', { name: 'aiChat.threadList.newThread' }));

    await waitFor(() => {
      expect(screen.getByTestId('chat-workbench')).toHaveTextContent('preferred-draft');
    });

    threadList = [...activeThreads];
    view.rerenderHome();

    expect(screen.getByTestId('chat-workbench')).toHaveTextContent('preferred-draft');
  });

  it('keeps a newly selected draft when the page was opened with another thread query parameter', async () => {
    const user = userEvent.setup();
    let threadList = activeThreads;
    const createDraft = vi.fn(async () => buildSummary('query-draft', '2026-07-09T04:00:00.000Z', {
      status: 'draft',
      agenticTool: 'codex',
      model: 'codex-alpha',
      claudeMode: null,
    }));
    useThreadsMock.mockImplementation(() => ({
      query: {
        data: threadList,
        isLoading: false,
      },
      createDraft: {
        mutateAsync: createDraft,
      },
    }));
    localStorage.setItem(
      'aichat.preferredSettings',
      JSON.stringify({ agenticTool: 'codex', model: 'codex-alpha', claudeMode: null }),
    );

    const view = renderHome('/workspaces/workspace-home/home?thread=middle-thread');

    await waitFor(() => {
      expect(screen.getByTestId('chat-workbench')).toHaveTextContent('middle-thread');
    });
    await user.click(screen.getByRole('button', { name: 'aiChat.threadList.newThread' }));

    await waitFor(() => {
      expect(screen.getByTestId('chat-workbench')).toHaveTextContent('query-draft');
    });

    threadList = [...activeThreads];
    view.rerenderHome();

    expect(screen.getByTestId('chat-workbench')).toHaveTextContent('query-draft');
  });

  it('copies the selected thread id from the feature header action menu', async () => {
    const user = userEvent.setup();
    const writeText = vi.fn(async () => undefined);
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: { writeText },
    });
    renderHome();

    await waitFor(() => {
      expect(screen.getByTestId('chat-workbench')).toHaveTextContent('latest-thread');
    });
    await user.click(within(screen.getByTestId('ai-chat-thread-feature-header')).getByRole('button', {
      name: 'aiChat.threadActions.menu',
    }));
    await user.click(screen.getByRole('menuitem', { name: 'aiChat.threadActions.copyThreadId' }));

    expect(writeText).toHaveBeenCalledWith('latest-thread');
    await waitFor(() => {
      expect(screen.queryByRole('menuitem', { name: 'aiChat.threadActions.copyThreadId' })).not.toBeInTheDocument();
    });
    await waitFor(() => {
      expect(toastMock).toHaveBeenCalledWith({
        title: 'aiChat.threadActions.copyThreadIdSuccess.title',
        description: 'aiChat.threadActions.copyThreadIdSuccess.description',
        variant: 'success',
      });
    });
  });

  it('renders the selected archived thread detail without another archive action', async () => {
    const user = userEvent.setup();
    renderHome();

    await user.click(screen.getByRole('button', { name: 'aiChat.threadList.filter.label' }));
    await user.click(screen.getByText('aiChat.threadList.filter.archived'));
    await user.click(screen.getByRole('button', { name: 'select archived' }));

    expect(screen.getByRole('heading', { name: 'aiChat.mock.threadTitles.archived-thread' })).toBeInTheDocument();
    await user.click(within(screen.getByTestId('ai-chat-thread-feature-header')).getByRole('button', {
      name: 'aiChat.threadActions.menu',
    }));
    expect(screen.getByRole('menuitem', { name: 'aiChat.threadActions.copyThreadId' })).toBeInTheDocument();
    expect(screen.queryByRole('menuitem', { name: 'aiChat.threadActions.archive' })).not.toBeInTheDocument();
  });
});
