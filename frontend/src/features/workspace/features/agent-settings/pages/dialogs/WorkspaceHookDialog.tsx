import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Workflow } from 'lucide-react';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/shared/components/ui/dialog';
import { Input } from '@/shared/components/ui/input';
import { Label } from '@/shared/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/shared/components/ui/select';
import WarningIcon from '@/shared/components/ui/WarningIcon';
import { useI18n } from '@/shared/hooks/useI18n';
import {
  HookMatcherActionsEditor,
  type HookMatcher,
  type HookMatcherActionsLabels,
} from '@/shared/components/hook-workflow';
import {
  HOOK_EVENTS,
  HOOK_EVENT_MATCHER_HINTS,
  HOOK_TYPES,
  createEmptyExecution,
  createEmptyMatcher,
  getHookDefaults,
  getHookFieldSupport,
} from '@/shared/hooks/providerHookSpec';
import type { MarketplaceProvider } from '@/shared/types/marketplace';

export type HookScope = 'project' | 'user' | 'local';

export interface WorkspaceHookData {
  id: string;
  name?: string;
  scope: HookScope;
  eventName: string;
  matchers: HookMatcher[];
  pluginName?: string;
  marketplaceName?: string;
}

export interface EventOption {
  value: string;
  label: string;
  description?: string;
}

interface HookFormState {
  id: string;
  name: string;
  scope: HookScope;
  eventName: string;
  matchers: HookMatcher[];
}

const createDefaultForm = (
  provider: MarketplaceProvider,
  eventName = HOOK_EVENTS[provider][0],
  scope: HookScope = 'project',
  name = '',
): HookFormState => ({
  id: '',
  name,
  scope,
  eventName,
  matchers: [createEmptyMatcher(provider)],
});

const EMPTY_EXISTING_HOOKS: WorkspaceHookData[] = [];

export interface WorkspaceHookDialogProps {
  provider: MarketplaceProvider;
  open: boolean;
  mode: 'create' | 'edit';
  hook: WorkspaceHookData | null;
  existingHooks?: WorkspaceHookData[];
  availableScopes?: HookScope[];
  eventOptions?: EventOption[];
  showNameField?: boolean;
  showScopeField?: boolean;
  dialogVariant?: 'workspace' | 'marketplace';
  i18nNamespace?: string;
  onClose: () => void;
  onSubmit: (hook: WorkspaceHookData) => void;
}

