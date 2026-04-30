import React, { useCallback, useEffect, useState } from 'react';
import { Bot } from 'lucide-react';
import {
  DocumentEditorDialogCore,
  ensureMarkdownExtension,
  formatDocumentContentSize,
} from '@/shared/components/document-workflow';
import { useI18n } from '@/shared/hooks/useI18n';
import type { AgentFormValue } from '../formTypes';

interface TemplateAgentFormState {
  fileName: string;
  content: string;
}

export interface TemplateAgentDialogProps {
  open: boolean;
  mode: 'create' | 'edit';
  initialValue?: AgentFormValue | null;
  onClose: () => void;
  onSubmit: (agent: AgentFormValue) => void;
}

export const TemplateAgentDialog: React.FC<TemplateAgentDialogProps> = ({
  open,
  mode,
  initialValue,
  onClose,
  onSubmit,
}) => {
  const { t } = useI18n();

  const buildInitialState = useCallback((): TemplateAgentFormState => ({
    fileName: initialValue?.fileName ?? '',
    content: initialValue?.content ?? '',
  }), [initialValue]);

  const [formState, setFormState] = useState<TemplateAgentFormState>(buildInitialState);
  const [submitting, setSubmitting] = useState(false);
  const [errors, setErrors] = useState<{ fileName?: string; content?: string }>({});
  const isEdit = mode === 'edit';

  useEffect(() => {
    if (!open) return;
    setFormState(buildInitialState());
    setErrors({});
    setSubmitting(false);
  }, [buildInitialState, open]);

  const getTranslationKey = (key: string) => `template.editor.agents.dialog.${key}`;

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

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    if (!validate()) return;
    setSubmitting(true);

    try {
      const agent: AgentFormValue = {
        localId: initialValue?.localId || `local-${Math.random().toString(36).slice(2, 10)}`,
        fileName: ensureMarkdownExtension(formState.fileName),
        description: '',
        content: formState.content,
      };

      onSubmit(agent);
      onClose();
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <DocumentEditorDialogCore
      open={open}
      isEdit={isEdit}
      submitting={submitting}
      icon={Bot}
      title={isEdit ? t(getTranslationKey('title.edit')) : t(getTranslationKey('title.create'))}
      description={isEdit ? t(getTranslationKey('description.edit')) : t(getTranslationKey('description.create'))}
      showScope={false}
      scopeValue="project"
      scopeOptions={[]}
      scopeLabel=""
      onScopeChange={() => undefined}
      fileName={formState.fileName}
      fileNameLabel={t(getTranslationKey('fields.fileName.label'))}
      fileNamePlaceholder={t(getTranslationKey('fields.fileName.placeholder'))}
      fileNameHelper={t(getTranslationKey('fields.fileName.helper'))}
      fileNameError={errors.fileName}
      onFileNameChange={(fileName) => setFormState((previous) => ({ ...previous, fileName }))}
      content={formState.content}
      contentLabel={t(getTranslationKey('fields.content.label'))}
      contentHelper={t(getTranslationKey('fields.content.helper'))}
      contentError={errors.content}
      contentFooter={
        <span className="text-xs text-muted-foreground">
          {t(getTranslationKey('fields.content.sizeHint'), {
            size: formatDocumentContentSize(formState.content),
          })}
        </span>
      }
      onContentChange={(content) => setFormState((previous) => ({ ...previous, content }))}
      cancelLabel={t('common.cancel')}
      submitLabel={isEdit ? t(getTranslationKey('actions.save')) : t(getTranslationKey('actions.create'))}
      onClose={onClose}
      onSubmit={handleSubmit}
    />
  );
};

export default TemplateAgentDialog;
