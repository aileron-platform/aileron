import React from 'react';
import { Edit, Plus, RefreshCw, Trash2, type LucideIcon } from 'lucide-react';

import { SettingsListWorkbench, SettingsWorkflowCountBadge, SettingsWorkflowShell } from '@/shared/components/settings-workflow';
import { Button } from '@/shared/components/ui/button';
import {
  HOOK_EVENTS,
  HookCard,
  HookDialog,
  createEmptyHookValue,
  getHookEventI18nKey,
  type HookDialogData,
} from '@/shared/components/hook-workflow';
import { useI18n } from '@/shared/hooks/useI18n';
import type { MarketplaceProvider } from '@/features/marketplace/model/marketplaceTypes';

import type { MarketplaceEditorResourceItem } from './marketplaceEditorResourceItems';
import {
  createMarketplaceHookDialogLabels,
  createMarketplaceHookDialogOptions,
  formatMarketplaceHookTimeout,
  marketplaceHookActionSummary,
  marketplaceHookDataFromValue,
  marketplaceHookDialogValueFromItem,
  marketplaceHookNativeContent,
  marketplaceHookResourceItemFromValue,
  type MarketplaceHookDialogValue,
  MARKETPLACE_HOOK_SOURCE_EVENT,
} from './marketplaceHookModel';

const commonHookEventLabelKey = (eventName: string) => getHookEventI18nKey(eventName, 'label');
const commonHookEventDescriptionKey = (eventName: string) => getHookEventI18nKey(eventName, 'description');

export interface MarketplaceEditorHookSectionProps {
  provider: MarketplaceProvider;
  icon: LucideIcon;
  items: MarketplaceEditorResourceItem[];
  onDirty?: () => void;
  onItemsChange?: (items: MarketplaceEditorResourceItem[]) => Promise<void>;
  onRefresh?: () => void;
  defaultSource?: { sourceId: string; path: string; manifestPointer: string } | null;
}

export const MarketplaceEditorHookSection: React.FC<MarketplaceEditorHookSectionProps> = ({ provider, icon: Icon, items: initialItems, onDirty, onItemsChange, onRefresh, defaultSource = null }) => {
  const { t } = useI18n();
  const [items, setItems] = React.useState(initialItems);
  const [hookDialogOpen, setHookDialogOpen] = React.useState(false);

  React.useEffect(() => {
    setItems(initialItems);
  }, [initialItems]);

  const emptyHook: MarketplaceHookDialogValue = createEmptyHookValue(provider);

  const addHook = async (value: MarketplaceHookDialogValue) => {
    const id = `local-${Math.random().toString(36).slice(2, 10)}`;
    const firstMatcher = value.matchers[0];
    const firstAction = firstMatcher?.hooks[0];
    const nextItems = [
      ...items,
      {
        id,
        titleKey: 'marketplace.editor.hooks.dialog.create.defaultTitle',
        descriptionKey: 'marketplace.editor.hooks.dialog.create.defaultDescription',
        title: value.name || value.event,
        description: value.event,
        path: defaultSource?.path ?? 'hooks/hooks.json',
        content: marketplaceHookNativeContent(value),
        data: {
          ...marketplaceHookDataFromValue(value, defaultSource ?? undefined),
          [MARKETPLACE_HOOK_SOURCE_EVENT]: value.event,
        },
        badge: value.event,
        code: marketplaceHookActionSummary(firstAction),
        meta: [
          { labelKey: 'marketplace.editor.featureMeta.labels.type', value: firstAction?.type ?? 'command' },
          { labelKey: 'marketplace.editor.featureMeta.labels.matcher', value: firstMatcher?.matcher ?? '*' },
          { labelKey: 'marketplace.editor.featureMeta.labels.timeout', value: formatMarketplaceHookTimeout(provider, firstAction?.timeout) },
          ...(firstMatcher?.sequential ? [{ labelKey: 'marketplace.editor.featureMeta.labels.sequential', value: t('marketplace.common.labels.enabled') }] : []),
        ],
      },
    ];
    await onItemsChange?.(nextItems);
    setItems(nextItems);
    setHookDialogOpen(false);
    onDirty?.();
  };

  return (
    <SettingsWorkflowShell
      title={t('marketplace.editor.tabs.hooks')}
      icon={Icon}
      hasItems
      summary={<SettingsWorkflowCountBadge label={t('marketplace.editor.featureSections.count', { count: items.length })} />}
      headerActions={(
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="sm" className="h-7 px-2 text-xs" onClick={onRefresh}>
            <RefreshCw className="mr-1 h-3 w-3" />
            {t('marketplace.common.actions.refresh')}
          </Button>
          <Button size="sm" className="h-7 px-2 text-xs" onClick={() => setHookDialogOpen(true)}>
            <Plus className="mr-1 h-3 w-3" />
            {t('marketplace.editor.featureSections.actions.add')}
          </Button>
        </div>
      )}
      emptyTitle={t('marketplace.editor.featureSections.hooks.emptyTitle')}
      emptyDescription={t('marketplace.editor.featureSections.hooks.emptyDescription')}
      contentClassName="h-full overflow-y-auto"
    >
      <div className="p-6">
        <SettingsListWorkbench
          items={items}
          getItemKey={item => item.id}
          i18nKeys={{
            emptyTitle: 'marketplace.editor.featureSections.hooks.emptyTitle',
            emptyDescription: 'marketplace.editor.featureSections.hooks.emptyDescription',
          }}
          card={item => (
            <MarketplaceHookCard
              provider={provider}
              item={item}
              onDirty={onDirty}
              onRemove={async (itemId) => {
                const nextItems = items.filter(current => current.id !== itemId);
                await onItemsChange?.(nextItems);
                setItems(nextItems);
                onDirty?.();
              }}
              onChange={async (nextItem) => {
                const nextItems = items.map(current => (current.id === nextItem.id ? nextItem : current));
                await onItemsChange?.(nextItems);
                setItems(nextItems);
              }}
            />
          )}
          dialog={(
            <MarketplaceHookDialog
              open={hookDialogOpen}
              mode="create"
              value={emptyHook}
              provider={provider}
              onOpenChange={setHookDialogOpen}
              onSave={addHook}
            />
          )}
        />
      </div>
    </SettingsWorkflowShell>
  );
};

