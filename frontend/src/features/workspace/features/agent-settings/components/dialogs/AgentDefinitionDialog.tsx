import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Bot } from 'lucide-react';
import yaml from 'js-yaml';
import {
  DocumentEditorDialogCore,
  ensureMarkdownExtension,
  formatDocumentContentSize,
  type DocumentWorkflowDialogProps,
} from '@/shared/components/document-workflow';
import { Input } from '@/shared/components/ui/input';
import { useI18n } from '@/shared/hooks/useI18n';
import type { AgentDocument, AgentScope, SubagentFieldSchema } from '../../types';

interface AgentDefinitionFormState {
  fileName: string;
  scope: AgentScope;
  content: string;
  frontmatter: Record<string, unknown>;
}

export interface AgentDefinitionDialogProps extends DocumentWorkflowDialogProps<AgentDocument> {
  i18nNamespace?: string;
  fields?: SubagentFieldSchema[];
}

const parseMarkdownDocument = (content: string): { frontmatter: Record<string, unknown>; body: string } => {
  if (!content.startsWith('---')) {
    return { frontmatter: {}, body: content };
  }
  const endIndex = content.indexOf('\n---', 3);
  if (endIndex === -1) {
    return { frontmatter: {}, body: content };
  }
  const rawFrontmatter = content.slice(3, endIndex).trim();
  const body = content.slice(endIndex + 4).replace(/^\n/, '');
  try {
    const parsed = yaml.load(rawFrontmatter);
    return {
      frontmatter: parsed && typeof parsed === 'object' && !Array.isArray(parsed)
        ? parsed as Record<string, unknown>
        : {},
      body,
    };
  } catch {
    return { frontmatter: {}, body: content };
  }
};

const buildMarkdownDocument = (frontmatter: Record<string, unknown>, body: string): string => {
  const cleaned = Object.fromEntries(
    Object.entries(frontmatter).filter(([, value]) => {
      if (Array.isArray(value)) return value.length > 0;
      return value !== undefined && value !== null && value !== '';
    }),
  );
  if (Object.keys(cleaned).length === 0) {
    return body;
  }
  return `---\n${yaml.dump(cleaned, { lineWidth: -1 }).trim()}\n---\n${body.trimStart()}`;
};

const normalizeFieldValue = (field: SubagentFieldSchema, value: unknown): string => {
  if (Array.isArray(value)) return value.join(', ');
  if (value === undefined || value === null) return field.default === undefined ? '' : String(field.default);
  return String(value);
};

const parseFieldValue = (field: SubagentFieldSchema, value: string): unknown => {
  const trimmed = value.trim();
  if (!trimmed) return undefined;
  if (field.type === 'number') {
    const parsed = Number(trimmed);
    return Number.isFinite(parsed) ? parsed : undefined;
  }
  if (field.type === 'boolean') {
    return trimmed === 'true';
  }
  if (field.type === 'string[]') {
    return trimmed.split(',').map((item) => item.trim()).filter(Boolean);
  }
  return trimmed;
};

export const AgentDefinitionDialog: React.FC<AgentDefinitionDialogProps> = ({
  open,
  mode,
  initialValue,
  i18nNamespace = 'workspace.agentSettings.common',
  fields,
  onClose,
  onSubmit,
}) => {
  const { t } = useI18n();

  const buildInitialState = useCallback((): AgentDefinitionFormState => {
    const parsed = parseMarkdownDocument(initialValue?.content ?? '');
    const frontmatter = { ...parsed.frontmatter };
    for (const field of fields ?? []) {
      if (frontmatter[field.key] === undefined && field.default !== undefined) {
        frontmatter[field.key] = field.default;
      }
    }
    return {
      fileName: (initialValue?.metadata?.fileName as string | undefined) ?? '',
      scope: initialValue?.scope ?? 'project',
      content: fields ? parsed.body : initialValue?.content ?? '',
      frontmatter,
    };
  }, [fields, initialValue]);

  const [formState, setFormState] = useState<AgentDefinitionFormState>(buildInitialState);
  const [submitting, setSubmitting] = useState(false);
  const [errors, setErrors] = useState<{ fileName?: string; content?: string }>({});
  const isEdit = mode === 'edit';
  const fieldIdPrefix = React.useId();

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
    for (const field of fields ?? []) {
      if (!field.required) continue;
      const value = formState.frontmatter[field.key];
      const empty = Array.isArray(value) ? value.length === 0 : !String(value ?? '').trim();
      if (empty) {
        nextErrors.content = t(getTranslationKey('validation.content'));
      }
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
      const content = fields
        ? buildMarkdownDocument(formState.frontmatter, formState.content)
        : formState.content;
      const document: AgentDocument = {
        id: `${formState.scope}:${identifier}`,
        title: normalizedFileName,
        description: '',
        scope: formState.scope,
        content,
        size: formatDocumentContentSize(content),
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

  const extraFields = fields?.map((field) => {
    const value = normalizeFieldValue(field, formState.frontmatter[field.key]);
    const inputId = `${fieldIdPrefix}-${field.key}`;
    return (
      <div key={field.key} className="space-y-2">
        <label htmlFor={inputId} className="text-sm font-medium text-foreground">
          {t(field.labelKey)}
        </label>
        <Input
          id={inputId}
          type={field.type === 'number' ? 'number' : 'text'}
          value={value}
          placeholder={field.placeholderKey ? t(field.placeholderKey) : field.placeholder}
          onChange={(event) => {
            const nextValue = parseFieldValue(field, event.target.value);
            setFormState((previous) => ({
              ...previous,
              frontmatter: {
                ...previous.frontmatter,
                [field.key]: nextValue,
              },
            }));
          }}
        />
      </div>
    );
  });

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
      extraFields={extraFields}
      onContentChange={(content) => setFormState((previous) => ({ ...previous, content }))}
      cancelLabel={t(getTranslationKey('actions.cancel'))}
      submitLabel={isEdit ? t(getTranslationKey('actions.save')) : t(getTranslationKey('actions.create'))}
      onClose={onClose}
      onSubmit={handleSubmit}
    />
  );
};

export default AgentDefinitionDialog;
