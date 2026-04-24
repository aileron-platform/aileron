import * as React from 'react';
import type {
  TemplateFormValues,
  McpServerFormValue,
  CommandFormValue,
  HookFormValue,
  AgentFormValue,
  FileEntryFormValue,
} from '../formTypes';
import { useI18n } from '@/shared/hooks/useI18n';

export type FieldError = string;
export type TemplateEditorErrors = Partial<Record<keyof TemplateFormValues, FieldError>> & {
  mcpServers?: Record<string, FieldError | undefined>;
  commands?: Record<string, FieldError | undefined>;
  hooks?: Record<string, FieldError | undefined>;
  agents?: Record<string, FieldError | undefined>;
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

    // Commands - name/content required
    if (v.commands?.length) {
      next.commands = {};
      v.commands.forEach((item: CommandFormValue) => {
        if (!item.name?.trim()) next.commands![item.localId] = t('template.editor.validation.commandName');
        else if (!item.content?.trim()) next.commands![item.localId] = t('template.editor.validation.commandContent');
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

    // Agents - fileName/content required
    if (v.agents?.length) {
      next.agents = {};
      v.agents.forEach((item: AgentFormValue) => {
        if (!item.fileName?.trim()) next.agents![item.localId] = t('template.editor.validation.agentFile');
        else if (!item.content?.trim()) next.agents![item.localId] = t('template.editor.validation.agentContent');
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
