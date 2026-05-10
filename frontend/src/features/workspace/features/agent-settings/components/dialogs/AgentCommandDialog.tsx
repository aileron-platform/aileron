import React, { useEffect, useMemo, useState } from 'react';
import { Terminal } from 'lucide-react';
import {
  DocumentEditorDialogCore,
  ensureDocumentExtension,
  formatDocumentContentSize,
  type DocumentWorkflowDialogProps,
} from '@/shared/components/document-workflow';
import { Input } from '@/shared/components/ui/input';
import { useI18n } from '@/shared/hooks/useI18n';
import type { AgentDocument, AgentScope } from '../../types';

export interface AgentCommandDialogProps extends DocumentWorkflowDialogProps<AgentDocument> {
  availableScopes?: AgentScope[];
  format?: 'markdown' | 'toml';
  i18nNamespace?: string;
  dialogKey?: 'slashCommands' | 'prompts';
}

const extensionForFormat = (format: 'markdown' | 'toml'): '.md' | '.toml' => (format === 'toml' ? '.toml' : '.md');

export const AgentCommandDialog: React.FC<AgentCommandDialogProps> = ({
  open,
  mode,
  initialValue,
  availableScopes,
  format = 'markdown',
  i18nNamespace = 'workspace.agentSettings.common',
  dialogKey = 'slashCommands',
  onClose,
  onSubmit,
}) => {
  const { t } = useI18n();
  const [fileName, setFileName] = useState('');
  const [namespace, setNamespace] = useState('');
  const [scope, setScope] = useState<AgentScope>('project');
  const [content, setContent] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [errors, setErrors] = useState<{ fileName?: string; content?: string }>({});
  const isEdit = mode === 'edit';
  const extension = extensionForFormat(format);

  const scopeOptions = useMemo(() => {
    const options = [
      { value: 'project' as AgentScope, label: t(`${i18nNamespace}.documents.scope.values.project`) },
      { value: 'user' as AgentScope, label: t(`${i18nNamespace}.documents.scope.values.user`) },
    ];
    return availableScopes
      ? options.filter((option) => availableScopes.includes(option.value))
      : options;
  }, [availableScopes, i18nNamespace, t]);

  useEffect(() => {
    if (!open) {
      return;
    }
    setFileName((initialValue?.metadata?.fileName as string | undefined) ?? '');
    setNamespace((initialValue?.metadata?.namespace as string | undefined) ?? '');
    setScope(initialValue?.scope ?? 'project');
    setContent(initialValue?.content ?? '');
    setErrors({});
    setSubmitting(false);
  }, [initialValue, open]);

  const getTranslationKey = (key: string) => `${i18nNamespace}.${dialogKey}.dialog.${key}`;

  const validate = () => {
    const nextErrors: { fileName?: string; content?: string } = {};
    if (!fileName.trim()) {
      nextErrors.fileName = t(getTranslationKey('validation.fileName'));
    } else if (fileName.includes('.') && !fileName.toLowerCase().endsWith(extension)) {
      nextErrors.fileName = t(getTranslationKey('validation.fileName'));
    }
    if (!content.trim()) {
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

    try {
      const normalizedFileName = ensureDocumentExtension(fileName, extension);
      const identifier = isEdit
        ? (initialValue?.metadata?.fileName as string | undefined) ?? initialValue?.id ?? normalizedFileName
        : normalizedFileName;
      const normalizedNamespace = namespace.trim();
      const document: AgentDocument = {
        id: `${scope}:${identifier}`,
        title: normalizedFileName,
        description: '',
        scope,
        content,
        size: formatDocumentContentSize(content),
        metadata: {
          fileName: identifier,
          namespace: normalizedNamespace || undefined,
          format,
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
      icon={Terminal}
      title={isEdit ? t(getTranslationKey('title.edit')) : t(getTranslationKey('title.create'))}
      description={isEdit ? t(getTranslationKey('description.edit')) : t(getTranslationKey('description.create'))}
      showScope
      scopeValue={scope}
      scopeOptions={scopeOptions}
      scopeLabel={t(getTranslationKey('fields.scope.label'))}
      onScopeChange={(value) => setScope(value)}
      fileName={fileName}
      fileNameLabel={t(getTranslationKey('fields.fileName.label'))}
      fileNamePlaceholder={t(getTranslationKey('fields.fileName.placeholder'))}
      fileNameError={errors.fileName}
      onFileNameChange={setFileName}
      extraFields={(
        <div className="col-span-2 space-y-2">
          <label className="text-sm font-medium text-foreground">
            {t(getTranslationKey('fields.namespace.label'))}
          </label>
          <Input
            value={namespace}
            onChange={(event) => setNamespace(event.target.value)}
            placeholder={t(getTranslationKey('fields.namespace.placeholder'))}
          />
          <p className="text-xs text-muted-foreground">
            {t(getTranslationKey('fields.namespace.helper'))}
          </p>
        </div>
      )}
      content={content}
      contentLabel={t(getTranslationKey('fields.content.label'))}
      contentFooter={(
        <span className="text-xs text-muted-foreground">
          {t(getTranslationKey('fields.content.estimatedSize'), {
            size: formatDocumentContentSize(content),
          })}
        </span>
      )}
      editorMode={format === 'toml' ? 'plain' : 'markdown'}
      contentError={errors.content}
      onContentChange={setContent}
      cancelLabel={t(getTranslationKey('actions.cancel'))}
      cancelVariant="ghost"
      submitLabel={isEdit ? t(getTranslationKey('actions.save')) : t(getTranslationKey('actions.create'))}
      onClose={onClose}
      onSubmit={handleSubmit}
    />
  );
};

export default AgentCommandDialog;
