import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { AlertCircle, Download, Edit3, Loader2, X } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import { useI18n } from '@/shared/hooks/useI18n';
import { cn } from '@/shared/utils/cn';
import { createLogger } from '@/shared/services/logger';
import { CodeTextEditor } from './CodeTextEditor';
import { useFileViewerWorkbench } from './FileViewerWorkbenchContext';
import type { FileViewerWorkbenchAdapter } from './types';

const logger = createLogger('SharedDrawioViewer');

interface SharedDrawioViewerProps {
  filePath: string;
  fileName: string;
  content: string;
  originalContent: string;
  readOnly: boolean;
  adapter: FileViewerWorkbenchAdapter;
  canPreview?: boolean;
  className?: string;
  i18nBase?: string;
  onContentChange: (content: string) => void;
  onModifiedChange: (isModified: boolean) => void;
}

interface DrawioMessage {
  event: 'init' | 'save' | 'export' | 'exit' | 'autosave';
  xml?: string;
  data?: string;
  exit?: boolean;
}

type DrawioFallbackReason = 'DISABLED' | 'UNREACHABLE' | null;
type DrawioViewerMode = 'view' | 'edit';

const MAX_RETRIES = 3;
const RETRY_DELAY_MS = 1000;

const isDrawioUnavailable = (error: unknown): error is { status: number; errorCode?: string; reason?: string } => (
  typeof error === 'object'
  && error !== null
  && 'status' in error
  && 'errorCode' in error
  && (error as { status?: unknown; errorCode?: unknown }).status === 503
  && (error as { errorCode?: unknown }).errorCode === 'DRAWIO_UNAVAILABLE'
);

