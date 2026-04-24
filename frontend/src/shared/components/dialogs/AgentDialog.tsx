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
import { Input } from '@/shared/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/shared/components/ui/select';
import { Badge } from '@/shared/components/ui/badge';
import { MarkdownEditor } from '@/shared/components/composite/MarkdownEditor';
import { useI18n } from '@/shared/hooks/useI18n';

// ============================================================================
// 類型定義
// ============================================================================

export type AgentScope = 'project' | 'user' | 'local' | 'plugin';

/**
 * 工作區版本的 SubAgent 數據（兼容 ClaudeDocument）
 */
export interface WorkspaceAgentData {
  id: string;
  workspaceId?: string;
  title: string;
  scope: AgentScope;
  content: string;
  description?: string;
  size?: string;
  metadata?: Record<string, unknown>;
  pluginName?: string;
  marketplaceName?: string;
}

/**
 * 模板版本的 SubAgent 數據
 */
export interface TemplateAgentData {
  localId: string;
  fileName: string;
  content: string;
  description: string;
}

interface FormState {
  fileName: string;
  scope: AgentScope;
  content: string;
}

// ============================================================================
// 工具函數
// ============================================================================

const formatSize = (content: string) => {
  if (!content) {
    return '1KB';
  }
  const kiloBytes = Math.max(1, Math.ceil(content.length / 1024));
  return `${kiloBytes}KB`;
};

const ensureMdExtension = (fileName: string): string => {
  const trimmed = fileName.trim();
  return trimmed.toLowerCase().endsWith('.md') ? trimmed : `${trimmed}.md`;
};

// ============================================================================
// 工作區版本 Props（向後兼容，variant 為可選）
// ============================================================================

interface WorkspaceAgentDialogProps {
  variant?: 'workspace';
  open: boolean;
  mode: 'create' | 'edit';
  initialValue?: WorkspaceAgentData | null;
  onClose: () => void;
  onSubmit: (document: WorkspaceAgentData) => void | Promise<void>;
}

// ============================================================================
// 模板版本 Props
// ============================================================================

interface TemplateAgentDialogProps {
  variant: 'template';
  open: boolean;
  mode: 'create' | 'edit';
  initialValue?: TemplateAgentData | null;
  onClose: () => void;
  onSubmit: (subAgent: TemplateAgentData) => void;
}

export type AgentDialogProps = WorkspaceAgentDialogProps | TemplateAgentDialogProps;

// ============================================================================
// 元件實作
// ============================================================================

