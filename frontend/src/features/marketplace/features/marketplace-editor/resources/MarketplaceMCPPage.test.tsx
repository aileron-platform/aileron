import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { MarketplaceMCPPage } from './MarketplaceMCPPage';
import type { MarketplacePackageDetail } from '@/features/marketplace/model/marketplaceTypes';

const apiMock = vi.hoisted(() => ({
  createMCPServer: vi.fn(),
  deleteMCPServer: vi.fn(),
  getMCPServer: vi.fn(),
  listMCPServers: vi.fn(),
  saveMCPServer: vi.fn(),
}));

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

vi.mock('../../../api/marketplaceApi', () => ({
  createMCPServer: (...args: unknown[]) => apiMock.createMCPServer(...args),
  deleteMCPServer: (...args: unknown[]) => apiMock.deleteMCPServer(...args),
  getMCPServer: (...args: unknown[]) => apiMock.getMCPServer(...args),
  listMCPServers: (...args: unknown[]) => apiMock.listMCPServers(...args),
  saveMCPServer: (...args: unknown[]) => apiMock.saveMCPServer(...args),
}));

vi.mock('../MarketplaceEditorMCPSection', () => ({
  MarketplaceEditorMCPSection: ({ items, onItemsChange, onLoadItem }: {
    items: Array<{
      id: string;
      title: string;
      path: string;
      content: string;
      ownerFilePath?: string;
      baseEntryFingerprint?: string;
    }>;
    onItemsChange?: (items: Array<{
      id: string;
      title: string;
      path: string;
      content: string;
      ownerFilePath?: string;
      baseEntryFingerprint?: string;
    }>) => Promise<void>;
    onLoadItem?: (item: {
      id: string;
      title: string;
      path: string;
      content: string;
      ownerFilePath?: string;
      baseEntryFingerprint?: string;
    }) => Promise<{
      id: string;
      title: string;
      path: string;
      content: string;
      ownerFilePath?: string;
      baseEntryFingerprint?: string;
    }>;
  }) => (
    <>
      <span>mcp-count:{items.length}</span>
      <span data-testid="mcp-item-ids">{items.map(item => item.id).join('|')}</span>
      <button
      type="button"
      onClick={() => {
        void (async () => {
          if (items.length > 0) {
            const loaded = onLoadItem ? await onLoadItem(items[0]) : items[0];
            await onItemsChange?.(items.map((item, index) => (
              index === 0
                ? {
                    ...loaded,
                    content: JSON.stringify({
                      name: loaded.title,
                      command: 'node',
                      args: ['updated.js'],
                    }),
                  }
                : item
            )));
            return;
          }
          await onItemsChange?.([
              {
                id: 'local-server',
                title: 'local-server',
                path: 'mcp/local-server.json',
                content: JSON.stringify({ name: 'local-server', command: 'node', args: ['server.js'] }),
              },
          ]);
        })().catch(() => undefined);
      }}
    >
      submit-mcp-dialog
      </button>
      {items.length > 0 ? (
        <button
          type="button"
          onClick={() => {
            void onItemsChange?.(items.slice(1)).catch(() => undefined);
          }}
        >
          delete-first-mcp
        </button>
      ) : null}
    </>
  ),
}));

const packageDetail = (): MarketplacePackageDetail => ({
  provider: 'codex',
  packageType: 'plugin',
  packageId: 'codex-toolkit',
  displayName: 'Codex Toolkit',
  version: '0.1.0',
  description: 'Package description',
  category: 'coding',
  tags: [],
  sourceType: 'created',
  indexedResourceNames: [],
  validationSeverity: 'none',
  lifecycleStatus: 'draft',
  registryPath: 'codex/plugins/codex-toolkit',
  revision: 'rev1',
  updatedAt: '2026-06-26T00:00:00.000Z',
  variants: [],
  catalogMetadata: {},
  manifestMetadata: {},
  validationResults: [],
});

const mutationResult = (
  revision = 'rev2',
  baseEntryFingerprint: string | null = 'new-fp',
) => ({
  success: true as const,
  path: '.mcp.json',
  revision,
  ownerFilePath: '.mcp.json',
  baseEntryFingerprint,
});

const deferred = <T,>() => {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((resolvePromise) => {
    resolve = resolvePromise;
  });
  return { promise, resolve };
};

