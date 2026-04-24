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
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/shared/components/ui/tabs';
import { Badge } from '@/shared/components/ui/badge';
import { MarkdownEditor } from '@/shared/components/composite/MarkdownEditor';
import Editor from '@monaco-editor/react';
import { useI18n } from '@/shared/hooks/useI18n';
import { Terminal } from 'lucide-react';

// ============================================================================
// 類型定義
// ============================================================================

export type CommandScope = 'project' | 'user' | 'local' | 'plugin';

export interface WorkspaceCommandData {
  id: string;
  workspaceId?: string;
  title: string;
  scope: CommandScope;
  content: string;
  description?: string;
  size?: string;
  metadata?: Record<string, unknown>;
  pluginName?: string;
  marketplaceName?: string;
}

export interface TemplateCommandData {
  localId: string;
  fileName: string;
  content: string;
  description?: string;
}

interface WorkspaceFormState {
  fileName: string;
  namespace: string;
  scope: CommandScope;
  content: string;
}

interface TemplateFormState {
  namespace: string;
  name: string;
  content: string;
}

// ============================================================================
// 工具函數
// ============================================================================

const formatSize = (content: string) => {
  if (!content) return '1KB';
  const kiloBytes = Math.max(1, Math.ceil(content.length / 1024));
  return `${kiloBytes}KB`;
};

const ensureFileExtension = (fileName: string, format: 'markdown' | 'toml' = 'markdown'): string => {
  const trimmed = fileName.trim();
  const ext = format === 'toml' ? '.toml' : '.md';
  return trimmed.toLowerCase().endsWith(ext) ? trimmed : `${trimmed}${ext}`;
};

// ============================================================================
// Props 類型
// ============================================================================

interface WorkspaceCommandDialogProps {
  variant?: 'workspace';
  open: boolean;
  mode: 'create' | 'edit';
  initialValue?: WorkspaceCommandData | null;
  availableScopes?: CommandScope[];
  format?: 'markdown' | 'toml';
  i18nNamespace?: string;
  onClose: () => void;
  onSubmit: (document: WorkspaceCommandData) => void | Promise<void>;
}

interface TemplateCommandDialogProps {
  variant: 'template';
  open: boolean;
  mode: 'create' | 'edit';
  initialValue?: TemplateCommandData | null;
  onClose: () => void;
  onSubmit: (command: TemplateCommandData) => void;
}

export type CommandDialogProps = WorkspaceCommandDialogProps | TemplateCommandDialogProps;

// ============================================================================
// 元件實作
// ============================================================================

