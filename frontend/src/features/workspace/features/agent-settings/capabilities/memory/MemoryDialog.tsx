import { DialogHeading } from '@/shared/components/ui/dialog-heading';
import React, { useEffect, useMemo, useState } from 'react';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader } from '@/shared/components/ui/dialog';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { MarkdownEditor } from '@/shared/components/markdown/MarkdownEditor';
import { useI18n } from '@/shared/hooks/useI18n';
import type { AgentDocument } from '../../model/documents';
import type { DocumentDialogProps } from '@/shared/components/document-resource';
import { NotebookPen } from 'lucide-react';

const formatSize = (content: string) => {
  if (!content) return '1KB';
  const kiloBytes = Math.max(1, Math.ceil(content.length / 1024));
  return `${kiloBytes}KB`;
};

const ensureMarkdownExtension = (fileName: string): string => {
  const trimmed = fileName.trim();
  return trimmed.toLowerCase().endsWith('.md') ? trimmed : `${trimmed}.md`;
};

const MemoryDialog: React.FC<DocumentDialogProps> = ({
  open,
  initialValue,
  onClose,
  onSubmit,
  submitDisabled = false,
}) => {
  const { t } = useI18n();
  const [fileName, setFileName] = useState('');
  const [content, setContent] = useState('');
  const [errors, setErrors] = useState<{ fileName?: string; content?: string }>({});
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!open) return;
    setFileName((initialValue?.metadata?.fileName as string | undefined) ?? '');
    setContent(initialValue?.content ?? '');
    setErrors({});
    setSubmitting(false);
  }, [open, initialValue]);

  const estimatedSize = useMemo(() => formatSize(content), [content]);

  const validate = () => {
    const nextErrors: { content?: string } = {};
    if (!content.trim()) {
      nextErrors.content = t('workspace.claudeCode.memory.dialog.validation.content');
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
      const normalizedFileName = ensureMarkdownExtension(fileName);
      const document: AgentDocument = {
        id: `user:${normalizedFileName}`,
        title: normalizedFileName.replace(/\.md$/i, ''),
        description: '',
        content,
        scope: 'user',
        size: formatSize(content),
        metadata: {
          fileName: normalizedFileName,
        },
      };
      await onSubmit(document);
      onClose();
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(nextOpen) => !nextOpen && onClose()}>
      <DialogContent className="max-w-4xl">
        <form className="space-y-4" onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogHeading icon={NotebookPen}>
              {t('workspace.claudeCode.memory.dialog.title.edit')}
            </DialogHeading>
            <DialogDescription>
              {t('workspace.claudeCode.memory.dialog.description.edit')}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-2">
            <label className="text-sm font-medium">
              {t('workspace.claudeCode.memory.dialog.fields.fileName.label')}
            </label>
            <Input
              value={fileName}
              disabled
            />
            <p className="text-xs text-muted-foreground">
              {t('workspace.claudeCode.memory.dialog.fields.fileName.helper')}
            </p>
            {errors.fileName && <p className="text-xs text-destructive">{errors.fileName}</p>}
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between gap-2">
              <label className="text-sm font-medium">
                {t('workspace.claudeCode.memory.dialog.fields.content.label')}
              </label>
              <span className="text-xs text-muted-foreground">
                {t('workspace.claudeCode.memory.dialog.fields.content.estimatedSize', { size: estimatedSize })}
              </span>
            </div>
            <MarkdownEditor
              value={content}
              onChange={setContent}
              className="h-[420px]"
              readOnly={submitting || submitDisabled}
            />
            {errors.content && <p className="text-xs text-destructive">{errors.content}</p>}
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose} disabled={submitting}>
              {t('workspace.claudeCode.memory.dialog.actions.cancel')}
            </Button>
            <Button type="submit" disabled={submitting || submitDisabled}>
              {t('workspace.claudeCode.memory.dialog.actions.save')}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
};

export default MemoryDialog;
