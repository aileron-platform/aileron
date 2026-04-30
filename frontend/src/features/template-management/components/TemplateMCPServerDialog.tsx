import React, { useEffect, useState } from 'react';
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
  parseMCPArgsText,
  parseMCPKeyValueText,
  toMCPKeyValueRecord,
  toMCPKeyValueText,
  type MCPKeyValueRow,
  type MCPTransport,
  type MCPTransportFieldsLabels,
} from '@/shared/components/mcp-workflow';
import { useI18n } from '@/shared/hooks/useI18n';
import type { McpServerFormValue } from '@/features/template-management/features/template-editor/formTypes';

interface MCPFormState {
  id: string;
  name: string;
  description: string;
  transport: MCPTransport;
  command: string;
  args: string[];
  url: string;
  env: MCPKeyValueRow[];
  headers: MCPKeyValueRow[];
}

const DEFAULT_FORM: MCPFormState = {
  id: '',
  name: '',
  description: '',
  transport: 'stdio',
  command: '',
  args: [],
  url: '',
  env: [],
  headers: [],
};

export interface TemplateMCPServerDialogProps {
  open: boolean;
  initialData?: McpServerFormValue;
  onOpenChange: (open: boolean) => void;
  onSave: (data: McpServerFormValue) => void;
}

export const TemplateMCPServerDialog: React.FC<TemplateMCPServerDialogProps> = ({
  open,
  initialData,
  onOpenChange,
  onSave,
}) => {
  const { t } = useI18n();
  const [form, setForm] = useState<MCPFormState>(DEFAULT_FORM);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const isEdit = Boolean(initialData);

  useEffect(() => {
    if (!open) return;

    if (initialData) {
      setForm({
        id: initialData.localId,
        name: initialData.name,
        description: initialData.description || '',
        transport: initialData.type,
        command: initialData.command,
        args: parseMCPArgsText(initialData.argsText),
        url: initialData.url || '',
        env: createMCPKeyValueRows(parseMCPKeyValueText(initialData.envText, '=')),
        headers: createMCPKeyValueRows(parseMCPKeyValueText(initialData.headersText, ':')),
      });
    } else {
      setForm({
        ...DEFAULT_FORM,
        id: `local-${Math.random().toString(36).slice(2, 10)}`,
      });
    }

    setSubmitError(null);
    setSubmitting(false);
  }, [open, initialData]);

  const handleChange = <TField extends keyof MCPFormState>(
    field: TField,
    value: MCPFormState[TField],
  ) => {
    setSubmitError(null);
    setForm((prev) => ({ ...prev, [field]: value }));
  };

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    setSubmitError(null);

    const name = form.name.trim();

    if (!name) {
      setSubmitError(t('template.editor.mcp.dialog.validation.nameRequired'));
      return;
    }

    if (!form.description.trim()) {
      setSubmitError(t('template.editor.mcp.dialog.validation.descriptionRequired'));
      return;
    }

    if (form.transport === 'stdio' && !form.command.trim()) {
      setSubmitError(t('template.editor.mcp.dialog.validation.commandRequired'));
      return;
    }

    if ((form.transport === 'http' || form.transport === 'sse') && !form.url.trim()) {
      setSubmitError(t('template.editor.mcp.dialog.validation.urlRequired'));
      return;
    }

    const sanitizedEnv = toMCPKeyValueRecord(form.env);
    const sanitizedHeaders = toMCPKeyValueRecord(form.headers);
    const sanitizedArgs = form.args.map((arg) => arg.trim()).filter(Boolean);

    try {
      setSubmitting(true);
      onSave({
        localId: initialData?.localId || form.id,
        name,
        type: form.transport,
        command: form.command.trim(),
        argsText: sanitizedArgs.join('\n'),
        url: form.url.trim(),
        description: form.description.trim(),
        envText: toMCPKeyValueText(sanitizedEnv, '='),
        headersText: toMCPKeyValueText(sanitizedHeaders, ': '),
      });
      onOpenChange(false);
    } catch (err) {
      const message = err instanceof Error
        ? err.message
        : t('template.editor.mcp.dialog.validation.saveFailed');
      setSubmitError(message);
    } finally {
      setSubmitting(false);
    }
  };

  const transportOptions = (['stdio', 'sse', 'http'] as MCPTransport[]).map((transport) => ({
    value: transport,
    title: t(`template.editor.mcp.dialog.transport.options.${transport}.label`),
    description: t(`template.editor.mcp.dialog.transport.options.${transport}.description`),
  }));

  const transportFieldLabels: MCPTransportFieldsLabels = {
    commandLabel: t('template.editor.mcp.dialog.fields.command.label'),
    commandPlaceholder: t('template.editor.mcp.dialog.fields.command.placeholder'),
    argsLabel: t('template.editor.mcp.dialog.fields.args.label'),
    argsAdd: t('template.editor.mcp.dialog.fields.args.add'),
    argsEmpty: t('template.editor.mcp.dialog.fields.args.empty'),
    argsPlaceholder: (index) => t('template.editor.mcp.dialog.fields.args.placeholder', { index }),
    urlLabel: t('template.editor.mcp.dialog.fields.url.label'),
    urlPlaceholder: t(
      form.transport === 'sse'
        ? 'template.editor.mcp.dialog.fields.url.placeholderSse'
        : 'template.editor.mcp.dialog.fields.url.placeholderHttp',
    ),
    urlHint: t(
      form.transport === 'sse'
        ? 'template.editor.mcp.dialog.fields.url.hintSse'
        : 'template.editor.mcp.dialog.fields.url.hintHttp',
    ),
    headersLabel: t('template.editor.mcp.dialog.fields.headers.label'),
    headersAdd: t('template.editor.mcp.dialog.fields.headers.add'),
    headersKeyPlaceholder: t('template.editor.mcp.dialog.fields.headers.keyPlaceholder'),
    headersValuePlaceholder: t('template.editor.mcp.dialog.fields.headers.valuePlaceholder'),
    headersEmpty: t('template.editor.mcp.dialog.fields.headers.empty'),
    headersHint: t('template.editor.mcp.dialog.fields.headers.hint'),
    envLabel: t('template.editor.mcp.dialog.fields.env.label'),
    envAdd: t('template.editor.mcp.dialog.fields.env.add'),
    envKeyPlaceholder: t('template.editor.mcp.dialog.fields.env.keyPlaceholder'),
    envValuePlaceholder: t('template.editor.mcp.dialog.fields.env.valuePlaceholder'),
    envEmpty: t('template.editor.mcp.dialog.fields.env.empty'),
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="flex h-[85vh] max-h-[85vh] max-w-2xl flex-col p-0">
        <DialogHeader className="flex-shrink-0 px-6 pt-6">
          <DialogTitle className="flex items-center gap-2">
            <Server className="h-5 w-5 text-primary" />
            {t(`template.editor.mcp.dialog.title.${isEdit ? 'edit' : 'create'}`)}
          </DialogTitle>
          <DialogDescription>
            {t(`template.editor.mcp.dialog.description.${isEdit ? 'edit' : 'create'}`)}
          </DialogDescription>
        </DialogHeader>

        <div className="flex-1 overflow-y-auto px-6 py-4">
          <form onSubmit={handleSubmit} className="space-y-6">
            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="mcp-name">
                  {t('template.editor.mcp.dialog.fields.name.label')}
                </Label>
                <Input
                  id="mcp-name"
                  value={form.name}
                  onChange={(event) => handleChange('name', event.target.value)}
                  placeholder={t('template.editor.mcp.dialog.fields.name.placeholder')}
                  className="font-medium"
                  required
                />
              </div>

              <div className="space-y-2">
                <Label>{t('template.editor.mcp.dialog.transport.label')}</Label>
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
              <Button
                type="button"
                variant="outline"
                onClick={() => onOpenChange(false)}
                disabled={submitting}
              >
                {t('common.cancel')}
              </Button>
              <Button type="submit" onClick={handleSubmit} disabled={submitting}>
                {submitting ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                {t(`template.editor.mcp.dialog.actions.${isEdit ? 'save' : 'create'}`)}
              </Button>
            </div>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default TemplateMCPServerDialog;
