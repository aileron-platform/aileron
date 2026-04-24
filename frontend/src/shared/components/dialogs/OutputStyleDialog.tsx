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
import { Paintbrush } from 'lucide-react';

// ============================================================================
// 類型定義
// ============================================================================

export type OutputStyleScope = 'project' | 'user' | 'local' | 'plugin';

/**
 * 工作區版本的 OutputStyle 數據（兼容 ClaudeDocument）
 */
export interface WorkspaceOutputStyleData {
  id: string;
  workspaceId?: string;
  title: string;
  scope: OutputStyleScope;
  content: string;
  description?: string;
  size?: string;
  metadata?: Record<string, unknown>;
  pluginName?: string;
  marketplaceName?: string;
}

/**
 * 模板版本的 OutputStyle 數據
 */
export interface TemplateOutputStyleData {
  localId: string;
  fileName: string;
  content: string;
  description: string;
}

interface FormState {
  fileName: string;
  scope: OutputStyleScope;
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
// Props 類型
// ============================================================================

interface WorkspaceOutputStyleDialogProps {
  variant?: 'workspace';
  open: boolean;
  mode: 'create' | 'edit';
  initialValue?: WorkspaceOutputStyleData | null;
  onClose: () => void;
  onSubmit: (document: WorkspaceOutputStyleData) => void | Promise<void>;
}

interface TemplateOutputStyleDialogProps {
  variant: 'template';
  open: boolean;
  mode: 'create' | 'edit';
  initialValue?: TemplateOutputStyleData | null;
  onClose: () => void;
  onSubmit: (outputStyle: TemplateOutputStyleData) => void;
}

export type OutputStyleDialogProps = WorkspaceOutputStyleDialogProps | TemplateOutputStyleDialogProps;

// ============================================================================
// 元件實作
// ============================================================================

export const OutputStyleDialog: React.FC<OutputStyleDialogProps> = (props) => {
  const { open, mode, onClose } = props;
  const variant = props.variant ?? 'workspace';
  const { t } = useI18n();

  const showScope = variant === 'workspace';

  const buildInitialState = useCallback((): FormState => {
    if (variant === 'workspace') {
      const initial = props.initialValue as WorkspaceOutputStyleData | null | undefined;
      return {
        fileName: (initial?.metadata?.fileName as string | undefined) ?? '',
        scope: initial?.scope ?? 'project',
        content: initial?.content ?? '',
      };
    } else {
      const initial = props.initialValue as TemplateOutputStyleData | null | undefined;
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

  const getTranslationKey = (key: string) => {
    if (variant === 'workspace') {
      return `workspace.claudeCode.outputStyles.dialog.${key}`;
    }
    return `template.editor.outputStyle.dialog.${key}`;
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
        const initial = props.initialValue as WorkspaceOutputStyleData | null | undefined;
        const identifier = isEdit
          ? (initial?.metadata?.fileName as string | undefined) ?? normalizedFileName
          : normalizedFileName;
        const scope = formState.scope;

        const document: WorkspaceOutputStyleData = {
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

        (props as WorkspaceOutputStyleDialogProps).onSubmit(document);
      } else {
        const initial = props.initialValue as TemplateOutputStyleData | null | undefined;
        const outputStyle: TemplateOutputStyleData = {
          localId: initial?.localId || `local-${Math.random().toString(36).slice(2, 10)}`,
          fileName: normalizedFileName,
          description: '',
          content: formState.content,
        };

        (props as TemplateOutputStyleDialogProps).onSubmit(outputStyle);
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
          <DialogTitle className="flex items-center gap-2">
            <Paintbrush className="h-5 w-5 text-primary" />
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
              {showScope ? (
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <label className="text-sm font-medium text-foreground">
                      {t('workspace.claudeCode.outputStyles.dialog.fields.scope.label')}
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
                          setFormState((prev) => ({ ...prev, scope: value as OutputStyleScope }))
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
                    <p className="text-xs text-muted-foreground">
                      {t('workspace.claudeCode.outputStyles.dialog.fields.fileName.helper')}
                    </p>
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
                    {t('template.editor.outputStyle.dialog.fields.fileName.helper')}
                  </p>
                </div>
              )}

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
                          ? t('workspace.claudeCode.outputStyles.dialog.fields.content.estimatedSize', {
                              size: formatSize(formState.content),
                            })
                          : t('template.editor.outputStyle.dialog.fields.content.sizeHint', {
                              size: formatSize(formState.content),
                            })}
                      </span>
                    }
                  />
                </div>
                {errors.content && <p className="mt-2 text-xs text-destructive">{errors.content}</p>}
              </div>
            </div>
          </div>

          <DialogFooter className="flex-shrink-0 gap-2 px-6 pb-6">
            <Button
              type="button"
              variant={variant === 'workspace' ? 'ghost' : 'outline'}
              onClick={onClose}
              disabled={submitting}
            >
              {variant === 'workspace'
                ? t('workspace.claudeCode.outputStyles.dialog.actions.cancel')
                : t('template.editor.outputStyle.dialog.actions.cancel')}
            </Button>
            <Button type="submit" disabled={submitting}>
              {submitting && variant === 'template'
                ? t('template.editor.outputStyle.dialog.actions.submitting')
                : isEdit
                  ? variant === 'workspace'
                    ? t('workspace.claudeCode.outputStyles.dialog.actions.save')
                    : t('template.editor.outputStyle.dialog.actions.update')
                  : t(getTranslationKey('actions.create'))}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
};

export default OutputStyleDialog;
