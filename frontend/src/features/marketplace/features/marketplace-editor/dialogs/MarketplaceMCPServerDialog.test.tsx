import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@/__tests__/utils/render';
import { MarketplaceMCPServerDialog } from './MarketplaceMCPServerDialog';
import type { MarketplaceEditorResourceItem } from '../marketplaceEditorResourceItems';

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string, options?: Record<string, string | number>) => {
      const map: Record<string, string> = {
        'marketplace.common.actions.cancel': 'Cancel',
        'marketplace.editor.mcp.dialog.titleCreate': 'Add MCP server',
        'marketplace.editor.mcp.dialog.title': 'Edit MCP server',
        'marketplace.editor.mcp.dialog.descriptionCreate': 'Create an MCP server definition.',
        'marketplace.editor.mcp.dialog.description': 'Update an MCP server definition.',
        'marketplace.editor.mcp.dialog.fields.name.label': 'Name',
        'marketplace.editor.mcp.dialog.fields.name.placeholder': 'repository-context',
        'marketplace.editor.mcp.dialog.fields.name.hint': 'Name hint',
        'marketplace.editor.mcp.dialog.fields.description.label': 'Description',
        'marketplace.editor.mcp.dialog.fields.description.placeholder': 'Describe the server',
        'marketplace.editor.mcp.dialog.fields.scope.label': 'Scope',
        'marketplace.editor.mcp.dialog.transport.label': 'Transport',
        'marketplace.editor.mcp.dialog.transport.options.stdio.label': 'Standard I/O',
        'marketplace.editor.mcp.dialog.transport.options.stdio.description': 'stdio',
        'marketplace.editor.mcp.dialog.transport.options.http.label': 'HTTP',
        'marketplace.editor.mcp.dialog.transport.options.http.description': 'http',
        'marketplace.editor.mcp.dialog.transport.options.sse.label': 'SSE',
        'marketplace.editor.mcp.dialog.transport.options.sse.description': 'sse',
        'marketplace.editor.mcp.dialog.fields.command.label': 'Command',
        'marketplace.editor.mcp.dialog.fields.command.placeholder': 'npx',
        'marketplace.editor.mcp.dialog.fields.args.label': 'Arguments',
        'marketplace.editor.mcp.dialog.fields.args.add': 'Add argument',
        'marketplace.editor.mcp.dialog.fields.args.empty': 'No arguments',
        'marketplace.editor.mcp.dialog.fields.url.label': 'URL',
        'marketplace.editor.mcp.dialog.fields.url.placeholderHttp': 'https://example.com/mcp',
        'marketplace.editor.mcp.dialog.fields.url.placeholderSse': 'https://example.com/sse',
        'marketplace.editor.mcp.dialog.fields.url.hintHttp': 'HTTP URL',
        'marketplace.editor.mcp.dialog.fields.url.hintSse': 'SSE URL',
        'marketplace.editor.mcp.dialog.fields.headers.label': 'Headers',
        'marketplace.editor.mcp.dialog.fields.headers.add': 'Add header',
        'marketplace.editor.mcp.dialog.fields.headers.keyPlaceholder': 'Header name',
        'marketplace.editor.mcp.dialog.fields.headers.valuePlaceholder': 'Header value',
        'marketplace.editor.mcp.dialog.fields.headers.empty': 'No headers',
        'marketplace.editor.mcp.dialog.fields.headers.hint': 'Header hint',
        'marketplace.editor.mcp.dialog.fields.env.label': 'Environment',
        'marketplace.editor.mcp.dialog.fields.env.add': 'Add variable',
        'marketplace.editor.mcp.dialog.fields.env.keyPlaceholder': 'Variable name',
        'marketplace.editor.mcp.dialog.fields.env.valuePlaceholder': 'Variable value',
        'marketplace.editor.mcp.dialog.fields.env.empty': 'No environment',
        'marketplace.editor.mcp.dialog.actions.create': 'Create server',
        'marketplace.editor.mcp.dialog.actions.save': 'Save server',
        'marketplace.editor.mcp.dialog.validation.nameRequired': 'Name is required.',
        'marketplace.editor.mcp.dialog.validation.descriptionRequired': 'Description is required.',
        'marketplace.editor.mcp.dialog.validation.commandRequired': 'Command is required.',
        'marketplace.editor.mcp.dialog.validation.urlRequired': 'URL is required.',
        'marketplace.editor.mcp.dialog.validation.saveFailed': 'Save failed.',
      };

      if (key.endsWith('.placeholder') && options?.index) {
        return `Argument ${options.index}`;
      }

      return map[key] ?? key;
    },
  }),
}));

const renderDialog = (
  item: MarketplaceEditorResourceItem | null,
  mode: 'create' | 'edit' = 'create',
  onSubmit = vi.fn().mockResolvedValue(undefined),
) => {
  render(
    <MarketplaceMCPServerDialog
      open
      mode={mode}
      item={item}
      onClose={vi.fn()}
      onSubmit={onSubmit}
    />,
  );

  return { onSubmit };
};

describe('MarketplaceMCPServerDialog', () => {
  it('hides scope selection and validates description in create mode', async () => {
    const user = userEvent.setup();
    renderDialog(null);

    expect(screen.queryByText('Scope')).not.toBeInTheDocument();

    await user.type(screen.getByLabelText('Name'), 'repo-context');
    await user.type(screen.getByPlaceholderText('npx'), 'npx');
    await user.click(screen.getByRole('button', { name: 'Create server' }));

    expect(screen.getByText('Description is required.')).toBeInTheDocument();
  });

  it('submits a marketplace resource item through the shared dialog payload', async () => {
    const user = userEvent.setup();
    const { onSubmit } = renderDialog(null);

    await user.type(screen.getByLabelText('Name'), 'repo-context');
    await user.type(screen.getByLabelText('Description'), 'Repository context server');
    await user.type(screen.getByPlaceholderText('npx'), 'npx');
    await user.click(screen.getByRole('button', { name: 'Add argument' }));
    await user.type(screen.getByPlaceholderText('Argument 1'), '--stdio');
    await user.click(screen.getByRole('button', { name: 'Create server' }));

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({
        title: 'repo-context',
        description: 'Repository context server',
        path: 'mcp/repo-context.json',
        badge: 'stdio',
        code: 'npx --stdio',
      }));
    });
  });

  it('keeps the name field read-only in edit mode', async () => {
    renderDialog({
      id: 'figma-context',
      title: 'figma-context',
      description: 'Figma context',
      path: 'mcp/figma-context.json',
      content: JSON.stringify({
        name: 'figma-context',
        description: 'Figma context',
        transport: 'http',
        url: 'https://api.figma.com/mcp',
      }),
    }, 'edit');

    expect(screen.getByLabelText('Name')).toBeDisabled();
  });
});
