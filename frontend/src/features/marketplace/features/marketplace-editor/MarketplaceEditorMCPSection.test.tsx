import { fireEvent, render, screen } from '@testing-library/react';
import { Network } from 'lucide-react';
import { describe, expect, it, vi } from 'vitest';

import { MarketplaceEditorMCPSection } from './MarketplaceEditorMCPSection';
import {
  marketplaceMCPResourceItemFromValue,
  marketplaceMCPServerContentFromValue,
  type MarketplaceMCPServerValue,
} from './marketplaceMCPServerDialogSchema';
import type { MarketplaceEditorResourceItem } from './marketplaceEditorResourceItems';

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

const value: MarketplaceMCPServerValue = {
  name: 'repo-context',
  description: 'Repository context',
  transport: 'stdio',
  command: 'node',
  args: ['servers/repo.js'],
  url: '',
  env: [{ id: 'env-1', key: 'REPOSITORY_ROOT', value: '${workspaceFolder}' }],
  headers: [],
};

describe('MarketplaceEditorMCPSection helpers', () => {
  it('renders through the shared settings list workbench shell', () => {
    const onRefresh = vi.fn();
    render(
      <MarketplaceEditorMCPSection icon={Network} items={[]} onDirty={() => undefined} onItemsChange={() => undefined} onRefresh={onRefresh} />,
    );

    expect(screen.getByText('marketplace.editor.tabs.mcp')).toBeInTheDocument();
    expect(screen.getByText('marketplace.editor.featureSections.mcp.emptyTitle')).toBeInTheDocument();
    expect(screen.getByText('marketplace.editor.featureSections.mcp.emptyDescription')).toBeInTheDocument();
    expect(screen.queryAllByRole('button', { name: 'marketplace.common.actions.refresh' })).toHaveLength(1);
    fireEvent.click(screen.getByRole('button', { name: 'marketplace.common.actions.refresh' }));
    expect(onRefresh).toHaveBeenCalled();
    const addButton = screen.getByRole('button', { name: 'marketplace.editor.featureSections.actions.add' });
    expect(addButton).toHaveClass('bg-primary');
  });

  it('serializes MCP values and updates resource item metadata', () => {
    const item: MarketplaceEditorResourceItem = {
      id: 'repo-context',
      title: 'old',
      description: 'old',
      path: 'mcp/repo-context.json',
      content: '{}',
    };

    expect(JSON.parse(marketplaceMCPServerContentFromValue(value))).toEqual({
      name: 'repo-context',
      description: 'Repository context',
      transport: 'stdio',
      command: 'node',
      args: ['servers/repo.js'],
      env: {
        REPOSITORY_ROOT: '${workspaceFolder}',
      },
    });

    expect(marketplaceMCPResourceItemFromValue(item, value)).toEqual(expect.objectContaining({
      title: 'repo-context',
      description: 'Repository context',
      badge: 'stdio',
      code: 'node servers/repo.js',
      meta: [
        { labelKey: 'marketplace.editor.featureMeta.labels.transport', value: 'stdio' },
        { labelKey: 'marketplace.editor.featureMeta.labels.env', value: 'REPOSITORY_ROOT' },
      ],
    }));
  });
});
