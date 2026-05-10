import React from 'react';
import { Plus, Trash2 } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import { Checkbox } from '@/shared/components/ui/checkbox';
import { Input } from '@/shared/components/ui/input';
import { Label } from '@/shared/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/shared/components/ui/select';
import { Textarea } from '@/shared/components/ui/textarea';
import type { MarketplaceProvider } from '@/shared/types/marketplace';
import {
  HOOK_TYPES,
  HOOK_TYPE_FIELDS,
  HOOK_EVENT_MATCHER_HINTS,
  getHookDefaults,
  getHookFieldSupport,
  getHookTimeoutDefault,
  isConditionSupportedForEvent,
  migrateActionToType,
  type HookType,
} from '@/shared/hooks/providerHookSpec';

export interface BaseHookAction {
  type: HookType;
  name?: string | null;
  description?: string | null;
  timeout?: number;
  statusMessage?: string | null;
  if?: string | null;
  once?: boolean;
  raw?: Record<string, unknown>;
}

export interface CommandHookAction extends BaseHookAction {
  type: 'command';
  command: string;
  async?: boolean;
  asyncRewake?: boolean;
  shell?: 'bash' | 'powershell' | null;
}

export interface HttpHookAction extends BaseHookAction {
  type: 'http';
  url: string;
  headers?: Record<string, string>;
  allowedEnvVars?: string[];
}

export interface McpToolHookAction extends BaseHookAction {
  type: 'mcp_tool';
  server: string;
  tool: string;
  input?: Record<string, unknown>;
}

export interface PromptHookAction extends BaseHookAction {
  type: 'prompt';
  prompt: string;
  model?: string | null;
}

export interface AgentHookAction extends BaseHookAction {
  type: 'agent';
  prompt: string;
  model?: string | null;
}

export type HookActionConfig =
  | CommandHookAction
  | HttpHookAction
  | McpToolHookAction
  | PromptHookAction
  | AgentHookAction;

export interface HookMatcher {
  matcher: string;
  sequential?: boolean;
  hooks: HookActionConfig[];
  raw?: Record<string, unknown>;
}

export interface HookMatcherActionsLabels {
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
  executionTypeLabel?: string;
  executionTypeOptions?: Array<{ value: HookType; label: string; description?: string }>;
  executionNameLabel?: string;
  executionNamePlaceholder?: string;
  executionNameHelp?: string;
  executionTimeoutLabel: string;
  executionTimeoutPlaceholder: string;
  executionTimeoutHelp: string;
  executionTimeoutMax?: number;
  executionConditionLabel?: string;
  executionConditionPlaceholder?: string;
  executionConditionHelp?: string;
  executionDescriptionLabel?: string;
  executionDescriptionPlaceholder?: string;
  executionDescriptionHelp?: string;
  executionCommandLabel: string;
  executionCommandPlaceholder: string;
  executionCommandHelp: string;
  executionUrlLabel?: string;
  executionUrlPlaceholder?: string;
  executionUrlHelp?: string;
  executionHeadersLabel?: string;
  executionHeadersHelp?: string;
  executionHeaderKeyPlaceholder?: string;
  executionHeaderValuePlaceholder?: string;
  executionHeadersAdd?: string;
  executionHeadersRemove?: string;
  executionAllowedEnvVarsLabel?: string;
  executionAllowedEnvVarsPlaceholder?: string;
  executionAllowedEnvVarsHelp?: string;
  executionServerLabel?: string;
  executionServerPlaceholder?: string;
  executionServerHelp?: string;
  executionToolLabel?: string;
  executionToolPlaceholder?: string;
  executionToolHelp?: string;
  executionInputLabel?: string;
  executionInputPlaceholder?: string;
  executionInputHelp?: string;
  executionPromptLabel?: string;
  executionPromptPlaceholder?: string;
  executionPromptHelp?: string;
  executionModelLabel?: string;
  executionModelPlaceholder?: string;
  executionModelHelp?: string;
  executionStatusMessageLabel?: string;
  executionStatusMessagePlaceholder?: string;
  executionStatusMessageHelp?: string;
  executionAsyncLabel?: string;
  executionAsyncRewakeLabel?: string;
  executionOnceLabel?: string;
  executionOnceHelp?: string;
  executionShellLabel?: string;
  executionShellPlaceholder?: string;
  executionShellHelp?: string;
  executionShellOptions?: Array<{ value: 'bash' | 'powershell'; label: string }>;
  executionRemove: string;
}

