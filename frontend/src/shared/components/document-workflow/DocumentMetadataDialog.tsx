import React from 'react';
import { FileText } from 'lucide-react';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import { Alert, AlertDescription } from '@/shared/components/ui/alert';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
} from '@/shared/components/ui/dialog';
import { DialogHeading } from '@/shared/components/ui/dialog-heading';
import { Input } from '@/shared/components/ui/input';
import { Label } from '@/shared/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/shared/components/ui/select';
import { useI18n } from '@/shared/hooks/useI18n';
import type { DocumentMetadataCapabilities, DocumentMetadataValue } from './documentMetadata';

export interface DocumentMetadataScopeOption {
  value: string;
  labelKey: string;
}

export interface DocumentMetadataDialogProps {
  open: boolean;
  mode: 'create' | 'rename';
  titleKey: string;
  descriptionKey: string;
  value: DocumentMetadataValue;
  capabilities: DocumentMetadataCapabilities;
  scopeOptions: DocumentMetadataScopeOption[];
  errorMessage?: string | null;
  submitting?: boolean;
  submitDisabled?: boolean;
  onChange(value: DocumentMetadataValue): void;
  onClose(): void;
  onSubmit(value: DocumentMetadataValue): void;
}

export const DocumentMetadataDialog: React.FC<DocumentMetadataDialogProps> = ({
  open,
  mode,
  titleKey,
  descriptionKey,
  value,
  capabilities,
  scopeOptions,
  errorMessage = null,
  submitting = false,
  submitDisabled = false,
  onChange,
  onClose,
  onSubmit,
}) => {
  const { t } = useI18n();
  const canEditStructure = mode === 'create';
  const actionKey = mode === 'create'
    ? 'shared.documentWorkflow.metadata.actions.create'
    : 'shared.documentWorkflow.metadata.actions.rename';
  const trimmedFileName = value.fileName.trim();

  return (
    <Dialog open={open} onOpenChange={(next) => { if (!next) onClose(); }}>
      <DialogContent>
        <DialogHeader>
          <DialogHeading icon={FileText}>{t(titleKey)}</DialogHeading>
          <DialogDescription>{t(descriptionKey)}</DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="document-metadata-file-name">
              {t('shared.documentWorkflow.metadata.fileName.label')}
            </Label>
            <Input
              id="document-metadata-file-name"
              value={value.fileName}
              disabled={submitDisabled}
              onChange={(event) => onChange({ ...value, fileName: event.target.value })}
              className="font-mono text-sm"
            />
          </div>

          {capabilities.scope ? (
            <div className="space-y-2">
              <Label>{t('shared.documentWorkflow.metadata.scope.label')}</Label>
              {canEditStructure ? (
                <Select
                  value={value.scope}
                  disabled={submitDisabled}
                  onValueChange={(scope) => onChange({ ...value, scope })}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {scopeOptions.map((option) => (
                      <SelectItem key={option.value} value={option.value}>{t(option.labelKey)}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              ) : (
                <Badge variant="outline">{value.scope}</Badge>
              )}
            </div>
          ) : null}

          {capabilities.namespace ? (
            <div className="space-y-2">
              <Label htmlFor="document-metadata-namespace">
                {t('shared.documentWorkflow.metadata.namespace.label')}
              </Label>
              {canEditStructure ? (
                <Input
                  id="document-metadata-namespace"
                  value={value.namespace ?? ''}
                  disabled={submitDisabled}
                  onChange={(event) => onChange({ ...value, namespace: event.target.value || undefined })}
                  className="font-mono text-sm"
                />
              ) : (
                <Badge variant="outline">{value.namespace}</Badge>
              )}
            </div>
          ) : null}

          {value.path ? (
            <div className="space-y-2">
              <Label>{t('shared.documentWorkflow.metadata.path.label')}</Label>
              <div className="rounded-md border bg-muted/30 px-3 py-2 font-mono text-xs text-muted-foreground">
                {value.path}
              </div>
            </div>
          ) : null}
        </div>

        {errorMessage ? (
          <Alert variant="destructive">
            <AlertDescription>{errorMessage}</AlertDescription>
          </Alert>
        ) : null}

        <DialogFooter>
          <Button type="button" variant="outline" onClick={onClose} disabled={submitting}>
            {t('shared.documentWorkflow.metadata.actions.cancel')}
          </Button>
          <Button
            type="button"
            disabled={!trimmedFileName || submitting || submitDisabled}
            onClick={() => onSubmit({ ...value, fileName: trimmedFileName })}
          >
            {t(actionKey)}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};
