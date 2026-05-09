import React from 'react';
import { Copy, Database, Edit, Server, Trash2 } from 'lucide-react';

import { MarketplaceFeatureContentSection } from '../../components/MarketplaceFeatureContentSection';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/shared/components/ui/dialog';
import { Input } from '@/shared/components/ui/input';
import { Label } from '@/shared/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/shared/components/ui/select';
import { LoadingSpinner } from '@/shared/components/ui/LoadingSpinner';
import { useI18n } from '@/shared/hooks/useI18n';
import type { MarketplacePackageFile } from '@/shared/types/marketplace';
import {
  MCPTransportFieldsEditor,
  createMCPKeyValueRows,
  parseMCPArgsText,
  toMCPKeyValueRecord,
  type MCPKeyValueRow,
  type MCPTransport,
  type MCPTransportFieldsLabels,
} from '@/shared/components/mcp-workflow';

import {
  marketplaceEditorItemDescription,
  marketplaceEditorItemTitle,
  type MarketplaceEditorResourceItem,
} from './marketplaceEditorResourceItems';

export interface MarketplaceEditorMcpSectionProps {
  icon: React.ComponentType<{ className?: string }>;
  items: MarketplaceEditorResourceItem[];
  onDirty?: () => void;
  onItemsChange?: (items: MarketplaceEditorResourceItem[]) => void;
}

export const MarketplaceEditorMcpSection: React.FC<MarketplaceEditorMcpSectionProps> = ({ icon: Icon, items: initialItems, onDirty, onItemsChange }) => {
  const { t } = useI18n();
  const [items, setItems] = React.useState(initialItems);
  const [mcpDialogOpen, setMcpDialogOpen] = React.useState(false);

  React.useEffect(() => {
    setItems(initialItems);
  }, [initialItems]);

  const emptyMcpServer: MarketplaceMcpServerDialogValue = {
    name: '',
    description: '',
    transport: 'stdio',
    command: '',
    args: [],
    url: '',
    env: [],
    headers: [],
  };

  const addMcpServer = (value: MarketplaceMcpServerDialogValue) => {
    const id = `local-${Math.random().toString(36).slice(2, 10)}`;
    const commandText = [value.command, ...value.args].filter(Boolean).join(' ');
    const nextItems = [
      ...items,
      {
        id,
        titleKey: 'marketplace.editor.mcp.dialog.create.defaultTitle',
        descriptionKey: 'marketplace.editor.mcp.dialog.create.defaultDescription',
        title: value.name,
        description: value.description,
        path: `mcp/${value.name || id}.json`,
        content: marketplaceMcpServerContentFromValue(value),
        badge: value.transport,
        code: commandText,
        meta: [
          { labelKey: 'marketplace.editor.featureMeta.labels.transport', value: value.transport },
          ...(value.env[0]?.key ? [{ labelKey: 'marketplace.editor.featureMeta.labels.env', value: value.env[0].key }] : []),
        ],
      },
    ];
    setItems(nextItems);
    onItemsChange?.(nextItems);
    setMcpDialogOpen(false);
    onDirty?.();
  };

  return (
    <>
      <MarketplaceFeatureContentSection
        title={t('marketplace.editor.tabs.mcp')}
        icon={Icon}
        items={items}
        countLabel={t('marketplace.editor.featureSections.count', { count: items.length })}
        emptyTitle={t('marketplace.editor.featureSections.mcp.emptyTitle')}
        emptyDescription={t('marketplace.editor.featureSections.mcp.emptyDescription')}
        addLabel={t('marketplace.editor.featureSections.actions.add')}
        onAdd={() => setMcpDialogOpen(true)}
        getItemKey={item => item.id}
        renderItem={item => (
          <MarketplaceMcpServerCard
            item={item}
            onDirty={onDirty}
            onChange={(nextItem) => {
              const nextItems = items.map(current => (current.id === nextItem.id ? nextItem : current));
              setItems(nextItems);
              onItemsChange?.(nextItems);
            }}
          />
        )}
      />
      <MarketplaceMcpServerDialog
        open={mcpDialogOpen}
        mode="create"
        value={emptyMcpServer}
        onOpenChange={setMcpDialogOpen}
        onSave={addMcpServer}
      />
    </>
  );
};

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

