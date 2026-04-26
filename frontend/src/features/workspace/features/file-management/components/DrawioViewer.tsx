/**
 * Draw.io 圖表預覽組件（本地服務版本）
 * 使用本地 Draw.io 容器服務進行渲染和編輯
 */

import React, { useEffect, useRef, useState, useCallback } from 'react';
import { createLogger } from '@/shared/services/logger';

const logger = createLogger('DrawioViewer');
import { AlertCircle, Loader2, Download, Edit3, Image as ImageIcon, X } from 'lucide-react';
import { ApiClient, ApiError } from '@/shared/api/apiClient';
import { Button } from '@/shared/components/ui/button';
import { useI18n } from '@/shared/hooks/useI18n';
import { cn } from '@/shared/utils/cn';
import { FileFocusToolbar } from './FileFocusToolbar';

interface DrawioViewerProps {
  content: string;
  filePath: string;
  runtimeBaseUrl: string;
  className?: string;
  isFocusMode?: boolean;
  onExitFocusMode?: () => void;
  onSave?: (newContent: string) => void;
}

interface DrawioMessage {
  event: 'init' | 'save' | 'export' | 'exit' | 'autosave';
  xml?: string;
  data?: string;
  exit?: boolean;
}

const MAX_RETRIES = 3;
const RETRY_DELAY_MS = 1000;

type DrawioFallbackReason = 'DISABLED' | 'UNREACHABLE' | null;
type DrawioViewerMode = 'view' | 'edit';

const isDrawioUnavailable = (error: unknown): error is ApiError => {
  return error instanceof ApiError
    && error.status === 503
    && error.errorCode === 'DRAWIO_UNAVAILABLE';
};

