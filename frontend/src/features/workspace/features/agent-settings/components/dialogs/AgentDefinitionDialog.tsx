import React, { useEffect, useMemo, useState } from 'react';
import { Bot } from 'lucide-react';
import {
  DocumentEditorDialogCore,
  ensureDocumentExtension,
  formatDocumentContentSize,
  type DocumentWorkflowDialogProps,
} from '@/shared/components/document-workflow';
import { useI18n } from '@/shared/hooks/useI18n';
import type { AgentDocument, AgentScope } from '../../types';

interface AgentDefinitionFormState {
  fileName: string;
  scope: AgentScope;
  content: string;
}

export interface AgentDefinitionDialogProps extends DocumentWorkflowDialogProps<AgentDocument> {
  i18nNamespace?: string;
  format?: 'markdown' | 'toml';
}

const extensionForFormat = (format: 'markdown' | 'toml') => (format === 'toml' ? '.toml' : '.md');

export const AgentDefinitionDialog: React.FC<AgentDefinitionDialogProps> = ({
  open,
  mode,
  initialValue,
  i18nNamespace = 'workspace.agentSettings.common',
  format = 'markdown',
  onClose,
  onSubmit,
}) => {
  const { t } = useI18n();
  const contentDefaultKey = `${i18nNamespace}.subagents.dialog.fields.content.defaults.${format}`;
  const resolvedDefaultContent = useMemo(() => {
    const translated = t(contentDefaultKey);
    return translated === contentDefaultKey ? '' : translated;
  }, [contentDefaultKey, t]);
  const [formState, setFormState] = useState<AgentDefinitionFormState>(() => ({
    fileName: (initialValue?.metadata?.fileName as string | undefined)
      ?? (initialValue?.metadata?.relativePath as string | undefined)
      ?? '',
    scope: initialValue?.scope ?? 'project',
    content: initialValue?.content ?? resolvedDefaultContent,
  }));
  const [submitting, setSubmitting] = useState(false);
  const [errors, setErrors] = useState<{ fileName?: string; content?: string }>({});
  const isEdit = mode === 'edit';
  const extension = extensionForFormat(format);

  const scopeOptions = useMemo(
    () => [
      { value: 'project' as AgentScope, label: t(`${i18nNamespace}.documents.scope.values.project`) },
      { value: 'user' as AgentScope, label: t(`${i18nNamespace}.documents.scope.values.user`) },
    ],
    [i18nNamespace, t],
  );

  useEffect(() => {
    if (!open) return;
    setFormState({
      fileName: (initialValue?.metadata?.fileName as string | undefined)
        ?? (initialValue?.metadata?.relativePath as string | undefined)
        ?? '',
      scope: initialValue?.scope ?? 'project',
      content: initialValue?.content ?? resolvedDefaultContent,
    });
    setErrors({});
    setSubmitting(false);
  }, [initialValue, open, resolvedDefaultContent]);

  const getTranslationKey = (key: string) => `${i18nNamespace}.subagents.dialog.${key}`;

  const validate = () => {
    const nextErrors: { fileName?: string; content?: string } = {};
    const fileName = formState.fileName.trim();
    if (!fileName) {
      nextErrors.fileName = t(getTranslationKey('validation.fileName'));
    } else if (fileName.includes('.') && !fileName.toLowerCase().endsWith(extension)) {
      nextErrors.fileName = t(getTranslationKey('validation.fileExtension'), { extension });
    }
    if (!formState.content.trim()) {
      nextErrors.content = t(getTranslationKey('validation.content'));
    }
    setErrors(nextErrors);
    return Object.keys(nextErrors).length === 0;
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!validate()) return;
    setSubmitting(true);

    const normalizedFileName = ensureDocumentExtension(formState.fileName, extension);

    try {
      const previousFileName = (initialValue?.metadata?.fileName as string | undefined)
        ?? (initialValue?.metadata?.relativePath as string | undefined)
        ?? initialValue?.id;
      const metadata: Record<string, unknown> = {
        ...initialValue?.metadata,
        fileName: normalizedFileName,
      };
      if (previousFileName) {
        metadata.previousFileName = previousFileName;
      }
      if (format === 'toml') {
        metadata.format = format;
      }
      const document: AgentDocument = {
        id: `${formState.scope}:${normalizedFileName}`,
        title: normalizedFileName,
        description: initialValue?.description ?? '',
        scope: formState.scope,
        content: formState.content,
        size: formatDocumentContentSize(formState.content),
        metadata,
      };

      try {
        await onSubmit(document);
        onClose();
      } catch (error) {
        setErrors((previous) => ({
          ...previous,
          content: error instanceof Error ? error.message : t(getTranslationKey('validation.content')),
        }));
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <DocumentEditorDialogCore<AgentScope>
      open={open}
      isEdit={isEdit}
      submitting={submitting}
      icon={Bot}
      title={isEdit ? t(getTranslationKey('title.edit')) : t(getTranslationKey('title.create'))}
      description={isEdit ? t(getTranslationKey('description.edit')) : t(getTranslationKey('description.create'))}
      showScope
      scopeValue={formState.scope}
      scopeOptions={scopeOptions}
      scopeLabel={t(getTranslationKey('fields.scope.label'))}
      onScopeChange={(scope) => setFormState((previous) => ({ ...previous, scope }))}
      fileName={formState.fileName}
      fileNameLabel={t(getTranslationKey('fields.fileName.label'))}
      fileNamePlaceholder={t(getTranslationKey(`fields.fileName.placeholders.${format}`))}
      fileNameError={errors.fileName}
      onFileNameChange={(fileName) => setFormState((previous) => ({ ...previous, fileName }))}
      content={formState.content}
      contentLabel={t(getTranslationKey(`fields.content.labels.${format}`))}
      contentHelper={t(getTranslationKey(`fields.content.helpers.${format}`))}
      contentError={errors.content}
      contentFooter={
        <span className="text-xs text-muted-foreground">
          {t(getTranslationKey('fields.content.estimatedSize'), {
            size: formatDocumentContentSize(formState.content),
          })}
        </span>
      }
      editorMode={format === 'toml' ? 'plain' : 'markdown'}
      contentPlaceholder={t(getTranslationKey(`fields.content.placeholders.${format}`))}
      onContentChange={(content) => setFormState((previous) => ({ ...previous, content }))}
      cancelLabel={t(getTranslationKey('actions.cancel'))}
      submitLabel={isEdit ? t(getTranslationKey('actions.save')) : t(getTranslationKey('actions.create'))}
      onClose={onClose}
      onSubmit={handleSubmit}
    />
  );
};

export default AgentDefinitionDialog;