const marketplaceMcpServerValueFromItem = (
  item: MarketplaceEditorResourceItem,
  t: (key: string) => string,
): MarketplaceMcpServerDialogValue => {
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

const marketplaceMcpRecordFromValue = (value: MarketplaceMcpServerDialogValue): Record<string, unknown> => ({
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

export const marketplaceMcpServerContentFromValue = (value: MarketplaceMcpServerDialogValue): string => (
  JSON.stringify(marketplaceMcpRecordFromValue(value), null, 2)
);

export const marketplaceMcpResourceItemFromValue = (
  item: MarketplaceEditorResourceItem,
  value: MarketplaceMcpServerDialogValue,
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

interface MarketplaceMcpServerCardProps {
  item: MarketplaceEditorResourceItem;
  onDirty?: () => void;
  onChange: (item: MarketplaceEditorResourceItem) => void;
}

const MarketplaceMcpServerCard: React.FC<MarketplaceMcpServerCardProps> = ({ item, onDirty, onChange }) => {
  const { t } = useI18n();
  const [dialogOpen, setDialogOpen] = React.useState(false);
  const [server, setServer] = React.useState(() => marketplaceMcpServerValueFromItem(item, t));
  const envKeys = server.env.map(row => row.key.trim()).filter(Boolean).join(', ');

  return (
    <>
      <div className="rounded-lg border border-border bg-background p-4 transition-shadow hover:shadow-sm">
        <div className="mb-3 flex items-start justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
              <Database className="h-5 w-5 text-primary" />
            </div>
            <div>
              <div className="mb-1 flex items-center gap-2">
                <h3 className="font-semibold text-foreground">{server.name}</h3>
                <Badge variant="outline" className="border-blue-200 bg-blue-50 text-xs text-blue-700">
                  {server.transport.toUpperCase()}
                </Badge>
              </div>
              <p className="text-sm text-muted-foreground">{server.description}</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="ghost" size="sm" type="button" onClick={() => setDialogOpen(true)}>
              <Edit className="h-4 w-4" />
            </Button>
            <Button variant="ghost" size="sm" type="button">
              <Trash2 className="h-4 w-4" />
            </Button>
            <Button variant="ghost" size="sm" type="button">
              <Copy className="h-4 w-4" />
            </Button>
          </div>
        </div>

        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <div>
            <h4 className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
              {t('marketplace.editor.mcp.card.sections.command')}
            </h4>
            <div className="rounded-md bg-muted/50 p-3">
              <code className="break-all font-mono text-sm text-foreground">{server.command}</code>
            </div>
          </div>

          {server.args.length > 0 ? (
            <div>
              <h4 className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                {t('marketplace.editor.mcp.card.sections.arguments')}
              </h4>
              <div className="rounded-md bg-muted/50 p-3">
                <code className="break-all font-mono text-sm text-foreground">{server.args.join(' ')}</code>
              </div>
            </div>
          ) : null}

          {envKeys ? (
            <div>
              <h4 className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                {t('marketplace.editor.mcp.card.sections.environment')}
              </h4>
              <div className="rounded-md bg-muted/50 p-3">
                <div className="flex items-center justify-between gap-2">
                  <code className="font-mono text-sm text-foreground">{envKeys}</code>
                  <span className="text-xs text-muted-foreground">••••••••</span>
                </div>
              </div>
            </div>
          ) : null}
        </div>
      </div>

      <MarketplaceMcpServerDialog
        open={dialogOpen}
        value={server}
        onOpenChange={setDialogOpen}
        onSave={(value) => {
          setServer(value);
          onChange(marketplaceMcpResourceItemFromValue(item, value));
          setDialogOpen(false);
          onDirty?.();
        }}
      />
    </>
  );
};

export interface MarketplaceMcpServerDialogValue {
  name: string;
  description: string;
  transport: MCPTransport;
  command: string;
  args: string[];
  url: string;
  env: MCPKeyValueRow[];
  headers: MCPKeyValueRow[];
}

interface MarketplaceMcpServerDialogProps {
  open: boolean;
  mode?: 'create' | 'edit';
  value: MarketplaceMcpServerDialogValue;
  onOpenChange: (open: boolean) => void;
  onSave: (value: MarketplaceMcpServerDialogValue) => void;
}

const MarketplaceMcpServerDialog: React.FC<MarketplaceMcpServerDialogProps> = ({
  open,
  mode = 'edit',
  value,
  onOpenChange,
  onSave,
}) => {
  const { t } = useI18n();
  const [draft, setDraft] = React.useState(value);
  const [submitting, setSubmitting] = React.useState(false);
  const [submitError, setSubmitError] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (open) {
      setDraft(value);
      setSubmitError(null);
      setSubmitting(false);
    }
  }, [open, value]);

  const handleChange = <TField extends keyof MarketplaceMcpServerDialogValue>(
    field: TField,
    nextValue: MarketplaceMcpServerDialogValue[TField],
  ) => {
    setSubmitError(null);
    setDraft(prev => ({ ...prev, [field]: nextValue }));
  };

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    setSubmitError(null);

    if (!draft.name.trim()) {
      setSubmitError(t('marketplace.editor.mcp.dialog.validation.nameRequired'));
      return;
    }
    if (!draft.description.trim()) {
      setSubmitError(t('marketplace.editor.mcp.dialog.validation.descriptionRequired'));
      return;
    }
    if (draft.transport === 'stdio' && !draft.command.trim()) {
      setSubmitError(t('marketplace.editor.mcp.dialog.validation.commandRequired'));
      return;
    }
    if ((draft.transport === 'http' || draft.transport === 'sse') && !draft.url.trim()) {
      setSubmitError(t('marketplace.editor.mcp.dialog.validation.urlRequired'));
      return;
    }

    setSubmitting(true);
    onSave({
      ...draft,
      name: draft.name.trim(),
      description: draft.description.trim(),
      command: draft.command.trim(),
      args: draft.args.map(arg => arg.trim()).filter(Boolean),
      url: draft.url.trim(),
      env: createMCPKeyValueRows(toMCPKeyValueRecord(draft.env)),
      headers: createMCPKeyValueRows(toMCPKeyValueRecord(draft.headers)),
    });
    setSubmitting(false);
  };

  const transportOptions = (['stdio', 'sse', 'http'] as MCPTransport[]).map(transport => ({
    value: transport,
    title: t(`marketplace.editor.mcp.dialog.transport.options.${transport}.label`),
    description: t(`marketplace.editor.mcp.dialog.transport.options.${transport}.description`),
  }));

  const transportFieldLabels: MCPTransportFieldsLabels = {
    commandLabel: t('marketplace.editor.mcp.dialog.fields.command.label'),
    commandPlaceholder: t('marketplace.editor.mcp.dialog.fields.command.placeholder'),
    argsLabel: t('marketplace.editor.mcp.dialog.fields.args.label'),
    argsAdd: t('marketplace.editor.mcp.dialog.fields.args.add'),
    argsEmpty: t('marketplace.editor.mcp.dialog.fields.args.empty'),
    argsPlaceholder: index => t('marketplace.editor.mcp.dialog.fields.args.placeholder', { index }),
    urlLabel: t('marketplace.editor.mcp.dialog.fields.url.label'),
    urlPlaceholder: t(
      draft.transport === 'sse'
        ? 'marketplace.editor.mcp.dialog.fields.url.placeholderSse'
        : 'marketplace.editor.mcp.dialog.fields.url.placeholderHttp',
    ),
    urlHint: t(
      draft.transport === 'sse'
        ? 'marketplace.editor.mcp.dialog.fields.url.hintSse'
        : 'marketplace.editor.mcp.dialog.fields.url.hintHttp',
    ),
    headersLabel: t('marketplace.editor.mcp.dialog.fields.headers.label'),
    headersAdd: t('marketplace.editor.mcp.dialog.fields.headers.add'),
    headersKeyPlaceholder: t('marketplace.editor.mcp.dialog.fields.headers.keyPlaceholder'),
    headersValuePlaceholder: t('marketplace.editor.mcp.dialog.fields.headers.valuePlaceholder'),
    headersEmpty: t('marketplace.editor.mcp.dialog.fields.headers.empty'),
    headersHint: t('marketplace.editor.mcp.dialog.fields.headers.hint'),
    envLabel: t('marketplace.editor.mcp.dialog.fields.env.label'),
    envAdd: t('marketplace.editor.mcp.dialog.fields.env.add'),
    envKeyPlaceholder: t('marketplace.editor.mcp.dialog.fields.env.keyPlaceholder'),
    envValuePlaceholder: t('marketplace.editor.mcp.dialog.fields.env.valuePlaceholder'),
    envEmpty: t('marketplace.editor.mcp.dialog.fields.env.empty'),
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="flex h-[85vh] max-h-[85vh] max-w-2xl flex-col p-0">
        <DialogHeader className="flex-shrink-0 px-6 pt-6">
          <DialogTitle className="flex items-center gap-2">
            <Server className="h-5 w-5 text-primary" />
            {t(mode === 'create' ? 'marketplace.editor.mcp.dialog.titleCreate' : 'marketplace.editor.mcp.dialog.title')}
          </DialogTitle>
          <DialogDescription>
            {t(mode === 'create' ? 'marketplace.editor.mcp.dialog.descriptionCreate' : 'marketplace.editor.mcp.dialog.description')}
          </DialogDescription>
        </DialogHeader>

        <div className="flex-1 overflow-y-auto px-6 py-4">
          <form onSubmit={handleSubmit} className="space-y-6">
            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="marketplace-mcp-name">{t('marketplace.editor.mcp.dialog.fields.name.label')}</Label>
                <Input
                  id="marketplace-mcp-name"
                  value={draft.name}
                  onChange={event => handleChange('name', event.target.value)}
                  placeholder={t('marketplace.editor.mcp.dialog.fields.name.placeholder')}
                  className="font-medium"
                  required
                />
              </div>
              <div className="space-y-2">
                <Label>{t('marketplace.editor.mcp.dialog.transport.label')}</Label>
                <Select value={draft.transport} onValueChange={(transport: MCPTransport) => handleChange('transport', transport)}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {transportOptions.map(option => (
                      <SelectItem key={option.value} value={option.value}>
                        <div>
                          <div className="font-medium">{option.title}</div>
                          <div className="text-xs text-muted-foreground">{option.description}</div>
                        </div>
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="marketplace-mcp-description">{t('marketplace.editor.mcp.dialog.fields.description.label')}</Label>
              <Input
                id="marketplace-mcp-description"
                value={draft.description}
                onChange={event => handleChange('description', event.target.value)}
                placeholder={t('marketplace.editor.mcp.dialog.fields.description.placeholder')}
              />
            </div>

            <MCPTransportFieldsEditor
              transport={draft.transport}
              command={draft.command}
              args={draft.args}
              url={draft.url}
              env={draft.env}
              headers={draft.headers}
              submitting={submitting}
              labels={transportFieldLabels}
              onCommandChange={command => handleChange('command', command)}
              onArgsChange={args => handleChange('args', args)}
              onUrlChange={url => handleChange('url', url)}
              onEnvChange={env => handleChange('env', env)}
              onHeadersChange={headers => handleChange('headers', headers)}
            />
          </form>
        </div>

        <DialogFooter className="flex-shrink-0 px-6 pb-6">
          <div className="flex w-full flex-col gap-3">
            {submitError ? (
              <div className="w-full">
                <p className="text-sm text-destructive">{submitError}</p>
              </div>
            ) : null}
            <div className="flex justify-end gap-2">
              <Button type="button" variant="outline" onClick={() => onOpenChange(false)} disabled={submitting}>
                {t('marketplace.common.actions.cancel')}
              </Button>
              <Button type="submit" onClick={handleSubmit} disabled={submitting}>
                {submitting ? <LoadingSpinner size="sm" className="mr-2" /> : null}
                {t('marketplace.editor.mcp.dialog.actions.save')}
              </Button>
            </div>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};
