import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Check, Copy, Download, Edit3, Eye, FileText, RefreshCw, Save, X, ZoomIn, ZoomOut } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import { MarkdownContent } from '@/shared/components/markdown/MarkdownContent';
import { classifyMarkdownHref, resolveWorkspaceMarkdownPath } from '@/shared/components/markdown/markdownLinkUtils';
import { useI18n } from '@/shared/hooks/useI18n';
import { cn } from '@/shared/utils/cn';
import { useFileViewerWorkbench } from './FileViewerWorkbenchContext';
import { EmptyState } from '@/shared/components/ui/empty-state';

interface MarkdownViewerProps {
  content: string;
  fileName: string;
  filePath?: string;
  readOnly?: boolean;
  onReload?: () => Promise<string>;
  onContentChange?: (content: string) => void;
  onSave?: (content: string) => Promise<void> | void;
  onOpenPath?: (path: string) => void;
  toolbarOwnerKey?: string;
}

const MARKDOWN_TOOLBAR_BUTTON_CLASS = '!h-7 !px-2';
const MARKDOWN_TOOLBAR_ICON_CLASS = 'h-3.5 w-3.5';

export const MarkdownViewer: React.FC<MarkdownViewerProps> = ({
  content,
  fileName,
  filePath,
  readOnly = false,
  onReload,
  onContentChange,
  onSave,
  onOpenPath,
  toolbarOwnerKey,
}) => {
  const { t, state: i18nState } = useI18n();
  const { registerFormatActions } = useFileViewerWorkbench();
  const [zoom, setZoom] = useState(1);
  const [copied, setCopied] = useState(false);
  const [isEditMode, setIsEditMode] = useState(false);
  const [editContent, setEditContent] = useState(content);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const canEdit = !readOnly && Boolean(onContentChange);

  useEffect(() => {
    setEditContent(content);
  }, [content]);

  const previewContent = useMemo(() => content, [content]);

  const handleZoomOut = useCallback(() => setZoom((current) => Math.max(0.5, current - 0.1)), []);
  const handleZoomIn = useCallback(() => setZoom((current) => Math.min(2, current + 0.1)), []);
  const handleResetZoom = useCallback(() => setZoom(1), []);

  const handleReload = useCallback(async () => {
    if (!onReload) return;
    setIsRefreshing(true);
    try {
      const nextContent = await onReload();
      onContentChange?.(nextContent);
    } finally {
      setIsRefreshing(false);
    }
  }, [onContentChange, onReload]);

  const handleCopy = useCallback(async () => {
    await navigator.clipboard?.writeText(content);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1200);
  }, [content]);

  const handleDownload = useCallback(() => {
    const blob = new Blob([content], { type: 'text/markdown;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = fileName;
    link.click();
    URL.revokeObjectURL(url);
  }, [content, fileName]);

  const handleSave = useCallback(async () => {
    onContentChange?.(editContent);
    if (onSave) {
      setIsSaving(true);
      try {
        await onSave(editContent);
      } finally {
        setIsSaving(false);
      }
    }
    setIsEditMode(false);
  }, [editContent, onContentChange, onSave]);

  const handleCancel = useCallback(() => {
    setEditContent(content);
    setIsEditMode(false);
  }, [content]);

  const handleMarkdownLinkClick = (href: string, event: React.MouseEvent<HTMLAnchorElement>) => {
    if (!filePath || !onOpenPath || classifyMarkdownHref(href) !== 'internal') {
      return;
    }

    const targetPath = resolveWorkspaceMarkdownPath(filePath, href);
    if (!targetPath) {
      return;
    }

    event.preventDefault();
    onOpenPath(targetPath);
  };

  const toolbarActions = useMemo(() => (
    <>
      {isEditMode ? (
        <>
          <Button
            variant="ghost"
            size="sm"
            className={MARKDOWN_TOOLBAR_BUTTON_CLASS}
            onClick={() => void handleSave()}
            disabled={isSaving}
            title={t('shared.fileViewer.markdown.save')}
            aria-label={t('shared.fileViewer.markdown.save')}
          >
            <Save className={MARKDOWN_TOOLBAR_ICON_CLASS} />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            className={MARKDOWN_TOOLBAR_BUTTON_CLASS}
            onClick={handleCancel}
            disabled={isSaving}
            title={t('shared.fileViewer.markdown.cancel')}
            aria-label={t('shared.fileViewer.markdown.cancel')}
          >
            <X className={MARKDOWN_TOOLBAR_ICON_CLASS} />
          </Button>
          <div className="mx-1 h-4 w-px bg-border" />
          <Button
            variant="ghost"
            size="sm"
            className={MARKDOWN_TOOLBAR_BUTTON_CLASS}
            onClick={() => setIsEditMode(false)}
            title={t('shared.fileViewer.markdown.switchToPreview')}
            aria-label={t('shared.fileViewer.markdown.switchToPreview')}
          >
            <Eye className={MARKDOWN_TOOLBAR_ICON_CLASS} />
          </Button>
        </>
      ) : (
        <>
          <Button
            variant="ghost"
            size="sm"
            className={MARKDOWN_TOOLBAR_BUTTON_CLASS}
            onClick={handleZoomOut}
            disabled={zoom <= 0.5}
            title={t('shared.fileViewer.markdown.zoomOut')}
            aria-label={t('shared.fileViewer.markdown.zoomOut')}
          >
            <ZoomOut className={MARKDOWN_TOOLBAR_ICON_CLASS} />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            className={MARKDOWN_TOOLBAR_BUTTON_CLASS}
            onClick={handleResetZoom}
            title={t('shared.fileViewer.markdown.resetZoom')}
            aria-label={t('shared.fileViewer.markdown.resetZoom')}
          >
            <span className="min-w-[3rem] text-center text-xs">{Math.round(zoom * 100)}%</span>
          </Button>
          <Button
            variant="ghost"
            size="sm"
            className={MARKDOWN_TOOLBAR_BUTTON_CLASS}
            onClick={handleZoomIn}
            disabled={zoom >= 2}
            title={t('shared.fileViewer.markdown.zoomIn')}
            aria-label={t('shared.fileViewer.markdown.zoomIn')}
          >
            <ZoomIn className={MARKDOWN_TOOLBAR_ICON_CLASS} />
          </Button>
          <div className="mx-1 h-4 w-px bg-border" />
          <Button
            variant="ghost"
            size="sm"
            className={MARKDOWN_TOOLBAR_BUTTON_CLASS}
            onClick={() => void handleReload()}
            disabled={!onReload || isRefreshing}
            title={isRefreshing ? t('shared.fileViewer.markdown.refreshing') : t('shared.fileViewer.markdown.refresh')}
            aria-label={isRefreshing ? t('shared.fileViewer.markdown.refreshing') : t('shared.fileViewer.markdown.refresh')}
          >
            <RefreshCw className={cn(MARKDOWN_TOOLBAR_ICON_CLASS, isRefreshing && 'animate-spin')} />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            className={MARKDOWN_TOOLBAR_BUTTON_CLASS}
            onClick={() => void handleCopy()}
            disabled={!content}
            title={t('shared.fileViewer.markdown.copy')}
            aria-label={t('shared.fileViewer.markdown.copy')}
          >
            {copied ? <Check className={`${MARKDOWN_TOOLBAR_ICON_CLASS} text-green-500`} /> : <Copy className={MARKDOWN_TOOLBAR_ICON_CLASS} />}
          </Button>
          <Button
            variant="ghost"
            size="sm"
            className={MARKDOWN_TOOLBAR_BUTTON_CLASS}
            onClick={handleDownload}
            disabled={!content}
            title={t('shared.fileViewer.markdown.download')}
            aria-label={t('shared.fileViewer.markdown.download')}
          >
            <Download className={MARKDOWN_TOOLBAR_ICON_CLASS} />
          </Button>
          {canEdit && (
            <>
              <div className="mx-1 h-4 w-px bg-border" />
              <Button
                variant="ghost"
                size="sm"
                className={MARKDOWN_TOOLBAR_BUTTON_CLASS}
                onClick={() => setIsEditMode(true)}
                title={t('shared.fileViewer.markdown.edit')}
                aria-label={t('shared.fileViewer.markdown.edit')}
              >
                <Edit3 className={MARKDOWN_TOOLBAR_ICON_CLASS} />
              </Button>
            </>
          )}
        </>
      )}
    </>
  ), [
    canEdit,
    content,
    copied,
    handleCancel,
    handleCopy,
    handleDownload,
    handleReload,
    handleResetZoom,
    handleSave,
    handleZoomIn,
    handleZoomOut,
    isEditMode,
    isRefreshing,
    isSaving,
    onReload,
    t,
    zoom,
  ]);
  const toolbarActionsRef = useRef(toolbarActions);
  toolbarActionsRef.current = toolbarActions;

  const toolbarRegistrationKey = useMemo(
    () => [
      'markdown',
      filePath ?? fileName,
      i18nState.currentLanguage,
      content,
      editContent,
      isEditMode,
      zoom,
      copied,
      isRefreshing,
      isSaving,
      canEdit,
      Boolean(onReload),
      readOnly,
    ].join('|'),
    [canEdit, content, copied, editContent, fileName, filePath, i18nState.currentLanguage, isEditMode, isRefreshing, isSaving, onReload, readOnly, zoom],
  );
  const resolvedToolbarOwnerKey = toolbarOwnerKey ?? `markdown:${filePath ?? fileName}`;

  useEffect(() => {
    registerFormatActions(toolbarActionsRef.current, toolbarRegistrationKey, resolvedToolbarOwnerKey);
    return () => registerFormatActions(null, toolbarRegistrationKey, resolvedToolbarOwnerKey);
  }, [registerFormatActions, resolvedToolbarOwnerKey, toolbarRegistrationKey]);

  return (
    <div id="markdown-preview-container" className="flex h-full flex-col bg-background">
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
            <MarkdownContent content={previewContent} onLinkClick={handleMarkdownLinkClick} />
          </div>
        ) : (
          <EmptyState
            icon={FileText}
            title={t('shared.fileViewer.markdown.empty')}
          />
        )}
      </div>
    </div>
  );
};
