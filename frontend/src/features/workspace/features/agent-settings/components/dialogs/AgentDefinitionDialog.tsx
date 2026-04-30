import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Bot } from 'lucide-react';
import {
  DocumentEditorDialogCore,
  ensureMarkdownExtension,
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
}

export const AgentDefinitionDialog: React.FC<AgentDefinitionDialogProps> = ({
  open,
  mode,
  initialValue,
  i18nNamespace = 'workspace.agentSettings.common',
  onClose,
  onSubmit,
}) => {
  const { t } = useI18n();

  const buildInitialState = useCallback((): AgentDefinitionFormState => ({
    fileName: (initialValue?.metadata?.fileName as string | undefined) ?? '',
    scope: initialValue?.scope ?? 'project',
    content: initialValue?.content ?? '',
  }), [initialValue]);

  const [formState, setFormState] = useState<AgentDefinitionFormState>(buildInitialState);
  const [submitting, setSubmitting] = useState(false);
  const [errors, setErrors] = useState<{ fileName?: string; content?: string }>({});
  const isEdit = mode === 'edit';

  const scopeOptions = useMemo(
    () => [
      { value: 'project' as AgentScope, label: t(`${i18nNamespace}.documents.scope.values.project`) },
      { value: 'user' as AgentScope, label: t(`${i18nNamespace}.documents.scope.values.user`) },
    ],
    [i18nNamespace, t],
  );

  useEffect(() => {
    if (!open) return;
    setFormState(buildInitialState());
    setErrors({});
    setSubmitting(false);
  }, [buildInitialState, open]);

  const getTranslationKey = (key: string) => `${i18nNamespace}.subagents.dialog.${key}`;

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
    if (!validate()) return;
    setSubmitting(true);

    const normalizedFileName = ensureMarkdownExtension(formState.fileName);

    try {
      const identifier =
        (initialValue?.metadata?.fileName as string | undefined) ?? initialValue?.id ?? normalizedFileName;
      const document: AgentDocument = {
        id: `${formState.scope}:${identifier}`,
        title: normalizedFileName,
        description: '',
        scope: formState.scope,
        content: formState.content,
        size: formatDocumentContentSize(formState.content),
        metadata: {
          fileName: identifier,
        },
      };

      await onSubmit(document);
      onClose();
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
      fileNamePlaceholder={t(getTranslationKey('fields.fileName.placeholder'))}
      fileNameError={errors.fileName}
      onFileNameChange={(fileName) => setFormState((previous) => ({ ...previous, fileName }))}
      content={formState.content}
      contentLabel={t(getTranslationKey('fields.content.label'))}
      contentHelper={t(getTranslationKey('fields.content.helper'))}
      contentError={errors.content}
      contentFooter={
        <span className="text-xs text-muted-foreground">
          {t(getTranslationKey('fields.content.estimatedSize'), {
            size: formatDocumentContentSize(formState.content),
          })}
        </span>
      }
      onContentChange={(content) => setFormState((previous) => ({ ...previous, content }))}
      cancelLabel={t(getTranslationKey('actions.cancel'))}
      submitLabel={isEdit ? t(getTranslationKey('actions.save')) : t(getTranslationKey('actions.create'))}
      onClose={onClose}
      onSubmit={handleSubmit}
    />
  );
};

export default AgentDefinitionDialog;
