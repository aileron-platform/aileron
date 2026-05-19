import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeAll, describe, expect, it, vi } from 'vitest';

import { ChatMessageArea } from './ChatMessageArea';
import type { PermissionRequest } from './agentSessionTypes';

const translations: Record<string, string> = {
  'workspace.chat.widgets.permission.title.active': 'Permission required',
  'workspace.chat.widgets.permission.subtitle.active': 'The agent needs your approval to continue',
  'workspace.chat.widgets.permission.codex.scope.once.label': 'Approve once',
  'workspace.chat.widgets.permission.codex.scope.once.description': 'Allow only this Codex request.',
  'workspace.chat.widgets.permission.codex.scope.session.label': 'Approve for this session',
  'workspace.chat.widgets.permission.codex.scope.session.description': 'Allow Codex requests for this conversation only.',
  'workspace.chat.widgets.permission.parameterDetails': 'Parameter details',
  'workspace.chat.widgets.permission.toolLabel': 'Tool:',
  'workspace.chat.widgets.permission.approve': 'Approve',
  'workspace.chat.widgets.permission.deny': 'Deny',
  'workspace.chat.empty.title': 'Start chatting',
  'workspace.chat.empty.description': 'Ask a question.',
  'workspace.chat.empty.action': 'Create new message',
  'workspace.chat.status.codexReconnecting': 'Codex connection lost. Reconnecting ({{attempt}}/{{max_attempts}}).',
};

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string, params?: Record<string, unknown>) => {
      const template = translations[key] ?? key;
      return Object.entries(params ?? {}).reduce(
        (result, [paramKey, value]) => result.replace(`{{${paramKey}}}`, String(value)),
        template,
      );
    },
  }),
}));

vi.mock('./ChatMessageItem', () => ({
  ChatMessageItem: () => <div data-testid="chat-message-item" />,
}));

vi.mock('@/features/agent-tools/components/AcpDecisionWidget', () => ({
  default: () => <div data-testid="acp-decision-widget" />,
}));

const t = (key: string, params?: Record<string, string | number>) => {
  const template = translations[key] ?? key;
  return Object.entries(params ?? {}).reduce(
    (result, [paramKey, value]) => result.replace(`{{${paramKey}}}`, String(value)),
    template,
  );
};

const pendingPermission: PermissionRequest = {
  request_id: 'request-1',
  task_id: 'task-1',
  tool_name: 'write_file',
  tool_input: {
    path: '/workspace/test.html',
  },
  options: [
    { option_id: 'allow_once', name: 'Allow once', kind: 'allow_once', scope: 'once' },
    { option_id: 'allow_session', name: 'Allow for session', kind: 'allow_always', scope: 'session' },
    { option_id: 'reject_once', name: 'Reject', kind: 'reject_once', scope: 'once' },
  ],
};

describe('ChatMessageArea', () => {
  beforeAll(() => {
    Element.prototype.scrollTo = vi.fn();
  });

  it('forwards the Codex widget-selected session scope to permission decisions', async () => {
    const user = userEvent.setup();
    const onPermissionDecision = vi.fn();

    render(
      <div style={{ height: 600 }}>
        <ChatMessageArea
          messages={[]}
          hasActiveRequests={false}
          hasActiveConversation
          onNewSession={vi.fn()}
          typingIndicator={null}
          t={t}
          agentTool="codex"
          pendingPermission={pendingPermission}
          onPermissionDecision={onPermissionDecision}
        />
      </div>,
    );

    await user.click(screen.getByRole('radio', { name: /Approve for this session/i }));
    await user.click(screen.getByRole('button', { name: 'Approve' }));

    expect(onPermissionDecision).toHaveBeenCalledWith('request-1', true, 'session');
  });

  it('renders task status notices with translated parameters', () => {
    render(
      <div style={{ height: 600 }}>
        <ChatMessageArea
          messages={[]}
          hasActiveRequests
          hasActiveConversation
          onNewSession={vi.fn()}
          typingIndicator={null}
          t={t}
          taskStatusNotice={{
            task_id: 'task-1',
            message_key: 'workspace.chat.status.codexReconnecting',
            severity: 'warning',
            params: {
              attempt: 2,
              max_attempts: 5,
            },
          }}
        />
      </div>,
    );

    expect(
      screen.getByText('Codex connection lost. Reconnecting (2/5).'),
    ).toBeInTheDocument();
  });
});
