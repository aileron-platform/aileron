import React, { useState, useEffect, useMemo, useCallback } from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/shared/components/ui/dialog';
import { Label } from '@/shared/components/ui/label';
import { Input } from '@/shared/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/shared/components/ui/select';
import { Button } from '@/shared/components/ui/button';
import { cn } from '@/shared/utils/cn';
import { Loader2, Plus, X } from 'lucide-react';
import { useI18n } from '@/shared/hooks/useI18n';

// ============================================================================
// 類型定義
// ============================================================================

export type MCPServerScope = 'project' | 'user' | 'local';
export type MCPTransport = 'stdio' | 'sse' | 'http';

export interface WorkspaceMCPServerData {
  id: string;
  name: string;
  scope: MCPServerScope;
  transport?: MCPTransport;
  command?: string;
  args?: string[];
  url?: string;
  env?: Record<string, string>;
  headers?: Record<string, string>;
}

export interface TemplateMCPServerData {
  localId: string;
  name: string;
  type: MCPTransport;
  command: string;
  argsText: string;
  url: string;
  description: string;
  envText: string;
  headersText: string;
}

interface MCPFormState {
  id: string;
  name: string;
  description: string;
  scope: MCPServerScope;
  transport: MCPTransport;
  command: string;
  args: string[];
  url: string;
  env: KeyValueRow[];
  headers: KeyValueRow[];
}

interface KeyValueRow {
  id: string;
  key: string;
  value: string;
}

const DEFAULT_FORM: MCPFormState = {
  id: '',
  name: '',
  description: '',
  scope: 'project',
  transport: 'stdio',
  command: '',
  args: [],
  url: '',
  env: [],
  headers: [],
};

// ============================================================================
// Props 類型
// ============================================================================

interface WorkspaceMCPServerDialogProps {
  variant?: 'workspace';
  open: boolean;
  mode: 'create' | 'edit';
  server: WorkspaceMCPServerData | null;
  availableScopes?: MCPServerScope[];
  i18nNamespace?: string;
  onClose: () => void;
  onSubmit: (server: WorkspaceMCPServerData) => Promise<void>;
}

interface TemplateMCPServerDialogProps {
  variant: 'template';
  open: boolean;
  initialData?: TemplateMCPServerData;
  onOpenChange: (open: boolean) => void;
  onSave: (data: TemplateMCPServerData) => void;
}

export type MCPServerDialogProps = WorkspaceMCPServerDialogProps | TemplateMCPServerDialogProps;

// ============================================================================
// 工具函數
// ============================================================================

const parseArgsText = (text: string): string[] =>
  text
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean);

const parseKeyValueText = (text: string, separator: string): Record<string, string> => {
  const result: Record<string, string> = {};
  text
    .split('\n')
    .map((line) => line.trim())
    .filter((line) => line && line.includes(separator))
    .forEach((line) => {
      const [key, ...rest] = line.split(separator);
      if (key?.trim()) {
        result[key.trim()] = rest.join(separator).trim();
      }
    });
  return result;
};

let keyValueRowCounter = 0;

const createKeyValueRow = (key = '', value = ''): KeyValueRow => ({
  id: `kv-row-${keyValueRowCounter++}`,
  key,
  value,
});

const createKeyValueRows = (record?: Record<string, string>): KeyValueRow[] =>
  Object.entries(record ?? {}).map(([key, value]) => createKeyValueRow(key, value));

const toKeyValueText = (record: Record<string, string>, separator: string): string =>
  Object.entries(record)
    .filter(([key, value]) => key.trim() && value.trim())
    .map(([key, value]) => `${key}${separator}${value}`)
    .join('\n');

const toKeyValueRecord = (rows: KeyValueRow[]): Record<string, string> =>
  Object.fromEntries(
    rows
      .map(({ key, value }) => [key.trim(), value] as const)
      .filter(([key]) => key.length > 0)
  );

// ============================================================================
// 元件實作
// ============================================================================

