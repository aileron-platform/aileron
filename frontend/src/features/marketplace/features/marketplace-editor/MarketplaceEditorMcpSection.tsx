import React from 'react';
import { MCPServerCard, type MCPServerCardData, type MCPServerCardLabels } from '@/shared/components/mcp-workflow';
import { useI18n } from '@/shared/hooks/useI18n';
import { MarketplaceFeatureContentSection } from '../../components/MarketplaceFeatureContentSection';
import {
  marketplaceMcpResourceItemFromValue,
  marketplaceMcpServerValueFromItem,
} from './marketplaceMcpServerDialogSchema';
import { MarketplaceMCPServerDialog } from './dialogs/MarketplaceMCPServerDialog';
import type { MarketplaceEditorResourceItem } from './marketplaceEditorResourceItems';

export interface MarketplaceEditorMcpSectionProps {
  icon: React.ComponentType<{ className?: string }>;
  items: MarketplaceEditorResourceItem[];
  onDirty?: () => void;
  onItemsChange?: (items: MarketplaceEditorResourceItem[]) => void;
}

interface MarketplaceEditorMcpCardServer extends MCPServerCardData {
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
): MarketplaceEditorMcpCardServer => {
  const server = marketplaceMcpServerValueFromItem(item, t);
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
  onChange: (item: MarketplaceEditorResourceItem) => void;
  onDelete: (itemId: string) => void;
}> = ({ item, onDirty, onChange, onDelete }) => {
  const { t } = useI18n();
  const labels = React.useMemo(() => buildEditorMCPCardLabels(t), [t]);
  const server = React.useMemo(() => buildEditorMCPCardProps(item, t), [item, t]);
  const [dialogOpen, setDialogOpen] = React.useState(false);
  const [envVisible, setEnvVisible] = React.useState(false);

  return (
    <>
      <MCPServerCard
        server={server}
        scopeBadge={null}
        labels={labels}
        supportsToggle={false}
        envVisible={envVisible}
        onEdit={() => setDialogOpen(true)}
        onDelete={() => {
          onDelete(item.id);
          onDirty?.();
        }}
        onToggleEnvVisibility={() => setEnvVisible(current => !current)}
      />
      <MarketplaceMCPServerDialog
        open={dialogOpen}
        item={item}
        onClose={() => setDialogOpen(false)}
        onSubmit={async (nextItem) => {
          onChange(nextItem);
          setDialogOpen(false);
          onDirty?.();
        }}
      />
    </>
  );
};

export const MarketplaceEditorMcpSection: React.FC<MarketplaceEditorMcpSectionProps> = ({
  icon: Icon,
  items: initialItems,
  onDirty,
  onItemsChange,
}) => {
  const { t } = useI18n();
  const [items, setItems] = React.useState(initialItems);
  const [dialogOpen, setDialogOpen] = React.useState(false);

  React.useEffect(() => {
    setItems(initialItems);
  }, [initialItems]);

  const handleItemsChange = React.useCallback((nextItems: MarketplaceEditorResourceItem[]) => {
    setItems(nextItems);
    onItemsChange?.(nextItems);
  }, [onItemsChange]);

  const handleDelete = React.useCallback((itemId: string) => {
    handleItemsChange(items.filter(item => item.id !== itemId));
  }, [handleItemsChange, items]);

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
        onAdd={() => setDialogOpen(true)}
        getItemKey={item => item.id}
        renderItem={item => (
          <MarketplaceEditorMCPCard
            item={item}
            onDirty={onDirty}
            onDelete={handleDelete}
            onChange={(nextItem) => {
              handleItemsChange(items.map(current => (current.id === nextItem.id ? nextItem : current)));
            }}
          />
        )}
      />
      <MarketplaceMCPServerDialog
        open={dialogOpen}
        mode="create"
        item={null}
        onClose={() => setDialogOpen(false)}
        onSubmit={async (nextItem) => {
          handleItemsChange([...items, nextItem]);
          setDialogOpen(false);
          onDirty?.();
        }}
      />
    </>
  );
};

export {
  marketplaceApplyMcpItemsToPackageFiles,
  marketplaceMcpResourceItemFromValue,
  type MarketplaceMCPServerValue,
} from './marketplaceMcpServerDialogSchema';

export default MarketplaceEditorMcpSection;
