import React from 'react';
import { Plus, Trash2 } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { Label } from '@/shared/components/ui/label';
import { Textarea } from '@/shared/components/ui/textarea';

export interface HookActionConfig {
  type: 'command';
  command: string;
  timeout: number;
  statusMessage?: string | null;
  raw?: Record<string, unknown>;
}

export interface HookMatcher {
  matcher: string;
  hooks: HookActionConfig[];
  raw?: Record<string, unknown>;
}

export interface HookMatcherActionsLabels {
  matcherSectionTitle: string;
  matcherAdd: string;
  matcherPatternLabel: string;
  matcherPatternPlaceholder: string;
  matcherPatternHelp: string[];
  matcherRemove: string;
  executionSectionTitle: string;
  executionAdd: string;
  executionTimeoutLabel: string;
  executionTimeoutPlaceholder: string;
  executionTimeoutHelp: string;
  executionCommandLabel: string;
  executionCommandPlaceholder: string;
  executionCommandHelp: string;
  executionStatusMessageLabel?: string;
  executionStatusMessagePlaceholder?: string;
  executionStatusMessageHelp?: string;
  executionRemove: string;
}

export interface HookMatcherActionsEditorProps {
  matchers: HookMatcher[];
  labels: HookMatcherActionsLabels;
  commandClassName?: string;
  matcherCardClassName?: string;
  onChange: (matchers: HookMatcher[]) => void;
}

const createEmptyExecution = (): HookActionConfig => ({
  type: 'command',
  command: '',
  timeout: 30,
});

const createEmptyMatcher = (): HookMatcher => ({
  matcher: '',
  hooks: [createEmptyExecution()],
});

export const HookMatcherActionsEditor: React.FC<HookMatcherActionsEditorProps> = ({
  matchers,
  labels,
  commandClassName,
  matcherCardClassName = 'bg-card',
  onChange,
}) => {
  const supportsStatusMessage = Boolean(labels.executionStatusMessageLabel);
  const handleMatcherChange = (matcherIndex: number, value: string) => {
    onChange(matchers.map((item, index) => (
      index === matcherIndex ? { ...item, matcher: value } : item
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
    updates: Partial<HookActionConfig>,
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
                <div key={hookIndex} className="rounded border border-border/70 bg-muted/30 p-3">
                  <div className="space-y-3">
                    <div className="space-y-2">
                      <Label className="text-sm">{labels.executionTimeoutLabel}</Label>
                      <Input
                        type="number"
                        min={1}
                        max={3600}
                        value={execution.timeout}
                        onChange={(event) =>
                          updateHookExecution(matcherIndex, hookIndex, {
                            timeout: Number(event.target.value) || 30,
                          })
                        }
                        placeholder={labels.executionTimeoutPlaceholder}
                      />
                      <p className="text-xs text-muted-foreground">{labels.executionTimeoutHelp}</p>
                    </div>

                    <div className="space-y-2">
                      <Label className="text-sm">{labels.executionCommandLabel}</Label>
                      <Textarea
                        value={execution.command}
                        onChange={(event) =>
                          updateHookExecution(matcherIndex, hookIndex, {
                            command: event.target.value,
                          })
                        }
                        placeholder={labels.executionCommandPlaceholder}
                        rows={2}
                        required
                        className={commandClassName}
                      />
                      <p className="text-xs text-muted-foreground">{labels.executionCommandHelp}</p>
                    </div>

                    {supportsStatusMessage ? (
                      <div className="space-y-2">
                        <Label className="text-sm">{labels.executionStatusMessageLabel}</Label>
                        <Input
                          value={execution.statusMessage ?? ''}
                          onChange={(event) =>
                            updateHookExecution(matcherIndex, hookIndex, {
                              statusMessage: event.target.value,
                            })
                          }
                          placeholder={labels.executionStatusMessagePlaceholder}
                        />
                        <p className="text-xs text-muted-foreground">{labels.executionStatusMessageHelp}</p>
                      </div>
                    ) : null}

                    {matcher.hooks.length > 1 ? (
                      <div className="flex justify-end">
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          onClick={() => removeHookExecution(matcherIndex, hookIndex)}
                          className="h-7 text-xs text-destructive hover:text-destructive"
                        >
                          <Trash2 className="mr-1 h-3 w-3" />
                          {labels.executionRemove}
                        </Button>
                      </div>
                    ) : null}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
};

export default HookMatcherActionsEditor;
