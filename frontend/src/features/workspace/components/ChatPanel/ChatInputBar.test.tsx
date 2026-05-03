import { fireEvent, render, screen } from '@/__tests__/utils/render';
import { describe, expect, it, vi } from 'vitest';

import { ChatInputBar } from './ChatInputBar';
import { DEFAULT_CODEX_PERMISSION_CONFIG } from './CodexPermissionSelector';

const t = (key: string) => key;

describe('ChatInputBar', () => {
  it('allows sending while the session has active requests', () => {
    render(
      <ChatInputBar
        value="follow-up"
        isConnected
        hasActiveRequests
        attachments={[]}
        codeReferences={[]}
        onChange={vi.fn()}
        onSend={vi.fn()}
        onAbort={vi.fn()}
        onOpenFilePicker={vi.fn()}
        onOpenUploadDialog={vi.fn()}
        onOpenSlashDialog={vi.fn()}
        onOpenOpenSpecDialog={vi.fn()}
        onRemoveAttachment={vi.fn()}
        onRemoveCodeReference={vi.fn()}
        t={t}
      />,
    );

    expect(screen.getByTitle('workspace.chat.input.send')).toBeEnabled();
  });

  it('submits on enter without shift even while active requests exist', () => {
    const onSend = vi.fn();
    render(
      <ChatInputBar
        value="queue me"
        isConnected
        hasActiveRequests
        attachments={[]}
        codeReferences={[]}
        onChange={vi.fn()}
        onSend={onSend}
        onAbort={vi.fn()}
        onOpenFilePicker={vi.fn()}
        onOpenUploadDialog={vi.fn()}
        onOpenSlashDialog={vi.fn()}
        onOpenOpenSpecDialog={vi.fn()}
        onRemoveAttachment={vi.fn()}
        onRemoveCodeReference={vi.fn()}
        t={t}
      />,
    );

    fireEvent.keyDown(screen.getByPlaceholderText('workspace.chat.input.placeholder'), {
      key: 'Enter',
      shiftKey: false,
    });

    expect(onSend).toHaveBeenCalledTimes(1);
  });

  it('shows Codex permission controls for Codex sessions', () => {
    render(
      <ChatInputBar
        value="prompt"
        isConnected
        hasActiveRequests={false}
        attachments={[]}
        codeReferences={[]}
        cliType="codex"
        codexPermissionConfig={DEFAULT_CODEX_PERMISSION_CONFIG}
        onChange={vi.fn()}
        onSend={vi.fn()}
        onAbort={vi.fn()}
        onOpenFilePicker={vi.fn()}
        onOpenUploadDialog={vi.fn()}
        onOpenSlashDialog={vi.fn()}
        onOpenOpenSpecDialog={vi.fn()}
        onRemoveAttachment={vi.fn()}
        onRemoveCodeReference={vi.fn()}
        onCodexPermissionConfigChange={vi.fn()}
        t={t}
      />,
    );

    expect(screen.getByTitle('workspace.chat.input.codexPermission.label')).toBeInTheDocument();
  });

  it('does not show a Codex network access toggle', () => {
    render(
      <ChatInputBar
        value="prompt"
        isConnected
        hasActiveRequests={false}
        attachments={[]}
        codeReferences={[]}
        cliType="codex"
        codexPermissionConfig={DEFAULT_CODEX_PERMISSION_CONFIG}
        onChange={vi.fn()}
        onSend={vi.fn()}
        onAbort={vi.fn()}
        onOpenFilePicker={vi.fn()}
        onOpenUploadDialog={vi.fn()}
        onOpenSlashDialog={vi.fn()}
        onOpenOpenSpecDialog={vi.fn()}
        onRemoveAttachment={vi.fn()}
        onRemoveCodeReference={vi.fn()}
        onCodexPermissionConfigChange={vi.fn()}
        t={t}
      />,
    );

    fireEvent.click(screen.getByTitle('workspace.chat.input.codexPermission.label'));

    expect(screen.queryByText('workspace.chat.input.codexPermission.network.label')).not.toBeInTheDocument();
  });
});
