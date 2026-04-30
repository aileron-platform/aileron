import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Workflow } from 'lucide-react';
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
import type { HookFormValue } from '@/features/template-management/features/template-editor/formTypes';

interface HookFormState {
  id: string;
  eventName: string;
  matchers: HookMatcher[];
}

const DEFAULT_FORM: HookFormState = {
  id: '',
  eventName: 'PreToolUse',
  matchers: [
    {
      matcher: '*',
      hooks: [{ type: 'command', command: '', timeout: 30 }],
    },
  ],
};

const EMPTY_EXISTING_HOOKS: HookFormValue[] = [];

export interface TemplateHookDialogProps {
  open: boolean;
  initialData?: HookFormValue;
  existingHooks?: HookFormValue[];
  onOpenChange: (open: boolean) => void;
  onSave: (data: HookFormValue) => void;
}

export const TemplateHookDialog: React.FC<TemplateHookDialogProps> = ({
  open,
  initialData,
  existingHooks,
  onOpenChange,
  onSave,
}) => {
  const { t } = useI18n();
  const [form, setForm] = useState<HookFormState>(DEFAULT_FORM);
  const [showDuplicateWarning, setShowDuplicateWarning] = useState(false);
  const isEdit = Boolean(initialData);
  const existingHookList = existingHooks ?? EMPTY_EXISTING_HOOKS;

  const eventOptions = useMemo(() => [
    {
      value: 'PreToolUse',
      label: t('template.editor.hooks.events.preToolUse.label'),
      description: t('template.editor.hooks.events.preToolUse.description'),
    },
    {
      value: 'PostToolUse',
      label: t('template.editor.hooks.events.postToolUse.label'),
      description: t('template.editor.hooks.events.postToolUse.description'),
    },
    {
      value: 'UserPromptSubmit',
      label: t('template.editor.hooks.events.userPromptSubmit.label'),
      description: t('template.editor.hooks.events.userPromptSubmit.description'),
    },
    {
      value: 'Notification',
      label: t('template.editor.hooks.events.notification.label'),
      description: t('template.editor.hooks.events.notification.description'),
    },
    {
      value: 'Stop',
      label: t('template.editor.hooks.events.stop.label'),
      description: t('template.editor.hooks.events.stop.description'),
    },
    {
      value: 'SubagentStop',
      label: t('template.editor.hooks.events.subagentStop.label'),
      description: t('template.editor.hooks.events.subagentStop.description'),
    },
    {
      value: 'PreCompact',
      label: t('template.editor.hooks.events.preCompact.label'),
      description: t('template.editor.hooks.events.preCompact.description'),
    },
    {
      value: 'SessionStart',
      label: t('template.editor.hooks.events.sessionStart.label'),
      description: t('template.editor.hooks.events.sessionStart.description'),
    },
    {
      value: 'SessionEnd',
      label: t('template.editor.hooks.events.sessionEnd.label'),
      description: t('template.editor.hooks.events.sessionEnd.description'),
    },
  ], [t]);

  const checkDuplicateEvent = useCallback(
    (eventType: string) => {
      if (isEdit) return false;

      const hasDuplicate = existingHookList.some((hook) => hook.event === eventType);
      setShowDuplicateWarning(hasDuplicate);
      return hasDuplicate;
    },
    [existingHookList, isEdit],
  );

  useEffect(() => {
    if (!open) return;

    if (initialData) {
      setForm({
        id: initialData.localId,
        eventName: initialData.event,
        matchers: initialData.matchers.map((matcher) => ({
          matcher: matcher.matcher ?? '*',
          hooks: matcher.hooks.map((exec) => ({
            type: 'command',
            command: exec.command ?? '',
            timeout: exec.timeout ?? 30,
          })),
        })),
      });
      setShowDuplicateWarning(false);
      return;
    }

    const nextForm = {
      ...DEFAULT_FORM,
      id: `local-${Math.random().toString(36).slice(2, 10)}`,
    };
    setForm(nextForm);
    checkDuplicateEvent(nextForm.eventName);
  }, [checkDuplicateEvent, initialData, open]);

  const handleEventChange = (eventName: string) => {
    setForm((prev) => ({ ...prev, eventName }));
    checkDuplicateEvent(eventName);
  };

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();

    if (!isEdit && showDuplicateWarning) {
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
            command: hookAction.command,
            timeout: hookAction.timeout,
          })),
      }))
      .filter((matcher) => matcher.hooks.length > 0);

    onSave({
      localId: form.id,
      event: form.eventName,
      matchers: processedMatchers,
    });
    onOpenChange(false);
  };

  const matcherLabels: HookMatcherActionsLabels = {
    matcherSectionTitle: t('template.editor.hooks.dialog.matchers.title'),
    matcherAdd: t('template.editor.hooks.dialog.matchers.add'),
    matcherPatternLabel: t('template.editor.hooks.dialog.matchers.patternLabel'),
    matcherPatternPlaceholder: t('template.editor.hooks.dialog.matchers.patternPlaceholder'),
    matcherPatternHelp: [
      t('template.editor.hooks.dialog.matchers.patternHelp.overview'),
      `- ${t('template.editor.hooks.dialog.matchers.patternHelp.literal')}`,
      `- ${t('template.editor.hooks.dialog.matchers.patternHelp.regex')}`,
      `- ${t('template.editor.hooks.dialog.matchers.patternHelp.wildcard')}`,
    ],
    matcherRemove: t('common.remove'),
    executionSectionTitle: t('template.editor.hooks.dialog.executions.title'),
    executionAdd: t('template.editor.hooks.dialog.executions.add'),
    executionTimeoutLabel: t('template.editor.hooks.dialog.executions.timeoutLabel'),
    executionTimeoutPlaceholder: t('template.editor.hooks.dialog.executions.timeoutPlaceholder'),
    executionTimeoutHelp: t('template.editor.hooks.dialog.executions.timeoutHelp'),
    executionCommandLabel: t('template.editor.hooks.dialog.executions.commandLabel'),
    executionCommandPlaceholder: t('template.editor.hooks.dialog.executions.commandPlaceholder'),
    executionCommandHelp: t('template.editor.hooks.dialog.executions.commandHelp'),
    executionRemove: t('template.editor.hooks.dialog.executions.remove'),
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="flex h-[85vh] max-h-[85vh] max-w-4xl flex-col p-0">
        <DialogHeader className="flex-shrink-0 px-6 pt-6">
          <DialogTitle className="flex items-center gap-2">
            <Workflow className="h-5 w-5 text-primary" />
            {t(`template.editor.hooks.dialog.title.${isEdit ? 'edit' : 'create'}`)}
          </DialogTitle>
          <DialogDescription>
            {t('template.editor.hooks.dialog.description')}
          </DialogDescription>
        </DialogHeader>

        <div className="flex-1 overflow-y-auto px-6 py-4">
          <form onSubmit={handleSubmit} className="space-y-6">
            <div className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="eventName">
                  {t('template.editor.hooks.dialog.fields.event.label')}
                </Label>
                <Select
                  value={form.eventName}
                  onValueChange={handleEventChange}
                  disabled={isEdit}
                >
                  <SelectTrigger>
                    <SelectValue placeholder={t('template.editor.hooks.dialog.fields.event.placeholder')} />
                  </SelectTrigger>
                  <SelectContent>
                    {eventOptions.map((option) => (
                      <SelectItem key={option.value} value={option.value}>
                        <div>
                          <div className="font-medium">{option.label}</div>
                          <div className="text-xs text-muted-foreground">{option.description}</div>
                        </div>
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
                          {t('template.editor.hooks.dialog.validation.duplicateEventWarning')}
                        </p>
                        <p className="mt-1 text-xs text-amber-700">
                          {t('template.editor.hooks.dialog.validation.duplicateEventSuggestion')}
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
              matcherCardClassName="bg-background"
              commandClassName="font-mono text-sm"
              onChange={(matchers) => setForm((prev) => ({ ...prev, matchers }))}
            />
          </form>
        </div>

        <DialogFooter className="flex-shrink-0 px-6 pb-6">
          <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
            {t('common.cancel')}
          </Button>
          <Button
            type="submit"
            onClick={handleSubmit}
            disabled={!isEdit && showDuplicateWarning}
          >
            {t(`template.editor.hooks.dialog.actions.${isEdit ? 'save' : 'create'}`)}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default TemplateHookDialog;
