import React from 'react';
import { Plus, Trash2 } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import { Checkbox } from '@/shared/components/ui/checkbox';
import { Input } from '@/shared/components/ui/input';
import { Label } from '@/shared/components/ui/label';
import {
  HookActionEditor,
  type HookActionEditorLabels,
} from './HookActionEditor';
import {
  HOOK_EVENT_MATCHER_HINTS,
  migrateActionToType,
  type HookProvider,
} from './model/providerHookSpec';
import type {
  HookActionConfig,
  HookMatcher,
  HookType,
} from './model/hookTypes';

export interface HookMatcherActionsLabels extends HookActionEditorLabels {
  matcherSectionTitle: string;
  matcherAdd: string;
  matcherPatternLabel: string;
  matcherPatternPlaceholder: string;
  matcherPatternHelp: string[];
  matcherUnsupportedMessage?: string;
  matcherSequentialLabel?: string;
  matcherSequentialHelp?: string;
  matcherRemove: string;
  executionSectionTitle: string;
  executionAdd: string;
}

export interface HookMatcherActionsEditorProps {
  matchers: HookMatcher[];
  labels: HookMatcherActionsLabels;
  provider?: HookProvider;
  eventName?: string;
  commandClassName?: string;
  matcherCardClassName?: string;
  createEmptyMatcher?: () => HookMatcher;
  createEmptyExecution?: () => HookActionConfig;
  onChange: (matchers: HookMatcher[]) => void;
}

const defaultCreateEmptyExecution = (): HookActionConfig => ({
  type: 'command',
  command: '',
  timeout: 30,
});

const defaultCreateEmptyMatcher = (): HookMatcher => ({
  matcher: '',
  hooks: [defaultCreateEmptyExecution()],
});

