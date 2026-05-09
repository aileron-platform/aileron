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

  const emptyHook: MarketplaceHookDialogValue = {
    name: '',
    event: provider === 'gemini' ? 'BeforeTool' : 'PreToolUse',
    matchers: [
      {
        matcher: '*',
        sequential: provider === 'gemini',
        hooks: [{ type: 'command', command: '', timeout: provider === 'gemini' ? 60000 : 120 }],
      },
    ],
  };

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
        content: JSON.stringify(value, null, 2),
        badge: value.event,
        code: firstAction?.command ?? '',
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
  onChange: (item: MarketplaceEditorResourceItem) => void;
}

const MarketplaceHookCard: React.FC<MarketplaceHookCardProps> = ({ provider, item, onDirty, onChange }) => {
  const { t } = useI18n();
  const [dialogOpen, setDialogOpen] = React.useState(false);
  const parsedTimeout = Number(item.meta?.find(meta => meta.labelKey === 'marketplace.editor.featureMeta.labels.timeout')?.value.replace(/[^0-9]/g, '') ?? (provider === 'gemini' ? 60000 : 120));
  const [hook, setHook] = React.useState({
    name: marketplaceEditorItemTitle(item, t),
    event: item.badge ?? (provider === 'gemini' ? 'BeforeTool' : 'PreToolUse'),
    matchers: [
      {
        matcher: item.meta?.find(meta => meta.labelKey === 'marketplace.editor.featureMeta.labels.matcher')?.value ?? '*',
        sequential: provider === 'gemini',
        hooks: [{
          type: (item.meta?.find(meta => meta.labelKey === 'marketplace.editor.featureMeta.labels.type')?.value ?? 'command') as HookMatcher['hooks'][number]['type'],
          command: item.code ?? '',
          timeout: parsedTimeout,
        }],
      },
    ] satisfies HookMatcher[],
  });
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
                  <p className="truncate font-mono text-muted-foreground">
                    {primaryAction?.command ?? ''}
                  </p>
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
          <button type="button" className="rounded-md p-2 transition-colors hover:bg-muted">
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

  React.useEffect(() => {
    if (open) {
      setDraft(value);
    }
  }, [open, value]);

  const eventOptions = React.useMemo(() => getMarketplaceHookEvents(provider).map(event => ({
    value: event,
    label: t(`marketplace.editor.hooks.events.${event}.label`),
    description: t(`marketplace.editor.hooks.events.${event}.description`),
  })), [provider, t]);

  const matcherLabels: HookMatcherActionsLabels = {
    matcherSectionTitle: t('marketplace.editor.hooks.dialog.matchers.title'),
    matcherAdd: t('marketplace.editor.hooks.dialog.matchers.add'),
    matcherPatternLabel: t('marketplace.editor.hooks.dialog.matchers.patternLabel'),
    matcherPatternPlaceholder: t('marketplace.editor.hooks.dialog.matchers.patternPlaceholder'),
    matcherPatternHelp: [
      t(`marketplace.editor.hooks.dialog.matchers.patternHelp.${provider}.overview`),
      `- ${t(`marketplace.editor.hooks.dialog.matchers.patternHelp.${provider}.literal`)}`,
      `- ${t(`marketplace.editor.hooks.dialog.matchers.patternHelp.${provider}.regex`)}`,
      `- ${t(`marketplace.editor.hooks.dialog.matchers.patternHelp.${provider}.wildcard`)}`,
    ],
    matcherSequentialLabel: provider === 'gemini' ? t('marketplace.editor.hooks.dialog.matchers.sequentialLabel') : undefined,
    matcherSequentialHelp: provider === 'gemini' ? t('marketplace.editor.hooks.dialog.matchers.sequentialHelp') : undefined,
    matcherRemove: t('marketplace.common.actions.remove'),
    executionSectionTitle: t('marketplace.editor.hooks.dialog.executions.title'),
    executionAdd: t('marketplace.editor.hooks.dialog.executions.add'),
    executionNameLabel: provider === 'gemini' ? t('marketplace.editor.hooks.dialog.executions.nameLabel') : undefined,
    executionNamePlaceholder: provider === 'gemini' ? t('marketplace.editor.hooks.dialog.executions.namePlaceholder') : undefined,
    executionNameHelp: provider === 'gemini' ? t('marketplace.editor.hooks.dialog.executions.nameHelp') : undefined,
    executionTimeoutLabel: t(`marketplace.editor.hooks.dialog.executions.timeoutLabel.${provider}`),
    executionTimeoutPlaceholder: provider === 'gemini' ? '60000' : '120',
    executionTimeoutHelp: t(`marketplace.editor.hooks.dialog.executions.timeoutHelp.${provider}`),
    executionTimeoutMax: provider === 'gemini' ? 600000 : 3600,
    executionConditionLabel: provider === 'claude-code' ? t('marketplace.editor.hooks.dialog.executions.conditionLabel') : undefined,
    executionConditionPlaceholder: provider === 'claude-code' ? t('marketplace.editor.hooks.dialog.executions.conditionPlaceholder') : undefined,
    executionConditionHelp: provider === 'claude-code' ? t('marketplace.editor.hooks.dialog.executions.conditionHelp') : undefined,
    executionDescriptionLabel: provider === 'gemini' ? t('marketplace.editor.hooks.dialog.executions.descriptionLabel') : undefined,
    executionDescriptionPlaceholder: provider === 'gemini' ? t('marketplace.editor.hooks.dialog.executions.descriptionPlaceholder') : undefined,
    executionDescriptionHelp: provider === 'gemini' ? t('marketplace.editor.hooks.dialog.executions.descriptionHelp') : undefined,
    executionCommandLabel: t(`marketplace.editor.hooks.dialog.executions.commandLabel.${provider}`),
    executionCommandPlaceholder: t(`marketplace.editor.hooks.dialog.executions.commandPlaceholder.${provider}`),
    executionCommandHelp: t(`marketplace.editor.hooks.dialog.executions.commandHelp.${provider}`),
    executionStatusMessageLabel: provider === 'codex' || provider === 'claude-code' ? t('marketplace.editor.hooks.dialog.executions.statusMessageLabel') : undefined,
    executionStatusMessagePlaceholder: provider === 'codex' || provider === 'claude-code' ? t('marketplace.editor.hooks.dialog.executions.statusMessagePlaceholder') : undefined,
    executionStatusMessageHelp: provider === 'codex' || provider === 'claude-code' ? t('marketplace.editor.hooks.dialog.executions.statusMessageHelp') : undefined,
    executionAsyncLabel: provider === 'claude-code' ? t('marketplace.editor.hooks.dialog.executions.asyncLabel') : undefined,
    executionAsyncRewakeLabel: provider === 'claude-code' ? t('marketplace.editor.hooks.dialog.executions.asyncRewakeLabel') : undefined,
    executionShellLabel: provider === 'claude-code' ? t('marketplace.editor.hooks.dialog.executions.shellLabel') : undefined,
    executionShellPlaceholder: provider === 'claude-code' ? t('marketplace.editor.hooks.dialog.executions.shellPlaceholder') : undefined,
    executionShellOptions: provider === 'claude-code' ? [
      { value: 'bash', label: t('marketplace.editor.hooks.dialog.executions.shellOptions.bash') },
      { value: 'powershell', label: t('marketplace.editor.hooks.dialog.executions.shellOptions.powershell') },
    ] : undefined,
    executionRemove: t('marketplace.editor.hooks.dialog.executions.remove'),
  };

  const hasValidHooks = draft.matchers.every(matcher => (
    matcher.hooks.some(hookAction => hookAction.command?.trim())
  ));

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    if (!hasValidHooks) return;

    onSave({
      ...draft,
      matchers: draft.matchers
        .map(matcher => ({
          matcher: matcher.matcher.trim() || '*',
          sequential: provider === 'gemini' ? Boolean(matcher.sequential) : undefined,
          hooks: matcher.hooks
            .filter(hookAction => hookAction.command?.trim())
            .map(hookAction => ({
              ...hookAction,
              type: 'command' as const,
              command: hookAction.command?.trim() ?? '',
              name: hookAction.name?.trim() || undefined,
              description: hookAction.description?.trim() || undefined,
              statusMessage: hookAction.statusMessage?.trim() || undefined,
              if: hookAction.if?.trim() || undefined,
              shell: provider === 'claude-code' ? (hookAction.shell ?? 'bash') : undefined,
              async: provider === 'claude-code' ? Boolean(hookAction.async) : undefined,
              asyncRewake: provider === 'claude-code' ? Boolean(hookAction.asyncRewake) : undefined,
              timeout: hookAction.timeout,
            })),
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
            {provider === 'codex' ? (
              <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
                {t('marketplace.editor.hooks.dialog.codexFeatureFlag')}
              </div>
            ) : null}

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
                        <div>
                          <div className="font-medium">{option.label}</div>
                          <div className="text-xs text-muted-foreground">{option.description}</div>
                        </div>
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
              labels={matcherLabels}
              matcherCardClassName="bg-background"
              commandClassName="font-mono text-sm"
              onChange={matchers => setDraft(prev => ({ ...prev, matchers }))}
            />
          </form>
        </div>

        <DialogFooter className="flex-shrink-0 px-6 pb-6">
          <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
            {t('marketplace.common.actions.cancel')}
          </Button>
          <Button type="submit" onClick={handleSubmit} disabled={!hasValidHooks}>
            {t('marketplace.editor.hooks.dialog.actions.save')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

const getMarketplaceHookEvents = (provider: MarketplaceProvider): string[] => {
  if (provider === 'codex') {
    return [
      'SessionStart',
      'PreToolUse',
      'PostToolUse',
      'PermissionRequest',
      'UserPromptSubmit',
      'Stop',
    ];
  }
  if (provider === 'gemini') {
    return [
      'BeforeTool',
      'AfterTool',
      'BeforeAgent',
      'AfterAgent',
      'BeforeModel',
      'SessionStart',
      'PreCompress',
    ];
  }
  return [
    'PreToolUse',
    'PostToolUse',
    'UserPromptSubmit',
    'Notification',
    'Stop',
    'SubagentStop',
    'PreCompact',
    'SessionStart',
    'SessionEnd',
  ];
};

export const formatMarketplaceHookTimeout = (provider: MarketplaceProvider, timeout?: number): string => (
  provider === 'gemini' ? `${timeout ?? 60000}ms` : `${timeout ?? 120}s`
);

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
    content: JSON.stringify(value, null, 2),
    badge: value.event,
    code: firstAction?.command ?? '',
    meta: [
      { labelKey: 'marketplace.editor.featureMeta.labels.type', value: firstAction?.type ?? 'command' },
      { labelKey: 'marketplace.editor.featureMeta.labels.matcher', value: firstMatcher?.matcher ?? '*' },
      { labelKey: 'marketplace.editor.featureMeta.labels.timeout', value: formatMarketplaceHookTimeout(provider, firstAction?.timeout) },
      ...(firstMatcher?.sequential ? [{ labelKey: 'marketplace.editor.featureMeta.labels.sequential', value: t('marketplace.common.labels.enabled') }] : []),
    ],
  };
};
