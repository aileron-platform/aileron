import React, { useState, useEffect, useMemo, useCallback } from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/shared/components/ui/dialog';
import { Button } from '@/shared/components/ui/button';
import { Label } from '@/shared/components/ui/label';
import { Input } from '@/shared/components/ui/input';
import { Textarea } from '@/shared/components/ui/textarea';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/shared/components/ui/select';
import { Plus, Trash2, Workflow } from 'lucide-react';
import { Badge } from '@/shared/components/ui/badge';
import WarningIcon from '@/shared/components/ui/WarningIcon';
import { useI18n } from '@/shared/hooks/useI18n';

// ============================================================================
// 類型定義
// ============================================================================

export type HookScope = 'project' | 'user' | 'local';

export interface HookActionConfig {
  type: 'command';
  command: string;
  timeout: number;
}

export interface HookMatcher {
  matcher: string;
  hooks: HookActionConfig[];
}

export interface WorkspaceHookData {
  id: string;
  scope: HookScope;
  eventName: string;
  matchers: HookMatcher[];
  pluginName?: string;
  marketplaceName?: string;
}

export interface TemplateHookData {
  localId: string;
  event: string;
  matchers: HookMatcher[];
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

// ============================================================================
// 事件選項
// ============================================================================

export interface EventOption {
  value: string;
  label: string;
  description?: string;
}

// ============================================================================
// Props 類型
// ============================================================================

interface WorkspaceHookDialogProps {
  variant?: 'workspace';
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

interface TemplateHookDialogProps {
  variant: 'template';
  open: boolean;
  initialData?: TemplateHookData;
  existingHooks?: TemplateHookData[];
  onOpenChange: (open: boolean) => void;
  onSave: (data: TemplateHookData) => void;
}

export type HookDialogProps = WorkspaceHookDialogProps | TemplateHookDialogProps;

// ============================================================================
// 元件實作
// ============================================================================

export const HookDialog: React.FC<HookDialogProps> = (props) => {
  const { open } = props;
  const variant = props.variant ?? 'workspace';
  const { t } = useI18n();

  const isWorkspace = variant === 'workspace';
  const mode = isWorkspace
    ? (props as WorkspaceHookDialogProps).mode
    : (props as TemplateHookDialogProps).initialData
      ? 'edit'
      : 'create';
  const isEdit = mode === 'edit';

  const [form, setForm] = useState<HookFormState>(DEFAULT_FORM);
  const [showDuplicateWarning, setShowDuplicateWarning] = useState(false);

  // i18n namespace（僅 workspace 使用）
  const i18nNs = isWorkspace
    ? ((props as WorkspaceHookDialogProps).i18nNamespace ?? 'workspace.claudeCode')
    : 'workspace.claudeCode';

  // 範圍選項（僅 workspace 使用）
  const workspaceAvailableScopes = isWorkspace
    ? (props as WorkspaceHookDialogProps).availableScopes
    : undefined;

  const scopeOptions = useMemo(() => {
    const allOptions: { value: HookScope; label: string }[] = [
      { value: 'project', label: t(`${i18nNs}.hooks.dialog.scope.options.project`) },
      { value: 'user', label: t(`${i18nNs}.hooks.dialog.scope.options.user`) },
      { value: 'local', label: t(`${i18nNs}.hooks.dialog.scope.options.local`) },
    ];
    if (!workspaceAvailableScopes) return allOptions;
    return allOptions.filter((opt) => workspaceAvailableScopes.includes(opt.value));
  }, [t, workspaceAvailableScopes, i18nNs]);

  // 外部傳入的事件選項（workspace variant）
  const externalEventOptions = isWorkspace
    ? (props as WorkspaceHookDialogProps).eventOptions
    : undefined;

  // 事件選項
  const eventOptions = useMemo<EventOption[]>(() => {
    // 優先使用外部傳入的 eventOptions
    if (isWorkspace && externalEventOptions) {
      return externalEventOptions;
    }

    if (isWorkspace) {
      return [
        { value: 'PreToolUse', label: t(`${i18nNs}.hooks.events.PreToolUse.option`) },
        { value: 'PostToolUse', label: t(`${i18nNs}.hooks.events.PostToolUse.option`) },
        { value: 'UserPromptSubmit', label: t(`${i18nNs}.hooks.events.UserPromptSubmit.option`) },
        { value: 'Notification', label: t(`${i18nNs}.hooks.events.Notification.option`) },
        { value: 'Stop', label: t(`${i18nNs}.hooks.events.Stop.option`) },
        { value: 'SubagentStop', label: t(`${i18nNs}.hooks.events.SubagentStop.option`) },
        { value: 'PreCompact', label: t(`${i18nNs}.hooks.events.PreCompact.option`) },
        { value: 'SessionStart', label: t(`${i18nNs}.hooks.events.SessionStart.option`) },
        { value: 'SessionEnd', label: t(`${i18nNs}.hooks.events.SessionEnd.option`) },
      ];
    } else {
      return [
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
      ];
    }
  }, [isWorkspace, externalEventOptions, t, i18nNs]);

  // 取得翻譯 key 前綴
  const getTranslationKey = useCallback(
    (key: string) => {
      return isWorkspace
        ? `${i18nNs}.hooks.dialog.${key}`
        : `template.editor.hooks.dialog.${key}`;
    },
    [isWorkspace, i18nNs]
  );

  // 檢查重複事件
  const checkDuplicateEvent = useCallback(
    (eventType: string, scope?: HookScope) => {
      if (isEdit) return false;

      if (isWorkspace) {
        const existingHooks = (props as WorkspaceHookDialogProps).existingHooks ?? [];
        const hasDuplicate = existingHooks.some(
          (hook) => hook.eventName === eventType && hook.scope === scope
        );
        setShowDuplicateWarning(hasDuplicate);
        return hasDuplicate;
      } else {
        const existingHooks = (props as TemplateHookDialogProps).existingHooks ?? [];
        const hasDuplicate = existingHooks.some((hook) => hook.event === eventType);
        setShowDuplicateWarning(hasDuplicate);
        return hasDuplicate;
      }
    },
    [isEdit, isWorkspace, props]
  );

  // 初始化表單
  useEffect(() => {
    if (!open) return;

    if (isWorkspace) {
      const hook = (props as WorkspaceHookDialogProps).hook;
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
            })),
          })),
        });
        setShowDuplicateWarning(false);
      } else {
        const defaultEvent = eventOptions[0]?.value ?? 'PreToolUse';
        const newForm = { ...DEFAULT_FORM, id: `hook-${Date.now()}`, eventName: defaultEvent };
        setForm(newForm);
        checkDuplicateEvent(newForm.eventName, newForm.scope);
      }
    } else {
      const initialData = (props as TemplateHookDialogProps).initialData;
      if (initialData) {
        setForm({
          id: initialData.localId,
          scope: 'project',
          eventName: initialData.event,
          matchers: initialData.matchers.map((matcher) => ({
            matcher: matcher.matcher,
            hooks: matcher.hooks.map((exec) => ({
              type: 'command',
              command: exec.command ?? '',
              timeout: exec.timeout ?? 30,
            })),
          })),
        });
        setShowDuplicateWarning(false);
      } else {
        const newForm = { ...DEFAULT_FORM, id: `local-${Math.random().toString(36).slice(2, 10)}` };
        setForm(newForm);
        checkDuplicateEvent(newForm.eventName);
      }
    }
  }, [open, mode, isWorkspace, props, checkDuplicateEvent]);

  const handleChange = (field: keyof HookFormState, value: HookFormState[typeof field]) => {
    setForm((prev) => ({ ...prev, [field]: value }));

    if (field === 'eventName' || field === 'scope') {
      checkDuplicateEvent(
        field === 'eventName' ? (value as string) : form.eventName,
        isWorkspace ? (field === 'scope' ? (value as HookScope) : form.scope) : undefined
      );
    }
  };

  const handleMatcherChange = (index: number, value: string) => {
    setForm((prev) => ({
      ...prev,
      matchers: prev.matchers.map((item, i) =>
        i === index ? { ...item, matcher: value } : item
      ),
    }));
  };

  const addMatcher = () => {
    setForm((prev) => ({
      ...prev,
      matchers: [
        ...prev.matchers,
        { matcher: '', hooks: [{ type: 'command', command: '', timeout: 30 }] },
      ],
    }));
  };

  const removeMatcher = (index: number) => {
    setForm((prev) => ({
      ...prev,
      matchers: prev.matchers.filter((_, i) => i !== index),
    }));
  };

  const addHookExecution = (matcherIndex: number) => {
    setForm((prev) => ({
      ...prev,
      matchers: prev.matchers.map((matcher, i) =>
        i === matcherIndex
          ? { ...matcher, hooks: [...matcher.hooks, { type: 'command', command: '', timeout: 30 }] }
          : matcher
      ),
    }));
  };

  const removeHookExecution = (matcherIndex: number, hookIndex: number) => {
    setForm((prev) => ({
      ...prev,
      matchers: prev.matchers.map((matcher, i) =>
        i === matcherIndex
          ? { ...matcher, hooks: matcher.hooks.filter((_, j) => j !== hookIndex) }
          : matcher
      ),
    }));
  };

  const updateHookExecution = (
    matcherIndex: number,
    hookIndex: number,
    updates: Partial<HookActionConfig>
  ) => {
    setForm((prev) => ({
      ...prev,
      matchers: prev.matchers.map((matcher, i) =>
        i === matcherIndex
          ? {
              ...matcher,
              hooks: matcher.hooks.map((exec, j) =>
                j === hookIndex ? { ...exec, ...updates } : exec
              ),
            }
          : matcher
      ),
    }));
  };

  const handleClose = () => {
    if (isWorkspace) {
      (props as WorkspaceHookDialogProps).onClose();
    } else {
      (props as TemplateHookDialogProps).onOpenChange(false);
    }
  };

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();

    if (mode === 'create' && showDuplicateWarning) {
      return;
    }

    const hasValidHooks = form.matchers.every((matcher) =>
      matcher.hooks.some((hook) => hook.command?.trim())
    );

    if (!hasValidHooks) {
      return;
    }

    const processedMatchers = form.matchers
      .map((matcher) => ({
        matcher: matcher.matcher.trim() || '*',
        hooks: matcher.hooks
          .filter((exec) => exec.command?.trim())
          .map((exec) => ({
            type: 'command' as const,
            command: exec.command,
            timeout: exec.timeout,
          })),
      }))
      .filter((matcher) => matcher.hooks.length > 0);

    if (isWorkspace) {
      const payload: WorkspaceHookData = {
        id: form.id,
        scope: form.scope,
        eventName: form.eventName,
        matchers: processedMatchers,
      };
      (props as WorkspaceHookDialogProps).onSubmit(payload);
    } else {
      const payload: TemplateHookData = {
        localId: form.id,
        event: form.eventName,
        matchers: processedMatchers,
      };
      (props as TemplateHookDialogProps).onSave(payload);
      (props as TemplateHookDialogProps).onOpenChange(false);
    }
  };

  // ========== 渲染 ==========

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="flex h-[85vh] max-h-[85vh] max-w-4xl flex-col p-0">
        <DialogHeader className="flex-shrink-0 px-6 pt-6">
          <DialogTitle className="flex items-center gap-2">
            <Workflow className="h-5 w-5 text-primary" />
            {isEdit
              ? t(getTranslationKey('title.edit'))
              : t(getTranslationKey('title.create'))}
          </DialogTitle>
          <DialogDescription>{t(getTranslationKey('description'))}</DialogDescription>
        </DialogHeader>

        <div className="flex-1 overflow-y-auto px-6 py-4">
          <form onSubmit={handleSubmit} className="space-y-6">
            {/* 基本資訊 */}
            <div className="space-y-4">
              {/* 範圍選擇 - 僅 workspace 版本顯示 */}
              {isWorkspace && (
                <>
                  {isEdit ? (
                    <div className="space-y-2">
                      <Label>{t(`${i18nNs}.hooks.dialog.scope.label`)}</Label>
                      <Badge variant="outline" className="w-fit">
                        {scopeOptions.find((opt) => opt.value === form.scope)?.label || form.scope}
                      </Badge>
                    </div>
                  ) : (
                    <div className="space-y-2">
                      <Label htmlFor="scope">
                        {t(`${i18nNs}.hooks.dialog.scope.labelWithAsterisk`)}
                      </Label>
                      <Select
                        value={form.scope}
                        onValueChange={(value: HookScope) => handleChange('scope', value)}
                      >
                        <SelectTrigger>
                          <SelectValue
                            placeholder={t(`${i18nNs}.hooks.dialog.scope.placeholder`)}
                          />
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
                </>
              )}

              {/* 事件類型選擇 */}
              <div className="space-y-2">
                <Label htmlFor="eventName">
                  {isWorkspace
                    ? t(`${i18nNs}.hooks.dialog.event.label`)
                    : t('template.editor.hooks.dialog.fields.event.label')}
                </Label>
                <Select
                  value={form.eventName}
                  onValueChange={(value) => handleChange('eventName', value)}
                  disabled={isEdit}
                >
                  <SelectTrigger>
                    <SelectValue
                      placeholder={
                        isWorkspace
                          ? t(`${i18nNs}.hooks.dialog.event.placeholder`)
                          : t('template.editor.hooks.dialog.fields.event.placeholder')
                      }
                    />
                  </SelectTrigger>
                  <SelectContent>
                    {eventOptions.map((option) => (
                      <SelectItem key={option.value} value={option.value}>
                        {option.description ? (
                          <div>
                            <div className="font-medium">{option.label}</div>
                            <div className="text-xs text-muted-foreground">{option.description}</div>
                          </div>
                        ) : (
                          option.label
                        )}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>

                {/* 重複事件警告 */}
                {showDuplicateWarning && (
                  <div className="rounded-md border border-amber-200 bg-amber-50 p-3">
                    <div className="flex">
                      <div className="flex-shrink-0">
                        <WarningIcon />
                      </div>
                      <div className="ml-3">
                        <p className="text-sm text-amber-800">
                          {t(
                            isWorkspace
                              ? `${i18nNs}.hooks.dialog.validation.duplicateEventWarning`
                              : 'template.editor.hooks.dialog.validation.duplicateEventWarning'
                          )}
                        </p>
                        <p className="mt-1 text-xs text-amber-700">
                          {t(
                            isWorkspace
                              ? `${i18nNs}.hooks.dialog.validation.duplicateEventSuggestion`
                              : 'template.editor.hooks.dialog.validation.duplicateEventSuggestion'
                          )}
                        </p>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Matcher 和 Hook 配置 */}
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <Label className="text-base font-medium">
                  {isWorkspace
                    ? t(`${i18nNs}.hooks.dialog.matcher.sectionTitle`)
                    : t('template.editor.hooks.dialog.matchers.title')}
                </Label>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={addMatcher}
                  className="h-8"
                >
                  <Plus className="mr-1 h-4 w-4" />
                  {isWorkspace
                    ? t(`${i18nNs}.hooks.dialog.matcher.add`)
                    : t('template.editor.hooks.dialog.matchers.add')}
                </Button>
              </div>

              {form.matchers.map((matcher, matcherIndex) => (
                <div
                  key={matcherIndex}
                  className={`rounded-lg border border-border p-4 ${isWorkspace ? 'bg-card' : 'bg-background'}`}
                >
                  <div className="space-y-4">
                    {/* 匹配器設定 */}
                    <div className="flex items-center gap-4">
                      <div className="flex-1 space-y-2">
                        <Label>
                          {isWorkspace
                            ? t(`${i18nNs}.hooks.dialog.matcher.patternLabel`)
                            : t('template.editor.hooks.dialog.matchers.patternLabel')}
                        </Label>
                        <Input
                          value={matcher.matcher}
                          onChange={(event) => handleMatcherChange(matcherIndex, event.target.value)}
                          placeholder={
                            isWorkspace
                              ? t(`${i18nNs}.hooks.dialog.matcher.patternPlaceholder`)
                              : t('template.editor.hooks.dialog.matchers.patternPlaceholder')
                          }
                        />
                        <div className="text-xs text-muted-foreground">
                          {isWorkspace ? (
                            <>
                              <p>{t(`${i18nNs}.hooks.dialog.matcher.helper.intro`)}</p>
                              <p>{t(`${i18nNs}.hooks.dialog.matcher.helper.simple`)}</p>
                              <p>{t(`${i18nNs}.hooks.dialog.matcher.helper.regex`)}</p>
                              <p>{t(`${i18nNs}.hooks.dialog.matcher.helper.wildcard`)}</p>
                            </>
                          ) : (
                            <>
                              <p>{t('template.editor.hooks.dialog.matchers.patternHelp.overview')}</p>
                              <p>• {t('template.editor.hooks.dialog.matchers.patternHelp.literal')}</p>
                              <p>• {t('template.editor.hooks.dialog.matchers.patternHelp.regex')}</p>
                              <p>• {t('template.editor.hooks.dialog.matchers.patternHelp.wildcard')}</p>
                            </>
                          )}
                        </div>
                      </div>

                      {/* 移除匹配器按鈕 */}
                      {form.matchers.length > 1 && (
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          onClick={() => removeMatcher(matcherIndex)}
                          className="mt-6 self-start text-destructive hover:text-destructive"
                        >
                          <Trash2 className="h-4 w-4" />
                          <span className="sr-only">
                            {isWorkspace
                              ? t(`${i18nNs}.hooks.dialog.matcher.remove`)
                              : t('common.remove')}
                          </span>
                        </Button>
                      )}
                    </div>

                    {/* Hook 執行配置 */}
                    <div className="space-y-3">
                      <div className="flex items-center justify-between">
                        <Label className="text-sm font-medium">
                          {isWorkspace
                            ? t(`${i18nNs}.hooks.dialog.execution.sectionTitle`)
                            : t('template.editor.hooks.dialog.executions.title')}
                        </Label>
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          onClick={() => addHookExecution(matcherIndex)}
                          className="h-7 text-xs"
                        >
                          <Plus className="mr-1 h-3 w-3" />
                          {isWorkspace
                            ? t(`${i18nNs}.hooks.dialog.execution.add`)
                            : t('template.editor.hooks.dialog.executions.add')}
                        </Button>
                      </div>

                      {matcher.hooks.map((exec, hookIndex) => (
                        <div
                          key={hookIndex}
                          className="rounded border border-border/70 bg-muted/30 p-3"
                        >
                          <div className="space-y-3">
                            {/* 超時時間 */}
                            <div className="space-y-2">
                              <Label className="text-sm">
                                {isWorkspace
                                  ? t(`${i18nNs}.hooks.dialog.execution.timeoutLabel`)
                                  : t('template.editor.hooks.dialog.executions.timeoutLabel')}
                              </Label>
                              <Input
                                type="number"
                                min={1}
                                max={3600}
                                value={exec.timeout}
                                onChange={(event) =>
                                  updateHookExecution(matcherIndex, hookIndex, {
                                    timeout: Number(event.target.value) || 30,
                                  })
                                }
                                placeholder={
                                  isWorkspace
                                    ? t(`${i18nNs}.hooks.dialog.execution.timeoutPlaceholder`)
                                    : t('template.editor.hooks.dialog.executions.timeoutPlaceholder')
                                }
                              />
                              <p className="text-xs text-muted-foreground">
                                {isWorkspace
                                  ? t(`${i18nNs}.hooks.dialog.execution.timeoutHelp`)
                                  : t('template.editor.hooks.dialog.executions.timeoutHelp')}
                              </p>
                            </div>

                            {/* 命令輸入 */}
                            <div className="space-y-2">
                              <Label className="text-sm">
                                {isWorkspace
                                  ? t(`${i18nNs}.hooks.dialog.execution.commandLabel`)
                                  : t('template.editor.hooks.dialog.executions.commandLabel')}
                              </Label>
                              <Textarea
                                value={exec.command}
                                onChange={(event) =>
                                  updateHookExecution(matcherIndex, hookIndex, {
                                    command: event.target.value,
                                  })
                                }
                                placeholder={
                                  isWorkspace
                                    ? t(`${i18nNs}.hooks.dialog.execution.commandPlaceholder`)
                                    : t('template.editor.hooks.dialog.executions.commandPlaceholder')
                                }
                                rows={2}
                                required
                                className={!isWorkspace ? 'font-mono text-sm' : ''}
                              />
                              <p className="text-xs text-muted-foreground">
                                {isWorkspace
                                  ? t(`${i18nNs}.hooks.dialog.execution.commandHelp`)
                                  : t('template.editor.hooks.dialog.executions.commandHelp')}
                              </p>
                            </div>

                            {/* 移除Hook按鈕 */}
                            {matcher.hooks.length > 1 && (
                              <div className="flex justify-end">
                                <Button
                                  type="button"
                                  variant="outline"
                                  size="sm"
                                  onClick={() => removeHookExecution(matcherIndex, hookIndex)}
                                  className="h-7 text-xs text-destructive hover:text-destructive"
                                >
                                  <Trash2 className="mr-1 h-3 w-3" />
                                  {isWorkspace
                                    ? t(`${i18nNs}.hooks.dialog.execution.remove`)
                                    : t('template.editor.hooks.dialog.executions.remove')}
                                </Button>
                              </div>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </form>
        </div>

        <DialogFooter className="flex-shrink-0 px-6 pb-6">
          <Button type="button" variant="outline" onClick={handleClose}>
            {isWorkspace ? t(`${i18nNs}.hooks.dialog.actions.cancel`) : t('common.cancel')}
          </Button>
          <Button
            type="submit"
            onClick={handleSubmit}
            disabled={mode === 'create' && showDuplicateWarning}
          >
            {isEdit
              ? t(
                  isWorkspace
                    ? `${i18nNs}.hooks.dialog.actions.save`
                    : 'template.editor.hooks.dialog.actions.save'
                )
              : t(
                  isWorkspace
                    ? `${i18nNs}.hooks.dialog.actions.create`
                    : 'template.editor.hooks.dialog.actions.create'
                )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default HookDialog;
