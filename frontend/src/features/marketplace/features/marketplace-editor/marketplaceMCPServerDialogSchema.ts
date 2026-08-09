import {
  createMCPKeyValueRows,
  parseMCPArgsText,
  type MCPKeyValueRow,
  type MCPTransport,
} from '@/shared/components/mcp-workflow';
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

const marketplaceMCPTransportValue = (value: unknown, url: string): MCPTransport => {
  if (value === 'stdio' || value === 'sse' || value === 'http') {
    return value;
  }
  return url ? 'http' : 'stdio';
};

export const marketplaceMCPServerValueFromItem = (
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
  const transport = marketplaceMCPTransportValue(
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

const marketplaceMCPRecordFromValue = (value: MarketplaceMCPServerValue): Record<string, unknown> => ({
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

export const marketplaceMCPServerContentFromValue = (value: MarketplaceMCPServerValue): string => (
  JSON.stringify(marketplaceMCPRecordFromValue(value), null, 2)
);

export const marketplaceMCPResourceItemFromValue = (
  item: MarketplaceEditorResourceItem,
  value: MarketplaceMCPServerValue,
): MarketplaceEditorResourceItem => {
  const commandText = [value.command, ...value.args].filter(Boolean).join(' ');
  return {
    ...item,
    title: value.name,
    description: value.description,
    content: marketplaceMCPServerContentFromValue(value),
    badge: value.transport,
    code: commandText,
    meta: [
      { labelKey: 'marketplace.editor.featureMeta.labels.transport', value: value.transport },
      ...(value.env[0]?.key ? [{ labelKey: 'marketplace.editor.featureMeta.labels.env', value: value.env[0].key }] : []),
    ],
  };
};