export interface HookMatcherActionsEditorProps {
  matchers: HookMatcher[];
  labels: HookMatcherActionsLabels;
  provider?: MarketplaceProvider;
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

interface HookActionEditorProps {
  provider: MarketplaceProvider;
  eventName?: string;
  action: HookActionConfig;
  labels: HookMatcherActionsLabels;
  commandClassName?: string;
  canRemove: boolean;
  actionIdPrefix: string;
  onChange: (updates: Record<string, unknown>) => void;
  onTypeChange: (hookType: HookType) => void;
  onRemove: () => void;
}

const HookActionEditor: React.FC<HookActionEditorProps> = ({
  provider,
  eventName,
  action,
  labels,
  commandClassName,
  canRemove,
  actionIdPrefix,
  onChange,
  onTypeChange,
  onRemove,
}) => {
  const providerSupport = getHookFieldSupport(provider);
  const typeFields = HOOK_TYPE_FIELDS[action.type];
  const timeout = getHookTimeoutDefault(provider, action.type);
  const conditionEventScoped = !eventName || isConditionSupportedForEvent(eventName);
  const supportsCondition = providerSupport.condition && conditionEventScoped;
  const typeOptions = labels.executionTypeOptions ?? HOOK_TYPES[provider].map(hookType => ({
    value: hookType,
    label: hookType,
  }));

  return (
    <div className="rounded border border-border/70 bg-muted/30 p-3">
      <div className="space-y-3">
        {HOOK_TYPES[provider].length > 1 ? (
          <div className="space-y-2">
            <Label className="text-sm">{labels.executionTypeLabel}</Label>
            <Select value={action.type} onValueChange={(value: HookType) => onTypeChange(value)}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {typeOptions.map(option => (
                  <SelectItem key={option.value} value={option.value}>
                    <div>
                      <div className="font-medium">{option.label}</div>
                      {option.description ? <div className="text-xs text-muted-foreground">{option.description}</div> : null}
                    </div>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        ) : null}

        {providerSupport.actionMetadata ? (
          <div className="grid gap-3 md:grid-cols-2">
            {labels.executionNameLabel ? (
              <div className="space-y-2">
                <Label className="text-sm">{labels.executionNameLabel}</Label>
                <Input value={action.name ?? ''} onChange={(event) => onChange({ name: event.target.value })} placeholder={labels.executionNamePlaceholder} />
                {labels.executionNameHelp ? <p className="text-xs text-muted-foreground">{labels.executionNameHelp}</p> : null}
              </div>
            ) : null}
            {labels.executionDescriptionLabel ? (
              <div className="space-y-2">
                <Label className="text-sm">{labels.executionDescriptionLabel}</Label>
                <Input value={action.description ?? ''} onChange={(event) => onChange({ description: event.target.value })} placeholder={labels.executionDescriptionPlaceholder} />
                {labels.executionDescriptionHelp ? <p className="text-xs text-muted-foreground">{labels.executionDescriptionHelp}</p> : null}
              </div>
            ) : null}
          </div>
        ) : null}

        {supportsCondition && labels.executionConditionLabel ? (
          <div className="space-y-2">
            <Label className="text-sm">{labels.executionConditionLabel}</Label>
            <Input value={action.if ?? ''} onChange={(event) => onChange({ if: event.target.value })} placeholder={labels.executionConditionPlaceholder} />
            <p className="text-xs text-muted-foreground">{labels.executionConditionHelp}</p>
          </div>
        ) : null}

        <div className="space-y-2">
          <Label className="text-sm">{labels.executionTimeoutLabel}</Label>
          <Input
            type="number"
            min={1}
            max={timeout.max}
            value={action.timeout ?? timeout.default}
            onChange={(event) => onChange({ timeout: Number(event.target.value) || timeout.default })}
            placeholder={labels.executionTimeoutPlaceholder}
          />
          <p className="text-xs text-muted-foreground">{labels.executionTimeoutHelp}</p>
        </div>

        {typeFields.command && action.type === 'command' ? (
          <div className="space-y-2">
            <Label className="text-sm">{labels.executionCommandLabel}</Label>
            <Textarea value={action.command} onChange={(event) => onChange({ command: event.target.value })} placeholder={labels.executionCommandPlaceholder} rows={2} required className={commandClassName} />
            <p className="text-xs text-muted-foreground">{labels.executionCommandHelp}</p>
          </div>
        ) : null}

        {typeFields.url && action.type === 'http' ? (
          <div className="space-y-3">
            <div className="space-y-2">
              <Label className="text-sm">{labels.executionUrlLabel}</Label>
              <Input value={action.url} onChange={(event) => onChange({ url: event.target.value })} placeholder={labels.executionUrlPlaceholder} />
              <p className="text-xs text-muted-foreground">{labels.executionUrlHelp}</p>
            </div>
            <HeadersEditor
              headers={action.headers ?? {}}
              labels={labels}
              onChange={(headers) => onChange({ headers })}
            />
            <div className="space-y-2">
              <Label className="text-sm">{labels.executionAllowedEnvVarsLabel}</Label>
              <Input
                value={(action.allowedEnvVars ?? []).join(', ')}
                onChange={(event) => onChange({ allowedEnvVars: event.target.value.split(',').map(item => item.trim()).filter(Boolean) })}
                placeholder={labels.executionAllowedEnvVarsPlaceholder}
              />
              <p className="text-xs text-muted-foreground">{labels.executionAllowedEnvVarsHelp}</p>
            </div>
          </div>
        ) : null}

        {typeFields.server && action.type === 'mcp_tool' ? (
          <div className="grid gap-3 md:grid-cols-2">
            <div className="space-y-2">
              <Label className="text-sm">{labels.executionServerLabel}</Label>
              <Input value={action.server} onChange={(event) => onChange({ server: event.target.value })} placeholder={labels.executionServerPlaceholder} />
              <p className="text-xs text-muted-foreground">{labels.executionServerHelp}</p>
            </div>
            <div className="space-y-2">
              <Label className="text-sm">{labels.executionToolLabel}</Label>
              <Input value={action.tool} onChange={(event) => onChange({ tool: event.target.value })} placeholder={labels.executionToolPlaceholder} />
              <p className="text-xs text-muted-foreground">{labels.executionToolHelp}</p>
            </div>
            <div className="space-y-2 md:col-span-2">
              <Label className="text-sm">{labels.executionInputLabel}</Label>
              <Textarea
                value={JSON.stringify(action.input ?? {}, null, 2)}
                onChange={(event) => {
                  try {
                    onChange({ input: JSON.parse(event.target.value || '{}') });
                  } catch {
                    onChange({ input: action.input ?? {} });
                  }
                }}
                placeholder={labels.executionInputPlaceholder}
                rows={4}
                className="font-mono text-sm"
              />
              <p className="text-xs text-muted-foreground">{labels.executionInputHelp}</p>
            </div>
          </div>
        ) : null}

        {typeFields.prompt && (action.type === 'prompt' || action.type === 'agent') ? (
          <div className="space-y-3">
            <div className="space-y-2">
              <Label className="text-sm">{labels.executionPromptLabel}</Label>
              <Textarea value={action.prompt} onChange={(event) => onChange({ prompt: event.target.value })} placeholder={labels.executionPromptPlaceholder} rows={3} />
              <p className="text-xs text-muted-foreground">{labels.executionPromptHelp}</p>
            </div>
            <div className="space-y-2">
              <Label className="text-sm">{labels.executionModelLabel}</Label>
              <Input value={action.model ?? ''} onChange={(event) => onChange({ model: event.target.value })} placeholder={labels.executionModelPlaceholder} />
              <p className="text-xs text-muted-foreground">{labels.executionModelHelp}</p>
            </div>
          </div>
        ) : null}

        {providerSupport.statusMessage ? (
          <div className="space-y-2">
            <Label className="text-sm">{labels.executionStatusMessageLabel}</Label>
            <Input value={action.statusMessage ?? ''} onChange={(event) => onChange({ statusMessage: event.target.value })} placeholder={labels.executionStatusMessagePlaceholder} />
            <p className="text-xs text-muted-foreground">{labels.executionStatusMessageHelp}</p>
          </div>
        ) : null}

        {(providerSupport.async || providerSupport.shell || providerSupport.once) && action.type === 'command' ? (
          <div className="grid gap-3 rounded-md border border-border/70 bg-background p-3 md:grid-cols-2">
            {providerSupport.async && labels.executionAsyncLabel ? (
              <HookExecutionFlag
                id={`${actionIdPrefix}-async`}
                label={labels.executionAsyncLabel}
                checked={Boolean(action.async)}
                onCheckedChange={(checked) => onChange(checked ? { async: true } : { async: false, asyncRewake: false })}
              />
            ) : null}
            {providerSupport.async && labels.executionAsyncRewakeLabel ? (
              <HookExecutionFlag
                id={`${actionIdPrefix}-async-rewake`}
                label={labels.executionAsyncRewakeLabel}
                checked={Boolean(action.asyncRewake)}
                onCheckedChange={(checked) => onChange(checked ? { asyncRewake: true, async: true } : { asyncRewake: false })}
              />
            ) : null}
            {providerSupport.once && labels.executionOnceLabel ? (
              <div>
                <HookExecutionFlag id={`${actionIdPrefix}-once`} label={labels.executionOnceLabel} checked={Boolean(action.once)} onCheckedChange={(checked) => onChange({ once: checked })} />
                {labels.executionOnceHelp ? <p className="mt-1 text-xs text-muted-foreground">{labels.executionOnceHelp}</p> : null}
              </div>
            ) : null}
            {providerSupport.shell && labels.executionShellLabel ? (
              <div className="space-y-2 md:col-span-2">
                <Label className="text-sm">{labels.executionShellLabel}</Label>
                <Select value={action.shell ?? getHookDefaults(provider).shell ?? 'bash'} onValueChange={(shell: 'bash' | 'powershell') => onChange({ shell })}>
                  <SelectTrigger>
                    <SelectValue placeholder={labels.executionShellPlaceholder} />
                  </SelectTrigger>
                  <SelectContent>
                    {(labels.executionShellOptions ?? []).map(option => (
                      <SelectItem key={option.value} value={option.value}>{option.label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                {labels.executionShellHelp ? (
                  <p className="text-xs text-muted-foreground">{labels.executionShellHelp}</p>
                ) : null}
              </div>
            ) : null}
          </div>
        ) : providerSupport.once && labels.executionOnceLabel ? (
          <div className="rounded-md border border-border/70 bg-background p-3">
            <HookExecutionFlag id={`${actionIdPrefix}-once`} label={labels.executionOnceLabel} checked={Boolean(action.once)} onCheckedChange={(checked) => onChange({ once: checked })} />
            {labels.executionOnceHelp ? <p className="mt-1 text-xs text-muted-foreground">{labels.executionOnceHelp}</p> : null}
          </div>
        ) : null}

        {canRemove ? (
          <div className="flex justify-end">
            <Button type="button" variant="outline" size="sm" onClick={onRemove} className="h-7 text-xs text-destructive hover:text-destructive">
              <Trash2 className="mr-1 h-3 w-3" />
              {labels.executionRemove}
            </Button>
          </div>
        ) : null}
      </div>
    </div>
  );
};

const HeadersEditor: React.FC<{
  headers: Record<string, string>;
  labels: HookMatcherActionsLabels;
  onChange: (headers: Record<string, string>) => void;
}> = ({ headers, labels, onChange }) => {
  const rows = Object.entries(headers);
  const updateRow = (index: number, key: string, value: string) => {
    const nextRows = rows.map((row, rowIndex) => (rowIndex === index ? [key, value] : row));
    onChange(Object.fromEntries(nextRows.filter(([nextKey]) => nextKey.trim())));
  };
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <div>
          <Label className="text-sm">{labels.executionHeadersLabel}</Label>
          {labels.executionHeadersHelp ? <p className="text-xs text-muted-foreground">{labels.executionHeadersHelp}</p> : null}
        </div>
        <Button type="button" variant="outline" size="sm" onClick={() => onChange({ ...headers, '': '' })}>
          {labels.executionHeadersAdd}
        </Button>
      </div>
      {(rows.length ? rows : [['', '']]).map(([key, value], index) => (
        <div key={index} className="grid gap-2 md:grid-cols-[1fr_1fr_auto]">
          <Input value={key} onChange={(event) => updateRow(index, event.target.value, value)} placeholder={labels.executionHeaderKeyPlaceholder} />
          <Input value={value} onChange={(event) => updateRow(index, key, event.target.value)} placeholder={labels.executionHeaderValuePlaceholder} />
          <Button type="button" variant="outline" size="sm" onClick={() => onChange(Object.fromEntries(rows.filter((_, rowIndex) => rowIndex !== index)))}>
            {labels.executionHeadersRemove}
          </Button>
        </div>
      ))}
    </div>
  );
};

interface HookExecutionFlagProps {
  id: string;
  label: string;
  checked: boolean;
  onCheckedChange: (checked: boolean) => void;
}

const HookExecutionFlag: React.FC<HookExecutionFlagProps> = ({
  id,
  label,
  checked,
  onCheckedChange,
}) => (
  <div className="flex items-center gap-2">
    <Checkbox
      id={id}
      checked={checked}
      onCheckedChange={(nextChecked) => onCheckedChange(nextChecked === true)}
    />
    <Label htmlFor={id} className="text-sm">
      {label}
    </Label>
  </div>
);

export default HookMatcherActionsEditor;
