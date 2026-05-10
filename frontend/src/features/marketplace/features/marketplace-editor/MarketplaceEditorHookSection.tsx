import React from 'react';
import { Edit, Trash2, Workflow } from 'lucide-react';

import { MarketplaceFeatureContentSection } from '../../components/MarketplaceFeatureContentSection';
import { Button } from '@/shared/components/ui/button';
import { HookCard } from '@/shared/components/hook-workflow/HookCard';
import { type HookActionConfig, type HookMatcher } from '@/shared/components/hook-workflow';
import { WorkspaceHookDialog, type WorkspaceHookData } from '@/features/workspace/features/agent-settings/pages/dialogs/WorkspaceHookDialog';
import {
  HOOK_EVENTS,
  HOOK_TYPES,
  createEmptyHookValue,
  createEmptyMatcher,
  getHookDefaults,
  getHookFieldSupport,
  isValidEventForProvider,
} from '@/shared/hooks/providerHookSpec';
import { useI18n } from '@/shared/hooks/useI18n';
import type { MarketplaceProvider } from '@/shared/types/marketplace';

import { marketplaceEditorItemTitle, type MarketplaceEditorResourceItem } from './marketplaceEditorResourceItems';

const marketplaceHookEventLabelKey = (eventName: string) => `marketplace.editor.hooks.events.${eventName}.label`;
const marketplaceHookEventDescriptionKey = (eventName: string) => `marketplace.editor.hooks.events.${eventName}.description`;

export interface MarketplaceEditorHookSectionProps {
  provider: MarketplaceProvider;
  icon: React.ComponentType<{ className?: string }>;
  items: MarketplaceEditorResourceItem[];
  onDirty?: () => void;
  onItemsChange?: (items: MarketplaceEditorResourceItem[]) => void;
}

export const MarketplaceEditorHookSection: React.FC<MarketplaceEditorHookSectionProps> = ({ provider, icon: Icon, items: initialItems, onDirty, onItemsChange }) => {
  const { t } = useI18n();
  const [items, setItems] = React.useState(initialItems);
  const [hookDialogOpen, setHookDialogOpen] = React.useState(false);

  React.useEffect(() => {
    setItems(initialItems);
  }, [initialItems]);

  const emptyHook: MarketplaceHookDialogValue = createEmptyHookValue(provider);

  const addHook = (value: MarketplaceHookDialogValue) => {
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
        path: `hooks/${value.name || id}.json`,
        content: marketplaceHookNativeContent(value),
        data: marketplaceHookDataFromValue(value),
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
    setItems(nextItems);
    onItemsChange?.(nextItems);
    setHookDialogOpen(false);
    onDirty?.();
  };

  return (
    <>
      <MarketplaceFeatureContentSection
        title={t('marketplace.editor.tabs.hooks')}
        icon={Icon}
        items={items}
        countLabel={t('marketplace.editor.featureSections.count', { count: items.length })}
        emptyTitle={t('marketplace.editor.featureSections.hooks.emptyTitle')}
        emptyDescription={t('marketplace.editor.featureSections.hooks.emptyDescription')}
        addLabel={t('marketplace.editor.featureSections.actions.add')}
        onAdd={() => setHookDialogOpen(true)}
        getItemKey={item => item.id}
        renderItem={item => (
          <MarketplaceHookCard
            provider={provider}
            item={item}
            onDirty={onDirty}
            onRemove={(itemId) => {
              const nextItems = items.filter(current => current.id !== itemId);
              setItems(nextItems);
              onItemsChange?.(nextItems);
              onDirty?.();
            }}
            onChange={(nextItem) => {
              const nextItems = items.map(current => (current.id === nextItem.id ? nextItem : current));
              setItems(nextItems);
              onItemsChange?.(nextItems);
            }}
          />
        )}
      />
      <MarketplaceHookDialog
        open={hookDialogOpen}
        mode="create"
        value={emptyHook}
        provider={provider}
        onOpenChange={setHookDialogOpen}
        onSave={addHook}
      />
    </>
  );
};

