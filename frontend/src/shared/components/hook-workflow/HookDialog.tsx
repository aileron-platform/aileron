import { DialogHeading } from '@/shared/components/ui/dialog-heading';
import React, { useCallback, useEffect, useState } from 'react';
import { Workflow } from 'lucide-react';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader } from '@/shared/components/ui/dialog';
import { Input } from '@/shared/components/ui/input';
import { Label } from '@/shared/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/shared/components/ui/select';
import { WarningIcon } from '@/shared/components/ui/warning-icon';
import {
  HookMatcherActionsEditor,
  type HookMatcherActionsLabels,
} from './HookMatcherActionsEditor';
import type { HookMatcher } from './model/hookTypes';
import {
  HOOK_EVENTS,
  HOOK_EVENT_MATCHER_HINTS,
  createEmptyExecution,
  createEmptyMatcher,
  getHookFieldSupport,
  type HookProvider,
} from './model/providerHookSpec';
import {
  buildHookDialogSubmitPayload,
  createHookDialogDefaultForm,
  hasDuplicateHookDialogEvent,
  hydrateHookDialogForm,
  isHookDialogActionValid,
  type EventOption,
  type HookFormValues,
  type HookScope,
  type HookDialogData,
} from './model/hookDialogModel';

export type { EventOption, HookScope, HookDialogData } from './model/hookDialogModel';

const EMPTY_EXISTING_HOOKS: HookDialogData[] = [];

type HookDialogMatcherActionsLabels = Omit<
  HookMatcherActionsLabels,
  'matcherPatternHelp' | 'executionTypeOptions' | 'executionShellOptions'
> & {
  matcherPatternHelp: (eventName: string) => string[];
};

export interface HookDialogLabels {
  title: string;
  description: string;
  cancel: string;
  submit: string;
  name: {
    label: string;
    placeholder: string;
  };
  scope: {
    label: string;
    requiredLabel: string;
    placeholder: string;
  };
  event: {
    label: string;
    placeholder: string;
  };
  duplicateEventWarning?: string;
  duplicateEventSuggestion?: string;
  invalidActionWarning?: string;
  matcherActions: HookDialogMatcherActionsLabels;
}

export interface HookDialogOptions {
  events: EventOption[];
  scopes: Array<{ value: HookScope; label: string }>;
  executionTypes: NonNullable<HookMatcherActionsLabels['executionTypeOptions']>;
  executionShells?: NonNullable<HookMatcherActionsLabels['executionShellOptions']>;
  showInvalidActionWarning?: boolean;
}

export interface HookDialogProps {
  provider: HookProvider;
  open: boolean;
  mode: 'create' | 'edit';
  hook: HookDialogData | null;
  existingHooks?: HookDialogData[];
  showNameField?: boolean;
  showScopeField?: boolean;
  labels: HookDialogLabels;
  options: HookDialogOptions;
  onClose: () => void;
  onSubmit: (hook: HookDialogData) => void;
  submitDisabled?: boolean;
}