export const WorkspaceHookDialog: React.FC<WorkspaceHookDialogProps> = ({
  provider = 'claude-code',
  open,
  mode,
  hook,
  existingHooks,
  availableScopes,
  eventOptions: externalEventOptions,
  showNameField = false,
  showScopeField = true,
  dialogVariant = 'workspace',
  i18nNamespace = 'workspace.agentSettings.common',
  onClose,
  onSubmit,
}) => {
  const { t } = useI18n();
  const [form, setForm] = useState<HookFormState>(() => createDefaultForm(provider));
  const [showDuplicateWarning, setShowDuplicateWarning] = useState(false);
  const fieldSupport = getHookFieldSupport(provider);
  const defaults = getHookDefaults(provider);
  const isEdit = mode === 'edit';
  const existingHookList = existingHooks ?? EMPTY_EXISTING_HOOKS;
  const hookI18nNamespace =
    provider === 'claude-code'
      ? 'workspace.agentSettings.claude'
      : provider === 'gemini'
        ? 'workspace.agentSettings.gemini'
        : i18nNamespace;
  const hookTypeI18nPath = provider === 'claude-code'
    ? `${hookI18nNamespace}.hooks.dialog.types`
    : `${i18nNamespace}.hooks.dialog.execution.types`;
  const isMarketplaceDialog = dialogVariant === 'marketplace';
  const dialogTitle = isMarketplaceDialog
    ? t(`marketplace.editor.hooks.dialog.${isEdit ? 'title' : 'titleCreate'}`)
    : t(`${i18nNamespace}.hooks.dialog.title.${isEdit ? 'edit' : 'create'}`);
  const dialogDescription = isMarketplaceDialog
    ? t(`marketplace.editor.hooks.dialog.description.${provider}`)
    : t(`${i18nNamespace}.hooks.dialog.description`);
  const cancelLabel = isMarketplaceDialog
    ? t('marketplace.common.actions.cancel')
    : t(`${i18nNamespace}.hooks.dialog.actions.cancel`);
  const submitLabel = isMarketplaceDialog
    ? t('marketplace.editor.hooks.dialog.actions.save')
    : t(`${i18nNamespace}.hooks.dialog.actions.${isEdit ? 'save' : 'create'}`);
  const nameLabel = isMarketplaceDialog
    ? t('marketplace.editor.hooks.dialog.fields.name.label')
    : t(`${i18nNamespace}.hooks.dialog.name.label`);
  const namePlaceholder = isMarketplaceDialog
    ? t('marketplace.editor.hooks.dialog.fields.name.placeholder')
    : t(`${i18nNamespace}.hooks.dialog.name.placeholder`);
  const eventLabel = isMarketplaceDialog
    ? t('marketplace.editor.hooks.dialog.fields.event.label')
    : t(`${i18nNamespace}.hooks.dialog.event.label`);
  const eventPlaceholder = isMarketplaceDialog
    ? t('marketplace.editor.hooks.dialog.fields.event.placeholder')
    : t(`${i18nNamespace}.hooks.dialog.event.placeholder`);
  const matcherSectionTitle = isMarketplaceDialog
    ? t('marketplace.editor.hooks.dialog.matchers.title')
    : t(`${i18nNamespace}.hooks.dialog.matcher.sectionTitle`);
  const matcherAdd = isMarketplaceDialog
    ? t('marketplace.editor.hooks.dialog.matchers.add')
    : t(`${i18nNamespace}.hooks.dialog.matcher.add`);
  const matcherPatternLabel = isMarketplaceDialog
    ? t('marketplace.editor.hooks.dialog.matchers.patternLabel')
    : t(`${i18nNamespace}.hooks.dialog.matcher.patternLabel`);
  const matcherPatternPlaceholder = isMarketplaceDialog
    ? t('marketplace.editor.hooks.dialog.matchers.patternPlaceholder')
    : t(`${i18nNamespace}.hooks.dialog.matcher.patternPlaceholder`);
  const matcherSequentialLabel = isMarketplaceDialog
    ? t('marketplace.editor.hooks.dialog.matchers.sequentialLabel')
    : t(`${i18nNamespace}.hooks.dialog.matcher.sequentialLabel`);
  const matcherSequentialHelp = isMarketplaceDialog
    ? t('marketplace.editor.hooks.dialog.matchers.sequentialHelp')
    : t(`${i18nNamespace}.hooks.dialog.matcher.sequentialHelp`);
  const matcherUnsupportedMessage = isMarketplaceDialog
    ? t('marketplace.editor.hooks.dialog.matchers.unsupported')
    : t(`${i18nNamespace}.hooks.dialog.matcher.unsupported`);
  const executionSectionTitle = isMarketplaceDialog
    ? t('marketplace.editor.hooks.dialog.executions.title')
    : t(`${i18nNamespace}.hooks.dialog.execution.sectionTitle`);
  const executionAdd = isMarketplaceDialog
    ? t('marketplace.editor.hooks.dialog.executions.add')
    : t(`${i18nNamespace}.hooks.dialog.execution.add`);
  const executionTypeLabel = isMarketplaceDialog
    ? t('marketplace.editor.hooks.dialog.executions.typeLabel')
    : t(`${i18nNamespace}.hooks.dialog.execution.typeLabel`);
  const executionTypeOptions = isMarketplaceDialog
    ? HOOK_TYPES[provider].map((hookType) => ({
      value: hookType,
      label: t(`marketplace.editor.hooks.dialog.executions.types.${hookType}.label`),
      description: t(`marketplace.editor.hooks.dialog.executions.types.${hookType}.description`),
    }))
    : HOOK_TYPES[provider].map((hookType) => ({
      value: hookType,
      label: t(`${hookTypeI18nPath}.${hookType}.label`),
      description: t(`${hookTypeI18nPath}.${hookType}.description`),
    }));

  const scopeOptions = useMemo(() => {
    const allOptions: { value: HookScope; label: string }[] = [
      { value: 'project', label: t(`${i18nNamespace}.hooks.dialog.scope.options.project`) },
      { value: 'user', label: t(`${i18nNamespace}.hooks.dialog.scope.options.user`) },
      { value: 'local', label: t(`${i18nNamespace}.hooks.dialog.scope.options.local`) },
    ];
    if (!availableScopes) return allOptions;
    return allOptions.filter((option) => availableScopes.includes(option.value));
  }, [availableScopes, i18nNamespace, t]);
  const showScopeSelector = scopeOptions.length > 1;
  const defaultScope = scopeOptions[0]?.value ?? 'project';

  const eventOptions = useMemo<EventOption[]>(() => {
    if (externalEventOptions) {
      return externalEventOptions;
    }

    return HOOK_EVENTS[provider].map((eventName) => ({
      value: eventName,
      label: t(`${hookI18nNamespace}.hooks.events.${eventName}.option`),
    }));
  }, [externalEventOptions, hookI18nNamespace, provider, t]);

  const checkDuplicateEvent = useCallback(
    (eventType: string, scope: HookScope) => {
      if (isEdit) return false;

      const hasDuplicate = existingHookList.some(
        (existingHook) => existingHook.eventName === eventType && existingHook.scope === scope,
      );
      setShowDuplicateWarning(hasDuplicate);
      return hasDuplicate;
    },
    [existingHookList, isEdit],
  );

  useEffect(() => {
    if (!open) return;

    if (mode === 'edit' && hook) {
      setForm({
        id: hook.id,
        name: hook.name ?? '',
        scope: hook.scope,
        eventName: hook.eventName,
        matchers: hook.matchers.map((matcher) => ({
          matcher: matcher.matcher,
          sequential: fieldSupport.sequential ? matcher.sequential : undefined,
          hooks: matcher.hooks.map((exec) => ({
            ...exec,
            timeout: exec.timeout,
            ...(fieldSupport.actionMetadata ? {
              name: exec.name ?? '',
              description: exec.description ?? '',
            } : {}),
            ...(fieldSupport.statusMessage ? { statusMessage: exec.statusMessage ?? '' } : {}),
          })),
        })),
      });
      setShowDuplicateWarning(false);
      return;
    }

    const defaultEvent = externalEventOptions?.[0]?.value ?? HOOK_EVENTS[provider][0];
    const nextForm = {
      ...createDefaultForm(provider, defaultEvent, defaultScope),
      id: `hook-${Date.now()}`,
    };
    setForm(nextForm);
    checkDuplicateEvent(nextForm.eventName, nextForm.scope);
  }, [checkDuplicateEvent, defaultScope, externalEventOptions, fieldSupport.actionMetadata, fieldSupport.statusMessage, hook, mode, open, provider]);

  const handleChange = <TField extends keyof HookFormState>(
    field: TField,
    value: HookFormState[TField],
  ) => {
    setForm((prev) => ({ ...prev, [field]: value }));

    if (field === 'eventName' || field === 'scope') {
      checkDuplicateEvent(
        field === 'eventName' ? (value as string) : form.eventName,
        field === 'scope' ? (value as HookScope) : form.scope,
      );
    }
  };

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();

    if (mode === 'create' && showDuplicateWarning) {
      return;
    }

    if (!hasValidHooks) {
      return;
    }

    const processedMatchers = form.matchers
      .map((matcher) => ({
        matcher: matcher.matcher.trim() || '*',
        sequential: fieldSupport.sequential ? Boolean(matcher.sequential) : undefined,
        hooks: matcher.hooks
          .filter(isWorkspaceHookActionValid)
          .map((hookAction) => sanitizeWorkspaceHookAction(hookAction, provider)),
      }))
      .filter((matcher) => matcher.hooks.length > 0);

    onSubmit({
      id: form.id,
      ...(showNameField ? { name: form.name.trim() } : {}),
      scope: form.scope,
      eventName: form.eventName,
      matchers: processedMatchers,
    });
  };

  const matcherHint = HOOK_EVENT_MATCHER_HINTS[form.eventName];
  const matcherPatternHelp = isMarketplaceDialog
    ? [
      t(`marketplace.editor.hooks.dialog.matcherHints.${matcherHint?.helpKey ?? 'generic'}.help`),
      `- ${t(`marketplace.editor.hooks.dialog.matcherHints.${matcherHint?.examplesKey ?? 'generic'}.example`)}`,
    ]
    : provider === 'claude-code'
      ? [
        t(`${hookI18nNamespace}.hooks.dialog.matcherHints.${matcherHint?.helpKey ?? 'generic'}.help`),
        `- ${t(`${hookI18nNamespace}.hooks.dialog.matcherHints.${matcherHint?.examplesKey ?? 'generic'}.example`)}`,
      ]
      : [
        t(`${i18nNamespace}.hooks.dialog.matcher.helper.intro`),
        t(`${i18nNamespace}.hooks.dialog.matcher.helper.simple`),
        t(`${i18nNamespace}.hooks.dialog.matcher.helper.regex`),
        t(`${i18nNamespace}.hooks.dialog.matcher.helper.wildcard`),
      ];
  const hasValidHooks = form.matchers.every((matcher) =>
    matcher.hooks.some(isWorkspaceHookActionValid),
  );

  const matcherLabels: HookMatcherActionsLabels = {
    matcherSectionTitle,
    matcherAdd,
    matcherPatternLabel,
    matcherPatternPlaceholder,
    matcherPatternHelp,
    matcherUnsupportedMessage,
    matcherRemove: isMarketplaceDialog
      ? t('marketplace.common.actions.remove')
      : t(`${i18nNamespace}.hooks.dialog.matcher.remove`),
    matcherSequentialLabel: fieldSupport.sequential ? matcherSequentialLabel : undefined,
    matcherSequentialHelp: fieldSupport.sequential ? matcherSequentialHelp : undefined,
    executionSectionTitle,
    executionAdd,
    executionTypeLabel,
    executionTypeOptions,
    ...(fieldSupport.actionMetadata ? {
      executionNameLabel: isMarketplaceDialog
        ? t('marketplace.editor.hooks.dialog.executions.nameLabel')
        : t(`${i18nNamespace}.hooks.dialog.execution.nameLabel`),
      executionNamePlaceholder: isMarketplaceDialog
        ? t('marketplace.editor.hooks.dialog.executions.namePlaceholder')
        : t(`${i18nNamespace}.hooks.dialog.execution.namePlaceholder`),
      executionNameHelp: isMarketplaceDialog
        ? t('marketplace.editor.hooks.dialog.executions.nameHelp')
        : t(`${i18nNamespace}.hooks.dialog.execution.nameHelp`),
      executionDescriptionLabel: isMarketplaceDialog
        ? t('marketplace.editor.hooks.dialog.executions.descriptionLabel')
        : t(`${i18nNamespace}.hooks.dialog.execution.descriptionLabel`),
      executionDescriptionPlaceholder: isMarketplaceDialog
        ? t('marketplace.editor.hooks.dialog.executions.descriptionPlaceholder')
        : t(`${i18nNamespace}.hooks.dialog.execution.descriptionPlaceholder`),
      executionDescriptionHelp: isMarketplaceDialog
        ? t('marketplace.editor.hooks.dialog.executions.descriptionHelp')
        : t(`${i18nNamespace}.hooks.dialog.execution.descriptionHelp`),
    } : {}),
    executionTimeoutLabel: isMarketplaceDialog
      ? t(`marketplace.editor.hooks.dialog.executions.timeoutLabel.${provider}`)
      : t(`${i18nNamespace}.hooks.dialog.execution.timeoutLabel`),
    executionTimeoutPlaceholder: String(defaults.timeout),
    executionTimeoutHelp: isMarketplaceDialog
      ? t(`marketplace.editor.hooks.dialog.executions.timeoutHelp.${provider}`)
      : t(`${i18nNamespace}.hooks.dialog.execution.timeoutHelp`),
    executionCommandLabel: isMarketplaceDialog
      ? t(`marketplace.editor.hooks.dialog.executions.commandLabel.${provider}`)
      : t(`${i18nNamespace}.hooks.dialog.execution.commandLabel`),
    executionCommandPlaceholder: isMarketplaceDialog
      ? t(`marketplace.editor.hooks.dialog.executions.commandPlaceholder.${provider}`)
      : t(`${i18nNamespace}.hooks.dialog.execution.commandPlaceholder`),
    executionCommandHelp: isMarketplaceDialog
      ? t(`marketplace.editor.hooks.dialog.executions.commandHelp.${provider}`)
      : t(`${i18nNamespace}.hooks.dialog.execution.commandHelp`),
    ...(fieldSupport.statusMessage ? {
      executionStatusMessageLabel: isMarketplaceDialog
        ? t('marketplace.editor.hooks.dialog.executions.statusMessageLabel')
        : t(`${i18nNamespace}.hooks.dialog.execution.statusMessageLabel`),
      executionStatusMessagePlaceholder: isMarketplaceDialog
        ? t('marketplace.editor.hooks.dialog.executions.statusMessagePlaceholder')
        : t(`${i18nNamespace}.hooks.dialog.execution.statusMessagePlaceholder`),
      executionStatusMessageHelp: isMarketplaceDialog
        ? t('marketplace.editor.hooks.dialog.executions.statusMessageHelp')
        : t(`${i18nNamespace}.hooks.dialog.execution.statusMessageHelp`),
    } : {}),
    executionUrlLabel: isMarketplaceDialog
      ? t('marketplace.editor.hooks.dialog.executions.url.label')
      : t(`${i18nNamespace}.hooks.dialog.execution.url.label`),
    executionUrlPlaceholder: isMarketplaceDialog
      ? t('marketplace.editor.hooks.dialog.executions.url.placeholder')
      : t(`${i18nNamespace}.hooks.dialog.execution.url.placeholder`),
    executionUrlHelp: isMarketplaceDialog
      ? t('marketplace.editor.hooks.dialog.executions.url.help')
      : t(`${i18nNamespace}.hooks.dialog.execution.url.help`),
    executionHeadersLabel: isMarketplaceDialog
      ? t('marketplace.editor.hooks.dialog.executions.headers.label')
      : t(`${i18nNamespace}.hooks.dialog.execution.headers.label`),
    executionHeadersHelp: isMarketplaceDialog
      ? t('marketplace.editor.hooks.dialog.executions.headers.help')
      : t(`${i18nNamespace}.hooks.dialog.execution.headers.help`),
    executionHeaderKeyPlaceholder: isMarketplaceDialog
      ? t('marketplace.editor.hooks.dialog.executions.headers.keyPlaceholder')
      : t(`${i18nNamespace}.hooks.dialog.execution.headers.keyPlaceholder`),
    executionHeaderValuePlaceholder: isMarketplaceDialog
      ? t('marketplace.editor.hooks.dialog.executions.headers.valuePlaceholder')
      : t(`${i18nNamespace}.hooks.dialog.execution.headers.valuePlaceholder`),
    executionHeadersAdd: isMarketplaceDialog
      ? t('marketplace.editor.hooks.dialog.executions.headers.add')
      : t(`${i18nNamespace}.hooks.dialog.execution.headers.add`),
    executionHeadersRemove: isMarketplaceDialog
      ? t('marketplace.editor.hooks.dialog.executions.headers.remove')
      : t(`${i18nNamespace}.hooks.dialog.execution.headers.remove`),
    executionAllowedEnvVarsLabel: isMarketplaceDialog
      ? t('marketplace.editor.hooks.dialog.executions.allowedEnvVars.label')
      : t(`${i18nNamespace}.hooks.dialog.execution.allowedEnvVars.label`),
    executionAllowedEnvVarsPlaceholder: isMarketplaceDialog
      ? t('marketplace.editor.hooks.dialog.executions.allowedEnvVars.placeholder')
      : t(`${i18nNamespace}.hooks.dialog.execution.allowedEnvVars.placeholder`),
    executionAllowedEnvVarsHelp: isMarketplaceDialog
      ? t('marketplace.editor.hooks.dialog.executions.allowedEnvVars.help')
      : t(`${i18nNamespace}.hooks.dialog.execution.allowedEnvVars.help`),
    executionServerLabel: isMarketplaceDialog
      ? t('marketplace.editor.hooks.dialog.executions.server.label')
      : t(`${i18nNamespace}.hooks.dialog.execution.server.label`),
    executionServerPlaceholder: isMarketplaceDialog
      ? t('marketplace.editor.hooks.dialog.executions.server.placeholder')
      : t(`${i18nNamespace}.hooks.dialog.execution.server.placeholder`),
    executionServerHelp: isMarketplaceDialog
      ? t('marketplace.editor.hooks.dialog.executions.server.help')
      : t(`${i18nNamespace}.hooks.dialog.execution.server.help`),
    executionToolLabel: isMarketplaceDialog
      ? t('marketplace.editor.hooks.dialog.executions.tool.label')
      : t(`${i18nNamespace}.hooks.dialog.execution.tool.label`),
    executionToolPlaceholder: isMarketplaceDialog
      ? t('marketplace.editor.hooks.dialog.executions.tool.placeholder')
      : t(`${i18nNamespace}.hooks.dialog.execution.tool.placeholder`),
    executionToolHelp: isMarketplaceDialog
      ? t('marketplace.editor.hooks.dialog.executions.tool.help')
      : t(`${i18nNamespace}.hooks.dialog.execution.tool.help`),
    executionInputLabel: isMarketplaceDialog
      ? t('marketplace.editor.hooks.dialog.executions.input.label')
      : t(`${i18nNamespace}.hooks.dialog.execution.input.label`),
    executionInputPlaceholder: isMarketplaceDialog
      ? t('marketplace.editor.hooks.dialog.executions.input.placeholder')
      : t(`${i18nNamespace}.hooks.dialog.execution.input.placeholder`),
    executionInputHelp: isMarketplaceDialog
      ? t('marketplace.editor.hooks.dialog.executions.input.help')
      : t(`${i18nNamespace}.hooks.dialog.execution.input.help`),
    executionPromptLabel: isMarketplaceDialog
      ? t('marketplace.editor.hooks.dialog.executions.promptField.label')
      : t(`${i18nNamespace}.hooks.dialog.execution.promptField.label`),
    executionPromptPlaceholder: isMarketplaceDialog
      ? t('marketplace.editor.hooks.dialog.executions.promptField.placeholder')
      : t(`${i18nNamespace}.hooks.dialog.execution.promptField.placeholder`),
    executionPromptHelp: isMarketplaceDialog
      ? t('marketplace.editor.hooks.dialog.executions.promptField.help')
      : t(`${i18nNamespace}.hooks.dialog.execution.promptField.help`),
    executionModelLabel: isMarketplaceDialog
      ? t('marketplace.editor.hooks.dialog.executions.model.label')
      : t(`${i18nNamespace}.hooks.dialog.execution.model.label`),
    executionModelPlaceholder: isMarketplaceDialog
      ? t('marketplace.editor.hooks.dialog.executions.model.placeholder')
      : t(`${i18nNamespace}.hooks.dialog.execution.model.placeholder`),
    executionModelHelp: isMarketplaceDialog
      ? t('marketplace.editor.hooks.dialog.executions.model.help')
      : t(`${i18nNamespace}.hooks.dialog.execution.model.help`),
    executionConditionLabel: fieldSupport.condition
      ? (isMarketplaceDialog
        ? t('marketplace.editor.hooks.dialog.executions.conditionLabel')
        : t(`${hookI18nNamespace}.hooks.dialog.execution.if.label`))
      : undefined,
    executionConditionPlaceholder: fieldSupport.condition
      ? (isMarketplaceDialog
        ? t('marketplace.editor.hooks.dialog.executions.conditionPlaceholder')
        : t(`${hookI18nNamespace}.hooks.dialog.execution.if.placeholder`))
      : undefined,
    executionConditionHelp: fieldSupport.condition
      ? (isMarketplaceDialog
        ? t('marketplace.editor.hooks.dialog.executions.conditionHelp')
        : t(`${hookI18nNamespace}.hooks.dialog.execution.if.help`))
      : undefined,
    executionAsyncLabel: fieldSupport.async
      ? (isMarketplaceDialog
        ? t('marketplace.editor.hooks.dialog.executions.asyncLabel')
        : t(`${hookI18nNamespace}.hooks.dialog.execution.async.label`))
      : undefined,
    executionAsyncRewakeLabel: fieldSupport.async
      ? (isMarketplaceDialog
        ? t('marketplace.editor.hooks.dialog.executions.asyncRewakeLabel')
        : t(`${hookI18nNamespace}.hooks.dialog.execution.asyncRewake.label`))
      : undefined,
    executionOnceLabel: undefined,
    executionOnceHelp: undefined,
    executionShellLabel: fieldSupport.shell
      ? (isMarketplaceDialog
        ? t('marketplace.editor.hooks.dialog.executions.shellLabel')
        : t(`${hookI18nNamespace}.hooks.dialog.execution.shell.label`))
      : undefined,
    executionShellPlaceholder: fieldSupport.shell
      ? (isMarketplaceDialog
        ? t('marketplace.editor.hooks.dialog.executions.shellPlaceholder')
        : t(`${hookI18nNamespace}.hooks.dialog.execution.shell.placeholder`))
      : undefined,
    executionShellHelp: fieldSupport.shell
      ? (isMarketplaceDialog
        ? t('marketplace.editor.hooks.dialog.executions.shellHelp')
        : t(`${hookI18nNamespace}.hooks.dialog.execution.shell.help`))
      : undefined,
    executionShellOptions: fieldSupport.shell ? [
      {
        value: 'bash',
        label: isMarketplaceDialog
          ? t('marketplace.editor.hooks.dialog.executions.shellOptions.bash')
          : t(`${hookI18nNamespace}.hooks.dialog.execution.shell.options.bash`),
      },
      {
        value: 'powershell',
        label: isMarketplaceDialog
          ? t('marketplace.editor.hooks.dialog.executions.shellOptions.powershell')
          : t(`${hookI18nNamespace}.hooks.dialog.execution.shell.options.powershell`),
      },
    ] : undefined,
    executionRemove: isMarketplaceDialog
      ? t('marketplace.editor.hooks.dialog.executions.remove')
      : t(`${i18nNamespace}.hooks.dialog.execution.remove`),
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="flex h-[85vh] max-h-[85vh] max-w-4xl flex-col p-0">
        <DialogHeader className="flex-shrink-0 px-6 pt-6">
          <DialogTitle className="flex items-center gap-2">
            <Workflow className="h-5 w-5 text-primary" />
            {dialogTitle}
          </DialogTitle>
          <DialogDescription>
            {dialogDescription}
          </DialogDescription>
        </DialogHeader>

        <div className="flex-1 overflow-y-auto px-6 py-4">
          <form onSubmit={handleSubmit} className="space-y-6">
            <div className="space-y-4">
              {showNameField ? (
                <div className="space-y-2">
                  <Label htmlFor="name">
                    {nameLabel}
                  </Label>
                  <Input
                    id="name"
                    value={form.name}
                    onChange={(event) => handleChange('name', event.target.value)}
                    placeholder={namePlaceholder}
                  />
                </div>
              ) : null}

              {showScopeField && isEdit ? (
                <div className="space-y-2">
                  <Label>{t(`${i18nNamespace}.hooks.dialog.scope.label`)}</Label>
                  <Badge variant="outline" className="w-fit">
                    {scopeOptions.find((option) => option.value === form.scope)?.label || form.scope}
                  </Badge>
                </div>
              ) : showScopeField && showScopeSelector ? (
                <div className="space-y-2">
                  <Label htmlFor="scope">
                    {isMarketplaceDialog
                      ? t('marketplace.editor.hooks.dialog.fields.scope.label')
                      : t(`${i18nNamespace}.hooks.dialog.scope.labelWithAsterisk`)}
                  </Label>
                  <Select
                    value={form.scope}
                    onValueChange={(value: HookScope) => handleChange('scope', value)}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder={t(`${i18nNamespace}.hooks.dialog.scope.placeholder`)} />
                    </SelectTrigger>
                    <SelectContent>
                      {scopeOptions.map((option) => (
                        <SelectItem key={option.value} value={option.value}>
                          {option.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              ) : null}

                <div className="space-y-2">
                  <Label htmlFor="eventName">
                    {eventLabel}
                  </Label>
                <Select
                  value={form.eventName}
                  onValueChange={(value) => handleChange('eventName', value)}
                  disabled={isEdit}
                >
                    <SelectTrigger>
                      <SelectValue placeholder={eventPlaceholder} />
                    </SelectTrigger>
                  <SelectContent>
                    {eventOptions.map((option) => (
                      <SelectItem key={option.value} value={option.value}>
                        {option.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>

                {showDuplicateWarning ? (
                  <div className="rounded-md border border-amber-200 bg-amber-50 p-3">
                    <div className="flex">
                      <div className="flex-shrink-0">
                        <WarningIcon />
                      </div>
                      <div className="ml-3">
                        <p className="text-sm text-amber-800">
                          {t(`${i18nNamespace}.hooks.dialog.validation.duplicateEventWarning`)}
                        </p>
                        <p className="mt-1 text-xs text-amber-700">
                          {t(`${i18nNamespace}.hooks.dialog.validation.duplicateEventSuggestion`)}
                        </p>
                      </div>
                    </div>
                  </div>
                ) : null}
                {isMarketplaceDialog && !hasValidHooks ? (
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
              matchers={form.matchers}
              provider={provider}
              eventName={form.eventName}
              labels={matcherLabels}
              matcherCardClassName="bg-card"
              createEmptyMatcher={() => createEmptyMatcher(provider)}
              createEmptyExecution={() => createEmptyExecution(provider)}
              onChange={(matchers) => setForm((prev) => ({ ...prev, matchers }))}
            />
          </form>
        </div>

        <DialogFooter className="flex-shrink-0 px-6 pb-6">
          <Button type="button" variant="outline" onClick={onClose}>
            {cancelLabel}
          </Button>
          <Button
            type="submit"
            onClick={handleSubmit}
            disabled={(mode === 'create' && showDuplicateWarning) || (isMarketplaceDialog && !hasValidHooks)}
          >
            {submitLabel}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

const isWorkspaceHookActionValid = (action: HookMatcher['hooks'][number]): boolean => {
  if (action.type === 'http') return Boolean(action.url.trim());
  if (action.type === 'mcp_tool') return Boolean(action.server.trim() && action.tool.trim());
  if (action.type === 'prompt' || action.type === 'agent') return Boolean(action.prompt.trim());
  return Boolean(action.command.trim());
};

const sanitizeWorkspaceHookAction = (
  action: HookMatcher['hooks'][number],
  provider: MarketplaceProvider,
): HookMatcher['hooks'][number] => {
  const support = getHookFieldSupport(provider);
  const common = {
    type: action.type,
    timeout: action.timeout,
    name: support.actionMetadata ? (action.name?.trim() || undefined) : undefined,
    description: support.actionMetadata ? (action.description?.trim() || undefined) : undefined,
    statusMessage: support.statusMessage ? (action.statusMessage?.trim() || undefined) : undefined,
    if: support.condition ? (action.if?.trim() || undefined) : undefined,
    once: support.once ? Boolean(action.once) : undefined,
  };
  if (action.type === 'http') return { ...common, type: 'http', url: action.url.trim(), headers: action.headers, allowedEnvVars: action.allowedEnvVars };
  if (action.type === 'mcp_tool') return { ...common, type: 'mcp_tool', server: action.server.trim(), tool: action.tool.trim(), input: action.input };
  if (action.type === 'prompt') return { ...common, type: 'prompt', prompt: action.prompt.trim(), model: action.model?.trim() || undefined };
  if (action.type === 'agent') return { ...common, type: 'agent', prompt: action.prompt.trim(), model: action.model?.trim() || undefined };
  return {
    ...common,
    type: 'command',
    command: action.command.trim(),
    shell: support.shell ? (action.shell ?? getHookDefaults(provider).shell) : undefined,
    async: support.async ? Boolean(action.async) : undefined,
    asyncRewake: support.async ? Boolean(action.asyncRewake) : undefined,
  };
};

export default WorkspaceHookDialog;
