import React from 'react';
import type { LucideIcon } from 'lucide-react';
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
import { MarkdownEditor } from '@/shared/components/markdown/MarkdownEditor';

export interface DocumentEditorScopeOption<TScope extends string> {
  value: TScope;
  label: string;
}

export interface DocumentEditorDialogCoreProps<TScope extends string> {
  open: boolean;
  isEdit: boolean;
  submitting: boolean;
  icon: LucideIcon;
  title: string;
  description: string;
  showScope: boolean;
  scopeValue: TScope;
  scopeOptions: DocumentEditorScopeOption<TScope>[];
  scopeLabel: string;
  onScopeChange: (scope: TScope) => void;
  fileName: string;
  fileNameLabel: string;
  fileNamePlaceholder: string;
  fileNameHelper?: string;
  fileNameError?: string;
  onFileNameChange: (fileName: string) => void;
  content: string;
  contentLabel: string;
  contentHelper?: string;
  contentError?: string;
  contentFooter: React.ReactNode;
  extraFields?: React.ReactNode;
  onContentChange: (content: string) => void;
  cancelLabel: string;
  cancelVariant?: React.ComponentProps<typeof Button>['variant'];
  submitLabel: string;
  onClose: () => void;
  onSubmit: (event: React.FormEvent) => void;
}

export const formatDocumentContentSize = (content: string): string => {
  if (!content) {
    return '1KB';
  }
  const kiloBytes = Math.max(1, Math.ceil(content.length / 1024));
  return `${kiloBytes}KB`;
};

export const ensureMarkdownExtension = (fileName: string): string => {
  const trimmed = fileName.trim();
  return trimmed.toLowerCase().endsWith('.md') ? trimmed : `${trimmed}.md`;
};

export function DocumentEditorDialogCore<TScope extends string>({
  open,
  isEdit,
  submitting,
  icon: Icon,
  title,
  description,
  showScope,
  scopeValue,
  scopeOptions,
  scopeLabel,
  onScopeChange,
  fileName,
  fileNameLabel,
  fileNamePlaceholder,
  fileNameHelper,
  fileNameError,
  onFileNameChange,
  content,
  contentLabel,
  contentHelper,
  contentError,
  contentFooter,
  extraFields,
  onContentChange,
  cancelLabel,
  cancelVariant = 'ghost',
  submitLabel,
  onClose,
  onSubmit,
}: DocumentEditorDialogCoreProps<TScope>) {
  return (
    <Dialog open={open} onOpenChange={(next) => !submitting && (!next ? onClose() : null)}>
      <DialogContent className="flex h-[85vh] max-h-[85vh] w-full max-w-4xl flex-col p-0">
        <DialogHeader className="flex-shrink-0 px-6 pt-6">
          <DialogTitle className="flex items-center gap-2">
            <Icon className="h-5 w-5 text-primary" />
            {title}
          </DialogTitle>
          <DialogDescription>{description}</DialogDescription>
        </DialogHeader>

        <form className="flex flex-1 flex-col overflow-hidden" onSubmit={onSubmit}>
          <div className="flex-1 overflow-hidden px-6 pb-6 pt-4">
            <div className="flex h-full flex-col space-y-6">
              {showScope ? (
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <label className="text-sm font-medium text-foreground">{scopeLabel}</label>
                    {isEdit ? (
                      <Badge variant="outline" className="text-sm">
                        {scopeOptions.find((option) => option.value === scopeValue)?.label ?? scopeValue}
                      </Badge>
                    ) : (
                      <Select value={scopeValue} onValueChange={(value) => onScopeChange(value as TScope)}>
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

                  <DocumentFileNameField
                    value={fileName}
                    label={fileNameLabel}
                    placeholder={fileNamePlaceholder}
                    helper={fileNameHelper}
                    error={fileNameError}
                    onChange={onFileNameChange}
                  />
                </div>
              ) : (
                <DocumentFileNameField
                  value={fileName}
                  label={fileNameLabel}
                  placeholder={fileNamePlaceholder}
                  helper={fileNameHelper}
                  error={fileNameError}
                  onChange={onFileNameChange}
                />
              )}

              {extraFields ? (
                <div className="grid grid-cols-2 gap-4">
                  {extraFields}
                </div>
              ) : null}

              <div className="flex flex-1 flex-col space-y-2">
                <label className="text-sm font-medium text-foreground">{contentLabel}</label>
                <div className="flex-1 overflow-hidden rounded-lg border">
                  <MarkdownEditor
                    value={content}
                    onChange={(value) => onContentChange(value ?? '')}
                    className="h-full"
                    footerExtras={contentFooter}
                  />
                </div>
                {contentError ? <p className="mt-2 text-xs text-destructive">{contentError}</p> : null}
                {contentHelper ? <p className="text-xs text-muted-foreground">{contentHelper}</p> : null}
              </div>
            </div>
          </div>

          <DialogFooter className="flex-shrink-0 gap-2 px-6 pb-6">
            <Button type="button" variant={cancelVariant} onClick={onClose} disabled={submitting}>
              {cancelLabel}
            </Button>
            <Button type="submit" disabled={submitting}>
              {submitLabel}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

interface DocumentFileNameFieldProps {
  value: string;
  label: string;
  placeholder: string;
  helper?: string;
  error?: string;
  onChange: (value: string) => void;
}

const DocumentFileNameField: React.FC<DocumentFileNameFieldProps> = ({
  value,
  label,
  placeholder,
  helper,
  error,
  onChange,
}) => (
  <div className="space-y-2">
    <label className="text-sm font-medium text-foreground">{label}</label>
    <Input value={value} onChange={(event) => onChange(event.target.value)} placeholder={placeholder} />
    {error ? <p className="text-xs text-destructive">{error}</p> : null}
    {helper ? <p className="text-xs text-muted-foreground">{helper}</p> : null}
  </div>
);

export default DocumentEditorDialogCore;
