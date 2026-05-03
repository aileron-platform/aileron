import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Terminal } from 'lucide-react';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/shared/components/ui/dialog';
import { Input } from '@/shared/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/shared/components/ui/select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/shared/components/ui/tabs';
import {
  formatDocumentContentSize,
  type DocumentWorkflowDialogProps,
} from '@/shared/components/document-workflow';
import { useI18n } from '@/shared/hooks/useI18n';
import { SettingsDocumentEditor } from '../SettingsDocumentEditor';
import type { AgentDocument, AgentScope } from '../../types';

export interface AgentCommandDialogProps extends DocumentWorkflowDialogProps<AgentDocument> {
  availableScopes?: AgentScope[];
  format?: 'markdown' | 'toml';
  i18nNamespace?: string;
  dialogKey?: 'slashCommands' | 'prompts';
}

const ensureFileExtension = (fileName: string, format: 'markdown' | 'toml'): string => {
  const trimmed = fileName.trim();
  const extension = format === 'toml' ? '.toml' : '.md';
  return trimmed.toLowerCase().endsWith(extension) ? trimmed : `${trimmed}${extension}`;
};

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
  const [activeTab, setActiveTab] = useState<'basic' | 'editor'>('basic');
  const [fileName, setFileName] = useState('');
  const [namespace, setNamespace] = useState('');
  const [scope, setScope] = useState<AgentScope>('project');
  const [content, setContent] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [errors, setErrors] = useState<{ fileName?: string; content?: string }>({});
  const isEdit = mode === 'edit';

  const scopeOptions = useMemo(() => {
    const allOptions = [
      { value: 'project' as AgentScope, label: t(`${i18nNamespace}.documents.scope.values.project`) },
      { value: 'user' as AgentScope, label: t(`${i18nNamespace}.documents.scope.values.user`) },
    ];
    return availableScopes ? allOptions.filter((option) => availableScopes.includes(option.value)) : allOptions;
  }, [availableScopes, i18nNamespace, t]);

  const buildInitialState = useCallback(() => {
    setFileName((initialValue?.metadata?.fileName as string | undefined) ?? '');
    setNamespace((initialValue?.metadata?.namespace as string) ?? '');
    setScope(initialValue?.scope ?? 'project');
    setContent(initialValue?.content ?? '');
  }, [initialValue]);

  useEffect(() => {
    if (!open) return;
    buildInitialState();
    setActiveTab('basic');
    setErrors({});
    setSubmitting(false);
  }, [buildInitialState, open]);

  const getTranslationKey = (key: string) => `${i18nNamespace}.${dialogKey}.dialog.${key}`;

  const validate = () => {
    const nextErrors: { fileName?: string; content?: string } = {};
    if (!fileName.trim()) {
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
      setActiveTab('basic');
      return;
    }
    setSubmitting(true);

    try {
      const normalizedFileName = ensureFileExtension(fileName, format);
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
    <Dialog open={open} onOpenChange={(next) => !submitting && (!next ? onClose() : null)}>
      <DialogContent className="flex h-[85vh] max-h-[85vh] w-full max-w-4xl flex-col p-0">
        <DialogHeader className="flex-shrink-0 px-6 pt-6">
          <DialogTitle className="flex items-center gap-2">
            <Terminal className="h-5 w-5 text-primary" />
            {isEdit ? t(getTranslationKey('title.edit')) : t(getTranslationKey('title.create'))}
          </DialogTitle>
          <DialogDescription>
            {isEdit ? t(getTranslationKey('description.edit')) : t(getTranslationKey('description.create'))}
          </DialogDescription>
        </DialogHeader>

        <form className="flex flex-1 flex-col overflow-hidden" onSubmit={handleSubmit}>
          <Tabs
            value={activeTab}
            onValueChange={(value) => setActiveTab(value as 'basic' | 'editor')}
            className="flex h-full flex-col"
          >
            <div className="flex-shrink-0 px-6">
              <TabsList className="grid h-10 w-full grid-cols-2">
                <TabsTrigger value="basic">{t(getTranslationKey('tabs.basic'))}</TabsTrigger>
                <TabsTrigger value="editor">{t(getTranslationKey('tabs.editor'))}</TabsTrigger>
              </TabsList>
            </div>

            <TabsContent value="basic" className="mt-0 flex-1 overflow-auto px-6 pb-6 pt-4">
              <div className="space-y-6">
                <div className="space-y-2">
                  <label className="text-sm font-medium text-foreground">
                    {t(getTranslationKey('fields.scope.label'))}
                  </label>
                  {isEdit ? (
                    <Badge variant="outline" className="text-sm">
                      {scopeOptions.find((option) => option.value === scope)?.label ?? scope}
                    </Badge>
                  ) : (
                    <Select value={scope} onValueChange={(value) => setScope(value as AgentScope)}>
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
                    value={fileName}
                    onChange={(event) => setFileName(event.target.value)}
                    placeholder={t(getTranslationKey('fields.fileName.placeholder'))}
                  />
                  {errors.fileName ? <p className="text-xs text-destructive">{errors.fileName}</p> : null}
                </div>

                <div className="space-y-2">
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
              </div>
            </TabsContent>

            <TabsContent value="editor" className="mt-0 flex-1 overflow-hidden px-6 pb-6 pt-4">
              <div className="flex h-full flex-col">
                <label className="mb-2 text-sm font-medium text-foreground">
                  {t(getTranslationKey('fields.content.label'))}
                </label>
                <div className="flex-1 overflow-hidden rounded-lg border">
                  <SettingsDocumentEditor
                    value={content}
                    format={format}
                    onChange={setContent}
                    footerExtras={
                      <span className="text-xs text-muted-foreground">
                        {t(getTranslationKey('fields.content.estimatedSize'), {
                          size: formatDocumentContentSize(content),
                        })}
                      </span>
                    }
                  />
                </div>
                {errors.content ? <p className="mt-2 text-xs text-destructive">{errors.content}</p> : null}
              </div>
            </TabsContent>
          </Tabs>

          <DialogFooter className="flex-shrink-0 gap-2 px-6 pb-6">
            <Button type="button" variant="ghost" onClick={onClose} disabled={submitting}>
              {t(getTranslationKey('actions.cancel'))}
            </Button>
            <Button type="submit" disabled={submitting}>
              {isEdit ? t(getTranslationKey('actions.save')) : t(getTranslationKey('actions.create'))}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
};

export default AgentCommandDialog;