interface MarketplaceHookCardProps {
  provider: MarketplaceProvider;
  item: MarketplaceEditorResourceItem;
  onDirty?: () => void;
  onRemove: (id: string) => void;
  onChange: (item: MarketplaceEditorResourceItem) => void;
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
                event: t(marketplaceHookEventLabelKey(hook.event)),
                description: t(marketplaceHookEventDescriptionKey(hook.event)),
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
          <button type="button" className="rounded-md p-2 transition-colors hover:bg-muted" onClick={() => onRemove(item.id)}>
            <Trash2 className="h-4 w-4 text-muted-foreground" />
          </button>
        </div>
      </div>

      <MarketplaceHookDialog
        open={dialogOpen}
        value={hook}
        provider={provider}
        onOpenChange={setDialogOpen}
        onSave={(value) => {
          setHook(value);
          onChange(marketplaceHookResourceItemFromValue(item, provider, value, t));
          setDialogOpen(false);
          onDirty?.();
        }}
      />
    </>
  );
};

export interface MarketplaceHookDialogValue {
  name: string;
  event: string;
  matchers: HookMatcher[];
}

interface MarketplaceHookDialogProps {
  open: boolean;
  mode?: 'create' | 'edit';
  provider: MarketplaceProvider;
  value: MarketplaceHookDialogValue;
  onOpenChange: (open: boolean) => void;
  onSave: (value: MarketplaceHookDialogValue) => void;
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
      label: t(`marketplace.editor.hooks.events.${eventName}.label`),
    })),
    [provider, t],
  );
  const hook = React.useMemo<WorkspaceHookData | null>(() => ({
    id: value.name || value.event,
    name: value.name,
    scope: 'project',
    eventName: value.event,
    matchers: value.matchers,
  }), [value]);

  return (
    <WorkspaceHookDialog
      open={open}
      mode={mode}
      provider={provider}
      dialogVariant="marketplace"
      hook={mode === 'edit' ? hook : null}
      eventOptions={eventOptions}
      availableScopes={['project']}
      showNameField
      showScopeField={false}
      i18nNamespace="marketplace.editor"
      onClose={() => onOpenChange(false)}
      onSubmit={(payload) => {
        onSave({
          name: payload.name ?? '',
          event: payload.eventName,
          matchers: payload.matchers,
        });
        onOpenChange(false);
      }}
    />
  );
};

export const formatMarketplaceHookTimeout = (provider: MarketplaceProvider, timeout?: number): string => (
  getHookDefaults(provider).timeoutUnit === 'ms'
    ? `${timeout ?? getHookDefaults(provider).timeout}ms`
    : `${timeout ?? getHookDefaults(provider).timeout}s`
);

const marketplaceHookDataFromValue = (value: MarketplaceHookDialogValue): Record<string, unknown> => ({
  name: value.name,
  event: value.event,
  matchers: value.matchers,
});

const marketplaceHookNativeContent = (value: MarketplaceHookDialogValue): string => (
  JSON.stringify({ hooks: { [value.event]: value.matchers } }, null, 2)
);

const marketplaceHookDialogValueFromItem = (
  item: MarketplaceEditorResourceItem,
  provider: MarketplaceProvider,
  t: (key: string) => string,
): MarketplaceHookDialogValue => {
  const data = item.data;
  const nativeContent = marketplaceHookDialogValueFromNativeContent(item.content, provider);
  const event = typeof data?.event === 'string' && isValidEventForProvider(provider, data.event)
    ? data.event
    : nativeContent?.event ?? HOOK_EVENTS[provider][0];
  const matchers = Array.isArray(data?.matchers)
    ? data.matchers as HookMatcher[]
    : nativeContent?.matchers ?? [createEmptyMatcher(provider)];

  return {
    name: typeof data?.name === 'string' ? data.name : marketplaceEditorItemTitle(item, t),
    event,
    matchers,
  };
};

