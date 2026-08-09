import React, { useEffect, useState } from 'react';
import { FileCode2 } from 'lucide-react';
import {
  formatDocumentContentSize,
  type DocumentWorkflowDialogProps,
} from '@/shared/components/document-workflow';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader } from '@/shared/components/ui/dialog';
import { DialogHeading } from '@/shared/components/ui/dialog-heading';
import { Input } from '@/shared/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/shared/components/ui/select';
import { useI18n } from '@/shared/hooks/useI18n';
import { SettingsDocumentEditor } from '../../components/SettingsDocumentEditor';
import type { AgentDocument, AgentScope } from '../../model/documents';

type RulesDocumentLayer = Extract<AgentScope, 'project' | 'user'>;

interface RulesDocumentDialogProps extends DocumentWorkflowDialogProps<AgentDocument> {
  i18nNamespace?: string;
}

const RULES_LAYERS: RulesDocumentLayer[] = ['project', 'user'];
const DEFAULT_RULE_FILE_NAME = 'default.rules';

const fileNameFromRulesPath = (path: string): string => path.split('/').filter(Boolean).pop() || path;

const buildRulesDocumentId = (layer: RulesDocumentLayer, path: string): string => `${layer}:${path}`;

const isRulesLayer = (value: unknown): value is RulesDocumentLayer => value === 'project' || value === 'user';

const isValidRulesPath = (path: string): boolean => {
  const trimmed = path.trim();
  return Boolean(trimmed)
    && trimmed.endsWith('.rules')
    && !trimmed.startsWith('/')
    && !trimmed.split('/').includes('..');
};

const documentSize = (content: string): string => formatDocumentContentSize(content || ' ');

export const RulesDocumentDialog: React.FC<RulesDocumentDialogProps> = ({
  open,
  mode,
  initialValue,
  onClose,
  onSubmit,
  submitDisabled = false,
  i18nNamespace = 'workspace.agentSettings.codex',
}) => {
  const { t } = useI18n();
  const [fileName, setFileName] = useState(DEFAULT_RULE_FILE_NAME);
  const [scope, setScope] = useState<RulesDocumentLayer>('project');
  const [content, setContent] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [errors, setErrors] = useState<{ fileName?: string; content?: string }>({});
  const isEdit = mode === 'edit';

  useEffect(() => {
    if (!open) return;
    const initialScope = isRulesLayer(initialValue?.scope) ? initialValue.scope : 'project';
    setScope(initialScope);
    setFileName(
      (initialValue?.metadata?.relativePath as string | undefined)
      ?? (initialValue?.metadata?.fileName as string | undefined)
      ?? DEFAULT_RULE_FILE_NAME,
    );
    setContent(initialValue?.content ?? t(`${i18nNamespace}.rules.defaultContent`));
    setErrors({});
    setSubmitting(false);
  }, [i18nNamespace, initialValue, open, t]);

  const validate = () => {
    const nextErrors: { fileName?: string; content?: string } = {};
    if (!isValidRulesPath(fileName)) {
      nextErrors.fileName = t(`${i18nNamespace}.rules.dialog.validation.fileName`);
    }
    if (!content.trim()) {
      nextErrors.content = t(`${i18nNamespace}.rules.dialog.validation.content`);
    }
    setErrors(nextErrors);
    return Object.keys(nextErrors).length === 0;
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (submitDisabled) return;
    if (!validate()) return;
    setSubmitting(true);
    try {
      const normalizedPath = fileName.trim();
      await onSubmit({
        id: buildRulesDocumentId(scope, normalizedPath),
        title: fileNameFromRulesPath(normalizedPath),
        description: '',
        content,
        scope,
        size: documentSize(content),
        metadata: {
          fileName: normalizedPath,
          relativePath: normalizedPath,
          source: scope,
          sizeBytes: content.length,
        },
      });
      onClose();
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(next) => !submitting && (!next ? onClose() : null)}>
      <DialogContent className="flex h-[85vh] max-h-[85vh] w-full max-w-4xl flex-col p-0">
        <DialogHeader className="flex-shrink-0 px-6 pt-6">
          <DialogHeading icon={FileCode2}>
            {isEdit
              ? t(`${i18nNamespace}.rules.dialog.title.edit`)
              : t(`${i18nNamespace}.rules.dialog.title.create`)}
          </DialogHeading>
          <DialogDescription>
            {isEdit
              ? t(`${i18nNamespace}.rules.dialog.description.edit`)
              : t(`${i18nNamespace}.rules.dialog.description.create`)}
          </DialogDescription>
        </DialogHeader>

        <form className="flex flex-1 flex-col overflow-hidden" onSubmit={handleSubmit}>
          <div className="flex-1 overflow-hidden px-6 pb-6 pt-4">
            <div className="flex h-full flex-col gap-4">
              <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-2">
                  <label className="text-sm font-medium text-foreground">
                    {t(`${i18nNamespace}.rules.dialog.fields.scope.label`)}
                  </label>
                  {isEdit ? (
                    <Badge variant="outline" className="text-sm">
                      {t(`${i18nNamespace}.common.layers.${scope}`)}
                    </Badge>
                  ) : (
                    <Select
                      value={scope}
                      onValueChange={(value) => setScope(isRulesLayer(value) ? value : 'project')}
                      disabled={submitDisabled}
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {RULES_LAYERS.map((layer) => (
                          <SelectItem key={layer} value={layer}>
                            {t(`${i18nNamespace}.common.layers.${layer}`)}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  )}
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium text-foreground">
                    {t(`${i18nNamespace}.rules.dialog.fields.fileName.label`)}
                  </label>
                  <Input
                    value={fileName}
                    disabled={submitDisabled}
                    onChange={(event) => setFileName(event.target.value)}
                    placeholder={t(`${i18nNamespace}.rules.fileNamePlaceholder`)}
                  />
                  {errors.fileName ? <p className="text-xs text-destructive">{errors.fileName}</p> : null}
                  <p className="text-xs text-muted-foreground">
                    {t(`${i18nNamespace}.rules.dialog.fields.fileName.helper`)}
                  </p>
                </div>
              </div>

              <div className="flex min-h-0 flex-1 flex-col space-y-2">
                <label className="text-sm font-medium text-foreground">
                  {t(`${i18nNamespace}.rules.dialog.fields.content.label`)}
                </label>
                <div className="min-h-0 flex-1 overflow-hidden rounded-lg border">
                  <SettingsDocumentEditor
                    value={content}
                    format="starlark"
                    onChange={setContent}
                    readOnly={submitDisabled}
                    footerExtras={
                      <span className="text-xs text-muted-foreground">
                        {t(`${i18nNamespace}.rules.dialog.fields.content.estimatedSize`, {
                          size: documentSize(content),
                        })}
                      </span>
                    }
                  />
                </div>
                {errors.content ? <p className="text-xs text-destructive">{errors.content}</p> : null}
              </div>
            </div>
          </div>

          <DialogFooter className="flex-shrink-0 gap-2 px-6 pb-6">
            <Button type="button" variant="ghost" onClick={onClose} disabled={submitting}>
              {t(`${i18nNamespace}.rules.dialog.actions.cancel`)}
            </Button>
            <Button type="submit" disabled={submitting || submitDisabled}>
              {isEdit
                ? t(`${i18nNamespace}.rules.dialog.actions.save`)
                : t(`${i18nNamespace}.rules.dialog.actions.create`)}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
};

export default RulesDocumentDialog;
