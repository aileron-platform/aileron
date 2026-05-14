import { DialogHeading } from '@/shared/components/ui/dialog-heading';
import React, { useEffect, useMemo, useState } from 'react';
import { Loader2, Server } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader } from '@/shared/components/ui/dialog';
import { Input } from '@/shared/components/ui/input';
import { Label } from '@/shared/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/shared/components/ui/select';
import { cn } from '@/shared/utils/cn';
import {
  MCPTransportFieldsEditor,
  createMCPKeyValueRows,
  toMCPKeyValueRecord,
  type MCPKeyValueRow,
  type MCPTransport,
  type MCPTransportFieldsLabels,
} from './MCPTransportFieldsEditor';
import type { MCPServerCardData } from './MCPServerCard';

export interface MCPServerScopeOption<TScope extends string = string> {
  value: TScope;
  title: string;
  description: string;
}

export interface MCPServerTransportOption {
  value: MCPTransport;
  title: string;
  description: string;
}

export type MCPServerDialogData<TScope extends string = string> = MCPServerCardData & {
  scope: TScope;
  transport: MCPTransport;
};

export interface MCPServerDialogLabels {
  titleCreate: string;
  titleEdit: string;
  description: string;
  nameLabel: string;
  namePlaceholder: string;
  nameHint: string;
  scopeLabel: string;
  transportLabel: string;
  cancel: string;
  create: string;
  save: string;
  nameRequired: string;
  commandRequired: string;
  urlRequired: string;
  saveFailed: string;
}

export interface MCPServerDialogDescriptionField {
  label: string;
  placeholder: string;
  requiredMessage?: string;
}

interface MCPFormState<TScope extends string> {
  name: string;
  description: string;
  scope: TScope;
  transport: MCPTransport;
  command: string;
  args: string[];
  url: string;
  env: MCPKeyValueRow[];
  headers: MCPKeyValueRow[];
}

export interface MCPServerDialogProps<TScope extends string = string> {
  open: boolean;
  mode: 'create' | 'edit';
  server: MCPServerCardData | null;
  scopeOptions: MCPServerScopeOption<TScope>[];
  transportOptions: MCPServerTransportOption[];
  labels: MCPServerDialogLabels;
  transportFieldLabels: MCPTransportFieldsLabels | ((transport: MCPTransport) => MCPTransportFieldsLabels);
  descriptionField?: MCPServerDialogDescriptionField;
  onClose: () => void;
  onSubmit: (server: MCPServerDialogData<TScope>) => Promise<void>;
}