export const SharedDrawioViewer: React.FC<SharedDrawioViewerProps> = ({
  filePath,
  fileName,
  content,
  originalContent,
  readOnly,
  adapter,
  canPreview = true,
  className,
  i18nBase = 'shared.fileViewer.drawio',
  onContentChange,
  onModifiedChange,
}) => {
  const { t } = useI18n();
  const { registerFormatActions } = useFileViewerWorkbench();
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const latestContentRef = useRef(content);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const [viewerUrl, setViewerUrl] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  const [retryCount, setRetryCount] = useState(0);
  const [fallbackReason, setFallbackReason] = useState<DrawioFallbackReason | undefined>(undefined);
  const [reloadToken, setReloadToken] = useState(0);
  const [viewerMode, setViewerMode] = useState<DrawioViewerMode>('view');
  const hasContent = content.trim().length > 0;
  const hasRuntimePreview = Boolean(adapter.getDrawioViewerUrl) && canPreview;

  useEffect(() => {
    latestContentRef.current = content;
  }, [content]);

  useEffect(() => {
    if (!hasRuntimePreview || !hasContent) {
      setViewerUrl('');
      setError('');
      setIsLoading(false);
      setFallbackReason(undefined);
      return;
    }

    let isMounted = true;

    const fetchDrawioUrl = async () => {
      setIsLoading(true);
      setError('');
      setFallbackReason(undefined);

      try {
        const url = await adapter.getDrawioViewerUrl?.(filePath, viewerMode);
        if (isMounted) {
          setViewerUrl(url ?? '');
          setRetryCount(0);
        }
      } catch (loadError) {
        logger.error('Failed to load Draw.io URL', { error: loadError });
        if (!isMounted) return;

        if (isDrawioUnavailable(loadError)) {
          const reason = loadError.reason === 'DISABLED' || loadError.reason === 'UNREACHABLE'
            ? loadError.reason
            : null;
          setFallbackReason(reason);
          setViewerUrl('');
          setRetryCount(0);
          return;
        }

        const message = loadError instanceof Error ? loadError.message : 'Unknown error';
        if (retryCount < MAX_RETRIES) {
          logger.debug('Retrying Draw.io URL load', { retryCount: retryCount + 1, maxRetries: MAX_RETRIES });
          window.setTimeout(() => {
            if (isMounted) {
              setRetryCount((current) => current + 1);
            }
          }, RETRY_DELAY_MS * (retryCount + 1));
        } else {
          setError(message);
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    };

    void fetchDrawioUrl();

    return () => {
      isMounted = false;
    };
  }, [adapter, filePath, hasContent, hasRuntimePreview, reloadToken, retryCount, viewerMode]);

  const switchViewerMode = useCallback((mode: DrawioViewerMode) => {
    setViewerMode(mode);
    setError('');
    setViewerUrl('');
    setRetryCount(0);
    setReloadToken((current) => current + 1);
  }, []);

  const handleSave = useCallback(async (xml: string): Promise<boolean> => {
    if (!adapter.saveDrawio || isSaving || readOnly) {
      return false;
    }

    setIsSaving(true);

    try {
      await adapter.saveDrawio(filePath, xml);
      onContentChange(xml);
      onModifiedChange(false);
      iframeRef.current?.contentWindow?.postMessage(
        JSON.stringify({
          action: 'status',
          messageKey: 'allChangesSaved',
          modified: false,
        }),
        '*',
      );
      return true;
    } catch (saveError) {
      logger.error('Failed to save Draw.io file', { error: saveError });
      if (isDrawioUnavailable(saveError)) {
        const reason = saveError.reason === 'DISABLED' || saveError.reason === 'UNREACHABLE'
          ? saveError.reason
          : null;
        setFallbackReason(reason);
        return false;
      }
      setError(saveError instanceof Error ? saveError.message : 'Save failed');
      iframeRef.current?.contentWindow?.postMessage(
        JSON.stringify({
          action: 'status',
          messageKey: 'errorSavingFile',
          modified: true,
        }),
        '*',
      );
      return false;
    } finally {
      setIsSaving(false);
    }
  }, [adapter, filePath, isSaving, onContentChange, onModifiedChange, readOnly]);

  const handleMessage = useCallback((event: MessageEvent) => {
    if (!iframeRef.current || event.source !== iframeRef.current.contentWindow) {
      return;
    }

    try {
      const message: DrawioMessage = typeof event.data === 'string'
        ? JSON.parse(event.data)
        : event.data;

      logger.debug('Draw.io message received', { event: message.event });

      if (message.event === 'init') {
        const loadMessage = {
          action: 'load',
          xml: latestContentRef.current,
          autosave: viewerMode === 'edit' ? 1 : 0,
          saveAndExit: viewerMode === 'edit' ? '1' : undefined,
          modified: viewerMode === 'edit' ? 'unsavedChanges' : undefined,
          title: fileName,
        };

        iframeRef.current.contentWindow?.postMessage(JSON.stringify(loadMessage), '*');
      }

      if (message.event === 'save' && message.xml) {
        void handleSave(message.xml).then((saved) => {
          if (saved && message.exit) {
            switchViewerMode('view');
          }
        });
      }

      if (message.event === 'autosave' && message.xml) {
        void handleSave(message.xml);
      }

      if (message.event === 'exit') {
        setViewerMode('view');
        setViewerUrl('');
        setReloadToken((current) => current + 1);
      }
    } catch (messageError) {
      logger.error('Failed to parse Draw.io message', { error: messageError });
    }
  }, [fileName, handleSave, switchViewerMode, viewerMode]);

  useEffect(() => {
    window.addEventListener('message', handleMessage);
    return () => window.removeEventListener('message', handleMessage);
  }, [handleMessage]);

  const handleDownload = useCallback(() => {
    if (!content) return;
    const blob = new Blob([content], { type: 'application/xml' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = fileName || 'diagram.drawio';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  }, [content, fileName]);

  const canEditInDrawio = hasRuntimePreview && !readOnly && fallbackReason === undefined;
  const toolbarActions = useMemo(() => (
    <>
      {canEditInDrawio && (
        <Button
          variant="ghost"
          size="sm"
          onClick={() => switchViewerMode(viewerMode === 'edit' ? 'view' : 'edit')}
          disabled={!content || isLoading || isSaving}
          title={viewerMode === 'edit' ? t(`${i18nBase}.cancel`) : t(`${i18nBase}.edit`)}
          aria-label={viewerMode === 'edit' ? t(`${i18nBase}.cancel`) : t(`${i18nBase}.edit`)}
        >
          {viewerMode === 'edit' ? <X className="h-4 w-4" /> : <Edit3 className="h-4 w-4" />}
        </Button>
      )}
      <Button
        variant="ghost"
        size="sm"
        onClick={handleDownload}
        disabled={!content}
        title={t(`${i18nBase}.download`)}
        aria-label={t(`${i18nBase}.download`)}
      >
        <Download className="h-4 w-4" />
      </Button>
    </>
  ), [canEditInDrawio, content, handleDownload, i18nBase, isLoading, isSaving, switchViewerMode, t, viewerMode]);

  useEffect(() => {
    registerFormatActions(toolbarActions);
    return () => registerFormatActions(null);
  }, [registerFormatActions, toolbarActions]);

  const fallbackDescriptionKey = fallbackReason === 'DISABLED'
    ? `${i18nBase}.serviceUnavailable.disabled`
    : fallbackReason === 'UNREACHABLE'
      ? `${i18nBase}.serviceUnavailable.unreachable`
      : `${i18nBase}.serviceUnavailable.description`;

  const shouldShowCodeFallback = !hasRuntimePreview || fallbackReason !== undefined;

  return (
    <div id="drawio-viewer-container" className={cn('flex h-full flex-col bg-background', className)}>
      <div className="relative flex-1 overflow-hidden">
        {shouldShowCodeFallback ? (
          <div className="flex h-full flex-col overflow-hidden bg-background">
            <div className="border-b border-border bg-muted/40 px-4 py-3">
              <div className="flex items-start justify-between gap-3">
                <div className="flex min-w-0 gap-3">
                  <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
                  <div className="min-w-0">
                    <h3 className="text-sm font-medium">
                      {fallbackReason !== undefined
                        ? t(`${i18nBase}.serviceUnavailable.title`)
                        : t(`${i18nBase}.fallbackTitle`)}
                    </h3>
                    <p className="mt-1 text-sm text-muted-foreground">
                      {fallbackReason !== undefined ? t(fallbackDescriptionKey) : t(`${i18nBase}.fallback`)}
                    </p>
                  </div>
                </div>
                {hasRuntimePreview && fallbackReason !== undefined && (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      setFallbackReason(undefined);
                      setRetryCount(0);
                      setReloadToken((current) => current + 1);
                    }}
                  >
                    {t(`${i18nBase}.serviceUnavailable.retry`)}
                  </Button>
                )}
              </div>
            </div>
            <div className="min-h-0 flex-1">
              {fallbackReason !== undefined ? (
                <pre className="h-full overflow-auto whitespace-pre-wrap break-words p-4 font-mono text-sm text-foreground">
                  {content}
                </pre>
              ) : (
                <CodeTextEditor
                  fileName={fileName}
                  content={content}
                  originalContent={originalContent}
                  readOnly={readOnly}
                  onContentChange={onContentChange}
                  onModifiedChange={onModifiedChange}
                />
              )}
            </div>
          </div>
        ) : error ? (
          <div className="absolute inset-0 z-10 flex items-center justify-center bg-background/95">
            <div className="flex max-w-md flex-col items-center gap-4 p-6 text-center">
              <AlertCircle className="h-12 w-12 text-destructive" />
              <div>
                <h3 className="mb-2 text-lg font-semibold">{t(`${i18nBase}.error.title`)}</h3>
                <p className="text-sm text-muted-foreground">{error}</p>
              </div>
              <Button
                variant="outline"
                onClick={() => {
                  setError('');
                  setViewerUrl('');
                  setRetryCount(0);
                  setReloadToken((current) => current + 1);
                }}
              >
                {t(`${i18nBase}.retry`)}
              </Button>
              {retryCount > 0 && retryCount < MAX_RETRIES && (
                <p className="text-xs text-muted-foreground">
                  {t(`${i18nBase}.retrying`, { count: retryCount, max: MAX_RETRIES })}
                </p>
              )}
            </div>
          </div>
        ) : isLoading ? (
          <div className="flex h-full items-center justify-center">
            <div className="flex flex-col items-center gap-3">
              <Loader2 className="h-8 w-8 animate-spin text-primary" />
              <p className="text-sm text-muted-foreground">{t(`${i18nBase}.loading`)}</p>
            </div>
          </div>
        ) : viewerUrl ? (
          <iframe
            ref={iframeRef}
            title={t(`${i18nBase}.title`)}
            src={viewerUrl}
            className="h-full w-full border-0"
            allow="clipboard-read; clipboard-write"
            sandbox="allow-same-origin allow-scripts allow-forms allow-modals allow-popups"
          />
        ) : (
          <div className="flex h-full items-center justify-center">
            <p className="text-sm text-muted-foreground">{t(`${i18nBase}.empty`)}</p>
          </div>
        )}
      </div>
    </div>
  );
};