export const HookDialog: React.FC<HookDialogProps> = ({
  provider,
  open,
  mode,
  hook,
  existingHooks,
  showNameField = false,
  showScopeField = true,
  labels,
  options,
  onClose,
  onSubmit,
  submitDisabled = false,
}) => {
  const [form, setForm] = useState<HookFormValues>(() => createHookDialogDefaultForm(provider));
  const [showDuplicateWarning, setShowDuplicateWarning] = useState(false);
  const fieldSupport = getHookFieldSupport(provider);
  const isEdit = mode === 'edit';
  const existingHookList = existingHooks ?? EMPTY_EXISTING_HOOKS;
  const scopeOptions = options.scopes;
  const showScopeSelector = scopeOptions.length > 1;
  const defaultScope = scopeOptions[0]?.value ?? 'project';
  const eventOptions = options.events;

  const checkDuplicateEvent = useCallback(
    (eventType: string, scope: HookScope) => {
      const hasDuplicate = hasDuplicateHookDialogEvent(existingHookList, eventType, scope, isEdit);
      setShowDuplicateWarning(hasDuplicate);
      return hasDuplicate;
    },
    [existingHookList, isEdit],
  );

  useEffect(() => {
    if (!open) return;

    if (mode === 'edit' && hook) {
      setForm(hydrateHookDialogForm(hook, provider));
      setShowDuplicateWarning(false);
      return;
    }

    const defaultEvent = eventOptions[0]?.value ?? HOOK_EVENTS[provider][0];
    const nextForm = {
      ...createHookDialogDefaultForm(provider, defaultEvent, defaultScope),
      id: `hook-${Date.now()}`,
    };
    setForm(nextForm);
    checkDuplicateEvent(nextForm.eventName, nextForm.scope);
  }, [checkDuplicateEvent, defaultScope, eventOptions, hook, mode, open, provider]);

  const handleChange = <TField extends keyof HookFormValues>(
    field: TField,
    value: HookFormValues[TField],
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
    if (submitDisabled) {
      return;
    }

    if (mode === 'create' && showDuplicateWarning) {
      return;
    }

    if (!hasValidHooks) {
      return;
    }

    onSubmit(buildHookDialogSubmitPayload(form, provider, showNameField));
  };

  const matcherHint = HOOK_EVENT_MATCHER_HINTS[form.eventName];
  const supportsMatcherInput = matcherHint?.supportsMatcher !== false;
  const matcherPatternHelp = !supportsMatcherInput
    ? []
    : labels.matcherActions.matcherPatternHelp(form.eventName);
  const hasValidHooks = form.matchers.every((matcher) =>
    matcher.hooks.some(isHookDialogActionValid),
  );

  const matcherLabels: HookMatcherActionsLabels = {
    ...labels.matcherActions,
    matcherPatternHelp,
    executionTypeOptions: options.executionTypes,
    executionShellOptions: fieldSupport.shell ? options.executionShells : undefined,
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="flex h-[85vh] max-h-[85vh] max-w-4xl flex-col p-0">
        <DialogHeader className="flex-shrink-0 px-6 pt-6">
          <DialogHeading icon={Workflow}>
            {labels.title}
          </DialogHeading>
          <DialogDescription>
            {labels.description}
          </DialogDescription>
        </DialogHeader>

        <div className="flex-1 overflow-y-auto px-6 py-4">
          <form onSubmit={handleSubmit} className="space-y-6">
            <div className="space-y-4">
              {showNameField ? (
                <div className="space-y-2">
                  <Label htmlFor="name">
                    {labels.name.label}
                  </Label>
                  <Input
                    id="name"
                    value={form.name}
                    onChange={(event) => handleChange('name', event.target.value)}
                    placeholder={labels.name.placeholder}
                  />
                </div>
              ) : null}

              {showScopeField && isEdit ? (
                <div className="space-y-2">
                  <Label>{labels.scope.label}</Label>
                  <Badge variant="outline" className="w-fit">
                    {scopeOptions.find((option) => option.value === form.scope)?.label || form.scope}
                  </Badge>
                </div>
              ) : showScopeField && showScopeSelector ? (
                <div className="space-y-2">
                  <Label htmlFor="scope">
                    {labels.scope.requiredLabel}
                  </Label>
                  <Select
                    value={form.scope}
                    onValueChange={(value: HookScope) => handleChange('scope', value)}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder={labels.scope.placeholder} />
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
                    {labels.event.label}
                  </Label>
                <Select
                  value={form.eventName}
                  onValueChange={(value) => handleChange('eventName', value)}
                  disabled={isEdit}
                >
                    <SelectTrigger>
                      <SelectValue placeholder={labels.event.placeholder} />
                    </SelectTrigger>
                  <SelectContent>
                    {eventOptions.map((option) => (
                      <SelectItem key={option.value} value={option.value}>
                        {option.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>

                {showDuplicateWarning && labels.duplicateEventWarning && labels.duplicateEventSuggestion ? (
                  <div className="rounded-md border border-amber-200 bg-amber-50 p-3">
                    <div className="flex">
                      <div className="flex-shrink-0">
                        <WarningIcon />
                      </div>
                      <div className="ml-3">
                        <p className="text-sm text-amber-800">
                          {labels.duplicateEventWarning}
                        </p>
                        <p className="mt-1 text-xs text-amber-700">
                          {labels.duplicateEventSuggestion}
                        </p>
                      </div>
                    </div>
                  </div>
                ) : null}
                {options.showInvalidActionWarning && !hasValidHooks && labels.invalidActionWarning ? (
                  <div className="rounded-md border border-amber-200 bg-amber-50 p-3">
                    <div className="flex">
                      <div className="flex-shrink-0">
                        <WarningIcon />
                      </div>
                      <div className="ml-3">
                        <p className="text-sm text-amber-800">
                          {labels.invalidActionWarning}
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
            {labels.cancel}
          </Button>
          <Button
            type="submit"
            onClick={handleSubmit}
            disabled={
              submitDisabled
              || (mode === 'create' && showDuplicateWarning)
              || (options.showInvalidActionWarning && !hasValidHooks)
            }
          >
            {labels.submit}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};
