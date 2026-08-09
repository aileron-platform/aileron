import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { ThreadTurnMetadata, TimelineMessageItem } from '../../model/threadTimelineModel';
import { ThreadMessageList } from './ThreadMessageList';

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

const turn = (status: ThreadTurnMetadata['status']): ThreadTurnMetadata => ({
  id: 'turn-1', sequence: 1, version: 1, status, errorCode: null, errorInfo: null,
  createdAt: '2026-07-15T00:00:00Z', completedAt: status === 'running' ? null : '2026-07-15T00:01:00Z',
});

const items: TimelineMessageItem[] = [
  {
    id: 'thinking-1', sequence: 1, itemVersion: 1, turnId: 'turn-1',
    turnExecutionId: 'execution-1', type: 'thinking', parentItemId: null,
    content: { parts: [{ type: 'text', text: 'Inspecting' }] }, createdAt: '2026-07-15T00:00:00Z',
  },
  {
    id: 'answer-1', sequence: 2, itemVersion: 2, turnId: 'turn-1',
    turnExecutionId: 'execution-1', type: 'agent_text', parentItemId: null,
    content: { parts: [{ type: 'text', text: 'Finished answer' }] }, createdAt: '2026-07-15T00:00:01Z',
  },
];

describe('ThreadMessageList', () => {
  it('renders activity from the turn lifecycle and preserves thinking expansion', () => {
    const { rerender } = render(
      <ThreadMessageList items={items} turn={turn('running')} executions={[]} showInitMessages={false} />,
    );
    expect(screen.getByText('aiChat.activity.working')).toBeInTheDocument();
    rerender(
      <ThreadMessageList items={items} turn={turn('complete')} executions={[]} showInitMessages={false} />,
    );
    fireEvent.click(screen.getByRole('button', { name: 'aiChat.activity.finished' }));
    fireEvent.click(screen.getByRole('button', { name: 'aiChat.thinking.collapsed' }));
    expect(screen.getByText('Inspecting')).toBeInTheDocument();
    expect(screen.getByText('Finished answer')).toBeInTheDocument();
  });

  it('preserves the files changed display mode', () => {
    const diff: TimelineMessageItem = {
      id: 'diff-1', sequence: 3, itemVersion: 3, turnId: 'turn-1',
      turnExecutionId: 'execution-1', type: 'git_diff', parentItemId: null,
      content: {
        description: null,
        diff: ' app.ts | 1 +\n@@ -1 +1 @@\n-old\n+new',
        diffStats: { files: 1, additions: 1, deletions: 1 },
      },
      createdAt: '2026-07-15T00:00:02Z',
    };
    render(
      <ThreadMessageList items={[...items, diff]} turn={turn('complete')} executions={[]} showInitMessages={false} />,
    );
    expect(screen.getByText('aiChat.filesChanged.title')).toBeInTheDocument();
  });

  it('filters system initialization messages according to showInitMessages', () => {
    const initItem: TimelineMessageItem = {
      id: 'init-1', sequence: 0, itemVersion: 1, turnId: 'turn-1',
      turnExecutionId: 'execution-1', type: 'system_init', parentItemId: null,
      content: {
        agentResumeId: null, model: 'sonnet-5', cwd: '/workspace', tools: [],
        mcpServers: [],
      },
      createdAt: '2026-07-15T00:00:00Z',
    };
    const { rerender } = render(
      <ThreadMessageList
        items={[initItem, ...items]}
        turn={turn('complete')}
        executions={[]}
        showInitMessages={false}
      />,
    );
    expect(screen.queryByTestId('ai-chat-system-init')).not.toBeInTheDocument();

    rerender(
      <ThreadMessageList
        items={[initItem, ...items]}
        turn={turn('complete')}
        executions={[]}
        showInitMessages
      />,
    );
    expect(screen.getByTestId('ai-chat-system-init')).toBeInTheDocument();
  });
});
