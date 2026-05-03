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

const DEFAULT_FORM: HookFormState = {
  id: '',
  scope: 'project',
  eventName: 'PreToolUse',
  matchers: [
    {
      matcher: '*',
      hooks: [{ type: 'command', command: '', timeout: 30 }],
    },
  ],
};

const EMPTY_EXISTING_HOOKS: WorkspaceHookData[] = [];

export interface WorkspaceHookDialogProps {
  open: boolean;
  mode: 'create' | 'edit';
  hook: WorkspaceHookData | null;
  existingHooks?: WorkspaceHookData[];
  availableScopes?: HookScope[];
  eventOptions?: EventOption[];
  i18nNamespace?: string;
  matcherHelp?: (eventName: string) => string[];
  supportsStatusMessage?: boolean;
  supportsActionMetadata?: boolean;
  onClose: () => void;
  onSubmit: (hook: WorkspaceHookData) => void;
}

export const WorkspaceHookDialog: React.FC<WorkspaceHookDialogProps> = ({
  open,
  mode,
  hook,
  existingHooks,
  availableScopes,
  eventOptions: externalEventOptions,
  i18nNamespace = 'workspace.agentSettings.common',
  matcherHelp,
  supportsStatusMessage = false,
  supportsActionMetadata = false,
  onClose,
  onSubmit,
}) => {
  const { t } = useI18n();
  const [form, setForm] = useState<HookFormState>(DEFAULT_FORM);
  const [showDuplicateWarning, setShowDuplicateWarning] = useState(false);
  const isEdit = mode === 'edit';
  const existingHookList = existingHooks ?? EMPTY_EXISTING_HOOKS;

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
    ].map((eventName) => ({
      value: eventName,
      label: t(`${i18nNamespace}.hooks.events.${eventName}.option`),
    }));
  }, [externalEventOptions, i18nNamespace, t]);

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
          hooks: matcher.hooks.map((exec) => ({
            type: 'command',
            command: exec.command ?? '',
            timeout: exec.timeout ?? 30,
            ...(supportsActionMetadata ? {
              name: exec.name ?? '',
              description: exec.description ?? '',
            } : {}),
            ...(supportsStatusMessage ? { statusMessage: exec.statusMessage ?? '' } : {}),
          })),
        })),
      });
      setShowDuplicateWarning(false);
      return;
    }

    const defaultEvent = externalEventOptions?.[0]?.value ?? 'PreToolUse';
    const nextForm = { ...DEFAULT_FORM, id: `hook-${Date.now()}`, eventName: defaultEvent };
    setForm(nextForm);
    checkDuplicateEvent(nextForm.eventName, nextForm.scope);
  }, [checkDuplicateEvent, externalEventOptions, hook, mode, open, supportsActionMetadata, supportsStatusMessage]);

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
      matcher.hooks.some((hookAction) => hookAction.command?.trim()),
    );

    if (!hasValidHooks) {
      return;
    }

    const processedMatchers = form.matchers
      .map((matcher) => ({
        matcher: matcher.matcher.trim() || '*',
        hooks: matcher.hooks
          .filter((hookAction) => hookAction.command?.trim())
          .map((hookAction) => ({
            type: 'command' as const,
            ...(supportsActionMetadata && hookAction.name?.trim() ? { name: hookAction.name.trim() } : {}),
            command: hookAction.command,
            timeout: hookAction.timeout,
            ...(supportsActionMetadata && hookAction.description?.trim()
              ? { description: hookAction.description.trim() }
              : {}),
            ...(supportsStatusMessage ? { statusMessage: hookAction.statusMessage?.trim() || null } : {}),
          })),
      }))
      .filter((matcher) => matcher.hooks.length > 0);

    onSubmit({
      id: form.id,
      scope: form.scope,
      eventName: form.eventName,
      matchers: processedMatchers,
    });
  };

  const matcherLabels: HookMatcherActionsLabels = {
    matcherSectionTitle: t(`${i18nNamespace}.hooks.dialog.matcher.sectionTitle`),
    matcherAdd: t(`${i18nNamespace}.hooks.dialog.matcher.add`),
    matcherPatternLabel: t(`${i18nNamespace}.hooks.dialog.matcher.patternLabel`),
    matcherPatternPlaceholder: t(`${i18nNamespace}.hooks.dialog.matcher.patternPlaceholder`),
    matcherPatternHelp: matcherHelp?.(form.eventName) ?? [
      t(`${i18nNamespace}.hooks.dialog.matcher.helper.intro`),
      t(`${i18nNamespace}.hooks.dialog.matcher.helper.simple`),
      t(`${i18nNamespace}.hooks.dialog.matcher.helper.regex`),
      t(`${i18nNamespace}.hooks.dialog.matcher.helper.wildcard`),
    ],
    matcherRemove: t(`${i18nNamespace}.hooks.dialog.matcher.remove`),
    executionSectionTitle: t(`${i18nNamespace}.hooks.dialog.execution.sectionTitle`),
    executionAdd: t(`${i18nNamespace}.hooks.dialog.execution.add`),
    ...(supportsActionMetadata ? {
      executionNameLabel: t(`${i18nNamespace}.hooks.dialog.execution.nameLabel`),
      executionNamePlaceholder: t(`${i18nNamespace}.hooks.dialog.execution.namePlaceholder`),
      executionNameHelp: t(`${i18nNamespace}.hooks.dialog.execution.nameHelp`),
      executionDescriptionLabel: t(`${i18nNamespace}.hooks.dialog.execution.descriptionLabel`),
      executionDescriptionPlaceholder: t(`${i18nNamespace}.hooks.dialog.execution.descriptionPlaceholder`),
      executionDescriptionHelp: t(`${i18nNamespace}.hooks.dialog.execution.descriptionHelp`),
    } : {}),
    executionTimeoutLabel: t(`${i18nNamespace}.hooks.dialog.execution.timeoutLabel`),
    executionTimeoutPlaceholder: t(`${i18nNamespace}.hooks.dialog.execution.timeoutPlaceholder`),
    executionTimeoutHelp: t(`${i18nNamespace}.hooks.dialog.execution.timeoutHelp`),
    executionCommandLabel: t(`${i18nNamespace}.hooks.dialog.execution.commandLabel`),
    executionCommandPlaceholder: t(`${i18nNamespace}.hooks.dialog.execution.commandPlaceholder`),
    executionCommandHelp: t(`${i18nNamespace}.hooks.dialog.execution.commandHelp`),
    ...(supportsStatusMessage ? {
      executionStatusMessageLabel: t(`${i18nNamespace}.hooks.dialog.execution.statusMessageLabel`),
      executionStatusMessagePlaceholder: t(`${i18nNamespace}.hooks.dialog.execution.statusMessagePlaceholder`),
      executionStatusMessageHelp: t(`${i18nNamespace}.hooks.dialog.execution.statusMessageHelp`),
    } : {}),
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
              labels={matcherLabels}
              matcherCardClassName="bg-card"
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

export default WorkspaceHookDialog;
