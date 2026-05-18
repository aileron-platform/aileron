import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { AgentContentBlockRenderer } from './AgentContentBlockRenderer';
import type { AgentMessage, PermissionRequest } from './agentSessionTypes';

const translations: Record<string, string> = {
  'workspace.chat.generatedImage.alt': 'Generated image',
  'workspace.chat.generatedImage.previewAction': 'Open generated image preview',
  'workspace.chat.generatedImage.previewDescription': 'Preview generated image at a larger size',
  'workspace.chat.generatedImage.previewTitle': 'Generated image preview',
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
  it('renders assistant image blocks from base64 sources', () => {
    const message = {
      message_id: 'msg-image',
      session_id: 'session-1',
      task_id: 'task-1',
      created_at: '2026-05-17T00:00:00Z',
      index: 0,
      role: 'assistant',
      type: 'assistant',
      content_blocks: [
        {
          type: 'image',
          source: {
            type: 'base64',
            media_type: 'image/png',
            data: 'aW1hZ2U=',
          },
        },
      ],
      queued: false,
    } as AgentMessage;

    render(
      <AgentContentBlockRenderer
        message={message}
        allMessages={[message]}
        agentTool="codex"
      />,
    );

    const image = screen.getByRole('img', { name: 'Generated image' });
    expect(image).toHaveAttribute('src', 'data:image/png;base64,aW1hZ2U=');
  });

  it('opens generated image blocks in a dialog preview', async () => {
    const user = userEvent.setup();
    const message = {
      message_id: 'msg-image',
      session_id: 'session-1',
      task_id: 'task-1',
      created_at: '2026-05-17T00:00:00Z',
      index: 0,
      role: 'assistant',
      type: 'assistant',
      content_blocks: [
        {
          type: 'image',
          source: {
            type: 'base64',
            media_type: 'image/png',
            data: 'aW1hZ2U=',
          },
        },
      ],
      queued: false,
    } as AgentMessage;

    render(
      <AgentContentBlockRenderer
        message={message}
        allMessages={[message]}
        agentTool="codex"
      />,
    );

    await user.click(screen.getByRole('button', { name: 'Open generated image preview' }));

    const dialog = screen.getByRole('dialog', { name: 'Generated image preview' });
    expect(within(dialog).getByRole('img', { name: 'Generated image' })).toHaveAttribute(
      'src',
      'data:image/png;base64,aW1hZ2U=',
    );
  });

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
    expect(screen.getByText('Approve once')).toBeInTheDocument();
    expect(screen.getByText('Approve for this session')).toBeInTheDocument();
    expect(screen.queryByText('Sandbox mode')).not.toBeInTheDocument();
    expect(screen.queryByText('Approval policy')).not.toBeInTheDocument();

    await user.click(screen.getByRole('radio', { name: /Approve for this session/i }));
    await user.click(screen.getByRole('button', { name: 'Approve' }));

    expect(onApprove).toHaveBeenCalledWith('request-1', 'session');
  });
});
