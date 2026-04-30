import userEvent from '@testing-library/user-event';
import { render, screen, waitFor } from '@/__tests__/utils/render';
import { describe, expect, it, vi } from 'vitest';
import { TemplateMCPServerDialog } from './TemplateMCPServerDialog';

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string, options?: Record<string, string | number>) => {
      const map: Record<string, string> = {
        'common.cancel': 'Cancel',
        'template.editor.mcp.dialog.title.create': 'Add MCP Server',
        'template.editor.mcp.dialog.title.edit': 'Edit MCP Server',
        'template.editor.mcp.dialog.description.create': 'Create template MCP server',
        'template.editor.mcp.dialog.description.edit': 'Edit template MCP server',
        'template.editor.mcp.dialog.fields.name.label': 'Server name',
        'template.editor.mcp.dialog.fields.name.placeholder': 'Enter server name',
        'template.editor.mcp.dialog.fields.description.label': 'Description',
        'template.editor.mcp.dialog.fields.description.placeholder': 'Enter description',
        'template.editor.mcp.dialog.fields.command.label': 'Command',
        'template.editor.mcp.dialog.fields.command.placeholder': 'python -m server',
        'template.editor.mcp.dialog.fields.args.label': 'Arguments',
        'template.editor.mcp.dialog.fields.args.add': 'Add argument',
        'template.editor.mcp.dialog.fields.args.empty': 'No arguments',
        'template.editor.mcp.dialog.fields.env.label': 'Environment',
        'template.editor.mcp.dialog.fields.env.add': 'Add variable',
        'template.editor.mcp.dialog.fields.env.keyPlaceholder': 'Variable name',
        'template.editor.mcp.dialog.fields.env.valuePlaceholder': 'Variable value',
        'template.editor.mcp.dialog.fields.env.empty': 'No environment',
        'template.editor.mcp.dialog.fields.headers.label': 'Headers',
        'template.editor.mcp.dialog.fields.headers.add': 'Add header',
        'template.editor.mcp.dialog.fields.headers.keyPlaceholder': 'Header name',
        'template.editor.mcp.dialog.fields.headers.valuePlaceholder': 'Header value',
        'template.editor.mcp.dialog.fields.headers.empty': 'No headers',
        'template.editor.mcp.dialog.fields.headers.hint': 'Header hint',
        'template.editor.mcp.dialog.fields.url.label': 'Server URL',
        'template.editor.mcp.dialog.fields.url.placeholderHttp': 'https://api.example.com/mcp',
        'template.editor.mcp.dialog.fields.url.placeholderSse': 'https://api.example.com/sse',
        'template.editor.mcp.dialog.fields.url.hintHttp': 'HTTP URL',
        'template.editor.mcp.dialog.fields.url.hintSse': 'SSE URL',
        'template.editor.mcp.dialog.transport.label': 'Transport',
        'template.editor.mcp.dialog.transport.options.stdio.label': 'Stdio',
        'template.editor.mcp.dialog.transport.options.stdio.description': 'stdio',
        'template.editor.mcp.dialog.transport.options.http.label': 'HTTP',
        'template.editor.mcp.dialog.transport.options.http.description': 'http',
        'template.editor.mcp.dialog.transport.options.sse.label': 'SSE',
        'template.editor.mcp.dialog.transport.options.sse.description': 'sse',
        'template.editor.mcp.dialog.actions.create': 'Create',
        'template.editor.mcp.dialog.actions.save': 'Save changes',
        'template.editor.mcp.dialog.validation.nameRequired': 'Name is required.',
        'template.editor.mcp.dialog.validation.descriptionRequired': 'Description is required.',
        'template.editor.mcp.dialog.validation.commandRequired': 'Command is required.',
        'template.editor.mcp.dialog.validation.urlRequired': 'URL is required.',
        'template.editor.mcp.dialog.validation.saveFailed': 'Save failed',
      };

      if (key.endsWith('.placeholder') && options?.index) {
        return `Argument ${options.index}`;
      }

      return map[key] ?? key;
    },
  }),
}));

describe('TemplateMCPServerDialog', () => {
  it('keeps HTTP header input focus while editing an existing row', async () => {
    const user = userEvent.setup();

    render(
      <TemplateMCPServerDialog
        open
        initialData={{
          localId: 'template-server',
          name: 'template-server',
          type: 'http',
          command: '',
          argsText: '',
          url: 'https://example.com/mcp',
          description: 'desc',
          envText: '',
          headersText: 'Authorization: Bearer token',
        }}
        onOpenChange={vi.fn()}
        onSave={vi.fn()}
      />,
    );

    const headerKeyInput = screen.getByDisplayValue('Authorization');

    await user.click(headerKeyInput);
    await user.type(headerKeyInput, '-Extra');

    expect(headerKeyInput).toHaveValue('Authorization-Extra');
    expect(document.activeElement).toBe(headerKeyInput);
  });

  it('submits the template payload using text fields', async () => {
    const user = userEvent.setup();
    const onOpenChange = vi.fn();
    const onSave = vi.fn();

    render(
      <TemplateMCPServerDialog
        open
        onOpenChange={onOpenChange}
        onSave={onSave}
      />,
    );

    await user.type(screen.getByPlaceholderText('Enter server name'), 'template-server');
    await user.type(screen.getByPlaceholderText('Enter description'), 'desc');
    await user.type(screen.getByPlaceholderText('python -m server'), ' python -m server ');
    await user.click(screen.getByRole('button', { name: 'Add argument' }));
    await user.type(screen.getByPlaceholderText('Argument 1'), ' --debug ');
    await user.click(screen.getByRole('button', { name: 'Add variable' }));
    await user.type(screen.getByPlaceholderText('Variable name'), 'TOKEN');
    await user.type(screen.getByPlaceholderText('Variable value'), 'abc');
    await user.click(screen.getByRole('button', { name: 'Create' }));

    await waitFor(() => {
      expect(onSave).toHaveBeenCalledWith(expect.objectContaining({
        name: 'template-server',
        type: 'stdio',
        command: 'python -m server',
        argsText: '--debug',
        url: '',
        description: 'desc',
        envText: 'TOKEN=abc',
        headersText: '',
      }));
      expect(onOpenChange).toHaveBeenCalledWith(false);
    });
  });

  it('shows description validation and does not save an incomplete template payload', async () => {
    const user = userEvent.setup();
    const onSave = vi.fn();

    render(
      <TemplateMCPServerDialog
        open
        onOpenChange={vi.fn()}
        onSave={onSave}
      />,
    );

    await user.type(screen.getByPlaceholderText('Enter server name'), 'template-server');
    await user.click(screen.getByRole('button', { name: 'Create' }));

    expect(screen.getByText('Description is required.')).toBeInTheDocument();
    expect(onSave).not.toHaveBeenCalled();
  });
});
