import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import TemplateMcpSettingsWorkflow from './TemplateMcpSettingsWorkflow';
import type { McpServerFormValue } from '@/features/template-management/features/template-editor/formTypes';

const toastMock = vi.fn();
const saveMcpConfigMock = vi.fn();

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string) => {
      const translations: Record<string, string> = {
        'template.editor.tabs.mcp': 'MCP',
        'template.detail.mcp.header.title': 'Template MCP',
        'template.detail.mcp.badge': 'badge',
        'template.editor.mcp.actions.add': 'Add Server',
        'template.editor.mcp.empty.title': 'No servers yet',
        'template.editor.mcp.empty.description': 'Create server',
        'template.detail.mcp.empty.title': 'No servers',
        'template.detail.mcp.empty.description': 'Nothing here',
        'template.detail.mcp.actions.download': 'Download MCP',
        'template.detail.mcp.downloadFileName': 'mcp.json',
        'template.detail.mcp.toasts.downloadSuccess.title': 'Downloaded',
        'template.detail.mcp.toasts.downloadSuccess.description': 'MCP downloaded',
      };
      return translations[key] ?? key;
    },
  }),
}));

vi.mock('@/shared/components/ui/use-toast', () => ({
  useToast: () => ({
    toast: toastMock,
  }),
}));

vi.mock('@/features/template-management/features/template-editor/hooks/useTemplateApi', () => ({
  useTemplateApi: () => ({
    saveMcpConfig: saveMcpConfigMock,
  }),
}));

vi.mock('@/features/template-management/components/TemplateMcpServerCard', () => ({
  default: ({
    server,
    showActions,
    onDelete,
  }: {
    server: McpServerFormValue;
    showActions?: boolean;
    onDelete?: (serverId: string) => void;
  }) => (
    <div data-testid={`mcp-card-${server.localId}`}>
      <span>{server.name}</span>
      {showActions ? (
        <button type="button" onClick={() => onDelete?.(server.localId)}>
          delete-{server.localId}
        </button>
      ) : null}
    </div>
  ),
}));

vi.mock('@/shared/components/dialogs', () => ({
  MCPServerDialog: ({
    open,
    onSave,
  }: {
    open: boolean;
    onSave: (server: McpServerFormValue) => void;
  }) =>
    open ? (
      <div data-testid="mcp-dialog">
        <button
          type="button"
          onClick={() =>
            onSave({
              localId: 'server-2',
              name: 'server-b',
              type: 'stdio',
              command: 'npx server',
              argsText: '--help',
              url: '',
              description: 'desc',
              envText: 'TOKEN=abc',
              headersText: '',
            })
          }
        >
          save-server
        </button>
      </div>
    ) : null,
}));

describe('TemplateMcpSettingsWorkflow', () => {
  const servers: McpServerFormValue[] = [
    {
      localId: 'server-1',
      name: 'server-a',
      type: 'stdio',
      command: 'npx a',
      argsText: '',
      url: '',
      description: '',
      envText: '',
      headersText: '',
    },
  ];

  beforeEach(() => {
    toastMock.mockReset();
    saveMcpConfigMock.mockReset().mockResolvedValue(true);
  });

  it('editable 模式新增 server 會更新本地狀態並儲存', async () => {
    const onServersChange = vi.fn();

    render(
      <TemplateMcpSettingsWorkflow
        templateId="tpl-1"
        servers={servers}
        editable
        onServersChange={onServersChange}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: 'Add Server' }));
    fireEvent.click(screen.getByRole('button', { name: 'save-server' }));

    await waitFor(() => {
      expect(onServersChange).toHaveBeenCalledWith([
        servers[0],
        expect.objectContaining({ localId: 'server-2', name: 'server-b' }),
      ]);
      expect(saveMcpConfigMock).toHaveBeenCalledWith([
        servers[0],
        expect.objectContaining({ localId: 'server-2', name: 'server-b' }),
      ]);
    });
  });

  it('view 模式下載設定會顯示 toast', () => {
    const originalCreateObjectUrl = URL.createObjectURL;
    const originalRevokeObjectUrl = URL.revokeObjectURL;
    URL.createObjectURL = vi.fn(() => 'blob:mock');
    URL.revokeObjectURL = vi.fn();
    const originalCreateElement = document.createElement.bind(document);
    const clickSpy = vi.fn();

    vi.spyOn(document, 'createElement').mockImplementation(((tagName: string) => {
      if (tagName === 'a') {
        const anchor = originalCreateElement('a');
        anchor.click = clickSpy;
        return anchor;
      }
      return originalCreateElement(tagName);
    }) as typeof document.createElement);

    render(<TemplateMcpSettingsWorkflow servers={servers} />);

    fireEvent.click(screen.getByRole('button', { name: 'Download MCP' }));

    expect(clickSpy).toHaveBeenCalledTimes(1);
    expect(toastMock).toHaveBeenCalledWith(
      expect.objectContaining({
        title: 'Downloaded',
        description: 'MCP downloaded',
      }),
    );

    document.createElement = originalCreateElement;
    URL.createObjectURL = originalCreateObjectUrl;
    URL.revokeObjectURL = originalRevokeObjectUrl;
  });

  it('editable 模式只顯示單一 mcp header 並保留數量 badge 與新增按鈕', () => {
    render(
      <TemplateMcpSettingsWorkflow
        templateId="tpl-1"
        servers={servers}
        editable
      />
    );

    expect(screen.getByRole('button', { name: 'Add Server' })).toBeInTheDocument();
    expect(screen.getByText('badge')).toBeInTheDocument();
    expect(screen.getAllByText('MCP')).toHaveLength(1);
  });
});
