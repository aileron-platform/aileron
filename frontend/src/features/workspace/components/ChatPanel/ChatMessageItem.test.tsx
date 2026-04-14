import { render, screen } from '@/__tests__/utils/render';
import { describe, expect, it, vi } from 'vitest';

import { ChatMessageItem } from './ChatMessageItem';
import type { AgentMessage } from './agentSessionTypes';

vi.mock('./AgentContentBlockRenderer', () => ({
  AgentContentBlockRenderer: () => <div data-testid="agent-content-block-renderer" />,
}));

const baseMessage: AgentMessage = {
  message_id: 'msg-1',
  session_id: 'session-1',
  task_id: 'task-1',
  created_at: '2026-04-14T00:00:00Z',
  index: 0,
  role: 'assistant',
  type: 'assistant',
  content_blocks: [
    {
      type: 'text',
      text: 'Final answer fragment',
    },
  ],
};

describe('ChatMessageItem', () => {
  it('does not show preview while the latest assistant response is still active', () => {
    render(
      <ChatMessageItem
        message={baseMessage}
        allMessages={[baseMessage]}
        isLastAssistant
        onOpenPreview={vi.fn()}
        previewLabel="Open in preview"
        activeTaskId="task-1"
        hasActiveResponseLifecycle
      />,
    );

    expect(screen.queryByRole('button', { name: 'Open in preview' })).not.toBeInTheDocument();
  });

  it('shows preview after the assistant response lifecycle has finalized', () => {
    render(
      <ChatMessageItem
        message={baseMessage}
        allMessages={[baseMessage]}
        isLastAssistant
        onOpenPreview={vi.fn()}
        previewLabel="Open in preview"
        activeTaskId={null}
        hasActiveResponseLifecycle={false}
      />,
    );

    expect(screen.getByRole('button', { name: 'Open in preview' })).toBeInTheDocument();
  });

  it('does not let a last assistant message without task binding preview during active lifecycle', () => {
    const tasklessMessage: AgentMessage = {
      ...baseMessage,
      message_id: 'msg-2',
      task_id: null,
    };

    render(
      <ChatMessageItem
        message={tasklessMessage}
        allMessages={[tasklessMessage]}
        isLastAssistant
        onOpenPreview={vi.fn()}
        previewLabel="Open in preview"
        activeTaskId="task-1"
        hasActiveResponseLifecycle
      />,
    );

    expect(screen.queryByRole('button', { name: 'Open in preview' })).not.toBeInTheDocument();
  });
});
