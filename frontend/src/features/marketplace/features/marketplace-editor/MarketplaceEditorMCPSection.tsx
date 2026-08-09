import React from 'react';
import { Plus, RefreshCw, type LucideIcon } from 'lucide-react';
import { MCPServerCard, type MCPServerCardData, type MCPServerCardLabels } from '@/shared/components/mcp-workflow';
import { SettingsListWorkbench, SettingsWorkflowCountBadge, SettingsWorkflowShell } from '@/shared/components/settings-workflow';
import { Button } from '@/shared/components/ui/button';
import { useI18n } from '@/shared/hooks/useI18n';
import {
  marketplaceMCPResourceItemFromValue,
  marketplaceMCPServerValueFromItem,
} from './marketplaceMCPServerDialogSchema';
import { MarketplaceMCPServerDialog } from './dialogs/MarketplaceMCPServerDialog';
import type { MarketplaceEditorResourceItem } from './marketplaceEditorResourceItems';
import { MarketplaceResourceLoadError } from '../../components/MarketplaceResourceLoadError';
import { LoadingSpinner } from '@/shared/components/ui/loading-spinner';

export interface MarketplaceEditorMCPSectionProps {
  icon: LucideIcon;
  items: MarketplaceEditorResourceItem[];
  onDirty?: () => void;
  onItemsChange?: (items: MarketplaceEditorResourceItem[]) => Promise<void>;
  onRefresh?: () => void;
  onLoadItem?: (item: MarketplaceEditorResourceItem) => Promise<MarketplaceEditorResourceItem>;
}

interface MarketplaceEditorMCPCardServer extends MCPServerCardData {
  item: MarketplaceEditorResourceItem;
}

const buildEditorMCPCardLabels = (t: (key: string) => string): MCPServerCardLabels => ({
  enabled: t('marketplace.editor.mcp.card.status.enabled'),
  disabled: t('marketplace.editor.mcp.card.status.disabled'),
  transportType: t('marketplace.editor.mcp.card.sections.transport'),
  serverUrl: t('marketplace.editor.mcp.card.sections.url'),
  headers: t('marketplace.editor.mcp.card.sections.headers'),
  command: t('marketplace.editor.mcp.card.sections.command'),
  commandArgs: t('marketplace.editor.mcp.card.sections.arguments'),
  env: t('marketplace.editor.mcp.card.sections.environment'),
  showEnvValues: t('marketplace.editor.mcp.card.showEnvValues'),
  hideEnvValues: t('marketplace.editor.mcp.card.hideEnvValues'),
  edit: t('marketplace.editor.mcp.card.actions.edit'),
  delete: t('marketplace.editor.mcp.card.actions.delete'),
});

const buildEditorMCPCardProps = (
  item: MarketplaceEditorResourceItem,
  t: (key: string) => string,
): MarketplaceEditorMCPCardServer => {
  const server = marketplaceMCPServerValueFromItem(item, t);
  return {
    id: item.id,
    item,
    name: server.name,
    description: server.description,
    scope: '',
    transport: server.transport,
    command: server.command,
    args: server.args,
    url: server.url,
    env: Object.fromEntries(server.env.filter(row => row.key.trim()).map(row => [row.key.trim(), row.value])),
    headers: Object.fromEntries(server.headers.filter(row => row.key.trim()).map(row => [row.key.trim(), row.value])),
  };
};