export const AgentDialog: React.FC<AgentDialogProps> = (props) => {
  const { open, mode, onClose } = props;
  // 向後兼容：variant 為 undefined 時預設為 'workspace'
  const variant = props.variant ?? 'workspace';
  const { t } = useI18n();

  const showScope = variant === 'workspace';

  // 從初始值建立表單狀態
  const buildInitialState = useCallback((): FormState => {
    if (variant === 'workspace') {
      const initial = props.initialValue as WorkspaceAgentData | null | undefined;
      return {
        fileName: (initial?.metadata?.fileName as string | undefined) ?? '',
        scope: initial?.scope ?? 'project',
        content: initial?.content ?? '',
      };
    } else {
      const initial = props.initialValue as TemplateAgentData | null | undefined;
      return {
        fileName: initial?.fileName ?? '',
        scope: 'project',
        content: initial?.content ?? '',
      };
    }
  }, [variant, props.initialValue]);

  const [formState, setFormState] = useState<FormState>(buildInitialState);
  const [submitting, setSubmitting] = useState(false);
  const [errors, setErrors] = useState<{ fileName?: string; content?: string }>({});

  const scopeOptions = useMemo(
    () => [
      { value: 'project', label: t('workspace.claudeCode.documents.scope.values.project') },
      { value: 'user', label: t('workspace.claudeCode.documents.scope.values.user') },
    ],
    [t]
  );

  useEffect(() => {
    if (open) {
      setFormState(buildInitialState());
      setErrors({});
      setSubmitting(false);
    }
  }, [open, buildInitialState]);

  const isEdit = mode === 'edit';

  // 取得翻譯 key 前綴
  const getTranslationKey = (key: string) => {
    if (variant === 'workspace') {
      return `workspace.claudeCode.subagents.dialog.${key}`;
    }
    return `template.editor.agents.dialog.${key}`;
  };

  const validate = () => {
    const nextErrors: { fileName?: string; content?: string } = {};
    if (!formState.fileName.trim()) {
      nextErrors.fileName = t(getTranslationKey('validation.fileName'));
    }
    if (!formState.content.trim()) {
      nextErrors.content = t(getTranslationKey('validation.content'));
    }
    setErrors(nextErrors);
    return Object.keys(nextErrors).length === 0;
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!validate()) {
      return;
    }
    setSubmitting(true);

    const normalizedFileName = ensureMdExtension(formState.fileName);

    try {
      if (variant === 'workspace') {
        const initial = props.initialValue as WorkspaceAgentData | null | undefined;
        const identifier =
          (initial?.metadata?.fileName as string | undefined) ?? initial?.id ?? normalizedFileName;
        const scope = formState.scope;

        const document: WorkspaceAgentData = {
          id: `${scope}:${identifier}`,
          title: normalizedFileName,
          description: '',
          scope,
          content: formState.content,
          size: formatSize(formState.content),
          metadata: {
            fileName: identifier,
          },
        };

        (props as WorkspaceAgentDialogProps).onSubmit(document);
      } else {
        const initial = props.initialValue as TemplateAgentData | null | undefined;
        const subAgent: TemplateAgentData = {
          localId: initial?.localId || `local-${Math.random().toString(36).slice(2, 10)}`,
          fileName: normalizedFileName,
          description: '',
          content: formState.content,
        };

        (props as TemplateAgentDialogProps).onSubmit(subAgent);
      }
      onClose();
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(next) => !submitting && (!next ? onClose() : null)}>
      <DialogContent className="flex h-[85vh] max-h-[85vh] w-full max-w-4xl flex-col p-0">
        <DialogHeader className="flex-shrink-0 px-6 pt-6">
          <DialogTitle>
            {isEdit ? t(getTranslationKey('title.edit')) : t(getTranslationKey('title.create'))}
          </DialogTitle>
          <DialogDescription>
            {isEdit
              ? t(getTranslationKey('description.edit'))
              : t(getTranslationKey('description.create'))}
          </DialogDescription>
        </DialogHeader>

        <form className="flex flex-1 flex-col overflow-hidden" onSubmit={handleSubmit}>
          <div className="flex-1 overflow-hidden px-6 pb-6 pt-4">
            <div className="flex h-full flex-col space-y-6">
              {/* Scope + FileName (工作區版本) 或 FileName only (模板版本) */}
              {showScope ? (
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <label className="text-sm font-medium text-foreground">
                      {t('workspace.claudeCode.subagents.dialog.fields.scope.label')}
                    </label>
                    {isEdit ? (
                      <Badge variant="outline" className="text-sm">
                        {scopeOptions.find((option) => option.value === formState.scope)?.label ??
                          formState.scope}
                      </Badge>
                    ) : (
                      <Select
                        value={formState.scope}
                        onValueChange={(value) =>
                          setFormState((prev) => ({ ...prev, scope: value as AgentScope }))
                        }
                      >
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {scopeOptions.map((option) => (
                            <SelectItem key={option.value} value={option.value}>
                              {option.label}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    )}
                  </div>

                  <div className="space-y-2">
                    <label className="text-sm font-medium text-foreground">
                      {t(getTranslationKey('fields.fileName.label'))}
                    </label>
                    <Input
                      value={formState.fileName}
                      onChange={(event) =>
                        setFormState((prev) => ({ ...prev, fileName: event.target.value }))
                      }
                      placeholder={t(getTranslationKey('fields.fileName.placeholder'))}
                    />
                    {errors.fileName && (
                      <p className="text-xs text-destructive">{errors.fileName}</p>
                    )}
                  </div>
                </div>
              ) : (
                <div className="space-y-2">
                  <label className="text-sm font-medium text-foreground">
                    {t(getTranslationKey('fields.fileName.label'))}
                  </label>
                  <Input
                    value={formState.fileName}
                    onChange={(event) =>
                      setFormState((prev) => ({ ...prev, fileName: event.target.value }))
                    }
                    placeholder={t(getTranslationKey('fields.fileName.placeholder'))}
                  />
                  {errors.fileName && <p className="text-xs text-destructive">{errors.fileName}</p>}
                  <p className="text-xs text-muted-foreground">
                    {t('template.editor.agents.dialog.fields.fileName.helper')}
                  </p>
                </div>
              )}

              {/* Content Editor */}
              <div className="flex flex-1 flex-col space-y-2">
                <label className="text-sm font-medium text-foreground">
                  {t(getTranslationKey('fields.content.label'))}
                </label>
                <div className="flex-1 overflow-hidden rounded-lg border">
                  <MarkdownEditor
                    value={formState.content}
                    onChange={(value) => setFormState((prev) => ({ ...prev, content: value ?? '' }))}
                    className="h-full"
                    footerExtras={
                      <span className="text-xs text-muted-foreground">
                        {variant === 'workspace'
                          ? t('workspace.claudeCode.subagents.dialog.fields.content.estimatedSize', {
                              size: formatSize(formState.content),
                            })
                          : t('template.editor.agents.dialog.fields.content.sizeHint', {
                              size: formatSize(formState.content),
                            })}
                      </span>
                    }
                  />
                </div>
                {errors.content && <p className="mt-2 text-xs text-destructive">{errors.content}</p>}
                <p className="text-xs text-muted-foreground">
                  {t(getTranslationKey('fields.content.helper'))}
                </p>
              </div>
            </div>
          </div>

          <DialogFooter className="flex-shrink-0 gap-2 px-6 pb-6">
            <Button type="button" variant="ghost" onClick={onClose} disabled={submitting}>
              {variant === 'workspace'
                ? t('workspace.claudeCode.subagents.dialog.actions.cancel')
                : t('common.cancel')}
            </Button>
            <Button type="submit" disabled={submitting}>
              {isEdit
                ? t(getTranslationKey('actions.save'))
                : t(getTranslationKey('actions.create'))}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
};

export default AgentDialog;
