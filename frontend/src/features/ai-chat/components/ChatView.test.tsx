// @vitest-environment jsdom

import '@testing-library/jest-dom/vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { Thread } from '../model/threadModel';
import type { WorkspaceCapabilities } from '../model/threadCapabilitiesModel';
import { ChatView } from './ChatView';

const mocks = vi.hoisted(() => ({
  timeline: vi.fn(),
}));

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

vi.mock('./messages/ThreadTimeline', () => ({
  ThreadTimeline: (props: { workspaceId: string; threadId: string }) => {
    mocks.timeline(props);
    return <div data-testid="thread-timeline">{props.threadId}</div>;
  },
}));

vi.mock('@/shared/components/prompt-invocation-picker', () => ({
  PromptInvocationPickerDialog: () => null,
}));

vi.mock('@/shared/api/promptInvocationApi', () => ({
  promptInvocationApi: { list: vi.fn() },
}));

const capabilities: WorkspaceCapabilities = {
  defaultTool: 'claude',
  tools: [{
    id: 'claude',
    models: ['sonnet-5'],
    defaultModel: 'sonnet-5',
    modes: ['execute'],
    defaultMode: 'execute',
    contextWindow: 200000,
  }],
};

const buildThread = (overrides: Partial<Thread> = {}): Thread => ({
  id: 'thread-1',
  workspaceId: 'workspace-1',
  userId: 'user-1',
  origin: 'user',
  automationJobId: null,
  automationExecutionId: null,
  title: 'Thread',
  agenticTool: 'claude',
  model: 'sonnet-5',
  claudeMode: 'execute',
  status: 'complete',
  version: 3,
  activeTurnId: null,
  activeTurnExecutionId: null,
  archived: false,
  errorCode: null,
  errorInfo: null,
  errorMessage: null,
  contextTokens: 100,
  contextWindow: 200000,
  createdAt: '2026-07-15T00:00:00Z',
  updatedAt: '2026-07-15T00:00:00Z',
  queuedMessages: [],
  draftMessage: null,
  ...overrides,
});

const renderView = (thread: Thread, overrides: Partial<Parameters<typeof ChatView>[0]> = {}) => {
  const props = {
    thread,
    capabilities,
    variant: 'workbench' as const,
    onSubmitDraft: vi.fn(),
    onPostMessage: vi.fn(),
    onPatchDraft: vi.fn(),
    onStop: vi.fn(),
    onRetry: vi.fn(),
    onRemoveQueuedMessage: vi.fn(),
    ...overrides,
  };
  render(<ChatView {...props} />);
  return props;
};

beforeEach(() => {
  mocks.timeline.mockClear();
  Object.defineProperty(HTMLElement.prototype, 'scrollIntoView', {
    configurable: true,
    value: vi.fn(),
  });
});

describe('ChatView', () => {
  it('renders the shared metadata-driven timeline', () => {
    renderView(buildThread());

    expect(screen.getByTestId('thread-timeline')).toHaveTextContent('thread-1');
    expect(mocks.timeline).toHaveBeenCalledWith(expect.objectContaining({
      workspaceId: 'workspace-1',
      threadId: 'thread-1',
    }));
  });

  it('renders the empty state only for a draft without queued messages', () => {
    renderView(buildThread({ status: 'draft' }));

    expect(screen.getByText('aiChat.messages.empty')).toBeInTheDocument();
    expect(screen.queryByTestId('thread-timeline')).not.toBeInTheDocument();
  });

  it('keeps working and stop controls driven by metadata status', () => {
    const props = renderView(buildThread({ status: 'working', activeTurnId: 'turn-1' }));

    expect(screen.getByText('aiChat.working.working')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'aiChat.workbench.stop' }));
    expect(props.onStop).toHaveBeenCalledOnce();
  });

  it('renders and removes queued messages without loading history', () => {
    const props = renderView(buildThread({
      status: 'working',
      queuedMessages: [{ id: 'queued-1', text: 'follow up', attachments: [] }],
    }));

    expect(screen.getByText('follow up')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'aiChat.queue.remove' }));
    expect(props.onRemoveQueuedMessage).toHaveBeenCalledWith('queued-1');
  });

  it('omits the workbench header in companion mode', () => {
    renderView(buildThread(), { variant: 'companion' });

    expect(screen.getByTestId('chat-view-compact')).toBeInTheDocument();
    expect(screen.queryByText('Thread')).not.toBeInTheDocument();
  });
});
