import React, { useEffect, useMemo, useState } from 'react';
import { Loader2, Server } from 'lucide-react';
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
import { Label } from '@/shared/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/shared/components/ui/select';
import {
  MCPTransportFieldsEditor,
  createMCPKeyValueRows,
  toMCPKeyValueRecord,
  type MCPKeyValueRow,
  type MCPTransport,
  type MCPTransportFieldsLabels,
} from '@/shared/components/mcp-workflow';
import { useI18n } from '@/shared/hooks/useI18n';
import { cn } from '@/shared/utils/cn';
import type { AgentMcpServer, AgentScope } from '@/features/workspace/features/agent-settings/types';

export type EditableMCPServerScope = Exclude<AgentScope, 'plugin'>;
export type WorkspaceMCPServerData = AgentMcpServer & {
  scope: EditableMCPServerScope;
  transport?: MCPTransport;
};

interface MCPFormState {
  name: string;
  scope: EditableMCPServerScope;
  transport: MCPTransport;
  command: string;
  args: string[];
  url: string;
  env: MCPKeyValueRow[];
  headers: MCPKeyValueRow[];
}

const DEFAULT_FORM: MCPFormState = {
  name: '',
  scope: 'project',
  transport: 'stdio',
  command: '',
  args: [],
  url: '',
  env: [],
  headers: [],
};

const EDITABLE_SCOPES: EditableMCPServerScope[] = ['project', 'user', 'local'];

export interface WorkspaceMCPServerDialogProps {
  open: boolean;
  mode: 'create' | 'edit';
  server: AgentMcpServer | null;
  availableScopes?: AgentScope[];
  i18nNamespace?: string;
  onClose: () => void;
  onSubmit: (server: WorkspaceMCPServerData) => Promise<void>;
}

