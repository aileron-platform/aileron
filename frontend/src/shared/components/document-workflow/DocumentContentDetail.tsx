import React from 'react';
import { Check, Edit3, RotateCcw, X } from 'lucide-react';
import { MarkdownContent } from '@/shared/components/markdown/MarkdownContent';
import { MarkdownEditor } from '@/shared/components/markdown/MarkdownEditor';
import { Button } from '@/shared/components/ui/button';
import { CodeTextEditor } from '@/shared/components/file-workbench/viewer-entry';
import { useI18n } from '@/shared/hooks/useI18n';

export type DocumentContentFormat = 'markdown' | 'toml' | 'plain';

export interface DocumentContentMetadataItem {
  label: string;
  value?: React.ReactNode;
}

export interface DocumentContentDetailProps {
  title: string;
  content: string;
  format: DocumentContentFormat;
  metadata: DocumentContentMetadataItem[];
  initialMode?: 'preview' | 'edit';
  showHeader?: boolean;
  headerLeading?: React.ReactNode;
  headerActions?: React.ReactNode;
  emptyPreview?: React.ReactNode;
  onSave(content: string): void | Promise<void>;
  onDirtyChange?(dirty: boolean): void;
  onModeChange?(mode: 'preview' | 'edit', saving: boolean): void;
  readOnly?: boolean;
}

export interface DocumentContentDetailHandle {
  edit(): void;
  cancel(): void;
  save(): Promise<void>;
}

export const DocumentContentDetail = React.forwardRef<DocumentContentDetailHandle, DocumentContentDetailProps>(({
  title,
  content,
  format,
  metadata,
  initialMode = 'preview',
  showHeader = true,
  headerLeading,
  headerActions,
  emptyPreview,
  onSave,
  onDirtyChange,
  onModeChange,
  readOnly = false,
}, ref) => {
  const { t } = useI18n();
  const [mode, setMode] = React.useState<'preview' | 'edit'>(initialMode);
  const [draft, setDraft] = React.useState(content);
  const [saving, setSaving] = React.useState(false);

  React.useEffect(() => {
    setDraft(content);
    onDirtyChange?.(false);
  }, [content, onDirtyChange]);

  React.useEffect(() => {
    setMode(initialMode);
  }, [initialMode]);

  React.useEffect(() => {
    onModeChange?.(mode, saving);
  }, [mode, onModeChange, saving]);

  const updateDraft = (value: string) => {
    setDraft(value);
    onDirtyChange?.(value !== content);
  };

  const handleCancel = React.useCallback(() => {
    setDraft(content);
    setMode('preview');
    onDirtyChange?.(false);
  }, [content, onDirtyChange]);

  const handleSave = React.useCallback(async () => {
    if (readOnly) {
      return;
    }
    setSaving(true);
    try {
      await onSave(draft);
      setMode('preview');
      onDirtyChange?.(false);
    } finally {
      setSaving(false);
    }
  }, [draft, onDirtyChange, onSave, readOnly]);

  React.useImperativeHandle(ref, () => ({
    edit: () => {
      if (!readOnly) {
        setMode('edit');
      }
    },
    cancel: handleCancel,
    save: handleSave,
  }), [handleCancel, handleSave, readOnly]);

  return (
    <div className="flex h-full min-h-0 flex-col bg-background">
      {showHeader ? (
        <div className="flex flex-shrink-0 items-start justify-between gap-3 border-b border-border px-4 py-3">
          <div className="flex min-w-0 items-start gap-2">
            {headerLeading ? <div className="mt-0.5 shrink-0">{headerLeading}</div> : null}
            <div className="min-w-0 space-y-1">
              <h3 className="truncate text-sm font-semibold text-foreground">{title}</h3>
              {metadata.length > 0 ? (
                <dl className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
                  {metadata.map((item) => (
                    <div key={item.label} className="flex min-w-0 items-center gap-1">
                      <dt className="font-medium">{item.label}</dt>
                      <dd className="truncate">{item.value}</dd>
                    </div>
                  ))}
                </dl>
              ) : null}
            </div>
          </div>
          <div className="flex flex-shrink-0 items-center gap-2">
            {mode === 'edit' ? (
              <>
                <Button type="button" size="sm" variant="ghost" onClick={handleCancel} disabled={saving}>
                  <X className="mr-1.5 h-3.5 w-3.5" />
                  {t('shared.documentWorkflow.detail.actions.cancel')}
                </Button>
                <Button type="button" size="sm" onClick={handleSave} disabled={saving || readOnly}>
                  {saving ? (
                    <RotateCcw className="mr-1.5 h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <Check className="mr-1.5 h-3.5 w-3.5" />
                  )}
                  {t('shared.documentWorkflow.detail.actions.save')}
                </Button>
              </>
            ) : (
              !readOnly ? (
              <Button type="button" size="sm" variant="outline" onClick={() => setMode('edit')}>
                <Edit3 className="mr-1.5 h-3.5 w-3.5" />
                {t('shared.documentWorkflow.detail.actions.edit')}
              </Button>
              ) : null
            )}
            {mode === 'preview' ? headerActions : null}
          </div>
        </div>
      ) : null}

      <div className="min-h-0 flex-1 overflow-hidden">
        {mode === 'edit' ? (
          format === 'markdown' ? (
            <MarkdownEditor
              value={draft}
              onChange={(value) => updateDraft(value ?? '')}
              className="h-full rounded-none border-0"
              readOnly={readOnly}
            />
          ) : (
            <CodeTextEditor
              fileName={title}
              content={draft}
              onContentChange={updateDraft}
              readOnly={readOnly}
            />
          )
        ) : (
          <div className="h-full overflow-y-auto p-4">
            {format === 'markdown' ? (
              content.trim() || !emptyPreview
                ? <MarkdownContent content={content} />
                : emptyPreview
            ) : (
              <pre className="min-h-full overflow-auto rounded-md border border-border bg-muted/30 p-4 font-mono text-xs leading-5 text-foreground">
                {content}
              </pre>
            )}
          </div>
        )}
      </div>
    </div>
  );
});

DocumentContentDetail.displayName = 'DocumentContentDetail';