export const CommandDialog: React.FC<CommandDialogProps> = (props) => {
  const { open, mode, onClose } = props;
  const variant = props.variant ?? 'workspace';
  const { t } = useI18n();

  const isWorkspace = variant === 'workspace';
  const i18nNs = isWorkspace
    ? ((props as WorkspaceCommandDialogProps).i18nNamespace ?? 'workspace.claudeCode')
    : 'workspace.claudeCode';
  const [activeTab, setActiveTab] = useState<'basic' | 'editor'>('basic');

  // 表單狀態
  const [fileName, setFileName] = useState('');
  const [namespace, setNamespace] = useState('');
  const [name, setName] = useState('');
  const [scope, setScope] = useState<CommandScope>('project');
  const [content, setContent] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [errors, setErrors] = useState<{ fileName?: string; name?: string; content?: string }>({});

  const workspaceAvailableScopes = isWorkspace
    ? (props as WorkspaceCommandDialogProps).availableScopes
    : undefined;

  const format = isWorkspace
    ? ((props as WorkspaceCommandDialogProps).format ?? 'markdown')
    : 'markdown';

  const scopeOptions = useMemo(() => {
    const allOptions: { value: string; label: string }[] = [
      { value: 'project', label: t(`${i18nNs}.documents.scope.values.project`) },
      { value: 'user', label: t(`${i18nNs}.documents.scope.values.user`) },
    ];
    if (!workspaceAvailableScopes) return allOptions;
    return allOptions.filter((opt) => workspaceAvailableScopes.includes(opt.value as CommandScope));
  }, [t, workspaceAvailableScopes, i18nNs]);

  const buildInitialState = useCallback(() => {
    if (isWorkspace) {
      const initial = props.initialValue as WorkspaceCommandData | null | undefined;
      setFileName((initial?.metadata?.fileName as string | undefined) ?? '');
      setNamespace((initial?.metadata?.namespace as string) ?? '');
      setScope(initial?.scope ?? 'project');
      setContent(initial?.content ?? '');
    } else {
      const initial = props.initialValue as TemplateCommandData | null | undefined;
      const fileNameValue = initial?.fileName ?? '';
      let ns = '';
      let nm = '';
      if (fileNameValue) {
        const parts = fileNameValue.replace('.md', '').split('/');
        if (parts.length > 1) {
          ns = parts[0];
          nm = parts.slice(1).join('/');
        } else {
          nm = parts[0];
        }
      }
      setNamespace(ns);
      setName(nm);
      setContent(initial?.content ?? '');
    }
  }, [isWorkspace, props.initialValue]);

  useEffect(() => {
    if (open) {
      buildInitialState();
      setActiveTab('basic');
      setErrors({});
      setSubmitting(false);
    }
  }, [open, buildInitialState]);

  const isEdit = mode === 'edit';

  const getTranslationKey = (key: string) => {
    return isWorkspace
      ? `${i18nNs}.slashCommands.dialog.${key}`
      : `template.editor.commands.dialog.${key}`;
  };

  const validate = () => {
    const nextErrors: { fileName?: string; name?: string; content?: string } = {};
    if (isWorkspace) {
      if (!fileName.trim()) {
        nextErrors.fileName = t(getTranslationKey('validation.fileName'));
      }
    } else {
      if (!name.trim()) {
        nextErrors.name = t('template.editor.commands.dialog.validation.nameRequired');
      }
    }
    if (!content.trim()) {
      nextErrors.content = isWorkspace
        ? t(getTranslationKey('validation.content'))
        : t('template.editor.commands.dialog.validation.contentRequired');
    }
    setErrors(nextErrors);
    return Object.keys(nextErrors).length === 0;
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!validate()) {
      if (isWorkspace) setActiveTab('basic');
      return;
    }
    setSubmitting(true);

    try {
      if (isWorkspace) {
        const initial = props.initialValue as WorkspaceCommandData | null | undefined;
        const normalizedFileName = ensureFileExtension(fileName, format);
        const identifier = isEdit
          ? (initial?.metadata?.fileName as string | undefined) ?? initial?.id ?? normalizedFileName
          : normalizedFileName;
        const normalizedNamespace = namespace.trim();

        const document: WorkspaceCommandData = {
          id: `${scope}:${identifier}`,
          title: normalizedFileName,
          description: '',
          scope,
          content,
          size: formatSize(content),
          metadata: {
            fileName: identifier,
            namespace: normalizedNamespace || undefined,
            format,
          },
        };

        (props as WorkspaceCommandDialogProps).onSubmit(document);
      } else {
        const initial = props.initialValue as TemplateCommandData | null | undefined;
        const resultFileName = namespace.trim()
          ? `${namespace.trim()}/${name.trim()}.md`
          : `${name.trim()}.md`;

        const command: TemplateCommandData = {
          localId: initial?.localId || `local-${Math.random().toString(36).slice(2, 10)}`,
          fileName: resultFileName,
          content,
        };

        (props as TemplateCommandDialogProps).onSubmit(command);
      }
      onClose();
    } finally {
      setSubmitting(false);
    }
  };

  // ========== 渲染 ==========

  const renderWorkspaceContent = () => (
    <Tabs
      value={activeTab}
      onValueChange={(value) => setActiveTab(value as 'basic' | 'editor')}
      className="flex h-full flex-col"
    >
      <div className="flex-shrink-0 px-6">
        <TabsList className="grid h-10 w-full grid-cols-2">
          <TabsTrigger value="basic">
            {t(`${i18nNs}.slashCommands.dialog.tabs.basic`)}
          </TabsTrigger>
          <TabsTrigger value="editor">
            {t(`${i18nNs}.slashCommands.dialog.tabs.editor`)}
          </TabsTrigger>
        </TabsList>
      </div>

      <TabsContent value="basic" className="mt-0 flex-1 overflow-auto px-6 pb-6 pt-4">
        <div className="space-y-6">
          <div className="space-y-2">
            <label className="text-sm font-medium text-foreground">
              {t(`${i18nNs}.slashCommands.dialog.fields.scope.label`)}
            </label>
            {isEdit ? (
              <Badge variant="outline" className="text-sm">
                {scopeOptions.find((option) => option.value === scope)?.label ?? scope}
              </Badge>
            ) : (
              <Select value={scope} onValueChange={(value) => setScope(value as CommandScope)}>
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
              {t(`${i18nNs}.slashCommands.dialog.fields.fileName.label`)}
            </label>
            <Input
              value={fileName}
              onChange={(e) => setFileName(e.target.value)}
              placeholder={t(`${i18nNs}.slashCommands.dialog.fields.fileName.placeholder`)}
            />
            {errors.fileName && <p className="text-xs text-destructive">{errors.fileName}</p>}
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium text-foreground">
              {t(`${i18nNs}.slashCommands.dialog.fields.namespace.label`)}
            </label>
            <Input
              value={namespace}
              onChange={(e) => setNamespace(e.target.value)}
              placeholder={t(`${i18nNs}.slashCommands.dialog.fields.namespace.placeholder`)}
            />
            <p className="text-xs text-muted-foreground">
              {t(`${i18nNs}.slashCommands.dialog.fields.namespace.helper`)}
            </p>
          </div>
        </div>
      </TabsContent>

      <TabsContent value="editor" className="mt-0 flex-1 overflow-hidden px-6 pb-6 pt-4">
        <div className="flex h-full flex-col">
          <label className="mb-2 text-sm font-medium text-foreground">
            {t(`${i18nNs}.slashCommands.dialog.fields.content.label`)}
          </label>
          <div className="flex-1 overflow-hidden rounded-lg border">
            {format === 'toml' ? (
              <Editor
                height="100%"
                language="toml"
                value={content}
                onChange={(value) => setContent(value ?? '')}
                options={{ minimap: { enabled: false }, wordWrap: 'on', fontSize: 13 }}
              />
            ) : (
              <MarkdownEditor
                value={content}
                onChange={(value) => setContent(value ?? '')}
                className="h-full"
                footerExtras={
                  <span className="text-xs text-muted-foreground">
                    {t(`${i18nNs}.slashCommands.dialog.fields.content.estimatedSize`, {
                      size: formatSize(content),
                    })}
                  </span>
                }
              />
            )}
          </div>
          {errors.content && <p className="mt-2 text-xs text-destructive">{errors.content}</p>}
        </div>
      </TabsContent>
    </Tabs>
  );

  const renderTemplateContent = () => (
    <div className="flex flex-1 flex-col overflow-hidden px-6 pb-6 pt-4">
      <div className="mb-4 flex-shrink-0 space-y-2">
        <label className="text-sm font-medium text-foreground">
          {t('template.editor.commands.dialog.fields.name.label')}
        </label>
        <Input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder={t('template.editor.commands.dialog.fields.name.placeholder')}
        />
        {errors.name && <p className="text-xs text-destructive">{errors.name}</p>}
        <p className="text-xs text-muted-foreground">
          {t('template.editor.commands.dialog.fields.name.helper')}
        </p>
      </div>

      <div className="mb-4 flex-shrink-0 space-y-2">
        <label className="text-sm font-medium text-foreground">
          {t('template.editor.commands.dialog.fields.namespace.label')}
        </label>
        <Input
          value={namespace}
          onChange={(e) => setNamespace(e.target.value)}
          placeholder={t('template.editor.commands.dialog.fields.namespace.placeholder')}
        />
        <p className="text-xs text-muted-foreground">
          {t('template.editor.commands.dialog.fields.namespace.helper')}
        </p>
      </div>

      <div className="flex flex-1 flex-col overflow-hidden">
        <label className="mb-2 text-sm font-medium text-foreground">
          {t('template.editor.commands.dialog.fields.content.label')}
        </label>
        <div className="flex-1 overflow-hidden rounded-lg border">
          <MarkdownEditor
            value={content}
            onChange={(value) => setContent(value ?? '')}
            className="h-full"
            footerExtras={
              <span className="text-xs text-muted-foreground">
                {t('template.editor.commands.dialog.fields.content.sizeHint', {
                  size: formatSize(content),
                })}
              </span>
            }
          />
        </div>
        {errors.content && <p className="mt-2 text-xs text-destructive">{errors.content}</p>}
      </div>
    </div>
  );

  return (
    <Dialog open={open} onOpenChange={(next) => !submitting && (!next ? onClose() : null)}>
      <DialogContent className="flex h-[85vh] max-h-[85vh] w-full max-w-4xl flex-col p-0">
        <DialogHeader className="flex-shrink-0 px-6 pt-6">
          <DialogTitle className="flex items-center gap-2">
            <Terminal className="h-5 w-5 text-primary" />
            {isEdit ? t(getTranslationKey('title.edit')) : t(getTranslationKey('title.create'))}
          </DialogTitle>
          <DialogDescription>
            {isEdit
              ? t(getTranslationKey('description.edit'))
              : t(getTranslationKey('description.create'))}
          </DialogDescription>
        </DialogHeader>

        <form className="flex flex-1 flex-col overflow-hidden" onSubmit={handleSubmit}>
          {isWorkspace ? renderWorkspaceContent() : renderTemplateContent()}

          <DialogFooter className="flex-shrink-0 gap-2 px-6 pb-6">
            <Button type="button" variant="ghost" onClick={onClose} disabled={submitting}>
              {isWorkspace
                ? t(`${i18nNs}.slashCommands.dialog.actions.cancel`)
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

export default CommandDialog;
