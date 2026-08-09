import { act, render, screen, waitFor } from '@/__tests__/utils/render';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { JobExecution } from '../../model/automationTypes';
import { ThreadApiError } from '@/features/ai-chat/public';
import { ExecutionDetailDialog } from './ExecutionDetailDialog';

const mocks = vi.hoisted(() => {
  class MockThreadApiError extends Error {
    readonly code: string;
    readonly info: Record<string, unknown>;
    readonly status: number | undefined;

    constructor(code: string, info: Record<string, unknown> = {}, status?: number) {
      super(code);
      this.name = 'ThreadApiError';
      this.code = code;
      this.info = info;
      this.status = status;
    }
  }

  return {
    ThreadApiError: MockThreadApiError,
    aiChatIntegration: {
      workspaceId: null as string | null,
      runtimeBaseUrl: null as string | null,
      fileChooser: null,
      openCanvas: null,
    },
    cancelExecution: vi.fn(),
    getExecution: vi.fn(),
    getThreadByAutomationExecution: vi.fn(),
    timeline: vi.fn(),
    useThreadEvents: vi.fn(),
    t: vi.fn((key: string, params?: Record<string, string | number>) =>
      params ? `${key}:${JSON.stringify(params)}` : key),
  };
});

vi.mock('../../api/automationApi', () => ({
  automationApi: {
    cancelExecution: mocks.cancelExecution,
    getExecution: mocks.getExecution,
  },
}));

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({ t: mocks.t, state: { currentLanguage: 'en' } }),
}));

vi.mock('@/features/ai-chat/public', () => ({
  ThreadApiError: mocks.ThreadApiError,
  aiChatAutomationExecutionThreadQueryKey: (workspaceId: string, executionId: string | null) =>
    ['ai-chat', 'automation-execution-thread', workspaceId, executionId ?? ''],
  aiChatThreadQueryKey: (workspaceId: string, threadId: string | null) =>
    ['ai-chat', 'thread', workspaceId, threadId ?? ''],
  getThreadApi: () => ({
    getThreadByAutomationExecution: mocks.getThreadByAutomationExecution,
  }),
  ThreadTimeline: (props: {
    workspaceId: string;
    threadId: string;
    runtimeBaseUrl?: string | null;
  }) => {
    mocks.timeline(props);
    return <div data-testid="thread-timeline">{props.threadId}</div>;
  },
  useAiChatIntegration: () => mocks.aiChatIntegration,
  useThreadEvents: (workspaceId: string, runtimeBaseUrl: string, enabled: boolean) => {
    mocks.useThreadEvents(workspaceId, runtimeBaseUrl, enabled);
  },
}));

const execution = (overrides: Partial<JobExecution> = {}): JobExecution => ({
  id: 'execution-1',
  jobId: 'job-1',
  workspaceId: 'workspace-1',
  status: 'queued',
  trigger: 'manual',
  scheduledFor: '2026-07-15T01:00:00Z',
  queuedAt: '2026-07-15T01:00:01Z',
  startedAt: null,
  finishedAt: null,
  cancelRequestedAt: null,
  queuePosition: 1,
  errorCode: null,
  errorMessage: null,
  ...overrides,
});

