import {
  createMCPKeyValueRows,
  parseMCPArgsText,
  type MCPKeyValueRow,
  type MCPTransport,
} from '@/shared/components/mcp-workflow';
import type { MarketplacePackageFile } from '@/shared/types/marketplace';
import {
  marketplaceEditorItemDescription,
  marketplaceEditorItemTitle,
  type MarketplaceEditorResourceItem,
} from './marketplaceEditorResourceItems';

export interface MarketplaceMCPServerValue {
  name: string;
  description: string;
  transport: MCPTransport;
  command: string;
  args: string[];
  url: string;
  env: MCPKeyValueRow[];
  headers: MCPKeyValueRow[];
}

const marketplaceRecordFromJsonContent = (content: string): Record<string, unknown> | null => {
  try {
    const value: unknown = JSON.parse(content);
    if (value && typeof value === 'object' && !Array.isArray(value)) {
      return value as Record<string, unknown>;
    }
  } catch {
    return null;
  }
  return null;
};

const marketplaceStringValue = (value: unknown): string | undefined => (
  typeof value === 'string' ? value : undefined
);

const marketplaceStringArrayValue = (value: unknown): string[] => {
  if (Array.isArray(value)) {
    return value.filter((entry): entry is string => typeof entry === 'string');
  }
  return typeof value === 'string' ? parseMCPArgsText(value) : [];
};

const marketplaceKeyValueRowsFromRecord = (value: unknown): MCPKeyValueRow[] => {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return [];
  }
  return createMCPKeyValueRows(
    Object.fromEntries(
      Object.entries(value as Record<string, unknown>)
        .filter(([, entry]) => typeof entry === 'string')
        .map(([key, entry]) => [key, entry as string]),
    ),
  );
};

const marketplaceMcpTransportValue = (value: unknown, url: string): MCPTransport => {
  if (value === 'stdio' || value === 'sse' || value === 'http') {
    return value;
  }
  return url ? 'http' : 'stdio';
};

export const marketplaceMcpServerValueFromItem = (
  item: MarketplaceEditorResourceItem,
  t: (key: string) => string,
): MarketplaceMCPServerValue => {
  const data = marketplaceRecordFromJsonContent(item.content) ?? {};
  const url = marketplaceStringValue(data.url) ?? '';
  const command = marketplaceStringValue(data.command) ?? (item.code ?? '').split(' ')[0] ?? '';
  const args = marketplaceStringArrayValue(data.args);
  const fallbackArgs = parseMCPArgsText((item.code ?? '').split(' ').slice(1).join('\n'));
  const initialEnvKey = item.meta?.find(meta => meta.labelKey === 'marketplace.editor.featureMeta.labels.env')?.value ?? '';
  const env = marketplaceKeyValueRowsFromRecord(data.env);
  const transport = marketplaceMcpTransportValue(
    data.transport ?? item.meta?.find(meta => meta.labelKey === 'marketplace.editor.featureMeta.labels.transport')?.value ?? item.badge,
    url,
  );

  return {
    name: marketplaceStringValue(data.name) ?? marketplaceEditorItemTitle(item, t),
    description: marketplaceStringValue(data.description) ?? marketplaceEditorItemDescription(item, t),
    transport,
    command,
    args: args.length > 0 ? args : fallbackArgs,
    url,
    env: env.length > 0 ? env : (initialEnvKey ? createMCPKeyValueRows({ [initialEnvKey]: '${workspaceFolder}' }) : []),
    headers: marketplaceKeyValueRowsFromRecord(data.headers),
  };
};

const marketplaceMcpRecordFromValue = (value: MarketplaceMCPServerValue): Record<string, unknown> => ({
  ...(value.name.trim() ? { name: value.name.trim() } : {}),
  ...(value.description.trim() ? { description: value.description.trim() } : {}),
  ...(value.transport ? { transport: value.transport } : {}),
  ...(value.command.trim() ? { command: value.command.trim() } : {}),
  ...(value.args.length > 0 ? { args: value.args.filter(Boolean) } : {}),
  ...(value.url.trim() ? { url: value.url.trim() } : {}),
  ...(value.env.some(row => row.key.trim()) ? {
    env: Object.fromEntries(value.env.filter(row => row.key.trim()).map(row => [row.key.trim(), row.value])),
  } : {}),
  ...(value.headers.some(row => row.key.trim()) ? {
    headers: Object.fromEntries(value.headers.filter(row => row.key.trim()).map(row => [row.key.trim(), row.value])),
  } : {}),
});

export const marketplaceMcpServerContentFromValue = (value: MarketplaceMCPServerValue): string => (
  JSON.stringify(marketplaceMcpRecordFromValue(value), null, 2)
);

export const marketplaceMcpResourceItemFromValue = (
  item: MarketplaceEditorResourceItem,
  value: MarketplaceMCPServerValue,
): MarketplaceEditorResourceItem => {
  const commandText = [value.command, ...value.args].filter(Boolean).join(' ');
  return {
    ...item,
    title: value.name,
    description: value.description,
    content: marketplaceMcpServerContentFromValue(value),
    badge: value.transport,
    code: commandText,
    meta: [
      { labelKey: 'marketplace.editor.featureMeta.labels.transport', value: value.transport },
      ...(value.env[0]?.key ? [{ labelKey: 'marketplace.editor.featureMeta.labels.env', value: value.env[0].key }] : []),
    ],
  };
};

export const marketplaceApplyMcpItemsToPackageFiles = (
  files: MarketplacePackageFile[],
  items: MarketplaceEditorResourceItem[],
): MarketplacePackageFile[] => {
  const fileMap = new Map(files.map(file => [file.path, { ...file }]));
  const rootMcpPaths = new Set(['.mcp.json', 'mcp.json']);
  const rootItems = items.filter(item => rootMcpPaths.has(item.path));
  const standaloneItems = items.filter(item => !rootMcpPaths.has(item.path));

  if (rootItems.length > 0) {
    const rootPath = rootItems[0].path;
    const existing = marketplaceRecordFromJsonContent(fileMap.get(rootPath)?.content ?? '') ?? {};
    const existingServers = existing.mcpServers && typeof existing.mcpServers === 'object' && !Array.isArray(existing.mcpServers)
      ? (existing.mcpServers as Record<string, unknown>)
      : {};
    const mcpServers = { ...existingServers };
    rootItems.forEach(item => {
      const serverName = item.title || item.id.split(':').pop() || item.id;
      const serverConfig = marketplaceRecordFromJsonContent(item.content) ?? {};
      mcpServers[serverName] = serverConfig;
    });
    const content = JSON.stringify({ ...existing, mcpServers }, null, 2) + '\n';
    fileMap.set(rootPath, {
      path: rootPath,
      content,
      binary: false,
      mimeType: 'application/json',
      size: content.length,
    });
  }

  standaloneItems.forEach(item => {
    fileMap.set(item.path, {
      path: item.path,
      content: item.content,
      binary: false,
      mimeType: 'application/json',
      size: item.content.length,
    });
  });

  return Array.from(fileMap.values()).sort((first, second) => first.path.localeCompare(second.path));
};