export const MCPServerDialog: React.FC<MCPServerDialogProps> = (props) => {
  const { open } = props;
  const variant = props.variant ?? 'workspace';
  const { t } = useI18n();

  const isWorkspace = variant === 'workspace';
  const mode = isWorkspace
    ? (props as WorkspaceMCPServerDialogProps).mode
    : (props as TemplateMCPServerDialogProps).initialData
      ? 'edit'
      : 'create';
  const isEdit = mode === 'edit';

  const [form, setForm] = useState<MCPFormState>(DEFAULT_FORM);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  // i18n namespace（僅 workspace 使用）
  const i18nNs = isWorkspace
    ? ((props as WorkspaceMCPServerDialogProps).i18nNamespace ?? 'workspace.claudeCode')
    : 'workspace.claudeCode';

  // 範圍選項（僅 workspace 使用）
  const workspaceAvailableScopes = isWorkspace
    ? (props as WorkspaceMCPServerDialogProps).availableScopes
    : undefined;

  const scopeOptions = useMemo(() => {
    const allOptions: { value: MCPServerScope; title: string; description: string }[] = [
      {
        value: 'project',
        title: t(`${i18nNs}.mcp.dialogs.server.fields.scope.options.project.title`),
        description: t(`${i18nNs}.mcp.dialogs.server.fields.scope.options.project.description`),
      },
      {
        value: 'user',
        title: t(`${i18nNs}.mcp.dialogs.server.fields.scope.options.user.title`),
        description: t(`${i18nNs}.mcp.dialogs.server.fields.scope.options.user.description`),
      },
      {
        value: 'local',
        title: t(`${i18nNs}.mcp.dialogs.server.fields.scope.options.local.title`),
        description: t(`${i18nNs}.mcp.dialogs.server.fields.scope.options.local.description`),
      },
    ];
    if (!workspaceAvailableScopes) return allOptions;
    return allOptions.filter((opt) => workspaceAvailableScopes.includes(opt.value));
  }, [t, workspaceAvailableScopes, i18nNs]);

  // 傳輸類型選項
  const transportOptions = useMemo(
    () => [
      {
        value: 'stdio' as MCPTransport,
        title: isWorkspace
          ? t(`${i18nNs}.mcp.dialogs.server.fields.transport.options.stdio.title`)
          : t('template.editor.mcp.dialog.transport.options.stdio.label'),
        description: isWorkspace
          ? t(`${i18nNs}.mcp.dialogs.server.fields.transport.options.stdio.description`)
          : t('template.editor.mcp.dialog.transport.options.stdio.description'),
      },
      {
        value: 'sse' as MCPTransport,
        title: isWorkspace
          ? t(`${i18nNs}.mcp.dialogs.server.fields.transport.options.sse.title`)
          : t('template.editor.mcp.dialog.transport.options.sse.label'),
        description: isWorkspace
          ? t(`${i18nNs}.mcp.dialogs.server.fields.transport.options.sse.description`)
          : t('template.editor.mcp.dialog.transport.options.sse.description'),
      },
      {
        value: 'http' as MCPTransport,
        title: isWorkspace
          ? t(`${i18nNs}.mcp.dialogs.server.fields.transport.options.http.title`)
          : t('template.editor.mcp.dialog.transport.options.http.label'),
        description: isWorkspace
          ? t(`${i18nNs}.mcp.dialogs.server.fields.transport.options.http.description`)
          : t('template.editor.mcp.dialog.transport.options.http.description'),
      },
    ],
    [isWorkspace, t, i18nNs]
  );

  // 取得翻譯 key
  const getTranslationKey = useCallback(
    (key: string) => {
      return isWorkspace
        ? `${i18nNs}.mcp.dialogs.server.${key}`
        : `template.editor.mcp.dialog.${key}`;
    },
    [isWorkspace, i18nNs]
  );

  // 初始化表單
  useEffect(() => {
    if (!open) return;

    if (isWorkspace) {
      const server = (props as WorkspaceMCPServerDialogProps).server;
      if (mode === 'edit' && server) {
        setForm({
          id: server.id,
          name: server.name,
          description: '',
          scope: server.scope,
          transport: server.transport ?? 'stdio',
          command: server.command ?? '',
          args: server.args ?? [],
          url: server.url ?? '',
          env: createKeyValueRows(server.env),
          headers: createKeyValueRows(server.headers),
        });
      } else {
        setForm({ ...DEFAULT_FORM, id: `mcp-${Date.now()}` });
      }
    } else {
      const initialData = (props as TemplateMCPServerDialogProps).initialData;
      if (initialData) {
        setForm({
          id: initialData.localId,
          name: initialData.name,
          description: initialData.description || '',
          scope: 'project',
          transport: initialData.type,
          command: initialData.command,
          args: parseArgsText(initialData.argsText),
          url: initialData.url || '',
          env: createKeyValueRows(parseKeyValueText(initialData.envText, '=')),
          headers: createKeyValueRows(parseKeyValueText(initialData.headersText, ':')),
        });
      } else {
        setForm({
          ...DEFAULT_FORM,
          id: `local-${Math.random().toString(36).slice(2, 10)}`,
        });
      }
    }
    setSubmitError(null);
    setSubmitting(false);
  }, [open, mode, isWorkspace, props]);

  const handleChange = (field: keyof MCPFormState, value: MCPFormState[typeof field]) => {
    setSubmitError(null);
    setForm((prev) => ({ ...prev, [field]: value }));
  };

  const handleArgChange = (index: number, value: string) => {
    setSubmitError(null);
    setForm((prev) => ({
      ...prev,
      args: prev.args.map((arg, i) => (i === index ? value : arg)),
    }));
  };

  const addArg = () => {
    setSubmitError(null);
    setForm((prev) => ({ ...prev, args: [...prev.args, ''] }));
  };

  const removeArg = (index: number) => {
    setSubmitError(null);
    setForm((prev) => ({
      ...prev,
      args: prev.args.filter((_, i) => i !== index),
    }));
  };

  const addEnv = () => {
    setSubmitError(null);
    setForm((prev) => ({
      ...prev,
      env: [...prev.env, createKeyValueRow()],
    }));
  };

  const handleEnvChange = (id: string, field: 'key' | 'value', nextValue: string) => {
    setSubmitError(null);
    setForm((prev) => {
      const env = prev.env.map((row) =>
        row.id === id ? { ...row, [field]: nextValue } : row
      );
      return { ...prev, env };
    });
  };

  const removeEnv = (id: string) => {
    setSubmitError(null);
    setForm((prev) => {
      const env = prev.env.filter((row) => row.id !== id);
      return { ...prev, env };
    });
  };

  const addHeader = () => {
    setSubmitError(null);
    setForm((prev) => ({
      ...prev,
      headers: [...prev.headers, createKeyValueRow()],
    }));
  };

  const handleHeaderChange = (id: string, field: 'key' | 'value', nextValue: string) => {
    setSubmitError(null);
    setForm((prev) => {
      const headers = prev.headers.map((row) =>
        row.id === id ? { ...row, [field]: nextValue } : row
      );
      return { ...prev, headers };
    });
  };

  const removeHeader = (id: string) => {
    setSubmitError(null);
    setForm((prev) => {
      const headers = prev.headers.filter((row) => row.id !== id);
      return { ...prev, headers };
    });
  };

  const handleClose = () => {
    if (isWorkspace) {
      (props as WorkspaceMCPServerDialogProps).onClose();
    } else {
      (props as TemplateMCPServerDialogProps).onOpenChange(false);
    }
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setSubmitError(null);

    const name = form.name.trim();

    // 驗證
    if (!name) {
      setSubmitError(
        isWorkspace
          ? t(`${i18nNs}.mcp.dialogs.server.errors.nameRequired`)
          : t('template.editor.mcp.dialog.validation.nameRequired')
      );
      return;
    }

    if (!isWorkspace && !form.description.trim()) {
      setSubmitError(t('template.editor.mcp.dialog.validation.descriptionRequired'));
      return;
    }

    if (form.transport === 'stdio' && !form.command.trim()) {
      setSubmitError(
        isWorkspace
          ? t(`${i18nNs}.mcp.dialogs.server.errors.commandRequired`)
          : t('template.editor.mcp.dialog.validation.commandRequired')
      );
      return;
    }

    if ((form.transport === 'http' || form.transport === 'sse') && !form.url.trim()) {
      setSubmitError(
        isWorkspace
          ? t(`${i18nNs}.mcp.dialogs.server.errors.urlRequired`)
          : t('template.editor.mcp.dialog.validation.urlRequired')
      );
      return;
    }

    const sanitizedEnv = toKeyValueRecord(form.env);
    const sanitizedHeaders = toKeyValueRecord(form.headers);
    const sanitizedArgs = form.args.map((arg) => arg.trim()).filter((arg) => arg.length > 0);

    try {
      setSubmitting(true);

      if (isWorkspace) {
        const server = (props as WorkspaceMCPServerDialogProps).server;
        const payload: WorkspaceMCPServerData = {
          id: server?.id ?? `${form.scope}:${name}`,
          name,
          scope: form.scope,
          transport: form.transport,
          command: form.transport === 'stdio' ? form.command.trim() : undefined,
          args: form.transport === 'stdio' ? sanitizedArgs : [],
          env: Object.keys(sanitizedEnv).length > 0 ? sanitizedEnv : undefined,
          headers:
            form.transport !== 'stdio' && Object.keys(sanitizedHeaders).length > 0
              ? sanitizedHeaders
              : undefined,
        };

        if (form.transport === 'http' || form.transport === 'sse') {
          const url = form.url.trim();
          if (url) {
            payload.url = url;
          }
        }

        await (props as WorkspaceMCPServerDialogProps).onSubmit(payload);
      } else {
        const initialData = (props as TemplateMCPServerDialogProps).initialData;
        const payload: TemplateMCPServerData = {
          localId: initialData?.localId || form.id,
          name,
          type: form.transport,
          command: form.command.trim(),
          argsText: sanitizedArgs.join('\n'),
          url: form.url.trim(),
          description: form.description.trim(),
          envText: toKeyValueText(sanitizedEnv, '='),
          headersText: toKeyValueText(sanitizedHeaders, ': '),
        };

        (props as TemplateMCPServerDialogProps).onSave(payload);
        (props as TemplateMCPServerDialogProps).onOpenChange(false);
      }
    } catch (err) {
      const message = err instanceof Error
        ? err.message
        : t(
            isWorkspace
              ? `${i18nNs}.mcp.dialogs.server.errors.saveFailed`
              : 'template.editor.mcp.dialog.validation.saveFailed'
          );
      setSubmitError(message);
      if (isWorkspace) {
        throw err instanceof Error ? err : new Error(message);
      }
    } finally {
      setSubmitting(false);
    }
  };

  const isDisabled = isEdit && isWorkspace;

  // ========== 渲染 ==========

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="flex h-[85vh] max-h-[85vh] max-w-2xl flex-col p-0">
        <DialogHeader className="flex-shrink-0 px-6 pt-6">
          <DialogTitle>
            {isEdit
              ? t(getTranslationKey('title.edit'))
              : t(getTranslationKey('title.create'))}
          </DialogTitle>
          <DialogDescription>
            {isWorkspace
              ? t(`${i18nNs}.mcp.dialogs.server.description`)
              : isEdit
                ? t('template.editor.mcp.dialog.description.edit')
                : t('template.editor.mcp.dialog.description.create')}
          </DialogDescription>
        </DialogHeader>

        <div className="flex-1 overflow-y-auto px-6 py-4">
          <form onSubmit={handleSubmit} className="space-y-6">
            <div className="grid gap-4 md:grid-cols-2">
              {/* 名稱 */}
              <div className="space-y-2">
                <Label htmlFor="mcp-name">
                  {isWorkspace
                    ? t(`${i18nNs}.mcp.dialogs.server.fields.name.label`)
                    : t('template.editor.mcp.dialog.fields.name.label')}
                </Label>
                <Input
                  id="mcp-name"
                  value={form.name}
                  disabled={isDisabled}
                  onChange={(event) => handleChange('name', event.target.value)}
                  placeholder={
                    isWorkspace
                      ? t(`${i18nNs}.mcp.dialogs.server.fields.name.placeholder`)
                      : t('template.editor.mcp.dialog.fields.name.placeholder')
                  }
                  className={cn('font-medium', isDisabled && 'bg-muted text-muted-foreground')}
                  required
                />
                {isWorkspace && (
                  <p className="text-xs text-muted-foreground">
                    {t(`${i18nNs}.mcp.dialogs.server.fields.name.hint`)}
                  </p>
                )}
              </div>

              {/* 範圍（僅 workspace） */}
              {isWorkspace && (
                <div className="space-y-2">
                  <Label>{t(`${i18nNs}.mcp.dialogs.server.fields.scope.label`)}</Label>
                  <Select
                    value={form.scope}
                    onValueChange={(value: MCPServerScope) => handleChange('scope', value)}
                    disabled={isDisabled}
                  >
                    <SelectTrigger className={cn(isDisabled && 'bg-muted text-muted-foreground')}>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {scopeOptions.map((option) => (
                        <SelectItem key={option.value} value={option.value}>
                          <div>
                            <div className="font-medium">{option.title}</div>
                            <div className="text-xs text-muted-foreground">{option.description}</div>
                          </div>
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              )}

              {/* 傳輸類型 */}
              <div className="space-y-2">
                <Label>
                  {isWorkspace
                    ? t(`${i18nNs}.mcp.dialogs.server.fields.transport.label`)
                    : t('template.editor.mcp.dialog.transport.label')}
                </Label>
                <Select
                  value={form.transport}
                  onValueChange={(value: MCPTransport) => handleChange('transport', value)}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {transportOptions.map((option) => (
                      <SelectItem key={option.value} value={option.value}>
                        <div>
                          <div className="font-medium">{option.title}</div>
                          <div className="text-xs text-muted-foreground">{option.description}</div>
                        </div>
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            {/* 描述（僅 template） */}
            {!isWorkspace && (
              <div className="space-y-2">
                <Label htmlFor="description">
                  {t('template.editor.mcp.dialog.fields.description.label')}
                </Label>
                <Input
                  id="description"
                  value={form.description}
                  onChange={(event) => handleChange('description', event.target.value)}
                  placeholder={t('template.editor.mcp.dialog.fields.description.placeholder')}
                />
              </div>
            )}

            {/* Stdio 類型的欄位 */}
            {form.transport === 'stdio' && (
              <>
                <div className="space-y-2">
                  <Label>
                    {isWorkspace
                      ? t(`${i18nNs}.mcp.dialogs.server.fields.command.label`)
                      : t('template.editor.mcp.dialog.fields.command.label')}
                  </Label>
                  <Input
                    value={form.command}
                    onChange={(event) => handleChange('command', event.target.value)}
                    placeholder={
                      isWorkspace
                        ? t(`${i18nNs}.mcp.dialogs.server.fields.command.placeholder`)
                        : t('template.editor.mcp.dialog.fields.command.placeholder')
                    }
                    className="font-mono"
                    required
                  />
                </div>

                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <Label>
                      {isWorkspace
                        ? t(`${i18nNs}.mcp.dialogs.server.fields.commandArgs.label`)
                        : t('template.editor.mcp.dialog.fields.args.label')}
                    </Label>
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={addArg}
                      disabled={submitting}
                    >
                      <Plus className="mr-1 h-4 w-4" />
                      {isWorkspace
                        ? t(`${i18nNs}.mcp.dialogs.server.fields.commandArgs.add`)
                        : t('template.editor.mcp.dialog.fields.args.add')}
                    </Button>
                  </div>
                  <div className="space-y-2">
                    {form.args.map((arg, index) => (
                      <div key={index} className="flex items-center gap-2">
                        <Input
                          value={arg}
                          onChange={(event) => handleArgChange(index, event.target.value)}
                          placeholder={
                            isWorkspace
                              ? t(`${i18nNs}.mcp.dialogs.server.fields.commandArgs.placeholder`, {
                                  index: index + 1,
                                })
                              : t('template.editor.mcp.dialog.fields.args.placeholder', {
                                  index: index + 1,
                                })
                          }
                          className="font-mono"
                        />
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          onClick={() => removeArg(index)}
                          disabled={submitting}
                        >
                          <X className="h-4 w-4" />
                        </Button>
                      </div>
                    ))}
                    {form.args.length === 0 && (
                      <p className="text-sm text-muted-foreground">
                        {isWorkspace
                          ? t(`${i18nNs}.mcp.dialogs.server.fields.commandArgs.empty`)
                          : t('template.editor.mcp.dialog.fields.args.empty')}
                      </p>
                    )}
                  </div>
                </div>
              </>
            )}

            {/* HTTP/SSE 類型的欄位 */}
            {(form.transport === 'http' || form.transport === 'sse') && (
              <>
                <div className="space-y-2">
                  <Label>
                    {isWorkspace
                      ? t(`${i18nNs}.mcp.dialogs.server.fields.url.label`)
                      : t('template.editor.mcp.dialog.fields.url.label')}
                  </Label>
                  <Input
                    value={form.url}
                    onChange={(event) => handleChange('url', event.target.value)}
                    placeholder={
                      form.transport === 'sse'
                        ? isWorkspace
                          ? t(`${i18nNs}.mcp.dialogs.server.fields.url.placeholder.sse`)
                          : t('template.editor.mcp.dialog.fields.url.placeholderSse')
                        : isWorkspace
                          ? t(`${i18nNs}.mcp.dialogs.server.fields.url.placeholder.http`)
                          : t('template.editor.mcp.dialog.fields.url.placeholderHttp')
                    }
                    className="font-mono"
                    required
                  />
                  <p className="text-xs text-muted-foreground">
                    {form.transport === 'sse'
                      ? isWorkspace
                        ? t(`${i18nNs}.mcp.dialogs.server.fields.url.hint.sse`)
                        : t('template.editor.mcp.dialog.fields.url.hintSse')
                      : isWorkspace
                        ? t(`${i18nNs}.mcp.dialogs.server.fields.url.hint.http`)
                        : t('template.editor.mcp.dialog.fields.url.hintHttp')}
                  </p>
                </div>

                {/* HTTP Headers */}
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <Label>
                      {isWorkspace
                        ? t(`${i18nNs}.mcp.dialogs.server.fields.headers.label`)
                        : t('template.editor.mcp.dialog.fields.headers.label')}
                    </Label>
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={addHeader}
                      disabled={submitting}
                    >
                      <Plus className="mr-1 h-4 w-4" />
                      {isWorkspace
                        ? t(`${i18nNs}.mcp.dialogs.server.fields.headers.add`)
                        : t('template.editor.mcp.dialog.fields.headers.add')}
                    </Button>
                  </div>
                  <div className="space-y-2">
                    {form.headers.map((row) => (
                      <div key={row.id} className="flex items-center gap-2">
                        <Input
                          value={row.key}
                          onChange={(event) => handleHeaderChange(row.id, 'key', event.target.value)}
                          placeholder={
                            isWorkspace
                              ? t(`${i18nNs}.mcp.dialogs.server.fields.headers.keyPlaceholder`)
                              : t('template.editor.mcp.dialog.fields.headers.keyPlaceholder')
                          }
                          className="flex-1 font-mono"
                        />
                        <span className="text-muted-foreground">:</span>
                        <Input
                          value={row.value}
                          onChange={(event) => handleHeaderChange(row.id, 'value', event.target.value)}
                          placeholder={
                            isWorkspace
                              ? t(`${i18nNs}.mcp.dialogs.server.fields.headers.valuePlaceholder`)
                              : t('template.editor.mcp.dialog.fields.headers.valuePlaceholder')
                          }
                          className="flex-1 font-mono"
                        />
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          onClick={() => removeHeader(row.id)}
                          disabled={submitting}
                        >
                          <X className="h-4 w-4" />
                        </Button>
                      </div>
                    ))}
                    {form.headers.length === 0 && (
                      <p className="text-sm text-muted-foreground">
                        {isWorkspace
                          ? t(`${i18nNs}.mcp.dialogs.server.fields.headers.empty`)
                          : t('template.editor.mcp.dialog.fields.headers.empty')}
                      </p>
                    )}
                  </div>
                  {!isWorkspace && (
                    <p className="text-xs text-muted-foreground">
                      {t('template.editor.mcp.dialog.fields.headers.hint')}
                    </p>
                  )}
                </div>
              </>
            )}

            {/* 環境變數 */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <Label>
                  {isWorkspace
                    ? t(`${i18nNs}.mcp.dialogs.server.fields.env.label`)
                    : t('template.editor.mcp.dialog.fields.env.label')}
                </Label>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={addEnv}
                  disabled={submitting}
                >
                  <Plus className="mr-1 h-4 w-4" />
                  {isWorkspace
                    ? t(`${i18nNs}.mcp.dialogs.server.fields.env.add`)
                    : t('template.editor.mcp.dialog.fields.env.add')}
                </Button>
              </div>
              <div className="space-y-2">
                {form.env.map((row) => (
                  <div key={row.id} className="flex items-center gap-2">
                    <Input
                      value={row.key}
                      onChange={(event) => handleEnvChange(row.id, 'key', event.target.value)}
                      placeholder={
                        isWorkspace
                          ? t(`${i18nNs}.mcp.dialogs.server.fields.env.keyPlaceholder`)
                          : t('template.editor.mcp.dialog.fields.env.keyPlaceholder')
                      }
                      className="flex-1 font-mono"
                    />
                    <span className="text-muted-foreground">=</span>
                    <Input
                      value={row.value}
                      onChange={(event) => handleEnvChange(row.id, 'value', event.target.value)}
                      placeholder={
                        isWorkspace
                          ? t(`${i18nNs}.mcp.dialogs.server.fields.env.valuePlaceholder`)
                          : t('template.editor.mcp.dialog.fields.env.valuePlaceholder')
                      }
                      className="flex-1 font-mono"
                    />
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={() => removeEnv(row.id)}
                      disabled={submitting}
                    >
                      <X className="h-4 w-4" />
                    </Button>
                  </div>
                ))}
                {form.env.length === 0 && (
                  <p className="text-sm text-muted-foreground">
                    {isWorkspace
                      ? t(`${i18nNs}.mcp.dialogs.server.fields.env.empty`)
                      : t('template.editor.mcp.dialog.fields.env.empty')}
                  </p>
                )}
              </div>
            </div>
          </form>
        </div>

        <DialogFooter className="flex-shrink-0 px-6 pb-6">
          <div className="flex w-full flex-col gap-3">
            {submitError && (
              <div className="w-full">
                <p className="text-sm text-destructive">{submitError}</p>
              </div>
            )}
            <div className="flex justify-end gap-2">
              <Button type="button" variant="outline" onClick={handleClose} disabled={submitting}>
                {t('common.cancel')}
              </Button>
              <Button type="submit" onClick={handleSubmit} disabled={submitting}>
                {submitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                {isEdit
                  ? t(
                      isWorkspace
                        ? 'workspace.claudeCode.mcp.dialogs.server.actions.save'
                        : 'template.editor.mcp.dialog.actions.save'
                    )
                  : t(
                      isWorkspace
                        ? 'workspace.claudeCode.mcp.dialogs.server.actions.create'
                        : 'template.editor.mcp.dialog.actions.create'
                    )}
              </Button>
            </div>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default MCPServerDialog;