export const DrawioViewer: React.FC<DrawioViewerProps> = ({
  content,
  filePath,
  runtimeBaseUrl,
  className,
  isFocusMode = false,
  onExitFocusMode,
  onSave
}) => {
  const { t } = useI18n();
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const latestContentRef = useRef(content);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string>('');
  const [drawioUrl, setDrawioUrl] = useState<string>('');
  const [isSaving, setIsSaving] = useState(false);
  const [retryCount, setRetryCount] = useState(0);
  const [fallbackReason, setFallbackReason] = useState<DrawioFallbackReason | undefined>(undefined);
  const [reloadToken, setReloadToken] = useState(0);
  const [viewerMode, setViewerMode] = useState<DrawioViewerMode>('view');
  const hasContent = content.trim().length > 0;

  useEffect(() => {
    latestContentRef.current = content;
  }, [content]);

  // 獲取 Draw.io URL（帶重試機制）
  useEffect(() => {
    const fetchDrawioUrl = async () => {
      if (!runtimeBaseUrl || !hasContent) {
        return;
      }

      setIsLoading(true);
      setError('');
      setFallbackReason(undefined);

      try {
        const client = new ApiClient({ baseUrl: runtimeBaseUrl });
        const data = await client.get<{ url: string }>(
          `/api/v1/drawio/viewer?file_path=${encodeURIComponent(filePath)}&mode=${viewerMode}`
        );
        setDrawioUrl(data.url);
        setRetryCount(0); // 成功後重置重試計數
      } catch (err) {
        logger.error('Failed to load Draw.io URL', { error: err });
        if (isDrawioUnavailable(err)) {
          const reason = err.reason === 'DISABLED' || err.reason === 'UNREACHABLE'
            ? err.reason
            : null;
          setFallbackReason(reason);
          setDrawioUrl('');
          setRetryCount(0);
          return;
        }

        const errorMessage = err instanceof Error ? err.message : 'Unknown error';

        // 如果還有重試次數，則自動重試
        if (retryCount < MAX_RETRIES) {
          logger.debug(`Retrying... (${retryCount + 1}/${MAX_RETRIES})`);
          setTimeout(() => {
            setRetryCount(prev => prev + 1);
          }, RETRY_DELAY_MS * (retryCount + 1)); // 指數退避
        } else {
          setError(errorMessage);
        }
      } finally {
        setIsLoading(false);
      }
    };

    fetchDrawioUrl();
  }, [runtimeBaseUrl, filePath, hasContent, retryCount, reloadToken, viewerMode]);

  const switchViewerMode = useCallback((mode: DrawioViewerMode) => {
    setViewerMode(mode);
    setError('');
    setDrawioUrl('');
    setRetryCount(0);
    setReloadToken(prev => prev + 1);
  }, []);

  // 保存圖表
  const handleSave = useCallback(async (xml: string): Promise<boolean> => {
    if (!runtimeBaseUrl || isSaving) {
      return false;
    }

    setIsSaving(true);

    try {
      // 使用 ApiClient 來確保請求攜帶 Authorization header
      const client = new ApiClient({ baseUrl: runtimeBaseUrl });
      const path = `/api/v1/drawio/save?file_path=${encodeURIComponent(filePath)}`;

      await client.post(path, { content: xml });
      logger.debug('Draw.io file saved', { path });

      // 通知父組件
      if (onSave) {
        onSave(xml);
      }
      iframeRef.current?.contentWindow?.postMessage(
        JSON.stringify({
          action: 'status',
          messageKey: 'allChangesSaved',
          modified: false,
        }),
        '*'
      );
      return true;
    } catch (err) {
      logger.error('Failed to save Draw.io file', { error: err });
      if (isDrawioUnavailable(err)) {
        const reason = err.reason === 'DISABLED' || err.reason === 'UNREACHABLE'
          ? err.reason
          : null;
        setFallbackReason(reason);
        return false;
      }
      setError(err instanceof Error ? err.message : 'Save failed');
      iframeRef.current?.contentWindow?.postMessage(
        JSON.stringify({
          action: 'status',
          messageKey: 'errorSavingFile',
          modified: true,
        }),
        '*'
      );
      return false;
    } finally {
      setIsSaving(false);
    }
  }, [filePath, isSaving, onSave, runtimeBaseUrl]);

  // 處理來自 Draw.io 的訊息
  const handleMessage = useCallback((evt: MessageEvent) => {
    if (!iframeRef.current || evt.source !== iframeRef.current.contentWindow) {
      return;
    }

    try {
      const message: DrawioMessage = typeof evt.data === 'string'
        ? JSON.parse(evt.data)
        : evt.data;

      logger.debug('Draw.io message received', { event: message.event });

      // 處理 init 事件 - Draw.io 已準備好，發送圖表數據
      if (message.event === 'init') {
        logger.debug('Draw.io initialized, sending diagram data...');

        // 發送 load 消息來載入圖表
        const loadMessage = {
          action: 'load',
          xml: latestContentRef.current,
          autosave: viewerMode === 'edit' ? 1 : 0,
          saveAndExit: viewerMode === 'edit' ? '1' : undefined,
          modified: viewerMode === 'edit' ? 'unsavedChanges' : undefined,
          title: filePath.split('/').pop() || filePath,
        };

        iframeRef.current.contentWindow?.postMessage(
          JSON.stringify(loadMessage),
          '*'
        );
      }

      // 處理保存事件（檢視模式不應該觸發，但保留處理）
      if (message.event === 'save' && message.xml) {
        void handleSave(message.xml).then((saved) => {
          if (saved && message.exit) {
            switchViewerMode('view');
          }
        });
      }

      // 處理自動保存（檢視模式不應該觸發，但保留處理）
      if (message.event === 'autosave' && message.xml) {
        void handleSave(message.xml);
      }

      if (message.event === 'exit') {
        setViewerMode('view');
        setDrawioUrl('');
        setReloadToken(prev => prev + 1);
      }
    } catch (err) {
      logger.error('Failed to parse Draw.io message', { error: err });
    }
  }, [filePath, handleSave, switchViewerMode, viewerMode]);

  // 註冊訊息監聽器
  useEffect(() => {
    window.addEventListener('message', handleMessage);
    return () => window.removeEventListener('message', handleMessage);
  }, [handleMessage]);

  // 下載圖表
  const handleDownload = () => {
    if (!content) return;
    const blob = new Blob([content], { type: 'application/xml' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filePath.split('/').pop() || 'diagram.drawio';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  const toolbarActions = (
    <>
      {fallbackReason === undefined && (
        <Button
          variant="ghost"
          size="sm"
          onClick={() => switchViewerMode(viewerMode === 'edit' ? 'view' : 'edit')}
          disabled={!content || isLoading || isSaving}
          title={viewerMode === 'edit'
            ? t('workspace.fileManagement.drawio.cancel')
            : t('workspace.fileManagement.drawio.edit')}
        >
          {viewerMode === 'edit' ? <X className="h-4 w-4" /> : <Edit3 className="h-4 w-4" />}
        </Button>
      )}
      <Button
        variant="ghost"
        size="sm"
        onClick={handleDownload}
        disabled={!content}
        title={t('workspace.fileManagement.drawio.download')}
      >
        <Download className="h-4 w-4" />
      </Button>
    </>
  );

  const fallbackDescriptionKey = fallbackReason === 'DISABLED'
    ? 'workspace.fileManagement.drawio.serviceUnavailable.disabled'
    : fallbackReason === 'UNREACHABLE'
      ? 'workspace.fileManagement.drawio.serviceUnavailable.unreachable'
      : 'workspace.fileManagement.drawio.serviceUnavailable.description';

  return (
    <div
      id="drawio-viewer-container"
      className={cn(
        'flex flex-col h-full bg-background',
        className
      )}
    >
      {/* 工具列 */}
      {isFocusMode && onExitFocusMode ? (
        <FileFocusToolbar
          icon={<ImageIcon className="h-4 w-4" />}
          title={filePath.split('/').pop() || filePath}
          subtitle={filePath}
          actions={toolbarActions}
          exitLabel={t('workspace.fileManagement.focus.exit')}
          onExit={onExitFocusMode}
        />
      ) : (
      <div className="flex items-center justify-between px-4 py-2 border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
        <div className="flex items-center gap-2">
          <ImageIcon className="h-4 w-4 text-muted-foreground" />
          <span className="text-sm font-medium">{filePath.split('/').pop()}</span>
        </div>

        <div className="flex items-center gap-1">
          {toolbarActions}
        </div>
      </div>
      )}

      {/* 內容區域 */}
      <div className="flex-1 relative overflow-hidden">
        {fallbackReason !== undefined ? (
          <div className="flex h-full flex-col overflow-hidden bg-background">
            <div className="border-b border-border bg-muted/40 px-4 py-3">
              <div className="flex items-start justify-between gap-3">
                <div className="flex min-w-0 gap-3">
                  <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
                  <div className="min-w-0">
                    <h3 className="text-sm font-medium">
                      {t('workspace.fileManagement.drawio.serviceUnavailable.title')}
                    </h3>
                    <p className="mt-1 text-sm text-muted-foreground">
                      {t(fallbackDescriptionKey)}
                    </p>
                  </div>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    setFallbackReason(undefined);
                    setRetryCount(0);
                    setReloadToken(prev => prev + 1);
                  }}
                >
                  {t('workspace.fileManagement.drawio.serviceUnavailable.retry')}
                </Button>
              </div>
            </div>
            <pre className="m-0 flex-1 overflow-auto whitespace-pre-wrap break-words p-4 font-mono text-xs leading-relaxed text-foreground">
              {content}
            </pre>
          </div>
        ) : error && (
          <div className="absolute inset-0 flex items-center justify-center bg-background/95 z-10">
            <div className="flex flex-col items-center gap-4 p-6 max-w-md text-center">
              <AlertCircle className="w-12 h-12 text-destructive" />
              <div>
                <h3 className="text-lg font-semibold mb-2">
                  {t('workspace.fileManagement.drawio.error.title')}
                </h3>
                <p className="text-sm text-muted-foreground">{error}</p>
              </div>
              <Button
                variant="outline"
                onClick={() => {
                  setError('');
                  setDrawioUrl('');
                  setRetryCount(0); // 重置重試計數以觸發重新載入
                  setReloadToken(prev => prev + 1);
                }}
              >
                {t('workspace.fileManagement.drawio.retry')}
              </Button>
              {retryCount > 0 && retryCount < MAX_RETRIES && (
                <p className="text-xs text-muted-foreground">
                  {t('workspace.fileManagement.drawio.retrying', { count: retryCount, max: MAX_RETRIES })}
                </p>
              )}
            </div>
          </div>
        )}

        {fallbackReason !== undefined ? null : isLoading ? (
          <div className="flex items-center justify-center h-full">
            <div className="flex flex-col items-center gap-3">
              <Loader2 className="w-8 h-8 animate-spin text-primary" />
              <p className="text-sm text-muted-foreground">
                {t('workspace.fileManagement.drawio.loading')}
              </p>
            </div>
          </div>
        ) : drawioUrl ? (
          <iframe
            ref={iframeRef}
            src={drawioUrl}
            className="w-full h-full border-0"
            allow="clipboard-read; clipboard-write"
            sandbox="allow-same-origin allow-scripts allow-forms allow-modals allow-popups"
          />
        ) : (
          <div className="flex items-center justify-center h-full">
            <p className="text-sm text-muted-foreground">
              {t('workspace.fileManagement.drawio.empty')}
            </p>
          </div>
        )}
      </div>
    </div>
  );
};