const marketplaceHookDialogValueFromNativeContent = (
  content: string,
  provider: MarketplaceProvider,
): Pick<MarketplaceHookDialogValue, 'event' | 'matchers'> | null => {
  try {
    const parsed = JSON.parse(content) as unknown;
    if (!isMarketplaceRecord(parsed) || !isMarketplaceRecord(parsed.hooks)) return null;

    const hookEntry = Object.entries(parsed.hooks)
      .find(([event, value]) => isValidEventForProvider(provider, event) && Array.isArray(value));
    if (!hookEntry) return null;

    const [event, rawMatchers] = hookEntry;
    const matchers = (rawMatchers as unknown[])
      .map(rawMatcher => marketplaceHookMatcherFromNativeValue(rawMatcher, provider))
      .filter((matcher): matcher is HookMatcher => Boolean(matcher));

    return {
      event,
      matchers: matchers.length > 0 ? matchers : [createEmptyMatcher(provider)],
    };
  } catch {
    return null;
  }
};

const marketplaceHookMatcherFromNativeValue = (
  rawMatcher: unknown,
  provider: MarketplaceProvider,
): HookMatcher | null => {
  if (!isMarketplaceRecord(rawMatcher) || !Array.isArray(rawMatcher.hooks)) return null;

  const hooks = rawMatcher.hooks
    .map(rawAction => marketplaceHookActionFromNativeValue(rawAction, provider))
    .filter((action): action is HookActionConfig => Boolean(action));
  if (hooks.length === 0) return null;

  return {
    matcher: typeof rawMatcher.matcher === 'string' ? rawMatcher.matcher : '*',
    sequential: typeof rawMatcher.sequential === 'boolean' ? rawMatcher.sequential : undefined,
    hooks,
  };
};

const marketplaceHookActionFromNativeValue = (
  rawAction: unknown,
  provider: MarketplaceProvider,
): HookActionConfig | null => {
  if (!isMarketplaceRecord(rawAction)) return null;

  const actionType = typeof rawAction.type === 'string' && HOOK_TYPES[provider].includes(rawAction.type as HookActionConfig['type'])
    ? rawAction.type as HookActionConfig['type']
    : 'command';
  const timeout = typeof rawAction.timeout === 'number' ? rawAction.timeout : undefined;
  const common = {
    timeout,
    name: typeof rawAction.name === 'string' ? rawAction.name : undefined,
    description: typeof rawAction.description === 'string' ? rawAction.description : undefined,
    statusMessage: typeof rawAction.statusMessage === 'string' ? rawAction.statusMessage : undefined,
    if: typeof rawAction.if === 'string' ? rawAction.if : undefined,
    once: typeof rawAction.once === 'boolean' ? rawAction.once : undefined,
  };

  if (actionType === 'http') {
    return {
      ...common,
      type: 'http',
      url: typeof rawAction.url === 'string' ? rawAction.url : '',
      headers: marketplaceStringRecordFromValue(rawAction.headers),
      allowedEnvVars: Array.isArray(rawAction.allowedEnvVars)
        ? rawAction.allowedEnvVars.filter((value): value is string => typeof value === 'string')
        : undefined,
    };
  }
  if (actionType === 'mcp_tool') {
    return {
      ...common,
      type: 'mcp_tool',
      server: typeof rawAction.server === 'string' ? rawAction.server : '',
      tool: typeof rawAction.tool === 'string' ? rawAction.tool : '',
      input: isMarketplaceRecord(rawAction.input) ? rawAction.input : undefined,
    };
  }
  if (actionType === 'prompt' || actionType === 'agent') {
    return {
      ...common,
      type: actionType,
      prompt: typeof rawAction.prompt === 'string' ? rawAction.prompt : '',
      model: typeof rawAction.model === 'string' ? rawAction.model : undefined,
    };
  }

  return {
    ...common,
    type: 'command',
    command: typeof rawAction.command === 'string' ? rawAction.command : '',
    shell: rawAction.shell === 'bash' || rawAction.shell === 'powershell' ? rawAction.shell : undefined,
    async: typeof rawAction.async === 'boolean' ? rawAction.async : undefined,
    asyncRewake: typeof rawAction.asyncRewake === 'boolean' ? rawAction.asyncRewake : undefined,
  };
};

const isMarketplaceRecord = (value: unknown): value is Record<string, unknown> => (
  typeof value === 'object' && value !== null && !Array.isArray(value)
);

