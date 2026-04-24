import React, { useState, useEffect } from 'react';
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
import { MarkdownEditor } from '@/shared/components/composite/MarkdownEditor';
import type { CommandFormValue } from '../formTypes';
import { useI18n } from '@/shared/hooks/useI18n';

interface CommandDialogProps {
  open: boolean;
  mode: 'create' | 'edit';
  initialValue?: CommandFormValue | null;
  onClose: () => void;
  onSubmit: (command: CommandFormValue) => void;
}

interface FormState {
  namespace: string;
  name: string;
  content: string;
}

const buildInitialState = (initialValue?: CommandFormValue | null): FormState => {
  // 從檔案名稱解析 namespace 和 name
  const fileName = initialValue?.fileName ?? '';
  let namespace = '';
  let name = '';

  if (fileName) {
    const parts = fileName.replace('.md', '').split('/');
    if (parts.length > 1) {
      namespace = parts[0];
      name = parts.slice(1).join('/');
    } else {
      name = parts[0];
    }
  }

  return {
    namespace,
    name,
    content: initialValue?.content ?? '',
  };
};

const formatSize = (content: string) => {
  if (!content) {
    return '1KB';
  }
  const kiloBytes = Math.max(1, Math.ceil(content.length / 1024));
  return `${kiloBytes}KB`;
};

export const CommandDialog: React.FC<CommandDialogProps> = ({
  open,
  mode,
  initialValue,
  onClose,
  onSubmit,
}) => {
  const { t } = useI18n();
  const [formState, setFormState] = useState<FormState>(() => buildInitialState(initialValue));
  const [submitting, setSubmitting] = useState(false);
  const [errors, setErrors] = useState<{ name?: string; content?: string }>({});

  useEffect(() => {
    if (open) {
      setFormState(buildInitialState(initialValue));
      setErrors({});
      setSubmitting(false);
    }
  }, [open, initialValue]);

  const isEdit = mode === 'edit';

  const validate = () => {
    const nextErrors: { name?: string; content?: string } = {};
    if (!formState.name.trim()) {
      nextErrors.name = t('template.editor.commands.dialog.validation.nameRequired');
    }
    if (!formState.content.trim()) {
      nextErrors.content = t('template.editor.commands.dialog.validation.contentRequired');
    }
    setErrors(nextErrors);
    return Object.keys(nextErrors).length === 0;
  };

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    if (!validate()) {
      return;
    }
    setSubmitting(true);

    // 建立檔案名稱：如果有 namespace 就用 namespace/name.md，否則用 name.md
    const fileName = formState.namespace.trim()
      ? `${formState.namespace.trim()}/${formState.name.trim()}.md`
      : `${formState.name.trim()}.md`;

    const command: CommandFormValue = {
      localId: initialValue?.localId || `local-${Math.random().toString(36).slice(2, 10)}`,
      fileName,
      content: formState.content,
    };

    onSubmit(command);
    setSubmitting(false);
    onClose();
  };

  return (
    <Dialog open={open} onOpenChange={(next) => !submitting && (!next ? onClose() : null)}>
      <DialogContent className="flex h-[85vh] max-h-[85vh] w-full max-w-4xl flex-col p-0">
        <DialogHeader className="flex-shrink-0 px-6 pt-6">
          <DialogTitle>
            {isEdit
              ? t('template.editor.commands.dialog.title.edit')
              : t('template.editor.commands.dialog.title.create')}
          </DialogTitle>
          <DialogDescription>
            {isEdit
              ? t('template.editor.commands.dialog.description.edit')
              : t('template.editor.commands.dialog.description.create')}
          </DialogDescription>
        </DialogHeader>

        <form className="flex flex-1 flex-col overflow-hidden" onSubmit={handleSubmit}>
          <div className="flex flex-1 flex-col overflow-hidden px-6 pb-6 pt-4">
            {/* 命令名稱 - 必填 */}
            <div className="flex-shrink-0 space-y-2 mb-4">
              <label className="text-sm font-medium text-foreground">
                {t('template.editor.commands.dialog.fields.name.label')}
              </label>
              <Input
                value={formState.name}
                onChange={(event) =>
                  setFormState((prev) => ({ ...prev, name: event.target.value }))
                }
                placeholder={t('template.editor.commands.dialog.fields.name.placeholder')}
              />
              {errors.name && <p className="text-xs text-destructive">{errors.name}</p>}
              <p className="text-xs text-muted-foreground">
                {t('template.editor.commands.dialog.fields.name.helper')}
              </p>
            </div>

            {/* 命名空間 - 非必填 */}
            <div className="flex-shrink-0 space-y-2 mb-4">
              <label className="text-sm font-medium text-foreground">
                {t('template.editor.commands.dialog.fields.namespace.label')}
              </label>
              <Input
                value={formState.namespace}
                onChange={(event) =>
                  setFormState((prev) => ({ ...prev, namespace: event.target.value }))
                }
                placeholder={t('template.editor.commands.dialog.fields.namespace.placeholder')}
              />
              <p className="text-xs text-muted-foreground">
                {t('template.editor.commands.dialog.fields.namespace.helper')}
              </p>
            </div>

            {/* 指令內容 - 必填，Markdown 編輯器 */}
            <div className="flex flex-1 flex-col overflow-hidden">
              <label className="mb-2 text-sm font-medium text-foreground">
                {t('template.editor.commands.dialog.fields.content.label')}
              </label>
              <div className="flex-1 overflow-hidden rounded-lg border">
                <MarkdownEditor
                  value={formState.content}
                  onChange={(value) =>
                    setFormState((prev) => ({ ...prev, content: value ?? '' }))
                  }
                  className="h-full"
                  footerExtras={(
                    <span className="text-xs text-muted-foreground">
                      {t('template.editor.commands.dialog.fields.content.sizeHint', {
                        size: formatSize(formState.content)
                      })}
                    </span>
                  )}
                />
              </div>
              {errors.content && <p className="mt-2 text-xs text-destructive">{errors.content}</p>}
            </div>
          </div>

          <DialogFooter className="flex-shrink-0 gap-2 px-6 pb-6">
            <Button type="button" variant="ghost" onClick={onClose} disabled={submitting}>
              {t('common.cancel')}
            </Button>
            <Button type="submit" disabled={submitting}>
              {isEdit
                ? t('template.editor.commands.dialog.actions.save')
                : t('template.editor.commands.dialog.actions.create')}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
};

export default CommandDialog;