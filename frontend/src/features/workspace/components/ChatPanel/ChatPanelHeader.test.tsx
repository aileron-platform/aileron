import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { render, screen } from '@/__tests__/utils/render';

import { ChatPanelHeader } from './ChatPanelHeader';
import type { ChatPanelHeaderProps } from './ChatPanelHeader';

window.HTMLElement.prototype.scrollIntoView = vi.fn();

const translations: Record<string, string> = {
  'workspace.chat.header.title': 'AI 對話',
  'workspace.chat.header.connection.connected': '已連線',
  'workspace.chat.header.connection.disconnected': '連線中斷',
  'workspace.chat.header.sessionDefault': '新對話',
  'workspace.chat.header.sessions.placeholder': '選擇對話',
  'workspace.chat.header.sessions.newConversation': '新對話進行中',
  'workspace.chat.header.sessions.deleteAction': '刪除對話',
  'workspace.chat.header.sessions.empty': '尚無對話',
  'workspace.chat.header.sessions.recentSection': '最近對話',
  'workspace.chat.header.sessions.allSection': '更多對話',
  'workspace.chat.header.sessions.pendingSection': '正在建立',
  'workspace.chat.header.sessions.searchPlaceholder': '搜尋對話...',
  'workspace.chat.header.sessions.emptySearch': '沒有符合條件的對話。',
  'workspace.chat.header.sessions.loadMore': '載入更多對話',
  'workspace.chat.header.sessions.loadedCount': '已載入 {{count}} 則',
  'workspace.chat.header.actions.menu': '更多動作',
  'workspace.chat.header.actions.refresh': '重新整理對話',
  'workspace.chat.header.actions.new': '建立新對話',
  'workspace.chat.header.actions.collapse': '收折面板',
  'workspace.chat.header.actions.expand': '展開面板',
  'workspace.chat.header.actions.fullscreen': '進入全螢幕',
  'workspace.chat.header.actions.exitFullscreen': '退出全螢幕',
  'workspace.chat.header.sessions.messageCount': '{{count}} 則',
};

const t: ChatPanelHeaderProps['t'] = (key, params) => {
  const template = translations[key] ?? params?.defaultValue?.toString() ?? key;
  return Object.entries(params ?? {}).reduce(
    (text, [name, value]) => text.replace(`{{${name}}}`, String(value)),
    template,
  );
};

const baseProps: ChatPanelHeaderProps = {
  isCollapsed: false,
  isExpanded: false,
  sessionId: 'abcd-1234-session',
  isConnected: true,
  sessions: [],
  selectedSessionId: null,
  isLoadingSessions: false,
  hasActiveConversation: false,
  hasPendingNewConversation: false,
  onToggleCollapse: vi.fn(),
  onToggleFullscreen: vi.fn(),
  onNewSession: vi.fn(),
  onRefresh: vi.fn(),
  onClear: vi.fn(),
  onExport: vi.fn(),
  onSessionSelect: vi.fn(),
  onSessionDelete: vi.fn(),
  t,
};

describe('ChatPanelHeader', () => {
  it('shows the localized default label for persisted untitled sessions', async () => {
    const user = userEvent.setup();

    render(
      <ChatPanelHeader
        {...baseProps}
        sessions={[
          {
            session_id: 'abcd-1234-session',
            title: 'Session abcd',
            messageCount: 1,
          },
        ]}
        selectedSessionId="abcd-1234-session"
      />,
    );

    expect(screen.getByRole('combobox')).toHaveTextContent('新對話');
    expect(screen.queryByText('Session abcd')).not.toBeInTheDocument();

    await user.click(screen.getByRole('combobox'));

    expect(screen.getAllByText('新對話').length).toBeGreaterThanOrEqual(2);
    expect(screen.queryByText('Session abcd')).not.toBeInTheDocument();
  });

  it('keeps meaningful session titles unchanged', async () => {
    const user = userEvent.setup();

    render(
      <ChatPanelHeader
        {...baseProps}
        sessions={[
          {
            session_id: 'session-2',
            title: '修正聊天室標題',
            messageCount: 3,
          },
        ]}
        selectedSessionId="session-2"
      />,
    );

    expect(screen.getByRole('combobox')).toHaveTextContent('修正聊天室標題');

    await user.click(screen.getByRole('combobox'));

    expect(screen.getAllByText('修正聊天室標題').length).toBeGreaterThanOrEqual(2);
  });

  it('keeps the pending new conversation label distinct from persisted untitled sessions', () => {
    render(
      <ChatPanelHeader
        {...baseProps}
        sessionId={null}
        hasPendingNewConversation
        sessions={[]}
      />,
    );

    expect(screen.getByRole('combobox')).toHaveTextContent('新對話進行中');
    expect(screen.queryByText(/^新對話$/)).not.toBeInTheDocument();
  });

  it('renders delete actions for removable sessions and triggers delete without selecting', async () => {
    const user = userEvent.setup();
    const onSessionDelete = vi.fn().mockResolvedValue(undefined);
    const onSessionSelect = vi.fn();

    render(
      <ChatPanelHeader
        {...baseProps}
        sessions={[
          { session_id: 'session-1', title: '保留中的對話', messageCount: 1 },
          { session_id: 'session-2', title: '另一則對話', messageCount: 2 },
        ]}
        selectedSessionId="session-1"
        onSessionDelete={onSessionDelete}
        onSessionSelect={onSessionSelect}
      />,
    );

    await user.click(screen.getByRole('combobox'));

    const deleteButtons = screen.getAllByRole('button', { name: '刪除對話' });
    expect(deleteButtons).toHaveLength(2);

    await user.click(deleteButtons[1]!);

    expect(onSessionDelete).toHaveBeenCalledWith('session-2');
    expect(onSessionSelect).not.toHaveBeenCalled();
  });

  it('hides delete action for the selected session while deletion is blocked', async () => {
    const user = userEvent.setup();

    render(
      <ChatPanelHeader
        {...baseProps}
        sessions={[
          { session_id: 'session-1', title: '目前對話', messageCount: 1 },
          { session_id: 'session-2', title: '可刪除對話', messageCount: 2 },
        ]}
        selectedSessionId="session-1"
        isSelectedSessionDeleteBlocked
      />,
    );

    await user.click(screen.getByRole('combobox'));

    const deleteButtons = screen.getAllByRole('button', { name: '刪除對話' });
    expect(deleteButtons).toHaveLength(1);
  });
});
