import userEvent from '@testing-library/user-event';
import { render, screen } from '@/__tests__/utils/render';
import { describe, expect, it, vi } from 'vitest';
import { MCPServerDialog, type TemplateMCPServerData, type WorkspaceMCPServerData } from './MCPServerDialog';

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string, options?: Record<string, string | number>) => {
      const map: Record<string, string> = {
        'common.cancel': '取消',
        'workspace.claudeCode.mcp.dialogs.server.title.create': '新增 MCP 服務器',
        'workspace.claudeCode.mcp.dialogs.server.title.edit': '編輯 MCP 服務器',
        'workspace.claudeCode.mcp.dialogs.server.description': '配置 MCP 服務器連接設定。',
        'workspace.claudeCode.mcp.dialogs.server.fields.name.label': '服務器名稱 *',
        'workspace.claudeCode.mcp.dialogs.server.fields.name.placeholder': '例如：filesystem',
        'workspace.claudeCode.mcp.dialogs.server.fields.name.hint': 'hint',
        'workspace.claudeCode.mcp.dialogs.server.fields.scope.label': '配置範圍 *',
        'workspace.claudeCode.mcp.dialogs.server.fields.scope.options.project.title': '專案',
        'workspace.claudeCode.mcp.dialogs.server.fields.scope.options.project.description': '專案級別配置',
        'workspace.claudeCode.mcp.dialogs.server.fields.scope.options.user.title': '個人',
        'workspace.claudeCode.mcp.dialogs.server.fields.scope.options.user.description': '使用者級別配置',
        'workspace.claudeCode.mcp.dialogs.server.fields.scope.options.local.title': '本地',
        'workspace.claudeCode.mcp.dialogs.server.fields.scope.options.local.description': '本地級別配置',
        'workspace.claudeCode.mcp.dialogs.server.fields.transport.label': '傳輸類型 *',
        'workspace.claudeCode.mcp.dialogs.server.fields.transport.options.stdio.title': 'Stdio',
        'workspace.claudeCode.mcp.dialogs.server.fields.transport.options.stdio.description': 'stdio',
        'workspace.claudeCode.mcp.dialogs.server.fields.transport.options.http.title': 'HTTP',
        'workspace.claudeCode.mcp.dialogs.server.fields.transport.options.http.description': 'http',
        'workspace.claudeCode.mcp.dialogs.server.fields.transport.options.sse.title': 'SSE',
        'workspace.claudeCode.mcp.dialogs.server.fields.transport.options.sse.description': 'sse',
        'workspace.claudeCode.mcp.dialogs.server.fields.command.label': '執行命令 *',
        'workspace.claudeCode.mcp.dialogs.server.fields.command.placeholder': '例如：npx',
        'workspace.claudeCode.mcp.dialogs.server.fields.commandArgs.label': '命令參數',
        'workspace.claudeCode.mcp.dialogs.server.fields.commandArgs.add': '添加參數',
        'workspace.claudeCode.mcp.dialogs.server.fields.commandArgs.empty': '沒有命令參數',
        'workspace.claudeCode.mcp.dialogs.server.fields.env.label': '環境變數',
        'workspace.claudeCode.mcp.dialogs.server.fields.env.add': '添加變數',
        'workspace.claudeCode.mcp.dialogs.server.fields.env.keyPlaceholder': '變數名稱',
        'workspace.claudeCode.mcp.dialogs.server.fields.env.valuePlaceholder': '變數值',
        'workspace.claudeCode.mcp.dialogs.server.fields.env.empty': '沒有環境變數',
        'workspace.claudeCode.mcp.dialogs.server.fields.headers.label': 'HTTP 標頭',
        'workspace.claudeCode.mcp.dialogs.server.fields.headers.add': '添加標頭',
        'workspace.claudeCode.mcp.dialogs.server.fields.headers.keyPlaceholder': '標頭名稱',
        'workspace.claudeCode.mcp.dialogs.server.fields.headers.valuePlaceholder': '標頭值',
        'workspace.claudeCode.mcp.dialogs.server.fields.headers.empty': '沒有 HTTP 標頭',
        'workspace.claudeCode.mcp.dialogs.server.fields.url.label': '服務器 URL *',
        'workspace.claudeCode.mcp.dialogs.server.fields.url.placeholder.http': '例如：https://api.example.com/mcp',
        'workspace.claudeCode.mcp.dialogs.server.fields.url.placeholder.sse': '例如：https://api.example.com/sse',
        'workspace.claudeCode.mcp.dialogs.server.fields.url.hint.http': '輸入完整的 HTTP/HTTPS URL',
        'workspace.claudeCode.mcp.dialogs.server.fields.url.hint.sse': '輸入完整的 SSE 端點 URL',
        'workspace.claudeCode.mcp.dialogs.server.actions.create': '新增服務器',
        'workspace.claudeCode.mcp.dialogs.server.actions.save': '儲存變更',
        'workspace.claudeCode.mcp.dialogs.server.errors.nameRequired': '伺服器名稱為必填項。',
        'workspace.claudeCode.mcp.dialogs.server.errors.commandRequired': 'Stdio 傳輸需填寫執行命令。',
        'workspace.claudeCode.mcp.dialogs.server.errors.urlRequired': 'HTTP 或 SSE 傳輸需填寫伺服器 URL。',
        'workspace.claudeCode.mcp.dialogs.server.errors.saveFailed': '儲存失敗',
        'template.editor.mcp.dialog.title.create': '新增 MCP 伺服器',
        'template.editor.mcp.dialog.title.edit': '編輯 MCP 伺服器',
        'template.editor.mcp.dialog.description.create': '建立 template mcp',
        'template.editor.mcp.dialog.description.edit': '編輯 template mcp',
        'template.editor.mcp.dialog.fields.name.label': '伺服器名稱 *',
        'template.editor.mcp.dialog.fields.name.placeholder': '輸入伺服器名稱',
        'template.editor.mcp.dialog.fields.description.label': '描述 *',
        'template.editor.mcp.dialog.fields.description.placeholder': '輸入伺服器描述',
        'template.editor.mcp.dialog.fields.command.label': '執行命令 *',
        'template.editor.mcp.dialog.fields.command.placeholder': '例如：python -m my_mcp_server',
        'template.editor.mcp.dialog.fields.args.label': '命令參數',
        'template.editor.mcp.dialog.fields.args.add': '新增參數',
        'template.editor.mcp.dialog.fields.args.empty': '沒有命令參數',
        'template.editor.mcp.dialog.fields.env.label': '環境變數',
        'template.editor.mcp.dialog.fields.env.add': '新增變數',
        'template.editor.mcp.dialog.fields.env.keyPlaceholder': '變數名稱',
        'template.editor.mcp.dialog.fields.env.valuePlaceholder': '變數值',
        'template.editor.mcp.dialog.fields.env.empty': '沒有環境變數',
        'template.editor.mcp.dialog.fields.headers.label': 'HTTP 標頭',
        'template.editor.mcp.dialog.fields.headers.add': '新增標頭',
        'template.editor.mcp.dialog.fields.headers.keyPlaceholder': '標頭名稱',
        'template.editor.mcp.dialog.fields.headers.valuePlaceholder': '標頭值',
        'template.editor.mcp.dialog.fields.headers.empty': '沒有 HTTP 標頭',
        'template.editor.mcp.dialog.fields.headers.hint': '標頭說明',
        'template.editor.mcp.dialog.fields.url.label': '伺服器 URL *',
        'template.editor.mcp.dialog.fields.url.placeholderHttp': '例如：https://api.example.com/mcp',
        'template.editor.mcp.dialog.fields.url.placeholderSse': '例如：https://api.example.com/sse',
        'template.editor.mcp.dialog.fields.url.hintHttp': '完整的 HTTP/HTTPS 端點。',
        'template.editor.mcp.dialog.fields.url.hintSse': '完整的 SSE 端點網址。',
        'template.editor.mcp.dialog.transport.label': '傳輸類型 *',
        'template.editor.mcp.dialog.transport.options.stdio.label': 'Stdio',
        'template.editor.mcp.dialog.transport.options.stdio.description': 'stdio',
        'template.editor.mcp.dialog.transport.options.http.label': 'HTTP',
        'template.editor.mcp.dialog.transport.options.http.description': 'http',
        'template.editor.mcp.dialog.transport.options.sse.label': 'SSE',
        'template.editor.mcp.dialog.transport.options.sse.description': 'sse',
        'template.editor.mcp.dialog.actions.create': '新增',
        'template.editor.mcp.dialog.actions.save': '儲存變更',
        'template.editor.mcp.dialog.validation.nameRequired': '伺服器名稱為必填項。',
        'template.editor.mcp.dialog.validation.descriptionRequired': '描述為必填項。',
        'template.editor.mcp.dialog.validation.commandRequired': 'Stdio 傳輸需填寫執行命令。',
        'template.editor.mcp.dialog.validation.urlRequired': 'HTTP 或 SSE 傳輸需填寫伺服器 URL。',
        'template.editor.mcp.dialog.validation.saveFailed': '儲存失敗',
      };

      if (key.endsWith('.placeholder') && options?.index) {
        return `參數 ${options.index}`;
      }

      return map[key] ?? key;
    },
  }),
}));

