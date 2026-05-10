import { describe, expect, it } from 'vitest';

import {
  marketplaceApplyMcpItemsToPackageFiles,
  marketplaceMcpResourceItemFromValue,
  marketplaceMcpServerContentFromValue,
  type MarketplaceMCPServerValue,
} from './marketplaceMcpServerDialogSchema';
import type { MarketplaceEditorResourceItem } from './marketplaceEditorResourceItems';

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

describe('MarketplaceEditorMcpSection helpers', () => {
  it('serializes MCP values and updates resource item metadata', () => {
    const item: MarketplaceEditorResourceItem = {
      id: 'repo-context',
      title: 'old',
      description: 'old',
      path: 'mcp/repo-context.json',
      content: '{}',
    };

    expect(JSON.parse(marketplaceMcpServerContentFromValue(value))).toEqual({
      name: 'repo-context',
      description: 'Repository context',
      transport: 'stdio',
      command: 'node',
      args: ['servers/repo.js'],
      env: {
        REPOSITORY_ROOT: '${workspaceFolder}',
      },
    });

    expect(marketplaceMcpResourceItemFromValue(item, value)).toEqual(expect.objectContaining({
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

  it('merges root MCP entries while preserving standalone server files', () => {
    const files = marketplaceApplyMcpItemsToPackageFiles(
      [
        {
          path: '.mcp.json',
          content: JSON.stringify({ mcpServers: { existing: { command: 'node' } } }),
          binary: false,
          mimeType: 'application/json',
          size: 10,
        },
      ],
      [
        {
          id: 'root:repo-context',
          title: 'repo-context',
          path: '.mcp.json',
          content: marketplaceMcpServerContentFromValue(value),
        },
        {
          id: 'standalone',
          title: 'standalone',
          path: 'mcp/standalone.json',
          content: '{"name":"standalone"}',
        },
      ],
    );

    expect(JSON.parse(files.find(file => file.path === '.mcp.json')?.content ?? '{}')).toEqual({
      mcpServers: {
        existing: { command: 'node' },
        'repo-context': JSON.parse(marketplaceMcpServerContentFromValue(value)),
      },
    });
    expect(files.find(file => file.path === 'mcp/standalone.json')?.content).toBe('{"name":"standalone"}');
  });
});