describe('ExecutionDetailDialog', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.aiChatIntegration.workspaceId = null;
    mocks.aiChatIntegration.runtimeBaseUrl = null;
    mocks.getExecution.mockResolvedValue(execution());
    mocks.getThreadByAutomationExecution.mockRejectedValue(
      new ThreadApiError('automation_thread_not_found', {}, 404),
    );
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('renders canonical queued lifecycle without invalid nullable timestamps', async () => {
    render(
      <ExecutionDetailDialog
        open
        canUseAgentChat
        executionId="execution-1"
        runtimeBaseUrl="http://runtime.test"
        onOpenChange={vi.fn()}
      />,
    );

    expect(await screen.findByText('automation.executionDetail.status.queued')).toBeInTheDocument();
    expect(screen.getByText(/automation.executionDetail.subtitle.*execution-1/)).toBeInTheDocument();
    expect(screen.getByTestId('execution-lifecycle-strip')).toHaveClass('py-2.5');
    expect(screen.getByText(/automation.executionDetail.queuePosition.*1/)).toBeInTheDocument();
    expect(screen.queryByText(/Invalid Date/)).not.toBeInTheDocument();
    expect(screen.getByText('automation.executionDetail.thread.waiting')).toBeInTheDocument();
  });

  it('renders the shared timeline and preserves the viewer layout', async () => {
    mocks.getExecution.mockResolvedValue(execution({ status: 'success' }));
    mocks.getThreadByAutomationExecution.mockResolvedValue({
      id: 'thread-1',
      status: 'complete',
      version: 1,
    });

    render(
      <ExecutionDetailDialog
        open
        canUseAgentChat
        executionId="execution-1"
        runtimeBaseUrl="http://runtime.test"
        onOpenChange={vi.fn()}
      />,
    );

    expect(await screen.findByTestId('thread-timeline')).toHaveTextContent('thread-1');
    expect(mocks.timeline).toHaveBeenCalledWith(expect.objectContaining({
      workspaceId: 'workspace-1',
      threadId: 'thread-1',
      runtimeBaseUrl: 'http://runtime.test',
    }));
    expect(mocks.useThreadEvents).toHaveBeenLastCalledWith(
      'workspace-1',
      'http://runtime.test',
      true,
    );
    expect(screen.getByRole('dialog')).toHaveClass('max-w-6xl', 'h-[90vh]');
  });

  it('does not open a duplicate thread event connection for a matching integration scope', async () => {
    mocks.aiChatIntegration.workspaceId = 'workspace-1';
    mocks.aiChatIntegration.runtimeBaseUrl = 'http://runtime.test';
    mocks.getExecution.mockResolvedValue(execution({ status: 'success' }));
    mocks.getThreadByAutomationExecution.mockResolvedValue({
      id: 'thread-1',
      status: 'complete',
      version: 1,
    });

    render(
      <ExecutionDetailDialog
        open
        canUseAgentChat
        executionId="execution-1"
        runtimeBaseUrl="http://runtime.test"
        onOpenChange={vi.fn()}
      />,
    );

    expect(await screen.findByTestId('thread-timeline')).toHaveTextContent('thread-1');
    expect(mocks.useThreadEvents).toHaveBeenCalledWith('workspace-1', '', true);
    expect(mocks.useThreadEvents).not.toHaveBeenCalledWith(
      'workspace-1',
      'http://runtime.test',
      true,
    );
  });

  it('does not query or stream AI chat threads without workspace permission', async () => {
    mocks.getExecution.mockResolvedValue(execution({ status: 'success' }));

    render(
      <ExecutionDetailDialog
        open
        executionId="execution-1"
        runtimeBaseUrl="http://runtime.test"
        onOpenChange={vi.fn()}
      />,
    );

    expect(await screen.findByText('automation.executionDetail.status.success')).toBeInTheDocument();
    expect(mocks.useThreadEvents).toHaveBeenLastCalledWith(
      'workspace-1',
      'http://runtime.test',
      false,
    );
    expect(mocks.getThreadByAutomationExecution).not.toHaveBeenCalled();
    expect(mocks.timeline).not.toHaveBeenCalled();
  });

  it('renders a localized terminal state when execution messages no longer exist', async () => {
    mocks.getExecution.mockResolvedValue(execution({ status: 'success' }));

    render(
      <ExecutionDetailDialog
        open
        canUseAgentChat
        executionId="execution-1"
        runtimeBaseUrl="http://runtime.test"
        onOpenChange={vi.fn()}
      />,
    );

    expect(await screen.findByText('automation.executionDetail.thread.notFound')).toBeInTheDocument();
    expect(mocks.timeline).not.toHaveBeenCalled();
  });

  it('still renders terminal lifecycle when Runtime URL is missing', async () => {
    mocks.getExecution.mockResolvedValue(execution({
      status: 'failed',
      errorCode: 'automation_execution_failed',
      errorMessage: 'raw backend message',
    }));

    render(
      <ExecutionDetailDialog canUseAgentChat open executionId="execution-1" onOpenChange={vi.fn()} />,
    );

    expect(await screen.findByText('automation.executionDetail.status.failed')).toBeInTheDocument();
    expect(screen.getByText('automation.executionDetail.errors.automation_execution_failed')).toBeInTheDocument();
    expect(screen.queryByText('raw backend message')).not.toBeInTheDocument();
    expect(screen.getByText('automation.executionDetail.thread.runtimeUnavailable')).toBeInTheDocument();
    expect(mocks.getThreadByAutomationExecution).not.toHaveBeenCalled();
  });

  it('cancels active executions and refreshes canonical detail', async () => {
    mocks.cancelExecution.mockResolvedValue(execution({ status: 'running' }));
    render(
      <ExecutionDetailDialog
        open
        canUseAgentChat
        executionId="execution-1"
        runtimeBaseUrl="http://runtime.test"
        onOpenChange={vi.fn()}
      />,
    );

    await userEvent.click(await screen.findByRole('button', {
      name: 'automation.executionDetail.actions.cancel',
    }));

    await waitFor(() => {
      expect(mocks.cancelExecution).toHaveBeenCalledWith('execution-1');
      expect(mocks.getExecution).toHaveBeenCalledTimes(2);
    });
  });

  it('renders the running lifecycle as active and cancellable', async () => {
    mocks.getExecution.mockResolvedValue(execution({
      status: 'running',
      queuePosition: null,
      startedAt: '2026-07-15T01:00:02Z',
    }));

    render(
      <ExecutionDetailDialog
        open
        canUseAgentChat
        executionId="execution-1"
        runtimeBaseUrl="http://runtime.test"
        onOpenChange={vi.fn()}
      />,
    );

    expect(await screen.findByText('automation.executionDetail.status.running')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'automation.executionDetail.actions.cancel' })).toBeInTheDocument();
  });

  it('renders cancelled as terminal without a cancel action', async () => {
    mocks.getExecution.mockResolvedValue(execution({
      status: 'cancelled',
      queuePosition: null,
      finishedAt: '2026-07-15T01:00:03Z',
    }));

    render(
      <ExecutionDetailDialog
        open
        executionId="execution-1"
        runtimeBaseUrl="http://runtime.test"
        onOpenChange={vi.fn()}
      />,
    );

    expect(await screen.findByText('automation.executionDetail.status.cancelled')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'automation.executionDetail.actions.cancel' })).not.toBeInTheDocument();
  });

  it('retries a stable active thread 404 every three seconds', async () => {
    vi.useFakeTimers();
    mocks.getExecution.mockResolvedValue(execution({ status: 'running' }));

    const { unmount } = render(
      <ExecutionDetailDialog
        open
        canUseAgentChat
        executionId="execution-1"
        runtimeBaseUrl="http://runtime.test"
        onOpenChange={vi.fn()}
      />,
    );

    await act(async () => {
      await vi.waitFor(() => expect(mocks.getThreadByAutomationExecution).toHaveBeenCalledTimes(1));
    });
    await act(async () => vi.advanceTimersByTimeAsync(3000));
    await act(async () => {
      await vi.waitFor(() => expect(mocks.getThreadByAutomationExecution).toHaveBeenCalledTimes(2));
      unmount();
    });
  });

  it('stops polling a stable thread 404 after canonical terminal status', async () => {
    vi.useFakeTimers();
    mocks.getExecution.mockResolvedValue(execution({ status: 'success' }));

    render(
      <ExecutionDetailDialog
        open
        canUseAgentChat
        executionId="execution-1"
        runtimeBaseUrl="http://runtime.test"
        onOpenChange={vi.fn()}
      />,
    );

    await act(async () => {
      await vi.waitFor(() => expect(mocks.getThreadByAutomationExecution).toHaveBeenCalledTimes(1));
    });
    await act(async () => vi.advanceTimersByTimeAsync(9000));
    expect(mocks.getThreadByAutomationExecution).toHaveBeenCalledTimes(1);
  });

  it('maps agent execution failures to stable i18n instead of raw backend text', async () => {
    mocks.getExecution.mockResolvedValue(execution({
      status: 'failed',
      errorCode: 'agent_execution_failed',
      errorMessage: 'raw agent failure',
    }));

    render(<ExecutionDetailDialog open executionId="execution-1" onOpenChange={vi.fn()} />);

    expect(await screen.findByText('automation.executionDetail.errors.agent_execution_failed')).toBeInTheDocument();
    expect(screen.queryByText('raw agent failure')).not.toBeInTheDocument();
  });
});
