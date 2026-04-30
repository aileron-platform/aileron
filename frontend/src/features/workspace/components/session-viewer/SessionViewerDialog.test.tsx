import { render, screen, waitFor } from '@/__tests__/utils/render';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { SessionViewerDialog } from './SessionViewerDialog';
import type { AgentMessage, AgentSession } from '@/features/workspace/components/ChatPanel/agentSessionTypes';

const { getSessionMock, listMessagesMock, tMock } = vi.hoisted(() => ({
  getSessionMock: vi.fn(),
  listMessagesMock: vi.fn(),
  tMock: (key: string, params?: Record<string, string | number>) =>
    ({
      'common.sessionViewer.title': 'Conversation History',
      'common.sessionViewer.description': 'View complete AI conversation',
      'common.sessionViewer.messagesTitle': 'Messages',
      'common.sessionViewer.loading': 'Loading conversation',
      'common.sessionViewer.noMessages': 'No messages',
      'common.sessionViewer.refresh': 'Reload',
      'common.sessionViewer.retry': 'Retry',
      'common.messages.unknownError': 'Unknown error',
      'workspace.chat.messages.loadMoreWithCount': `Load older ${params?.count}`,
      'workspace.chat.messages.loadMore': 'Load older',
      'workspace.chat.messages.loadingMore': 'Loading older',
    }[key] ?? key),
}));

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({ t: tMock }),
}));

vi.mock('@/features/workspace/components/ChatPanel/agentSessionApi', () => ({
  agentApi: {
    sessions: {
      getSession: getSessionMock,
    },
    messages: {
      listMessages: listMessagesMock,
    },
  },
}));

vi.mock('@/features/workspace/components/ChatPanel/ChatMessageItem', () => ({
  ChatMessageItem: ({ message }: { message: AgentMessage }) => (
    <div data-testid="chat-message">{message.content_blocks?.[0]?.type === 'text' ? message.content_blocks[0].text : message.message_id}</div>
  ),
}));

const session: AgentSession = {
  session_id: 'session-1',
  created_at: '2026-04-30T03:00:00.000Z',
  created_by: 'user-1',
  status: 'running',
  agentic_tool: 'claude-code',
  workspace_id: 'ws-1',
  ready_for_prompt: true,
  archived: false,
  title: 'Investigate failure',
};

const createMessage = (index: number, text: string): AgentMessage => ({
  message_id: `msg-${index}`,
  session_id: 'session-1',
  created_at: `2026-04-30T03:00:${String(index).padStart(2, '0')}.000Z`,
  index,
  type: 'user',
  role: 'user',
  content_blocks: [{ type: 'text', text }],
});

describe('SessionViewerDialog', () => {
  it('loads session metadata and the newest messages', async () => {
    getSessionMock.mockResolvedValue(session);
    listMessagesMock
      .mockResolvedValueOnce({ items: [], total: 16, limit: 1, offset: 0 })
      .mockResolvedValueOnce({ items: [createMessage(15, 'Newest message')], total: 16, limit: 15, offset: 1 });

    render(
      <SessionViewerDialog
        isOpen
        onClose={vi.fn()}
        sessionId="session-1"
        workspaceId="ws-1"
        runtimeBaseUrl="http://runtime.test"
      />,
    );

    await waitFor(() => {
      expect(getSessionMock).toHaveBeenCalledWith('http://runtime.test', 'session-1');
      expect(screen.getByText('Investigate failure')).toBeInTheDocument();
      expect(screen.getByText('Newest message')).toBeInTheDocument();
    });

    expect(listMessagesMock).toHaveBeenNthCalledWith(1, 'http://runtime.test', 'session-1', { limit: 1, offset: 0 });
    expect(listMessagesMock).toHaveBeenNthCalledWith(2, 'http://runtime.test', 'session-1', { limit: 15, offset: 1 });
  });

  it('loads older messages before existing messages', async () => {
    const user = userEvent.setup();
    getSessionMock.mockResolvedValue(session);
    listMessagesMock
      .mockResolvedValueOnce({ items: [], total: 16, limit: 1, offset: 0 })
      .mockResolvedValueOnce({ items: [createMessage(15, 'Newest message')], total: 16, limit: 15, offset: 1 })
      .mockResolvedValueOnce({ items: [createMessage(0, 'Oldest message')], total: 16, limit: 1, offset: 0 });

    render(
      <SessionViewerDialog
        isOpen
        onClose={vi.fn()}
        sessionId="session-1"
        workspaceId="ws-1"
        runtimeBaseUrl="http://runtime.test"
      />,
    );

    await user.click(await screen.findByRole('button', { name: /load older 16/i }));

    await waitFor(() => {
      expect(screen.getByText('Oldest message')).toBeInTheDocument();
      expect(screen.getByText('Newest message')).toBeInTheDocument();
    });

    expect(listMessagesMock).toHaveBeenNthCalledWith(3, 'http://runtime.test', 'session-1', { limit: 1, offset: 0 });
  });
});
