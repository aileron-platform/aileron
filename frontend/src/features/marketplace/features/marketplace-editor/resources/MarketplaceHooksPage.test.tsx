import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { MarketplaceHooksPage } from './MarketplaceHooksPage';
import type { MarketplacePackageDetail } from '@/features/marketplace/model/marketplaceTypes';

const apiMock = vi.hoisted(() => ({
  getHooks: vi.fn(),
  updateHooks: vi.fn(),
}));

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

vi.mock('../../../api/marketplaceApi', () => ({
  getHooks: (...args: unknown[]) => apiMock.getHooks(...args),
  updateHooks: (...args: unknown[]) => apiMock.updateHooks(...args),
}));

vi.mock('../MarketplaceEditorHookSection', () => ({
  MarketplaceEditorHookSection: ({ items, onItemsChange }: {
    items: Array<{ id: string; content: string; data?: Record<string, unknown> }>;
    onItemsChange?: (items: Array<{ id: string; content: string; data?: Record<string, unknown> }>) => Promise<void>;
  }) => (
    <>
      <span>hook-count:{items.length}</span>
      <button
        type="button"
        onClick={() => {
          void onItemsChange?.([
            ...items,
            {
              id: 'hook-two',
              content: JSON.stringify({ hooks: { Stop: [{ matcher: '*', hooks: [{ type: 'command', command: 'npm run verify' }] }] } }),
              data: {
                ...items[0]?.data,
                __marketplaceSourceEvent: 'Stop',
              },
            },
          ]).catch(() => undefined);
        }}
      >
        submit-hook-dialog
      </button>
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

const mutationResult = {
  success: true as const,
  path: 'hooks/hooks.json',
  revision: 'rev2',
  ownerFilePath: null,
  baseEntryFingerprint: null,
};

describe('MarketplaceHooksPage', () => {
  it('saves merged hook content when the hook dialog submits', async () => {
    const user = userEvent.setup();
    const onMutation = vi.fn().mockResolvedValue(undefined);
    apiMock.getHooks.mockResolvedValueOnce({
      revision: 'rev1',
      sources: [{
        sourceId: 'hooks/hooks.json#/hooks',
        sourceType: 'file',
        path: 'hooks/hooks.json',
        manifestPointer: '/hooks',
        content: JSON.stringify({
          hooks: {
            BeforeTool: [{ matcher: '*', hooks: [{ type: 'command', command: 'npm test' }] }],
          },
        }, null, 2),
        nativeContent: {
          BeforeTool: [{ matcher: '*', hooks: [{ type: 'command', command: 'npm test' }] }],
        },
        writable: true,
        diagnostics: [],
      }],
      hookCapabilities: { mode: 'sources', groups: ['hooks/hooks.json#/hooks'] },
    });
    apiMock.updateHooks.mockResolvedValueOnce(mutationResult);

    const { container } = render(
      <MarketplaceHooksPage
        packageDetail={packageDetail()}
        onMutation={onMutation}
      />,
    );

    await screen.findByRole(
      'button',
      { name: 'submit-hook-dialog' },
      { timeout: 10_000 },
    );
    expect(container.firstElementChild).toHaveClass('flex-1');
    expect(screen.queryByRole('button', { name: 'marketplace.common.actions.save' })).not.toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'submit-hook-dialog' }));

    expect(apiMock.updateHooks).toHaveBeenCalledWith('codex', 'codex-toolkit', expect.objectContaining({
      revision: 'rev1',
      sourceId: 'hooks/hooks.json#/hooks',
      content: expect.any(String),
    }));
    const submitted = JSON.parse(apiMock.updateHooks.mock.calls[0][2].content) as { hooks: Record<string, unknown> };
    expect(submitted.hooks).toHaveProperty('BeforeTool');
    expect(submitted.hooks).toHaveProperty('Stop');
    expect(onMutation).toHaveBeenCalledWith(mutationResult);
  });

  it('does not retain optimistic hook state when persistence fails', async () => {
    const user = userEvent.setup();
    apiMock.getHooks.mockResolvedValueOnce({
      revision: 'rev1',
      sources: [{
        sourceId: 'hooks/hooks.json#/hooks',
        sourceType: 'file',
        path: 'hooks/hooks.json',
        manifestPointer: '/hooks',
        content: JSON.stringify({
          hooks: {
            BeforeTool: [{ matcher: '*', hooks: [{ type: 'command', command: 'npm test' }] }],
          },
        }, null, 2),
        nativeContent: {
          BeforeTool: [{ matcher: '*', hooks: [{ type: 'command', command: 'npm test' }] }],
        },
        writable: true,
        diagnostics: [],
      }],
      hookCapabilities: { mode: 'sources', groups: ['hooks/hooks.json#/hooks'] },
    });
    apiMock.updateHooks.mockRejectedValueOnce(new Error('save failed'));
    const onMutation = vi.fn();
    render(
      <MarketplaceHooksPage
        packageDetail={packageDetail()}
        onMutation={onMutation}
      />,
    );

    await user.click(await screen.findByRole('button', { name: 'submit-hook-dialog' }));

    expect(await screen.findByText('hook-count:1')).toBeInTheDocument();
    expect(onMutation).not.toHaveBeenCalled();
  });
});
