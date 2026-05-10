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
  scope: HookScope;
  eventName: string;
  matchers: HookMatcher[];
}

const createDefaultForm = (provider: MarketplaceProvider, eventName = HOOK_EVENTS[provider][0]): HookFormState => ({
  id: '',
  scope: 'project',
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
  i18nNamespace?: string;
  onClose: () => void;
  onSubmit: (hook: WorkspaceHookData) => void;
}

export const WorkspaceHookDialog: React.FC<WorkspaceHookDialogProps> = ({
  provider,
  open,
  mode,
  hook,
  existingHooks,
  availableScopes,
  eventOptions: externalEventOptions,
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

  const scopeOptions = useMemo(() => {
    const allOptions: { value: HookScope; label: string }[] = [
      { value: 'project', label: t(`${i18nNamespace}.hooks.dialog.scope.options.project`) },
      { value: 'user', label: t(`${i18nNamespace}.hooks.dialog.scope.options.user`) },
      { value: 'local', label: t(`${i18nNamespace}.hooks.dialog.scope.options.local`) },
    ];
    if (!availableScopes) return allOptions;
    return allOptions.filter((option) => availableScopes.includes(option.value));
  }, [availableScopes, i18nNamespace, t]);

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
    const nextForm = { ...createDefaultForm(provider, defaultEvent), id: `hook-${Date.now()}` };
    setForm(nextForm);
    checkDuplicateEvent(nextForm.eventName, nextForm.scope);
  }, [checkDuplicateEvent, externalEventOptions, fieldSupport.actionMetadata, fieldSupport.statusMessage, hook, mode, open, provider]);

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

    const hasValidHooks = form.matchers.every((matcher) =>
      matcher.hooks.some(isWorkspaceHookActionValid),
    );

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
      scope: form.scope,
      eventName: form.eventName,
      matchers: processedMatchers,
    });
  };

  const matcherHint = HOOK_EVENT_MATCHER_HINTS[form.eventName];
  const matcherPatternHelp = provider === 'claude-code'
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

  const matcherLabels: HookMatcherActionsLabels = {
    matcherSectionTitle: t(`${i18nNamespace}.hooks.dialog.matcher.sectionTitle`),
    matcherAdd: t(`${i18nNamespace}.hooks.dialog.matcher.add`),
    matcherPatternLabel: t(`${i18nNamespace}.hooks.dialog.matcher.patternLabel`),
    matcherPatternPlaceholder: t(`${i18nNamespace}.hooks.dialog.matcher.patternPlaceholder`),
    matcherPatternHelp,
    matcherUnsupportedMessage: provider === 'claude-code'
      ? t(`${hookI18nNamespace}.hooks.dialog.matcherHints.unsupported.message`)
      : t(`${i18nNamespace}.hooks.dialog.matcher.unsupported`),
    matcherRemove: t(`${i18nNamespace}.hooks.dialog.matcher.remove`),
    matcherSequentialLabel: fieldSupport.sequential ? t(`${hookI18nNamespace}.hooks.dialog.matcher.sequential.label`) : undefined,
    matcherSequentialHelp: fieldSupport.sequential ? t(`${hookI18nNamespace}.hooks.dialog.matcher.sequential.help`) : undefined,
    executionSectionTitle: t(`${i18nNamespace}.hooks.dialog.execution.sectionTitle`),
    executionAdd: t(`${i18nNamespace}.hooks.dialog.execution.add`),
    executionTypeLabel: t(`${i18nNamespace}.hooks.dialog.execution.typeLabel`),
    executionTypeOptions: HOOK_TYPES[provider].map(hookType => ({
      value: hookType,
      label: t(`${hookTypeI18nPath}.${hookType}.label`),
      description: t(`${hookTypeI18nPath}.${hookType}.description`),
    })),
    ...(fieldSupport.actionMetadata ? {
      executionNameLabel: t(`${i18nNamespace}.hooks.dialog.execution.nameLabel`),
      executionNamePlaceholder: t(`${i18nNamespace}.hooks.dialog.execution.namePlaceholder`),
      executionNameHelp: t(`${i18nNamespace}.hooks.dialog.execution.nameHelp`),
      executionDescriptionLabel: t(`${i18nNamespace}.hooks.dialog.execution.descriptionLabel`),
      executionDescriptionPlaceholder: t(`${i18nNamespace}.hooks.dialog.execution.descriptionPlaceholder`),
      executionDescriptionHelp: t(`${i18nNamespace}.hooks.dialog.execution.descriptionHelp`),
    } : {}),
    executionTimeoutLabel: t(`${i18nNamespace}.hooks.dialog.execution.timeoutLabel`),
    executionTimeoutPlaceholder: String(defaults.timeout),
    executionTimeoutHelp: t(`${i18nNamespace}.hooks.dialog.execution.timeoutHelp`),
    executionCommandLabel: t(`${i18nNamespace}.hooks.dialog.execution.commandLabel`),
    executionCommandPlaceholder: t(`${i18nNamespace}.hooks.dialog.execution.commandPlaceholder`),
    executionCommandHelp: t(`${i18nNamespace}.hooks.dialog.execution.commandHelp`),
    ...(fieldSupport.statusMessage ? {
      executionStatusMessageLabel: t(`${i18nNamespace}.hooks.dialog.execution.statusMessageLabel`),
      executionStatusMessagePlaceholder: t(`${i18nNamespace}.hooks.dialog.execution.statusMessagePlaceholder`),
      executionStatusMessageHelp: t(`${i18nNamespace}.hooks.dialog.execution.statusMessageHelp`),
    } : {}),
    executionUrlLabel: t(`${i18nNamespace}.hooks.dialog.execution.url.label`),
    executionUrlPlaceholder: t(`${i18nNamespace}.hooks.dialog.execution.url.placeholder`),
    executionUrlHelp: t(`${i18nNamespace}.hooks.dialog.execution.url.help`),
    executionHeadersLabel: t(`${i18nNamespace}.hooks.dialog.execution.headers.label`),
    executionHeadersHelp: t(`${i18nNamespace}.hooks.dialog.execution.headers.help`),
    executionHeaderKeyPlaceholder: t(`${i18nNamespace}.hooks.dialog.execution.headers.keyPlaceholder`),
    executionHeaderValuePlaceholder: t(`${i18nNamespace}.hooks.dialog.execution.headers.valuePlaceholder`),
    executionHeadersAdd: t(`${i18nNamespace}.hooks.dialog.execution.headers.add`),
    executionHeadersRemove: t(`${i18nNamespace}.hooks.dialog.execution.headers.remove`),
    executionAllowedEnvVarsLabel: t(`${i18nNamespace}.hooks.dialog.execution.allowedEnvVars.label`),
    executionAllowedEnvVarsPlaceholder: t(`${i18nNamespace}.hooks.dialog.execution.allowedEnvVars.placeholder`),
    executionAllowedEnvVarsHelp: t(`${i18nNamespace}.hooks.dialog.execution.allowedEnvVars.help`),
    executionServerLabel: t(`${i18nNamespace}.hooks.dialog.execution.server.label`),
    executionServerPlaceholder: t(`${i18nNamespace}.hooks.dialog.execution.server.placeholder`),
    executionServerHelp: t(`${i18nNamespace}.hooks.dialog.execution.server.help`),
    executionToolLabel: t(`${i18nNamespace}.hooks.dialog.execution.tool.label`),
    executionToolPlaceholder: t(`${i18nNamespace}.hooks.dialog.execution.tool.placeholder`),
    executionToolHelp: t(`${i18nNamespace}.hooks.dialog.execution.tool.help`),
    executionInputLabel: t(`${i18nNamespace}.hooks.dialog.execution.input.label`),
    executionInputPlaceholder: t(`${i18nNamespace}.hooks.dialog.execution.input.placeholder`),
    executionInputHelp: t(`${i18nNamespace}.hooks.dialog.execution.input.help`),
    executionPromptLabel: t(`${i18nNamespace}.hooks.dialog.execution.promptField.label`),
    executionPromptPlaceholder: t(`${i18nNamespace}.hooks.dialog.execution.promptField.placeholder`),
    executionPromptHelp: t(`${i18nNamespace}.hooks.dialog.execution.promptField.help`),
    executionModelLabel: t(`${i18nNamespace}.hooks.dialog.execution.model.label`),
    executionModelPlaceholder: t(`${i18nNamespace}.hooks.dialog.execution.model.placeholder`),
    executionModelHelp: t(`${i18nNamespace}.hooks.dialog.execution.model.help`),
    executionConditionLabel: fieldSupport.condition ? t(`${hookI18nNamespace}.hooks.dialog.execution.if.label`) : undefined,
    executionConditionPlaceholder: fieldSupport.condition ? t(`${hookI18nNamespace}.hooks.dialog.execution.if.placeholder`) : undefined,
    executionConditionHelp: fieldSupport.condition ? t(`${hookI18nNamespace}.hooks.dialog.execution.if.help`) : undefined,
    executionAsyncLabel: fieldSupport.async ? t(`${hookI18nNamespace}.hooks.dialog.execution.async.label`) : undefined,
    executionAsyncRewakeLabel: fieldSupport.async ? t(`${hookI18nNamespace}.hooks.dialog.execution.asyncRewake.label`) : undefined,
    executionOnceLabel: undefined,
    executionOnceHelp: undefined,
    executionShellLabel: fieldSupport.shell ? t(`${hookI18nNamespace}.hooks.dialog.execution.shell.label`) : undefined,
    executionShellPlaceholder: fieldSupport.shell ? t(`${hookI18nNamespace}.hooks.dialog.execution.shell.placeholder`) : undefined,
    executionShellHelp: fieldSupport.shell ? t(`${hookI18nNamespace}.hooks.dialog.execution.shell.help`) : undefined,
    executionShellOptions: fieldSupport.shell ? [
      { value: 'bash', label: t(`${hookI18nNamespace}.hooks.dialog.execution.shell.options.bash`) },
      { value: 'powershell', label: t(`${hookI18nNamespace}.hooks.dialog.execution.shell.options.powershell`) },
    ] : undefined,
    executionRemove: t(`${i18nNamespace}.hooks.dialog.execution.remove`),
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="flex h-[85vh] max-h-[85vh] max-w-4xl flex-col p-0">
        <DialogHeader className="flex-shrink-0 px-6 pt-6">
          <DialogTitle className="flex items-center gap-2">
            <Workflow className="h-5 w-5 text-primary" />
            {t(`${i18nNamespace}.hooks.dialog.title.${isEdit ? 'edit' : 'create'}`)}
          </DialogTitle>
          <DialogDescription>
            {t(`${i18nNamespace}.hooks.dialog.description`)}
          </DialogDescription>
        </DialogHeader>

        <div className="flex-1 overflow-y-auto px-6 py-4">
          <form onSubmit={handleSubmit} className="space-y-6">
            <div className="space-y-4">
              {isEdit ? (
                <div className="space-y-2">
                  <Label>{t(`${i18nNamespace}.hooks.dialog.scope.label`)}</Label>
                  <Badge variant="outline" className="w-fit">
                    {scopeOptions.find((option) => option.value === form.scope)?.label || form.scope}
                  </Badge>
                </div>
              ) : (
                <div className="space-y-2">
                  <Label htmlFor="scope">
                    {t(`${i18nNamespace}.hooks.dialog.scope.labelWithAsterisk`)}
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
              )}

              <div className="space-y-2">
                <Label htmlFor="eventName">
                  {t(`${i18nNamespace}.hooks.dialog.event.label`)}
                </Label>
                <Select
                  value={form.eventName}
                  onValueChange={(value) => handleChange('eventName', value)}
                  disabled={isEdit}
                >
                  <SelectTrigger>
                    <SelectValue placeholder={t(`${i18nNamespace}.hooks.dialog.event.placeholder`)} />
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
            {t(`${i18nNamespace}.hooks.dialog.actions.cancel`)}
          </Button>
          <Button
            type="submit"
            onClick={handleSubmit}
            disabled={mode === 'create' && showDuplicateWarning}
          >
            {t(`${i18nNamespace}.hooks.dialog.actions.${isEdit ? 'save' : 'create'}`)}
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
