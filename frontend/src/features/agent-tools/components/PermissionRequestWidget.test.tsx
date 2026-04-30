import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { PermissionRequestWidget } from './PermissionRequestWidget';

const translations: Record<string, string> = {
  'workspace.chat.widgets.permission.title.active': 'Permission required',
  'workspace.chat.widgets.permission.subtitle.active': 'The agent needs your approval to continue',
  'workspace.chat.widgets.permission.scope.project.label': 'Allow for project (.claude/)',
  'workspace.chat.widgets.permission.onceOnly': 'Allow this time only',
  'workspace.chat.widgets.permission.rememberChoice': 'Remember this choice and save to',
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

const baseInput = {
  message_id: 'msg-1',
  permission_status: 'pending',
  tool_name: 'Bash',
  tool_input: {
    command: 'npm test',
  },
};

describe('PermissionRequestWidget', () => {
  it('renders localized Claude permission labels and approves once by default', async () => {
    const user = userEvent.setup();
    const onApprove = vi.fn();
    const onDeny = vi.fn();

    render(
      <PermissionRequestWidget
        status="completed"
        isExpanded={false}
        input={baseInput}
        onApprove={onApprove}
        onDeny={onDeny}
      />,
    );

    expect(screen.getByText('Permission required')).toBeInTheDocument();
    expect(screen.getByText('The agent needs your approval to continue')).toBeInTheDocument();
    expect(screen.getByText('Tool:')).toBeInTheDocument();
    expect(screen.getByText('Parameter details')).toBeInTheDocument();
    expect(screen.getByText('Allow this time only')).toBeInTheDocument();
    expect(screen.getByText('Remember this choice and save to')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /Approve/i }));

    expect(onApprove).toHaveBeenCalledWith('msg-1', 'once');
    expect(onDeny).not.toHaveBeenCalled();
  });

  it('renders localized Codex selector labels without changing callback payloads', async () => {
    const user = userEvent.setup();
    const onCodexApprove = vi.fn();

    render(
      <PermissionRequestWidget
        status="completed"
        isExpanded={false}
        agentTool="codex"
        input={baseInput}
        onCodexApprove={onCodexApprove}
        onDeny={vi.fn()}
      />,
    );

    expect(screen.getByText('Sandbox mode')).toBeInTheDocument();
    expect(screen.getByText('Approval policy')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /Approve/i }));

    expect(onCodexApprove).toHaveBeenCalledWith('msg-1', 'workspace-write', 'on-request');
  });
});
