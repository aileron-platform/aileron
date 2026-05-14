import { DialogHeading } from '@/shared/components/ui/dialog-heading';
import React from 'react';
import type { LucideIcon } from 'lucide-react';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader } from '@/shared/components/ui/dialog';
import { Input } from '@/shared/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/shared/components/ui/select';
import { MarkdownEditor } from '@/shared/components/markdown/MarkdownEditor';
import { cn } from '@/shared/utils/cn';

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
  contentPlaceholder?: string;
  contentHelper?: string;
  contentError?: string;
  contentFooter: React.ReactNode;
  editorMode?: 'markdown' | 'plain';
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

export const ensureDocumentExtension = (fileName: string, extension: '.md' | '.toml'): string => {
  const trimmed = fileName.trim();
  return trimmed.toLowerCase().endsWith(extension) ? trimmed : `${trimmed}${extension}`;
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
  contentPlaceholder,
  contentHelper,
  contentError,
  contentFooter,
  editorMode = 'markdown',
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
          <DialogHeading icon={Icon}>
            {title}
          </DialogHeading>
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
                  {editorMode === 'markdown' ? (
                    <MarkdownEditor
                      value={content}
                      onChange={(value) => onContentChange(value ?? '')}
                      placeholder={contentPlaceholder}
                      className="h-full"
                      footerExtras={contentFooter}
                    />
                  ) : (
                    <div className="flex h-full flex-col bg-background">
                      <textarea
                        value={content}
                        onChange={(event) => onContentChange(event.target.value)}
                        placeholder={contentPlaceholder}
                        className={cn(
                          'h-full w-full flex-1 resize-none border-0 bg-background p-6 font-mono text-sm text-foreground focus:outline-none',
                        )}
                      />
                      <div className="border-t border-border bg-muted/40 px-4 py-2 text-xs text-muted-foreground">
                        <div className="flex items-center justify-end gap-3">{contentFooter}</div>
                      </div>
                    </div>
                  )}
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