export const WorkspaceMCPServerDialog: React.FC<WorkspaceMCPServerDialogProps> = ({
  open,
  mode,
  server,
  availableScopes,
  i18nNamespace = 'workspace.agentSettings.common',
  onClose,
  onSubmit,
}) => {
  const { t } = useI18n();
  const [form, setForm] = useState<MCPFormState>(DEFAULT_FORM);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const isEdit = mode === 'edit';
  const isDisabled = isEdit;

  const scopeOptions = useMemo(() => {
    const allowedScopes = availableScopes
      ? EDITABLE_SCOPES.filter((scope) => availableScopes.includes(scope))
      : EDITABLE_SCOPES;

    return allowedScopes.map((scope) => ({
      value: scope,
      title: t(`${i18nNamespace}.mcp.dialogs.server.fields.scope.options.${scope}.title`),
      description: t(`${i18nNamespace}.mcp.dialogs.server.fields.scope.options.${scope}.description`),
    }));
  }, [availableScopes, i18nNamespace, t]);

  const transportOptions = useMemo(
    () => (['stdio', 'sse', 'http'] as MCPTransport[]).map((transport) => ({
      value: transport,
      title: t(`${i18nNamespace}.mcp.dialogs.server.fields.transport.options.${transport}.title`),
      description: t(`${i18nNamespace}.mcp.dialogs.server.fields.transport.options.${transport}.description`),
    })),
    [i18nNamespace, t],
  );

  useEffect(() => {
    if (!open) return;

    if (mode === 'edit' && server) {
      setForm({
        name: server.name,
        scope: server.scope === 'plugin' ? 'project' : server.scope,
        transport: server.transport ?? 'stdio',
        command: server.command ?? '',
        args: server.args ?? [],
        url: server.url ?? '',
        env: createMCPKeyValueRows(server.env),
        headers: createMCPKeyValueRows(server.headers),
      });
    } else {
      setForm(DEFAULT_FORM);
    }

    setSubmitError(null);
    setSubmitting(false);
  }, [open, mode, server]);

  const handleChange = <TField extends keyof MCPFormState>(
    field: TField,
    value: MCPFormState[TField],
  ) => {
    setSubmitError(null);
    setForm((prev) => ({ ...prev, [field]: value }));
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setSubmitError(null);

    const name = form.name.trim();

    if (!name) {
      setSubmitError(t(`${i18nNamespace}.mcp.dialogs.server.errors.nameRequired`));
      return;
    }

    if (form.transport === 'stdio' && !form.command.trim()) {
      setSubmitError(t(`${i18nNamespace}.mcp.dialogs.server.errors.commandRequired`));
      return;
    }

    if ((form.transport === 'http' || form.transport === 'sse') && !form.url.trim()) {
      setSubmitError(t(`${i18nNamespace}.mcp.dialogs.server.errors.urlRequired`));
      return;
    }

    const sanitizedEnv = toMCPKeyValueRecord(form.env);
    const sanitizedHeaders = toMCPKeyValueRecord(form.headers);
    const sanitizedArgs = form.args.map((arg) => arg.trim()).filter(Boolean);

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
      payload.url = form.url.trim();
    }

    try {
      setSubmitting(true);
      await onSubmit(payload);
    } catch (err) {
      const message = err instanceof Error
        ? err.message
        : t(`${i18nNamespace}.mcp.dialogs.server.errors.saveFailed`);
      setSubmitError(message);
      throw err instanceof Error ? err : new Error(message);
    } finally {
      setSubmitting(false);
    }
  };

  const transportFieldLabels: MCPTransportFieldsLabels = {
    commandLabel: t(`${i18nNamespace}.mcp.dialogs.server.fields.command.label`),
    commandPlaceholder: t(`${i18nNamespace}.mcp.dialogs.server.fields.command.placeholder`),
    argsLabel: t(`${i18nNamespace}.mcp.dialogs.server.fields.commandArgs.label`),
    argsAdd: t(`${i18nNamespace}.mcp.dialogs.server.fields.commandArgs.add`),
    argsEmpty: t(`${i18nNamespace}.mcp.dialogs.server.fields.commandArgs.empty`),
    argsPlaceholder: (index) =>
      t(`${i18nNamespace}.mcp.dialogs.server.fields.commandArgs.placeholder`, { index }),
    urlLabel: t(`${i18nNamespace}.mcp.dialogs.server.fields.url.label`),
    urlPlaceholder: t(`${i18nNamespace}.mcp.dialogs.server.fields.url.placeholder.${form.transport === 'sse' ? 'sse' : 'http'}`),
    urlHint: t(`${i18nNamespace}.mcp.dialogs.server.fields.url.hint.${form.transport === 'sse' ? 'sse' : 'http'}`),
    headersLabel: t(`${i18nNamespace}.mcp.dialogs.server.fields.headers.label`),
    headersAdd: t(`${i18nNamespace}.mcp.dialogs.server.fields.headers.add`),
    headersKeyPlaceholder: t(`${i18nNamespace}.mcp.dialogs.server.fields.headers.keyPlaceholder`),
    headersValuePlaceholder: t(`${i18nNamespace}.mcp.dialogs.server.fields.headers.valuePlaceholder`),
    headersEmpty: t(`${i18nNamespace}.mcp.dialogs.server.fields.headers.empty`),
    envLabel: t(`${i18nNamespace}.mcp.dialogs.server.fields.env.label`),
    envAdd: t(`${i18nNamespace}.mcp.dialogs.server.fields.env.add`),
    envKeyPlaceholder: t(`${i18nNamespace}.mcp.dialogs.server.fields.env.keyPlaceholder`),
    envValuePlaceholder: t(`${i18nNamespace}.mcp.dialogs.server.fields.env.valuePlaceholder`),
    envEmpty: t(`${i18nNamespace}.mcp.dialogs.server.fields.env.empty`),
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="flex h-[85vh] max-h-[85vh] max-w-2xl flex-col p-0">
        <DialogHeader className="flex-shrink-0 px-6 pt-6">
          <DialogTitle className="flex items-center gap-2">
            <Server className="h-5 w-5 text-primary" />
            {t(`${i18nNamespace}.mcp.dialogs.server.title.${isEdit ? 'edit' : 'create'}`)}
          </DialogTitle>
          <DialogDescription>
            {t(`${i18nNamespace}.mcp.dialogs.server.description`)}
          </DialogDescription>
        </DialogHeader>

        <div className="flex-1 overflow-y-auto px-6 py-4">
          <form onSubmit={handleSubmit} className="space-y-6">
            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="mcp-name">
                  {t(`${i18nNamespace}.mcp.dialogs.server.fields.name.label`)}
                </Label>
                <Input
                  id="mcp-name"
                  value={form.name}
                  disabled={isDisabled}
                  onChange={(event) => handleChange('name', event.target.value)}
                  placeholder={t(`${i18nNamespace}.mcp.dialogs.server.fields.name.placeholder`)}
                  className={cn('font-medium', isDisabled && 'bg-muted text-muted-foreground')}
                  required
                />
                <p className="text-xs text-muted-foreground">
                  {t(`${i18nNamespace}.mcp.dialogs.server.fields.name.hint`)}
                </p>
              </div>

              <div className="space-y-2">
                <Label>{t(`${i18nNamespace}.mcp.dialogs.server.fields.scope.label`)}</Label>
                <Select
                  value={form.scope}
                  onValueChange={(value: EditableMCPServerScope) => handleChange('scope', value)}
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

              <div className="space-y-2">
                <Label>{t(`${i18nNamespace}.mcp.dialogs.server.fields.transport.label`)}</Label>
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

            <MCPTransportFieldsEditor
              transport={form.transport}
              command={form.command}
              args={form.args}
              url={form.url}
              env={form.env}
              headers={form.headers}
              submitting={submitting}
              labels={transportFieldLabels}
              onCommandChange={(command) => handleChange('command', command)}
              onArgsChange={(args) => handleChange('args', args)}
              onUrlChange={(url) => handleChange('url', url)}
              onEnvChange={(env) => handleChange('env', env)}
              onHeadersChange={(headers) => handleChange('headers', headers)}
            />
          </form>
        </div>

        <DialogFooter className="flex-shrink-0 px-6 pb-6">
          <div className="flex w-full flex-col gap-3">
            {submitError ? (
              <div className="w-full">
                <p className="text-sm text-destructive">{submitError}</p>
              </div>
            ) : null}
            <div className="flex justify-end gap-2">
              <Button type="button" variant="outline" onClick={onClose} disabled={submitting}>
                {t('common.cancel')}
              </Button>
              <Button type="submit" onClick={handleSubmit} disabled={submitting}>
                {submitting ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                {t(`${i18nNamespace}.mcp.dialogs.server.actions.${isEdit ? 'save' : 'create'}`)}
              </Button>
            </div>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default WorkspaceMCPServerDialog;