const marketplaceStringRecordFromValue = (value: unknown): Record<string, string> | undefined => {
  if (!isMarketplaceRecord(value)) return undefined;
  const entries = Object.entries(value).filter((entry): entry is [string, string] => typeof entry[1] === 'string');
  return entries.length > 0 ? Object.fromEntries(entries) : undefined;
};

export const marketplaceHookResourceItemFromValue = (
  item: MarketplaceEditorResourceItem,
  provider: MarketplaceProvider,
  value: MarketplaceHookDialogValue,
  t: (key: string) => string,
): MarketplaceEditorResourceItem => {
  const firstMatcher = value.matchers[0];
  const firstAction = firstMatcher?.hooks[0];
  const name = value.name.trim() || value.event;

  return {
    ...item,
    title: name,
    description: value.event,
    path: item.path,
    content: marketplaceHookNativeContent(value),
    data: marketplaceHookDataFromValue(value),
    badge: value.event,
    code: marketplaceHookActionSummary(firstAction),
    meta: [
      { labelKey: 'marketplace.editor.featureMeta.labels.type', value: firstAction?.type ?? 'command' },
      { labelKey: 'marketplace.editor.featureMeta.labels.matcher', value: firstMatcher?.matcher ?? '*' },
      { labelKey: 'marketplace.editor.featureMeta.labels.timeout', value: formatMarketplaceHookTimeout(provider, firstAction?.timeout) },
      ...(firstMatcher?.sequential ? [{ labelKey: 'marketplace.editor.featureMeta.labels.sequential', value: t('marketplace.common.labels.enabled') }] : []),
    ],
  };
};

const isMarketplaceHookActionValid = (action: HookMatcher['hooks'][number]): boolean => {
  if (action.type === 'http') return Boolean(action.url.trim());
  if (action.type === 'mcp_tool') return Boolean(action.server.trim() && action.tool.trim());
  if (action.type === 'prompt' || action.type === 'agent') return Boolean(action.prompt.trim());
  return Boolean(action.command.trim());
};

const marketplaceHookActionSummary = (action?: HookMatcher['hooks'][number]): string => {
  if (!action) return '';
  if (action.type === 'http') return action.url;
  if (action.type === 'mcp_tool') return [action.server, action.tool].filter(Boolean).join('.');
  if (action.type === 'prompt' || action.type === 'agent') return action.prompt;
  return action.command;
};

const sanitizeMarketplaceHookAction = (
  action: HookMatcher['hooks'][number],
  provider: MarketplaceProvider,
  fieldSupport: ReturnType<typeof getHookFieldSupport>,
  defaults: ReturnType<typeof getHookDefaults>,
): HookMatcher['hooks'][number] => {
  const common = {
    type: action.type,
    timeout: action.timeout,
    name: fieldSupport.actionMetadata ? (action.name?.trim() || undefined) : undefined,
    description: fieldSupport.actionMetadata ? (action.description?.trim() || undefined) : undefined,
    statusMessage: fieldSupport.statusMessage ? (action.statusMessage?.trim() || undefined) : undefined,
    if: fieldSupport.condition ? (action.if?.trim() || undefined) : undefined,
    once: fieldSupport.once ? Boolean(action.once) : undefined,
  };
  if (action.type === 'http') {
    return { ...common, type: 'http', url: action.url.trim(), headers: action.headers, allowedEnvVars: action.allowedEnvVars };
  }
  if (action.type === 'mcp_tool') {
    return { ...common, type: 'mcp_tool', server: action.server.trim(), tool: action.tool.trim(), input: action.input };
  }
  if (action.type === 'prompt') {
    return { ...common, type: 'prompt', prompt: action.prompt.trim(), model: action.model?.trim() || undefined };
  }
  if (action.type === 'agent') {
    return { ...common, type: 'agent', prompt: action.prompt.trim(), model: action.model?.trim() || undefined };
  }
  return {
    ...common,
    type: 'command',
    command: action.command.trim(),
    shell: fieldSupport.shell ? (action.shell ?? defaults.shell) : undefined,
    async: fieldSupport.async ? Boolean(action.async) : undefined,
    asyncRewake: fieldSupport.async ? Boolean(action.asyncRewake) : undefined,
  };
};
