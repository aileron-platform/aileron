import React, { useMemo } from 'react';
import {
  MCPServerDialog,
  type MCPServerDialogData,
  type MCPServerDialogLabels,
  type MCPServerTransportOption,
  type MCPTransport,
  type MCPTransportFieldsLabels,
} from '@/shared/components/mcp-workflow';
import { useI18n } from '@/shared/hooks/useI18n';
import type { MarketplaceEditorResourceItem } from '../marketplaceEditorResourceItems';
import {
  marketplaceMcpResourceItemFromValue,
  marketplaceMcpServerValueFromItem,
} from '../marketplaceMcpServerDialogSchema';

interface MarketplaceMCPServerDialogData extends MCPServerDialogData<string> {
  description?: string;
}

export interface MarketplaceMCPServerDialogProps {
  open: boolean;
  mode?: 'create' | 'edit';
  item: MarketplaceEditorResourceItem | null;
  onClose: () => void;
  onSubmit: (item: MarketplaceEditorResourceItem) => Promise<void> | void;
}

const buildCreateItem = (server: MarketplaceMCPServerDialogData): MarketplaceEditorResourceItem => {
  const id = `local-${Math.random().toString(36).slice(2, 10)}`;
  const nextName = server.name || id;

  return marketplaceMcpResourceItemFromValue({
    id,
    titleKey: 'marketplace.editor.mcp.dialog.create.defaultTitle',
    descriptionKey: 'marketplace.editor.mcp.dialog.create.defaultDescription',
    title: nextName,
    description: server.description ?? '',
    path: `mcp/${nextName}.json`,
    content: '{}',
  }, {
    name: server.name,
    description: server.description ?? '',
    transport: server.transport ?? 'stdio',
    command: server.command ?? '',
    args: server.args ?? [],
    url: server.url ?? '',
    env: Object.entries(server.env ?? {}).map(([key, value], index) => ({ id: `env-${index}`, key, value })),
    headers: Object.entries(server.headers ?? {}).map(([key, value], index) => ({ id: `header-${index}`, key, value })),
  });
};

export const MarketplaceMCPServerDialog: React.FC<MarketplaceMCPServerDialogProps> = ({
  open,
  mode = 'edit',
  item,
  onClose,
  onSubmit,
}) => {
  const { t } = useI18n();

  const dialogLabels: MCPServerDialogLabels = {
    titleCreate: t('marketplace.editor.mcp.dialog.titleCreate'),
    titleEdit: t('marketplace.editor.mcp.dialog.title'),
    description: t(mode === 'create' ? 'marketplace.editor.mcp.dialog.descriptionCreate' : 'marketplace.editor.mcp.dialog.description'),
    nameLabel: t('marketplace.editor.mcp.dialog.fields.name.label'),
    namePlaceholder: t('marketplace.editor.mcp.dialog.fields.name.placeholder'),
    nameHint: t('marketplace.editor.mcp.dialog.fields.name.hint'),
    scopeLabel: t('marketplace.editor.mcp.dialog.fields.scope.label'),
    transportLabel: t('marketplace.editor.mcp.dialog.transport.label'),
    cancel: t('marketplace.common.actions.cancel'),
    create: t('marketplace.editor.mcp.dialog.actions.create'),
    save: t('marketplace.editor.mcp.dialog.actions.save'),
    nameRequired: t('marketplace.editor.mcp.dialog.validation.nameRequired'),
    commandRequired: t('marketplace.editor.mcp.dialog.validation.commandRequired'),
    urlRequired: t('marketplace.editor.mcp.dialog.validation.urlRequired'),
    saveFailed: t('marketplace.editor.mcp.dialog.validation.saveFailed'),
  };

  const transportOptions = useMemo<MCPServerTransportOption[]>(
    () => (['stdio', 'sse', 'http'] as MCPTransport[]).map((transport) => ({
      value: transport,
      title: t(`marketplace.editor.mcp.dialog.transport.options.${transport}.label`),
      description: t(`marketplace.editor.mcp.dialog.transport.options.${transport}.description`),
    })),
    [t],
  );

  const buildTransportFieldLabels = React.useCallback((transport: MCPTransport): MCPTransportFieldsLabels => ({
    commandLabel: t('marketplace.editor.mcp.dialog.fields.command.label'),
    commandPlaceholder: t('marketplace.editor.mcp.dialog.fields.command.placeholder'),
    argsLabel: t('marketplace.editor.mcp.dialog.fields.args.label'),
    argsAdd: t('marketplace.editor.mcp.dialog.fields.args.add'),
    argsEmpty: t('marketplace.editor.mcp.dialog.fields.args.empty'),
    argsPlaceholder: (index) => t('marketplace.editor.mcp.dialog.fields.args.placeholder', { index }),
    urlLabel: t('marketplace.editor.mcp.dialog.fields.url.label'),
    urlPlaceholder: t(
      transport === 'sse'
        ? 'marketplace.editor.mcp.dialog.fields.url.placeholderSse'
        : 'marketplace.editor.mcp.dialog.fields.url.placeholderHttp',
    ),
    urlHint: t(
      transport === 'sse'
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
  }), [t]);

  const server = useMemo(() => {
    if (!item) {
      return null;
    }

    const value = marketplaceMcpServerValueFromItem(item, t);
    return {
      id: item.id,
      name: value.name,
      description: value.description,
      scope: '',
      transport: value.transport,
      command: value.command,
      args: value.args,
      url: value.url,
      env: Object.fromEntries(value.env.map(row => [row.key, row.value])),
      headers: Object.fromEntries(value.headers.map(row => [row.key, row.value])),
    };
  }, [item, t]);

  return (
    <MCPServerDialog<string>
      open={open}
      mode={mode}
      server={server}
      scopeOptions={[]}
      transportOptions={transportOptions}
      labels={dialogLabels}
      transportFieldLabels={buildTransportFieldLabels}
      descriptionField={{
        label: t('marketplace.editor.mcp.dialog.fields.description.label'),
        placeholder: t('marketplace.editor.mcp.dialog.fields.description.placeholder'),
        requiredMessage: t('marketplace.editor.mcp.dialog.validation.descriptionRequired'),
      }}
      onClose={onClose}
      onSubmit={async (payload) => {
        const nextItem = item
          ? marketplaceMcpResourceItemFromValue(item, {
            name: payload.name,
            description: payload.description ?? '',
            transport: payload.transport ?? 'stdio',
            command: payload.command ?? '',
            args: payload.args ?? [],
            url: payload.url ?? '',
            env: Object.entries(payload.env ?? {}).map(([key, value], index) => ({ id: `env-${index}`, key, value })),
            headers: Object.entries(payload.headers ?? {}).map(([key, value], index) => ({ id: `header-${index}`, key, value })),
          })
          : buildCreateItem(payload as MarketplaceMCPServerDialogData);
        await onSubmit(nextItem);
      }}
    />
  );
};

export default MarketplaceMCPServerDialog;