const MarketplaceEditorMCPCard: React.FC<{
  item: MarketplaceEditorResourceItem;
  onDirty?: () => void;
  onChange: (item: MarketplaceEditorResourceItem) => Promise<void>;
  onDelete: (itemId: string) => Promise<void>;
  onLoadItem?: (item: MarketplaceEditorResourceItem) => Promise<MarketplaceEditorResourceItem>;
}> = ({ item, onDirty, onChange, onDelete, onLoadItem }) => {
  const { t } = useI18n();
  const labels = React.useMemo(() => buildEditorMCPCardLabels(t), [t]);
  const server = React.useMemo(() => buildEditorMCPCardProps(item, t), [item, t]);
  const [dialogOpen, setDialogOpen] = React.useState(false);
  const [dialogItem, setDialogItem] = React.useState(item);
  const [envVisible, setEnvVisible] = React.useState(false);
  const [isLoading, setIsLoading] = React.useState(false);
  const [loadError, setLoadError] = React.useState(false);

  const handleEdit = React.useCallback(async () => {
    setIsLoading(true);
    setLoadError(false);
    try {
      const loadedItem = onLoadItem ? await onLoadItem(item) : item;
      setDialogItem(loadedItem);
      setDialogOpen(true);
    } catch {
      setLoadError(true);
    } finally {
      setIsLoading(false);
    }
  }, [item, onLoadItem]);

  if (loadError) {
    return (
      <MarketplaceResourceLoadError
        className="min-h-36 rounded-md border border-border"
        onRetry={() => { void handleEdit(); }}
      />
    );
  }

  if (isLoading) {
    return <LoadingSpinner className="min-h-36 rounded-md border border-border" />;
  }

  return (
    <>
      <MCPServerCard
        server={server}
        scopeBadge={null}
        labels={labels}
        supportsToggle={false}
        envVisible={envVisible}
        onEdit={() => { void handleEdit(); }}
        onDelete={() => {
          void onDelete(item.id).then(() => onDirty?.()).catch(() => undefined);
        }}
        onToggleEnvVisibility={() => setEnvVisible(current => !current)}
      />
      <MarketplaceMCPServerDialog
        open={dialogOpen}
        item={dialogItem}
        onClose={() => setDialogOpen(false)}
        onSubmit={async (nextItem) => {
          await onChange(nextItem);
          setDialogOpen(false);
          onDirty?.();
        }}
      />
    </>
  );
};

export const MarketplaceEditorMCPSection: React.FC<MarketplaceEditorMCPSectionProps> = ({
  icon: Icon,
  items: initialItems,
  onDirty,
  onItemsChange,
  onRefresh,
  onLoadItem,
}) => {
  const { t } = useI18n();
  const [items, setItems] = React.useState(initialItems);
  const [dialogOpen, setDialogOpen] = React.useState(false);

  React.useEffect(() => {
    setItems(initialItems);
  }, [initialItems]);

  const handleItemsChange = React.useCallback(async (nextItems: MarketplaceEditorResourceItem[]) => {
    await onItemsChange?.(nextItems);
    setItems(nextItems);
  }, [onItemsChange]);

  const handleDelete = React.useCallback(async (itemId: string) => {
    await handleItemsChange(items.filter(item => item.id !== itemId));
  }, [handleItemsChange, items]);

  return (
    <SettingsWorkflowShell
      title={t('marketplace.editor.tabs.mcp')}
      icon={Icon}
      hasItems
      summary={<SettingsWorkflowCountBadge label={t('marketplace.editor.featureSections.count', { count: items.length })} />}
      headerActions={(
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="sm" className="h-7 px-2 text-xs" onClick={onRefresh}>
            <RefreshCw className="mr-1 h-3 w-3" />
            {t('marketplace.common.actions.refresh')}
          </Button>
          <Button size="sm" className="h-7 px-2 text-xs" onClick={() => setDialogOpen(true)}>
            <Plus className="mr-1 h-3 w-3" />
            {t('marketplace.editor.featureSections.actions.add')}
          </Button>
        </div>
      )}
      emptyTitle={t('marketplace.editor.featureSections.mcp.emptyTitle')}
      emptyDescription={t('marketplace.editor.featureSections.mcp.emptyDescription')}
      contentClassName="h-full overflow-y-auto"
    >
      <div className="p-6">
        <SettingsListWorkbench
          items={items}
          getItemKey={item => item.id}
          i18nKeys={{
            emptyTitle: 'marketplace.editor.featureSections.mcp.emptyTitle',
            emptyDescription: 'marketplace.editor.featureSections.mcp.emptyDescription',
          }}
          card={item => (
            <MarketplaceEditorMCPCard
              item={item}
              onDirty={onDirty}
              onLoadItem={onLoadItem}
              onDelete={handleDelete}
              onChange={async (nextItem) => {
                await handleItemsChange(items.map(current => (current.id === nextItem.id ? nextItem : current)));
              }}
            />
          )}
          dialog={(
            <MarketplaceMCPServerDialog
              open={dialogOpen}
              mode="create"
              item={null}
              onClose={() => setDialogOpen(false)}
              onSubmit={async (nextItem) => {
                await handleItemsChange([...items, nextItem]);
                setDialogOpen(false);
                onDirty?.();
              }}
            />
          )}
        />
      </div>
    </SettingsWorkflowShell>
  );
};