export const MCPServerDialog = <TScope extends string = string>({
  open,
  mode,
  server,
  scopeOptions,
  transportOptions,
  labels,
  transportFieldLabels,
  descriptionField,
  onClose,
  onSubmit,
}: MCPServerDialogProps<TScope>) => {
  const defaultScope = scopeOptions[0]?.value ?? ('' as TScope);
  const hasScopeOptions = scopeOptions.length > 0;
  const defaultForm = useMemo<MCPFormState<TScope>>(() => ({
    name: '',
    description: '',
    scope: defaultScope,
    transport: 'stdio',
    command: '',
    args: [],
    url: '',
    env: [],
    headers: [],
  }), [defaultScope]);

  const [form, setForm] = useState<MCPFormState<TScope>>(defaultForm);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const isEdit = mode === 'edit';

  useEffect(() => {
    if (!open) return;

    if (mode === 'edit' && server) {
      setForm({
        name: server.name,
        description: server.description ?? '',
        scope: server.scope as TScope,
        transport: server.transport ?? 'stdio',
        command: server.command ?? '',
        args: server.args ?? [],
        url: server.url ?? '',
        env: createMCPKeyValueRows(server.env),
        headers: createMCPKeyValueRows(server.headers),
      });
    } else {
      setForm(defaultForm);
    }

    setSubmitError(null);
    setSubmitting(false);
  }, [defaultForm, mode, open, server]);

  const handleChange = <TField extends keyof MCPFormState<TScope>>(
    field: TField,
    value: MCPFormState<TScope>[TField],
  ) => {
    setSubmitError(null);
    setForm((prev) => ({ ...prev, [field]: value }));
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setSubmitError(null);

    const name = form.name.trim();
    if (!name) {
      setSubmitError(labels.nameRequired);
      return;
    }

    if (descriptionField?.requiredMessage && !form.description.trim()) {
      setSubmitError(descriptionField.requiredMessage);
      return;
    }

    if (form.transport === 'stdio' && !form.command.trim()) {
      setSubmitError(labels.commandRequired);
      return;
    }

    if ((form.transport === 'http' || form.transport === 'sse') && !form.url.trim()) {
      setSubmitError(labels.urlRequired);
      return;
    }

    const sanitizedEnv = toMCPKeyValueRecord(form.env);
    const sanitizedHeaders = toMCPKeyValueRecord(form.headers);
    const sanitizedArgs = form.args.map((arg) => arg.trim()).filter(Boolean);
    const resolvedScope = (hasScopeOptions ? form.scope : (server?.scope as TScope | undefined)) ?? defaultScope;

    const payload: MCPServerDialogData<TScope> = {
      id: server?.id ?? (hasScopeOptions && resolvedScope ? `${resolvedScope}:${name}` : name),
      name,
      description: form.description.trim() || undefined,
      scope: resolvedScope,
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
      const message = err instanceof Error ? err.message : labels.saveFailed;
      setSubmitError(message);
      throw err instanceof Error ? err : new Error(message);
    } finally {
      setSubmitting(false);
    }
  };

  const resolvedTransportFieldLabels = useMemo<MCPTransportFieldsLabels>(
    () => (typeof transportFieldLabels === 'function' ? transportFieldLabels(form.transport) : transportFieldLabels),
    [form.transport, transportFieldLabels],
  );

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="flex h-[85vh] max-h-[85vh] max-w-2xl flex-col p-0">
        <DialogHeader className="flex-shrink-0 px-6 pt-6">
          <DialogHeading icon={Server}>
            {isEdit ? labels.titleEdit : labels.titleCreate}
          </DialogHeading>
          <DialogDescription>{labels.description}</DialogDescription>
        </DialogHeader>

        <div className="flex-1 overflow-y-auto px-6 py-4">
          <form onSubmit={handleSubmit} className="space-y-6">
            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="mcp-name">{labels.nameLabel}</Label>
                <Input
                  id="mcp-name"
                  value={form.name}
                  disabled={isEdit}
                  onChange={(event) => handleChange('name', event.target.value)}
                  placeholder={labels.namePlaceholder}
                  className={cn('font-medium', isEdit && 'bg-muted text-muted-foreground')}
                  required
                />
                <p className="text-xs text-muted-foreground">{labels.nameHint}</p>
              </div>

              {hasScopeOptions ? (
                <div className="space-y-2">
                  <Label>{labels.scopeLabel}</Label>
                  <Select
                    value={form.scope}
                    onValueChange={(value) => handleChange('scope', value as TScope)}
                    disabled={isEdit}
                  >
                    <SelectTrigger className={cn(isEdit && 'bg-muted text-muted-foreground')}>
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
              ) : null}

              <div className="space-y-2">
                <Label>{labels.transportLabel}</Label>
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

            {descriptionField ? (
              <div className="space-y-2">
                <Label htmlFor="mcp-description">{descriptionField.label}</Label>
                <Input
                  id="mcp-description"
                  value={form.description}
                  onChange={(event) => handleChange('description', event.target.value)}
                  placeholder={descriptionField.placeholder}
                />
              </div>
            ) : null}

            <MCPTransportFieldsEditor
              transport={form.transport}
              command={form.command}
              args={form.args}
              url={form.url}
              env={form.env}
              headers={form.headers}
              submitting={submitting}
              labels={resolvedTransportFieldLabels}
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
                {labels.cancel}
              </Button>
              <Button type="submit" onClick={handleSubmit} disabled={submitting}>
                {submitting ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                {isEdit ? labels.save : labels.create}
              </Button>
            </div>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

MCPServerDialog.displayName = 'MCPServerDialog';

export default MCPServerDialog;