describe('MarketplaceMCPPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    apiMock.listMCPServers.mockResolvedValue([]);
  });

  it('creates an MCP server when the dialog submits', async () => {
    const user = userEvent.setup();
    const onMutation = vi.fn().mockResolvedValue(undefined);
    const result = mutationResult();
    apiMock.createMCPServer.mockResolvedValueOnce(result);

    const { container } = render(
      <MarketplaceMCPPage
        packageDetail={packageDetail()}
        onMutation={onMutation}
      />,
    );

    await screen.findByRole(
      'button',
      { name: 'submit-mcp-dialog' },
      { timeout: 10_000 },
    );
    expect(container.firstElementChild).toHaveClass('flex-1');
    expect(screen.queryByRole('button', { name: 'marketplace.common.actions.save' })).not.toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'submit-mcp-dialog' }));

    expect(apiMock.createMCPServer).toHaveBeenCalledWith('codex', 'codex-toolkit', expect.objectContaining({
      revision: 'rev1',
      name: 'local-server',
      server: expect.objectContaining({ command: 'node' }),
    }));
    expect(onMutation).toHaveBeenCalledWith(result);
    expect(onMutation).toHaveBeenCalledTimes(1);
  });

  it('updates an existing captured MCP server by server name with source tokens', async () => {
    const user = userEvent.setup();
    const onMutation = vi.fn().mockResolvedValue(undefined);
    apiMock.listMCPServers.mockResolvedValueOnce([{
      name: 'ASDF',
      path: '.mcp.json',
      ownerFilePath: '.mcp.json',
      baseEntryFingerprint: 'entry-fp',
    }]);
    apiMock.getMCPServer.mockResolvedValueOnce({
      name: 'ASDF',
      path: '.mcp.json',
      server: { command: 'node' },
      ownerFilePath: '.mcp.json',
      baseEntryFingerprint: 'entry-fp',
    });
    const result = mutationResult();
    apiMock.saveMCPServer.mockResolvedValueOnce(result);

    render(
      <MarketplaceMCPPage
        packageDetail={packageDetail()}
        onMutation={onMutation}
      />,
    );

    expect(await screen.findByTestId('mcp-item-ids')).toHaveTextContent(
      '["ASDF",".mcp.json"]',
    );
    await user.click(await screen.findByRole(
      'button',
      { name: 'submit-mcp-dialog' },
      { timeout: 10_000 },
    ));

    expect(apiMock.getMCPServer).toHaveBeenCalledWith(
      'codex',
      'codex-toolkit',
      'ASDF',
      '.mcp.json',
    );
    expect(apiMock.createMCPServer).not.toHaveBeenCalled();
    expect(apiMock.saveMCPServer).toHaveBeenCalledWith('codex', 'codex-toolkit', 'ASDF', {
      revision: 'rev1',
      server: expect.objectContaining({ command: 'node' }),
      ownerFilePath: '.mcp.json',
      baseEntryFingerprint: 'entry-fp',
    });
    expect(onMutation).toHaveBeenCalledWith(result);
    expect(onMutation).toHaveBeenCalledTimes(1);
  });

  it('deletes the selected MCP owner with canonical source tokens', async () => {
    const user = userEvent.setup();
    const onMutation = vi.fn().mockResolvedValue(undefined);
    apiMock.listMCPServers.mockResolvedValueOnce([{
      name: 'ASDF',
      path: '.mcp.json',
      ownerFilePath: '.mcp.json',
      baseEntryFingerprint: 'entry-fp',
    }]);
    const result = mutationResult('rev2', null);
    apiMock.deleteMCPServer.mockResolvedValueOnce(result);

    render(
      <MarketplaceMCPPage
        packageDetail={packageDetail()}
        onMutation={onMutation}
      />,
    );

    await user.click(await screen.findByRole('button', { name: 'delete-first-mcp' }));

    expect(apiMock.deleteMCPServer).toHaveBeenCalledWith(
      'codex',
      'codex-toolkit',
      'ASDF',
      {
        revision: 'rev1',
        ownerFilePath: '.mcp.json',
        baseEntryFingerprint: 'entry-fp',
      },
    );
    expect(onMutation).toHaveBeenCalledWith(result);
    expect(await screen.findByText('mcp-count:0')).toBeInTheDocument();
  });

  it('does not retain optimistic MCP state when persistence fails', async () => {
    const user = userEvent.setup();
    apiMock.createMCPServer.mockRejectedValueOnce(new Error('save failed'));
    const onMutation = vi.fn();
    render(
      <MarketplaceMCPPage
        packageDetail={packageDetail()}
        onMutation={onMutation}
      />,
    );

    await user.click(await screen.findByRole('button', { name: 'submit-mcp-dialog' }));

    expect(await screen.findByText('mcp-count:0')).toBeInTheDocument();
    expect(onMutation).not.toHaveBeenCalled();
  });

  it('ignores stale MCP list completion after package identity changes', async () => {
    const stale = deferred<Array<{
      name: string;
      path: string;
      ownerFilePath: string;
      baseEntryFingerprint: string;
    }>>();
    const current = deferred<Array<{
      name: string;
      path: string;
      ownerFilePath: string;
      baseEntryFingerprint: string;
    }>>();
    apiMock.listMCPServers
      .mockReturnValueOnce(stale.promise)
      .mockReturnValueOnce(current.promise);

    const { rerender } = render(
      <MarketplaceMCPPage
        packageDetail={packageDetail()}
        onMutation={vi.fn()}
      />,
    );
    await waitFor(() => expect(apiMock.listMCPServers).toHaveBeenCalledTimes(1));

    rerender(
      <MarketplaceMCPPage
        packageDetail={{
          ...packageDetail(),
          packageId: 'current-toolkit',
          revision: 'current-rev',
        }}
        onMutation={vi.fn()}
      />,
    );
    await waitFor(() => expect(apiMock.listMCPServers).toHaveBeenCalledTimes(2));

    current.resolve([
      {
        name: 'current-a',
        path: '.mcp.json',
        ownerFilePath: '.mcp.json',
        baseEntryFingerprint: 'a',
      },
      {
        name: 'current-b',
        path: '.mcp.json',
        ownerFilePath: '.mcp.json',
        baseEntryFingerprint: 'b',
      },
    ]);
    expect(await screen.findByText('mcp-count:2')).toBeInTheDocument();

    stale.resolve([{
      name: 'stale',
      path: '.mcp.json',
      ownerFilePath: '.mcp.json',
      baseEntryFingerprint: 'stale',
    }]);
    await waitFor(() => {
      expect(screen.getByText('mcp-count:2')).toBeInTheDocument();
      expect(screen.queryByText('mcp-count:1')).not.toBeInTheDocument();
    });
  });
});
