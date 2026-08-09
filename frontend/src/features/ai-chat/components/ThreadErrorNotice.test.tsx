// @vitest-environment jsdom

import '@testing-library/jest-dom/vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { Thread } from '../model/threadModel';
import { ThreadErrorNotice } from './ThreadErrorNotice';

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string, params?: Record<string, string | number>) => {
      if (params?.agentName) return `${key}:${params.agentName}`;
      return key;
    },
  }),
}));

const buildThread = (overrides: Partial<Thread> = {}): Thread => ({
  id: 'thread-1',
  workspaceId: 'workspace-1',
  userId: 'user-1',
  title: 'Thread',
  agenticTool: 'claude',
  model: 'sonnet-5',
  claudeMode: 'execute',
  status: 'error',
  archived: false,
  errorCode: 'agent_error',
  errorInfo: { message: 'Process exited with code 1' },
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

describe('ThreadErrorNotice', () => {
  it.each([
    ['claude' as const, 'Claude'],
    ['codex' as const, 'Codex'],
    ['opencode' as const, 'OpenCode'],
  ])('renders a shared agent failure notice for %s', (agenticTool, agentName) => {
    render(<ThreadErrorNotice thread={buildThread({ agenticTool })} onRetry={vi.fn()} />);

    expect(screen.getByText(`aiChat.error.agentFailed.title:${agentName}`)).toBeInTheDocument();
    expect(screen.getByText('aiChat.error.agentFailed.description')).toBeInTheDocument();
  });

  it('treats process failures as agent failures', () => {
    render(
      <ThreadErrorNotice
        thread={buildThread({
          agenticTool: 'codex',
          errorCode: 'agent_process_failed',
          errorMessage: 'The selected model requires a newer version of Codex.',
        })}
        onRetry={vi.fn()}
      />,
    );

    expect(screen.getByText('aiChat.error.agentFailed.title:Codex')).toBeInTheDocument();
    expect(screen.getByText('aiChat.error.agentFailed.description')).toBeInTheDocument();
  });

  it('renders errorMessage as the visible summary and full errorInfo in details', () => {
    render(
      <ThreadErrorNotice
        thread={buildThread({
          agenticTool: 'codex',
          errorCode: 'agent_error',
          errorMessage: "The 'gpt-5.6-sol' model requires a newer version of Codex.",
          errorInfo: {
            message: "The 'gpt-5.6-sol' model requires a newer version of Codex.",
            returncode: 1,
          },
        })}
        onRetry={vi.fn()}
      />,
    );

    expect(screen.getByText("The 'gpt-5.6-sol' model requires a newer version of Codex.")).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'aiChat.error.details.show' }));
    expect(screen.getByText(/"returncode": 1/)).toBeInTheDocument();
  });

  it('does not extract the visible summary from system raw payloads', () => {
    render(
      <ThreadErrorNotice
        thread={buildThread({
          errorCode: 'agent_error',
          errorMessage: null,
          errorInfo: { returncode: 1 },
          messages: [
            {
              id: 'system-error',
              type: 'system',
              parentToolUseId: null,
              content: {
                text: 'error',
                raw: {
                  type: 'error',
                  message: JSON.stringify({
                    type: 'error',
                    status: 400,
                    error: {
                      type: 'invalid_request_error',
                      message: 'Hidden raw message',
                    },
                  }),
                },
              },
              createdAt: '2026-07-11T00:02:01.053822Z',
            } as unknown as Thread['messages'][number],
          ],
        })}
        onRetry={vi.fn()}
      />,
    );

    expect(screen.queryByText('Hidden raw message')).not.toBeInTheDocument();
  });

  it('renders runtime restarted and queued drain failures with canonical branches', () => {
    const { rerender } = render(
      <ThreadErrorNotice
        thread={buildThread({
          errorCode: 'runtime_restarted',
          errorInfo: { active_execution_id: 'execution-1' },
        })}
        onRetry={vi.fn()}
      />,
    );

    expect(screen.getByText('aiChat.error.runtimeRestarted.title')).toBeInTheDocument();
    expect(screen.queryByText('aiChat.error.unknown.title')).not.toBeInTheDocument();

    rerender(
      <ThreadErrorNotice
        thread={buildThread({
          errorCode: 'queued_message_drain_failed',
          errorInfo: { queued_message_id: 'queued-1' },
        })}
        onRetry={vi.fn()}
      />,
    );

    expect(screen.getByText('aiChat.error.queuedMessageDrainFailed.title')).toBeInTheDocument();
    expect(screen.queryByText('aiChat.error.unknown.title')).not.toBeInTheDocument();
  });

  it('shows structured error details on demand', () => {
    render(<ThreadErrorNotice thread={buildThread()} onRetry={vi.fn()} />);

    fireEvent.click(screen.getByRole('button', { name: 'aiChat.error.details.show' }));

    expect(screen.getByText(/Process exited with code 1/)).toBeInTheDocument();
  });

  it('does not render for running threads with stale error fields', () => {
    const { container } = render(
      <ThreadErrorNotice
        thread={buildThread({ status: 'working', errorCode: 'agent_error' })}
        onRetry={vi.fn()}
      />,
    );

    expect(container).toBeEmptyDOMElement();
  });
});