interface MarketplaceHookCardProps {
  provider: MarketplaceProvider;
  item: MarketplaceEditorResourceItem;
  onDirty?: () => void;
  onRemove: (id: string) => Promise<void>;
  onChange: (item: MarketplaceEditorResourceItem) => Promise<void>;
}

const MarketplaceHookCard: React.FC<MarketplaceHookCardProps> = ({ provider, item, onDirty, onRemove, onChange }) => {
  const { t } = useI18n();
  const [dialogOpen, setDialogOpen] = React.useState(false);
  const [hook, setHook] = React.useState<MarketplaceHookDialogValue>(() => marketplaceHookDialogValueFromItem(item, provider, t));

  return (
    <>
      <div className="relative rounded-lg border border-border bg-background p-6">
        <div className="flex items-start">
          <div className="min-w-0 flex-1 pr-16">
            <HookCard
              provider={provider}
              hook={{
                event: t(commonHookEventLabelKey(hook.event)),
                description: t(commonHookEventDescriptionKey(hook.event)),
                matchers: hook.matchers,
              }}
              i18nKeyPrefix="marketplace.editor.hooks.card"
            />
          </div>
        </div>

        <div className="absolute right-4 top-4 flex items-center gap-2">
          <button type="button" className="rounded-md p-2 transition-colors hover:bg-muted" onClick={() => setDialogOpen(true)}>
            <Edit className="h-4 w-4 text-muted-foreground" />
          </button>
          <button
            type="button"
            className="rounded-md p-2 transition-colors hover:bg-muted"
            onClick={() => { void onRemove(item.id).catch(() => undefined); }}
          >
            <Trash2 className="h-4 w-4 text-muted-foreground" />
          </button>
        </div>
      </div>

      <MarketplaceHookDialog
        open={dialogOpen}
        value={hook}
        provider={provider}
        onOpenChange={setDialogOpen}
        onSave={async (value) => {
          await onChange(marketplaceHookResourceItemFromValue(item, provider, value, t));
          setHook(value);
          setDialogOpen(false);
          onDirty?.();
        }}
      />
    </>
  );
};

interface MarketplaceHookDialogProps {
  open: boolean;
  mode?: 'create' | 'edit';
  provider: MarketplaceProvider;
  value: MarketplaceHookDialogValue;
  onOpenChange: (open: boolean) => void;
  onSave: (value: MarketplaceHookDialogValue) => Promise<void>;
}

const MarketplaceHookDialog: React.FC<MarketplaceHookDialogProps> = ({
  open,
  mode = 'edit',
  provider,
  value,
  onOpenChange,
  onSave,
}) => {
  const { t } = useI18n();
  const eventOptions = React.useMemo(
    () => HOOK_EVENTS[provider].map((eventName) => ({
      value: eventName,
      label: t(commonHookEventLabelKey(eventName)),
    })),
    [provider, t],
  );
  const labels = React.useMemo(
    () => createMarketplaceHookDialogLabels(t, provider, mode),
    [mode, provider, t],
  );
  const options = React.useMemo(
    () => createMarketplaceHookDialogOptions(t, provider, eventOptions),
    [eventOptions, provider, t],
  );
  const hook = React.useMemo<HookDialogData | null>(() => ({
    id: value.name || value.event,
    name: value.name,
    scope: 'project',
    eventName: value.event,
    matchers: value.matchers,
  }), [value]);

  return (
    <HookDialog
      open={open}
      mode={mode}
      provider={provider}
      hook={mode === 'edit' ? hook : null}
      showNameField
      showScopeField={false}
      labels={labels}
      options={options}
      onClose={() => onOpenChange(false)}
      onSubmit={(payload) => {
        void onSave({
          name: payload.name ?? '',
          event: payload.eventName,
          matchers: payload.matchers,
        }).then(() => onOpenChange(false)).catch(() => undefined);
      }}
    />
  );
};
