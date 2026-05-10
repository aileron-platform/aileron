import React from 'react';
import { Edit, Terminal, Trash2, Workflow } from 'lucide-react';

import { MarketplaceFeatureContentSection } from '../../components/MarketplaceFeatureContentSection';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/shared/components/ui/dialog';
import { Input } from '@/shared/components/ui/input';
import { Label } from '@/shared/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/shared/components/ui/select';
import WarningIcon from '@/shared/components/ui/WarningIcon';
import { HookMatcherActionsEditor, type HookMatcher, type HookMatcherActionsLabels } from '@/shared/components/hook-workflow';
import {
  HOOK_EVENT_MATCHER_HINTS,
  HOOK_EVENTS,
  HOOK_TYPES,
  createEmptyExecution,
  createEmptyHookValue,
  createEmptyMatcher,
  getHookDefaults,
  getHookFieldSupport,
  isValidEventForProvider,
} from '@/shared/hooks/providerHookSpec';
import { useI18n } from '@/shared/hooks/useI18n';
import type { MarketplaceProvider } from '@/shared/types/marketplace';

import { marketplaceEditorItemTitle, type MarketplaceEditorResourceItem } from './marketplaceEditorResourceItems';

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
  const primaryMatcher = hook.matchers[0];
  const primaryAction = primaryMatcher?.hooks[0];
  const timeoutLabel = formatMarketplaceHookTimeout(provider, primaryAction?.timeout);

  return (
    <>
      <div className="relative rounded-lg border border-border bg-background p-6">
        <div className="flex items-start">
          <div className="min-w-0 flex-1">
            <div className="mb-3">
              <div className="flex items-center gap-3">
                <h3 className="text-lg font-semibold text-foreground">{hook.name}</h3>
                <Badge variant="outline" className="text-xs">
                  {hook.event}
                </Badge>
              </div>
            </div>

            <div className="mb-4">
              <div className="mb-3 flex items-center gap-2">
                <Terminal className="h-4 w-4 text-muted-foreground" />
                <span className="text-sm font-medium text-muted-foreground">
                  {t('marketplace.editor.hooks.card.matchersTitle')}
                </span>
              </div>
              <div className="rounded-lg bg-muted/50 p-3">
                <div className="mb-2 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-muted-foreground">
                      {t('marketplace.editor.hooks.card.matcherLabel')}
                    </span>
                    <code className="rounded bg-muted px-1 text-xs">{primaryMatcher?.matcher ?? '*'}</code>
                  </div>
                  <span className="text-xs text-muted-foreground">
                    {t('marketplace.editor.hooks.card.actionsCount', { count: 1 })}
                  </span>
                </div>
                <div className="mb-1 rounded bg-muted px-2 py-1 text-xs">
                  <div className="mb-1 flex items-center gap-2">
                    <Badge variant="outline" className="px-1 py-0 text-xs">
                      {t(`marketplace.editor.hooks.dialog.executions.types.${primaryAction?.type ?? 'command'}.label`)}
                    </Badge>
                    {primaryAction?.timeout ? <span className="text-muted-foreground">{timeoutLabel}</span> : null}
                    {primaryMatcher?.sequential ? (
                      <span className="text-muted-foreground">
                        {t('marketplace.editor.hooks.card.sequential')}
                      </span>
                    ) : null}
                  </div>
                  <p className="truncate font-mono text-muted-foreground">{marketplaceHookActionSummary(primaryAction)}</p>
                </div>
              </div>
            </div>

            <div className="flex gap-4 rounded bg-muted/30 px-3 py-2 text-xs text-muted-foreground">
              <span>{t('marketplace.editor.hooks.card.summary.matchers', { count: 1 })}</span>
              <span>{t('marketplace.editor.hooks.card.summary.commands', { count: 1 })}</span>
            </div>
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
  const [draft, setDraft] = React.useState(value);
  const fieldSupport = getHookFieldSupport(provider);
  const defaults = getHookDefaults(provider);

  React.useEffect(() => {
    if (open) {
      setDraft(value);
    }
  }, [open, value]);

  React.useEffect(() => {
    setDraft(prev => (
      isValidEventForProvider(provider, prev.event)
        ? prev
        : { ...prev, event: HOOK_EVENTS[provider][0] }
    ));
  }, [provider]);

  const eventOptions = React.useMemo(() => HOOK_EVENTS[provider].map(event => ({
    value: event,
    label: t(`marketplace.editor.hooks.events.${event}.label`),
    description: t(`marketplace.editor.hooks.events.${event}.description`),
  })), [provider, t]);
  const matcherHint = HOOK_EVENT_MATCHER_HINTS[draft.event];
  const matcherHelpKey = matcherHint?.helpKey ?? 'generic';
  const matcherExampleKey = matcherHint?.examplesKey ?? 'generic';

  const matcherLabels: HookMatcherActionsLabels = {
    matcherSectionTitle: t('marketplace.editor.hooks.dialog.matchers.title'),
    matcherAdd: t('marketplace.editor.hooks.dialog.matchers.add'),
    matcherPatternLabel: t('marketplace.editor.hooks.dialog.matchers.patternLabel'),
    matcherPatternPlaceholder: t('marketplace.editor.hooks.dialog.matchers.patternPlaceholder'),
    matcherPatternHelp: [
      t(`marketplace.editor.hooks.dialog.matcherHints.${matcherHelpKey}.help`),
      `- ${t(`marketplace.editor.hooks.dialog.matcherHints.${matcherExampleKey}.example`)}`,
    ],
    matcherUnsupportedMessage: t('marketplace.editor.hooks.dialog.matcherHints.unsupported.message'),
    matcherSequentialLabel: fieldSupport.sequential ? t('marketplace.editor.hooks.dialog.matchers.sequentialLabel') : undefined,
    matcherSequentialHelp: fieldSupport.sequential ? t('marketplace.editor.hooks.dialog.matchers.sequentialHelp') : undefined,
    matcherRemove: t('marketplace.common.actions.remove'),
    executionSectionTitle: t('marketplace.editor.hooks.dialog.executions.title'),
    executionAdd: t('marketplace.editor.hooks.dialog.executions.add'),
    executionTypeLabel: t('marketplace.editor.hooks.dialog.executions.typeLabel'),
    executionTypeOptions: HOOK_TYPES[provider].map(hookType => ({
      value: hookType,
      label: t(`marketplace.editor.hooks.dialog.executions.types.${hookType}.label`),
      description: t(`marketplace.editor.hooks.dialog.executions.types.${hookType}.description`),
    })),
    executionNameLabel: fieldSupport.actionMetadata ? t('marketplace.editor.hooks.dialog.executions.nameLabel') : undefined,
    executionNamePlaceholder: fieldSupport.actionMetadata ? t('marketplace.editor.hooks.dialog.executions.namePlaceholder') : undefined,
    executionNameHelp: fieldSupport.actionMetadata ? t('marketplace.editor.hooks.dialog.executions.nameHelp') : undefined,
    executionTimeoutLabel: t(`marketplace.editor.hooks.dialog.executions.timeoutLabel.${provider}`),
    executionTimeoutPlaceholder: String(defaults.timeout),
    executionTimeoutHelp: t(`marketplace.editor.hooks.dialog.executions.timeoutHelp.${provider}`),
    executionTimeoutMax: defaults.timeoutMax,
    executionConditionLabel: fieldSupport.condition ? t('marketplace.editor.hooks.dialog.executions.conditionLabel') : undefined,
    executionConditionPlaceholder: fieldSupport.condition ? t('marketplace.editor.hooks.dialog.executions.conditionPlaceholder') : undefined,
    executionConditionHelp: fieldSupport.condition ? t('marketplace.editor.hooks.dialog.executions.conditionHelp') : undefined,
    executionDescriptionLabel: fieldSupport.actionMetadata ? t('marketplace.editor.hooks.dialog.executions.descriptionLabel') : undefined,
    executionDescriptionPlaceholder: fieldSupport.actionMetadata ? t('marketplace.editor.hooks.dialog.executions.descriptionPlaceholder') : undefined,
    executionDescriptionHelp: fieldSupport.actionMetadata ? t('marketplace.editor.hooks.dialog.executions.descriptionHelp') : undefined,
    executionCommandLabel: t(`marketplace.editor.hooks.dialog.executions.commandLabel.${provider}`),
    executionCommandPlaceholder: t(`marketplace.editor.hooks.dialog.executions.commandPlaceholder.${provider}`),
    executionCommandHelp: t(`marketplace.editor.hooks.dialog.executions.commandHelp.${provider}`),
    executionStatusMessageLabel: fieldSupport.statusMessage ? t('marketplace.editor.hooks.dialog.executions.statusMessageLabel') : undefined,
    executionStatusMessagePlaceholder: fieldSupport.statusMessage ? t('marketplace.editor.hooks.dialog.executions.statusMessagePlaceholder') : undefined,
    executionStatusMessageHelp: fieldSupport.statusMessage ? t('marketplace.editor.hooks.dialog.executions.statusMessageHelp') : undefined,
    executionUrlLabel: t('marketplace.editor.hooks.dialog.executions.url.label'),
    executionUrlPlaceholder: t('marketplace.editor.hooks.dialog.executions.url.placeholder'),
    executionUrlHelp: t('marketplace.editor.hooks.dialog.executions.url.help'),
    executionHeadersLabel: t('marketplace.editor.hooks.dialog.executions.headers.label'),
    executionHeadersHelp: t('marketplace.editor.hooks.dialog.executions.headers.help'),
    executionHeaderKeyPlaceholder: t('marketplace.editor.hooks.dialog.executions.headers.keyPlaceholder'),
    executionHeaderValuePlaceholder: t('marketplace.editor.hooks.dialog.executions.headers.valuePlaceholder'),
    executionHeadersAdd: t('marketplace.editor.hooks.dialog.executions.headers.add'),
    executionHeadersRemove: t('marketplace.editor.hooks.dialog.executions.headers.remove'),
    executionAllowedEnvVarsLabel: t('marketplace.editor.hooks.dialog.executions.allowedEnvVars.label'),
    executionAllowedEnvVarsPlaceholder: t('marketplace.editor.hooks.dialog.executions.allowedEnvVars.placeholder'),
    executionAllowedEnvVarsHelp: t('marketplace.editor.hooks.dialog.executions.allowedEnvVars.help'),
    executionServerLabel: t('marketplace.editor.hooks.dialog.executions.server.label'),
    executionServerPlaceholder: t('marketplace.editor.hooks.dialog.executions.server.placeholder'),
    executionServerHelp: t('marketplace.editor.hooks.dialog.executions.server.help'),
    executionToolLabel: t('marketplace.editor.hooks.dialog.executions.tool.label'),
    executionToolPlaceholder: t('marketplace.editor.hooks.dialog.executions.tool.placeholder'),
    executionToolHelp: t('marketplace.editor.hooks.dialog.executions.tool.help'),
    executionInputLabel: t('marketplace.editor.hooks.dialog.executions.input.label'),
    executionInputPlaceholder: t('marketplace.editor.hooks.dialog.executions.input.placeholder'),
    executionInputHelp: t('marketplace.editor.hooks.dialog.executions.input.help'),
    executionPromptLabel: t('marketplace.editor.hooks.dialog.executions.promptField.label'),
    executionPromptPlaceholder: t('marketplace.editor.hooks.dialog.executions.promptField.placeholder'),
    executionPromptHelp: t('marketplace.editor.hooks.dialog.executions.promptField.help'),
    executionModelLabel: t('marketplace.editor.hooks.dialog.executions.model.label'),
    executionModelPlaceholder: t('marketplace.editor.hooks.dialog.executions.model.placeholder'),
    executionModelHelp: t('marketplace.editor.hooks.dialog.executions.model.help'),
    executionAsyncLabel: fieldSupport.async ? t('marketplace.editor.hooks.dialog.executions.asyncLabel') : undefined,
    executionAsyncRewakeLabel: fieldSupport.async ? t('marketplace.editor.hooks.dialog.executions.asyncRewakeLabel') : undefined,
    executionOnceLabel: fieldSupport.once ? t('marketplace.editor.hooks.dialog.executions.once.label') : undefined,
    executionOnceHelp: fieldSupport.once ? t('marketplace.editor.hooks.dialog.executions.once.help') : undefined,
    executionShellLabel: fieldSupport.shell ? t('marketplace.editor.hooks.dialog.executions.shellLabel') : undefined,
    executionShellPlaceholder: fieldSupport.shell ? t('marketplace.editor.hooks.dialog.executions.shellPlaceholder') : undefined,
    executionShellOptions: fieldSupport.shell ? [
      { value: 'bash', label: t('marketplace.editor.hooks.dialog.executions.shellOptions.bash') },
      { value: 'powershell', label: t('marketplace.editor.hooks.dialog.executions.shellOptions.powershell') },
    ] : undefined,
    executionRemove: t('marketplace.editor.hooks.dialog.executions.remove'),
  };

  const hasValidHooks = draft.matchers.every(matcher => (
    matcher.hooks.some(hookAction => isMarketplaceHookActionValid(hookAction))
  ));

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    if (!hasValidHooks) return;

    onSave({
      ...draft,
      matchers: draft.matchers
        .map(matcher => ({
          matcher: matcher.matcher.trim() || '*',
          sequential: fieldSupport.sequential ? Boolean(matcher.sequential) : undefined,
          hooks: matcher.hooks
            .filter(hookAction => isMarketplaceHookActionValid(hookAction))
            .map(hookAction => sanitizeMarketplaceHookAction(hookAction, provider, fieldSupport, defaults)),
        }))
        .filter(matcher => matcher.hooks.length > 0),
    });
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="flex h-[85vh] max-h-[85vh] max-w-4xl flex-col p-0">
        <DialogHeader className="flex-shrink-0 px-6 pt-6">
          <DialogTitle className="flex items-center gap-2">
            <Workflow className="h-5 w-5 text-primary" />
            {t(mode === 'create' ? 'marketplace.editor.hooks.dialog.titleCreate' : 'marketplace.editor.hooks.dialog.title')}
          </DialogTitle>
          <DialogDescription>
            {t(`marketplace.editor.hooks.dialog.description.${provider}`)}
          </DialogDescription>
        </DialogHeader>

        <div className="flex-1 overflow-y-auto px-6 py-4">
          <form onSubmit={handleSubmit} className="space-y-6">
            <div className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="marketplace-hook-name">{t('marketplace.editor.hooks.dialog.fields.name.label')}</Label>
                <Input
                  id="marketplace-hook-name"
                  value={draft.name}
                  onChange={event => setDraft(prev => ({ ...prev, name: event.target.value }))}
                  placeholder={t('marketplace.editor.hooks.dialog.fields.name.placeholder')}
                />
              </div>
              <div className="space-y-2">
                <Label>{t('marketplace.editor.hooks.dialog.fields.event.label')}</Label>
                <Select value={draft.event} onValueChange={event => setDraft(prev => ({ ...prev, event }))}>
                  <SelectTrigger>
                    <SelectValue placeholder={t('marketplace.editor.hooks.dialog.fields.event.placeholder')} />
                  </SelectTrigger>
                  <SelectContent>
                    {eventOptions.map(option => (
                      <SelectItem key={option.value} value={option.value}>
                        {option.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                {!hasValidHooks ? (
                  <div className="rounded-md border border-amber-200 bg-amber-50 p-3">
                    <div className="flex">
                      <div className="flex-shrink-0">
                        <WarningIcon />
                      </div>
                      <div className="ml-3">
                        <p className="text-sm text-amber-800">
                          {t('marketplace.editor.hooks.dialog.validation.commandRequired')}
                        </p>
                      </div>
                    </div>
                  </div>
                ) : null}
              </div>
            </div>

            <HookMatcherActionsEditor
              matchers={draft.matchers}
              provider={provider}
              eventName={draft.event}
              labels={matcherLabels}
              matcherCardClassName="bg-background"
              commandClassName="font-mono text-sm"
              createEmptyMatcher={() => createEmptyMatcher(provider)}
              createEmptyExecution={() => createEmptyExecution(provider)}
              onChange={matchers => setDraft(prev => ({ ...prev, matchers }))}
            />
          </form>
        </div>

        <DialogFooter className="flex-shrink-0 px-6 pb-6">
          <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
            {t('marketplace.common.actions.cancel')}
          </Button>
          <Button type="submit" onClick={handleSubmit} disabled={!hasValidHooks}>
            {t(`marketplace.editor.hooks.dialog.actions.${mode === 'create' ? 'create' : 'save'}`)}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
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
  const event = typeof data?.event === 'string' && isValidEventForProvider(provider, data.event)
    ? data.event
    : HOOK_EVENTS[provider][0];
  const matchers = Array.isArray(data?.matchers)
    ? data.matchers as HookMatcher[]
    : [createEmptyMatcher(provider)];

  return {
    name: typeof data?.name === 'string' ? data.name : marketplaceEditorItemTitle(item, t),
    event,
    matchers,
  };
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
