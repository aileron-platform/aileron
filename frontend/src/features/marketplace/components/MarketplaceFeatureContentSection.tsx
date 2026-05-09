import React from 'react';
import { Button } from '@/shared/components/ui/button';
import {
  SettingsWorkflowActionButton,
  SettingsWorkflowCountBadge,
  SettingsWorkflowShell,
} from '@/shared/components/settings-workflow';
import { Plus } from 'lucide-react';
import { useI18n } from '@/shared/hooks/useI18n';

interface MarketplaceFeatureContentSectionProps<TItem> {
  title: string;
  icon: React.ComponentType<{ className?: string }>;
  items: TItem[];
  countLabel: string;
  emptyTitle: string;
  emptyDescription: string;
  addLabel: string;
  onAdd: () => void;
  renderItem: (item: TItem) => React.ReactNode;
  getItemKey: (item: TItem, index: number) => React.Key;
}

export const MarketplaceFeatureContentSection = <TItem,>({
  title,
  icon: Icon,
  items,
  countLabel,
  emptyTitle,
  emptyDescription,
  addLabel,
  onAdd,
  renderItem,
  getItemKey,
}: MarketplaceFeatureContentSectionProps<TItem>) => {
  const { t } = useI18n();

  return (
    <SettingsWorkflowShell
      title={title}
      icon={Icon}
      headerActions={(
        <SettingsWorkflowActionButton onClick={onAdd}>
          <Plus className="mr-1 h-3.5 w-3.5" />
          {addLabel}
        </SettingsWorkflowActionButton>
      )}
      summary={<SettingsWorkflowCountBadge label={countLabel} />}
      singleHeader
      hasItems={items.length > 0}
      emptyIcon={<Icon className="h-6 w-6 text-muted-foreground" />}
      emptyTitle={emptyTitle}
      emptyDescription={emptyDescription}
      emptyActions={(
        <Button size="sm" className="h-7 px-2 text-xs" onClick={onAdd}>
          <Plus className="mr-1 h-3.5 w-3.5" />
          {t('marketplace.editor.featureSections.actions.add')}
        </Button>
      )}
      contentClassName="space-y-4 p-4"
    >
      {items.map((item, index) => (
        <React.Fragment key={getItemKey(item, index)}>
          {renderItem(item)}
        </React.Fragment>
      ))}
    </SettingsWorkflowShell>
  );
};