export const HookMatcherActionsEditor: React.FC<HookMatcherActionsEditorProps> = ({
  matchers,
  labels,
  provider,
  eventName,
  commandClassName,
  matcherCardClassName = 'bg-card',
  createEmptyMatcher = defaultCreateEmptyMatcher,
  createEmptyExecution = defaultCreateEmptyExecution,
  onChange,
}) => {
  const supportsSequential = Boolean(labels.matcherSequentialLabel);
  const currentProvider = provider ?? 'codex';
  const matcherHint = eventName ? HOOK_EVENT_MATCHER_HINTS[eventName] : undefined;
  const supportsMatcherInput = matcherHint?.supportsMatcher !== false;
  const handleMatcherChange = (matcherIndex: number, value: string) => {
    onChange(matchers.map((item, index) => (
      index === matcherIndex ? { ...item, matcher: value } : item
    )));
  };

  const handleMatcherSequentialChange = (matcherIndex: number, checked: boolean) => {
    onChange(matchers.map((item, index) => (
      index === matcherIndex ? { ...item, sequential: checked } : item
    )));
  };

  const addMatcher = () => {
    onChange([...matchers, createEmptyMatcher()]);
  };

  const removeMatcher = (matcherIndex: number) => {
    onChange(matchers.filter((_, index) => index !== matcherIndex));
  };

  const addHookExecution = (matcherIndex: number) => {
    onChange(matchers.map((matcher, index) => (
      index === matcherIndex
        ? { ...matcher, hooks: [...matcher.hooks, createEmptyExecution()] }
        : matcher
    )));
  };

  const removeHookExecution = (matcherIndex: number, hookIndex: number) => {
    onChange(matchers.map((matcher, index) => (
      index === matcherIndex
        ? { ...matcher, hooks: matcher.hooks.filter((_, currentHookIndex) => currentHookIndex !== hookIndex) }
        : matcher
    )));
  };

  const updateHookExecution = (
    matcherIndex: number,
    hookIndex: number,
    updates: Record<string, unknown>,
  ) => {
    onChange(matchers.map((matcher, index) => (
      index === matcherIndex
        ? {
            ...matcher,
            hooks: matcher.hooks.map((execution, currentHookIndex) => (
              currentHookIndex === hookIndex ? { ...execution, ...updates } : execution
            )),
          }
        : matcher
    )));
  };

  const handleHookTypeChange = (matcherIndex: number, hookIndex: number, hookType: HookType) => {
    onChange(matchers.map((matcher, index) => (
      index === matcherIndex
        ? {
            ...matcher,
            hooks: matcher.hooks.map((execution, currentHookIndex) => (
              currentHookIndex === hookIndex
                ? migrateActionToType(execution, hookType, currentProvider)
                : execution
            )),
          }
        : matcher
    )));
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <Label className="text-base font-medium">{labels.matcherSectionTitle}</Label>
        <Button type="button" variant="outline" size="sm" onClick={addMatcher} className="h-8">
          <Plus className="mr-1 h-4 w-4" />
          {labels.matcherAdd}
        </Button>
      </div>

      {matchers.map((matcher, matcherIndex) => (
        <div
          key={matcherIndex}
          className={`rounded-lg border border-border p-4 ${matcherCardClassName}`}
        >
          <div className="space-y-4">
            <div className="flex items-center gap-4">
              {supportsMatcherInput ? (
                <div className="flex-1 space-y-2">
                  <Label>{labels.matcherPatternLabel}</Label>
                  <Input
                    value={matcher.matcher}
                    onChange={(event) => handleMatcherChange(matcherIndex, event.target.value)}
                    placeholder={labels.matcherPatternPlaceholder}
                  />
                  <div className="text-xs text-muted-foreground">
                    {labels.matcherPatternHelp.map((line, index) => (
                      <p key={`${line}-${index}`}>{line}</p>
                    ))}
                  </div>
                </div>
              ) : (
                <div className="flex-1 rounded-md border border-border/70 bg-muted/30 p-3 text-sm text-muted-foreground">
                  {labels.matcherUnsupportedMessage}
                </div>
              )}

              {matchers.length > 1 ? (
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => removeMatcher(matcherIndex)}
                  className="mt-6 self-start text-destructive hover:text-destructive"
                >
                  <Trash2 className="h-4 w-4" />
                  <span className="sr-only">{labels.matcherRemove}</span>
                </Button>
              ) : null}
            </div>

            {supportsSequential ? (
              <div className="rounded-md border border-border/70 bg-muted/20 p-3">
                <div className="flex items-start gap-3">
                  <Checkbox
                    id={`hook-matcher-${matcherIndex}-sequential`}
                    checked={Boolean(matcher.sequential)}
                    onCheckedChange={(checked) => handleMatcherSequentialChange(matcherIndex, checked === true)}
                  />
                  <div className="space-y-1">
                    <Label htmlFor={`hook-matcher-${matcherIndex}-sequential`} className="text-sm">
                      {labels.matcherSequentialLabel}
                    </Label>
                    {labels.matcherSequentialHelp ? (
                      <p className="text-xs text-muted-foreground">{labels.matcherSequentialHelp}</p>
                    ) : null}
                  </div>
                </div>
              </div>
            ) : null}

            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <Label className="text-sm font-medium">{labels.executionSectionTitle}</Label>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => addHookExecution(matcherIndex)}
                  className="h-7 text-xs"
                >
                  <Plus className="mr-1 h-3 w-3" />
                  {labels.executionAdd}
                </Button>
              </div>

              {matcher.hooks.map((execution, hookIndex) => (
                <HookActionEditor
                  key={hookIndex}
                  provider={currentProvider}
                  eventName={eventName}
                  action={execution}
                  labels={labels}
                  commandClassName={commandClassName}
                  canRemove={matcher.hooks.length > 1}
                  actionIdPrefix={`hook-${matcherIndex}-${hookIndex}`}
                  onChange={(updates) => updateHookExecution(matcherIndex, hookIndex, updates)}
                  onTypeChange={(hookType) => handleHookTypeChange(matcherIndex, hookIndex, hookType)}
                  onRemove={() => removeHookExecution(matcherIndex, hookIndex)}
                />
              ))}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
};
