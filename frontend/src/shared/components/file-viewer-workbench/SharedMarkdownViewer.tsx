import React, { useEffect, useMemo, useState, type ReactNode } from 'react';
import { Check, Copy, Download, Edit3, Eye, FileText, RefreshCw, Save, X, ZoomIn, ZoomOut } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import { MarkdownContent } from '@/shared/components/markdown/MarkdownContent';
import { useI18n } from '@/shared/hooks/useI18n';
import { cn } from '@/shared/utils/cn';

interface SharedMarkdownViewerProps {
  content: string;
  fileName: string;
  readOnly?: boolean;
  isFocusMode?: boolean;
  renderFocusToolbar?: (params: {
    actions: ReactNode;
    title: string;
    subtitle: string;
  }) => ReactNode;
  onReload?: () => Promise<string>;
  onContentChange?: (content: string) => void;
}

export const SharedMarkdownViewer: React.FC<SharedMarkdownViewerProps> = ({
  content,
  fileName,
  readOnly = false,
  isFocusMode = false,
  renderFocusToolbar,
  onReload,
  onContentChange,
}) => {
  const { t } = useI18n();
  const [zoom, setZoom] = useState(1);
  const [copied, setCopied] = useState(false);
  const [isEditMode, setIsEditMode] = useState(false);
  const [editContent, setEditContent] = useState(content);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const canEdit = !readOnly && Boolean(onContentChange);

  useEffect(() => {
    setEditContent(content);
  }, [content]);

  const previewContent = useMemo(() => content, [content]);

  const handleZoomOut = () => setZoom((current) => Math.max(0.5, current - 0.1));
  const handleZoomIn = () => setZoom((current) => Math.min(2, current + 0.1));
  const handleResetZoom = () => setZoom(1);

  const handleReload = async () => {
    if (!onReload) return;
    setIsRefreshing(true);
    try {
      const nextContent = await onReload();
      onContentChange?.(nextContent);
    } finally {
      setIsRefreshing(false);
    }
  };

  const handleCopy = async () => {
    await navigator.clipboard?.writeText(content);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1200);
  };

  const handleDownload = () => {
    const blob = new Blob([content], { type: 'text/markdown;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = fileName;
    link.click();
    URL.revokeObjectURL(url);
  };

  const handleSave = () => {
    onContentChange?.(editContent);
    setIsEditMode(false);
  };

  const handleCancel = () => {
    setEditContent(content);
    setIsEditMode(false);
  };

  const toolbarActions = (
    <>
      {isEditMode ? (
        <>
          <Button
            variant="ghost"
            size="sm"
            onClick={handleSave}
            title={t('shared.fileViewer.markdown.save')}
            aria-label={t('shared.fileViewer.markdown.save')}
          >
            <Save className="h-4 w-4" />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={handleCancel}
            title={t('shared.fileViewer.markdown.cancel')}
            aria-label={t('shared.fileViewer.markdown.cancel')}
          >
            <X className="h-4 w-4" />
          </Button>
          <div className="mx-1 h-4 w-px bg-border" />
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setIsEditMode(false)}
            title={t('shared.fileViewer.markdown.switchToPreview')}
            aria-label={t('shared.fileViewer.markdown.switchToPreview')}
          >
            <Eye className="h-4 w-4" />
          </Button>
        </>
      ) : (
        <>
          <Button
            variant="ghost"
            size="sm"
            onClick={handleZoomOut}
            disabled={zoom <= 0.5}
            title={t('shared.fileViewer.markdown.zoomOut')}
            aria-label={t('shared.fileViewer.markdown.zoomOut')}
          >
            <ZoomOut className="h-4 w-4" />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={handleResetZoom}
            title={t('shared.fileViewer.markdown.resetZoom')}
            aria-label={t('shared.fileViewer.markdown.resetZoom')}
          >
            <span className="min-w-[3rem] text-center text-xs">{Math.round(zoom * 100)}%</span>
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={handleZoomIn}
            disabled={zoom >= 2}
            title={t('shared.fileViewer.markdown.zoomIn')}
            aria-label={t('shared.fileViewer.markdown.zoomIn')}
          >
            <ZoomIn className="h-4 w-4" />
          </Button>
          <div className="mx-1 h-4 w-px bg-border" />
          <Button
            variant="ghost"
            size="sm"
            onClick={() => void handleReload()}
            disabled={!onReload || isRefreshing}
            title={isRefreshing ? t('shared.fileViewer.markdown.refreshing') : t('shared.fileViewer.markdown.refresh')}
            aria-label={isRefreshing ? t('shared.fileViewer.markdown.refreshing') : t('shared.fileViewer.markdown.refresh')}
          >
            <RefreshCw className={cn('h-4 w-4', isRefreshing && 'animate-spin')} />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => void handleCopy()}
            disabled={!content}
            title={t('shared.fileViewer.markdown.copy')}
            aria-label={t('shared.fileViewer.markdown.copy')}
          >
            {copied ? <Check className="h-4 w-4 text-green-500" /> : <Copy className="h-4 w-4" />}
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={handleDownload}
            disabled={!content}
            title={t('shared.fileViewer.markdown.download')}
            aria-label={t('shared.fileViewer.markdown.download')}
          >
            <Download className="h-4 w-4" />
          </Button>
          {canEdit && (
            <>
              <div className="mx-1 h-4 w-px bg-border" />
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setIsEditMode(true)}
                title={t('shared.fileViewer.markdown.edit')}
                aria-label={t('shared.fileViewer.markdown.edit')}
              >
                <Edit3 className="h-4 w-4" />
              </Button>
            </>
          )}
        </>
      )}
    </>
  );

  return (
    <div id="markdown-preview-container" className="flex h-full flex-col bg-background">
      {isFocusMode && renderFocusToolbar ? renderFocusToolbar({
        actions: toolbarActions,
        title: fileName,
        subtitle: t('shared.fileViewer.markdown.title'),
      }) : (
      <div className="h-10 flex-shrink-0 border-b border-border bg-card px-3 flex items-center justify-between">
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <FileText className="h-4 w-4" />
          <span>{t('shared.fileViewer.markdown.title')}</span>
        </div>

        <div className="flex items-center gap-1">{toolbarActions}</div>
      </div>
      )}

      <div className="min-h-0 flex-1 overflow-auto bg-background">
        {isEditMode ? (
          <textarea
            value={editContent}
            onChange={(event) => setEditContent(event.target.value)}
            className="h-full w-full resize-none bg-background p-6 font-mono text-sm text-foreground focus:outline-none"
            placeholder={t('shared.fileViewer.markdown.editPlaceholder')}
          />
        ) : previewContent.trim() ? (
          <div
            className="mx-auto max-w-none px-6 py-5"
            style={{
              transform: `scale(${zoom})`,
              transformOrigin: 'top center',
              transition: 'transform 0.2s ease-out',
            }}
          >
            <MarkdownContent content={previewContent} />
          </div>
        ) : (
          <div className="flex h-full items-center justify-center text-muted-foreground">
            <div className="text-center">
              <FileText className="mx-auto mb-4 h-12 w-12 opacity-50" />
              <p className="text-sm">{t('shared.fileViewer.markdown.empty')}</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
