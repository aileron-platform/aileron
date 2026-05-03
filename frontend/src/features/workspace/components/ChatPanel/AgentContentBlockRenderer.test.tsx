import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { AgentContentBlockRenderer } from './AgentContentBlockRenderer';
import type { AgentMessage, PermissionRequest } from './agentSessionTypes';

const translations: Record<string, string> = {
  'workspace.chat.widgets.permission.title.active': 'Permission required',
  'workspace.chat.widgets.permission.subtitle.active': 'The agent needs your approval to continue',
  'workspace.chat.widgets.permission.codex.sandbox.label': 'Sandbox mode',
  'workspace.chat.widgets.permission.codex.approval.label': 'Approval policy',
  'workspace.chat.widgets.permission.parameterDetails': 'Parameter details',
  'workspace.chat.widgets.permission.toolLabel': 'Tool:',
  'workspace.chat.widgets.permission.approve': 'Approve',
  'workspace.chat.widgets.permission.deny': 'Deny',
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

vi.mock('@/features/workspace/components/MarkdownRenderer', () => ({
  MarkdownRenderer: ({ content }: { content: string }) => <div>{content}</div>,
}));

vi.mock('@/features/agent-tools/components/AcpDecisionWidget', () => ({
  default: () => <div data-testid="acp-decision-widget" />,
}));

const permissionMessage = {
  message_id: 'msg-1',
  session_id: 'session-1',
  task_id: 'task-1',
  created_at: '2026-05-03T00:00:00Z',
  index: 0,
  role: 'system',
  type: 'permission_request',
  content: {
    request_id: 'request-1',
    tool_name: 'write_file',
    tool_input: {
      path: '/workspace/test.html',
    },
    decision_type: 'permission',
    status: 'pending',
  },
  content_blocks: [],
  queued: false,
} as AgentMessage;

const pendingPermission: PermissionRequest = {
  request_id: 'request-1',
  task_id: 'task-1',
  tool_name: 'write_file',
  tool_input: {
    path: '/workspace/test.html',
  },
};

describe('AgentContentBlockRenderer', () => {
  it('renders Codex permission requests with the Codex permission widget', async () => {
    const user = userEvent.setup();
    const onApprove = vi.fn();

    render(
      <AgentContentBlockRenderer
        message={permissionMessage}
        allMessages={[permissionMessage]}
        agentTool="codex"
        pendingPermission={pendingPermission}
        onApprove={onApprove}
        onDeny={vi.fn()}
      />,
    );

    expect(screen.queryByTestId('acp-decision-widget')).not.toBeInTheDocument();
    expect(screen.getByText('Sandbox mode')).toBeInTheDocument();
    expect(screen.getByText('Approval policy')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Approve' }));

    expect(onApprove).toHaveBeenCalledWith('request-1', 'once');
  });
});
