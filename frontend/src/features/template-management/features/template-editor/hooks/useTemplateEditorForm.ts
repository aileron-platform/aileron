import * as React from 'react';
import type {
  TemplateFormValues,
  McpServerFormValue,
  SlashCommandFormValue,
  HookFormValue,
  SubAgentFormValue,
  FileEntryFormValue,
} from '../formTypes';
import { useI18n } from '@/shared/hooks/useI18n';

export type FieldError = string;
export type TemplateEditorErrors = Partial<Record<keyof TemplateFormValues, FieldError>> & {
  mcpServers?: Record<string, FieldError | undefined>;
  slashCommands?: Record<string, FieldError | undefined>;
  hooks?: Record<string, FieldError | undefined>;
  subAgents?: Record<string, FieldError | undefined>;
  scripts?: Record<string, FieldError | undefined>;
};

export interface UseTemplateEditorFormOptions {
  initial: TemplateFormValues;
  onChange?: (next: TemplateFormValues) => void;
}

export function useTemplateEditorForm(options: UseTemplateEditorFormOptions) {
  const { initial, onChange } = options;
  const [values, setValues] = React.useState<TemplateFormValues>(initial);
  const [errors, setErrors] = React.useState<TemplateEditorErrors>({});
  const { t } = useI18n();

  const setField = React.useCallback(<K extends keyof TemplateFormValues>(key: K, value: TemplateFormValues[K]) => {
    setValues(prev => {
      const next = { ...prev, [key]: value } as TemplateFormValues;
      onChange?.(next);
      return next;
    });
  }, [onChange]);

  const validate = React.useCallback((v: TemplateFormValues = values): TemplateEditorErrors => {
    const next: TemplateEditorErrors = {};

    if (!v.name?.trim()) next.name = t('template.editor.validation.required');
    if (!v.version?.trim()) next.version = t('template.editor.validation.required');
    if (!v.categoryId?.trim()) next.categoryId = t('template.editor.validation.select');

    // Slash commands - name/content required
    if (v.slashCommands?.length) {
      next.slashCommands = {};
      v.slashCommands.forEach((item: SlashCommandFormValue) => {
        if (!item.name?.trim()) next.slashCommands![item.localId] = t('template.editor.validation.slashCommandName');
        else if (!item.content?.trim()) next.slashCommands![item.localId] = t('template.editor.validation.slashCommandContent');
      });
    }

    // Hooks - name, event required
    if (v.hooks?.length) {
      next.hooks = {};
      v.hooks.forEach((item: HookFormValue) => {
        if (!item.name?.trim()) next.hooks![item.localId] = t('template.editor.validation.hookName');
        else if (!item.event?.trim()) next.hooks![item.localId] = t('template.editor.validation.hookEvent');
      });
    }

    // SubAgents - fileName/content required
    if (v.subAgents?.length) {
      next.subAgents = {};
      v.subAgents.forEach((item: SubAgentFormValue) => {
        if (!item.fileName?.trim()) next.subAgents![item.localId] = t('template.editor.validation.subAgentFile');
        else if (!item.content?.trim()) next.subAgents![item.localId] = t('template.editor.validation.subAgentContent');
      });
    }

    // Files - path required
    if (v.scripts?.length) {
      next.scripts = {};
      v.scripts.forEach((item: FileEntryFormValue) => {
        if (!item.path?.trim()) next.scripts![item.localId] = t('template.editor.validation.filePath');
      });
    }

    setErrors(next);
    return next;
  }, [t, values]);

  const isValid = React.useCallback(() => {
    const res = validate(values);
    return Object.keys(res).length === 0 ||
      Object.entries(res).every(([key, val]) => {
        if (!val) return true;
        if (typeof val === 'string') return false;
        // object for collection errors
        return Object.keys(val).length === 0;
      });
  }, [validate, values]);

  return {
    values,
    setValues,
    setField,
    errors,
    validate,
    isValid,
  } as const;
}