const renderWorkspaceDialog = (server: WorkspaceMCPServerData | null, mode: 'create' | 'edit' = 'create') =>
  render(
    <MCPServerDialog
      open
      mode={mode}
      server={server}
      onClose={vi.fn()}
      onSubmit={vi.fn().mockResolvedValue(undefined)}
    />
  );

const renderTemplateDialog = (initialData?: TemplateMCPServerData) =>
  render(
    <MCPServerDialog
      variant="template"
      open
      initialData={initialData}
      onOpenChange={vi.fn()}
      onSave={vi.fn()}
    />
  );

describe('MCPServerDialog', () => {
  it('新增環境變數時建立空白列', async () => {
    const user = userEvent.setup();

    renderWorkspaceDialog(null, 'create');

    await user.click(screen.getByRole('button', { name: '添加變數' }));

    const keyInputs = screen.getAllByPlaceholderText('變數名稱');
    const valueInputs = screen.getAllByPlaceholderText('變數值');

    expect(keyInputs.at(-1)).toHaveValue('');
    expect(valueInputs.at(-1)).toHaveValue('');
  });

  it('編輯環境變數名稱時保留原 input focus', async () => {
    const user = userEvent.setup();

    renderWorkspaceDialog({
      id: 'project:test-server',
      name: 'test-server',
      scope: 'project',
      transport: 'stdio',
      command: 'npx',
      env: {
        FOO: 'bar',
      },
    }, 'edit');

    const envKeyInput = screen.getByDisplayValue('FOO');

    await user.click(envKeyInput);
    await user.type(envKeyInput, 'BAR');

    expect(envKeyInput).toHaveValue('FOOBAR');
    expect(document.activeElement).toBe(envKeyInput);
  });

  it('編輯 HTTP 標頭名稱時保留原 input focus', async () => {
    const user = userEvent.setup();

    renderTemplateDialog({
      localId: 'template-server',
      name: 'template-server',
      type: 'http',
      command: '',
      argsText: '',
      url: 'https://example.com/mcp',
      description: 'desc',
      envText: '',
      headersText: 'Authorization: Bearer token',
    });

    const headerKeyInput = screen.getByDisplayValue('Authorization');

    await user.click(headerKeyInput);
    await user.type(headerKeyInput, '-Extra');

    expect(headerKeyInput).toHaveValue('Authorization-Extra');
    expect(document.activeElement).toBe(headerKeyInput);
  });
});
