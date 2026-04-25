/**
 * BrowserFeature - 瀏覽器 WebRTC 連接功能
 *
 * 透過 neko WebRTC 串流提供 workspace-browser 容器的即時畫面
 */

import React, { useState } from 'react';
import { Globe, Maximize2, Minimize2, RotateCw, Loader2 } from 'lucide-react';
import { FeatureHeader } from '@/shared/components/layout/FeatureHeader';
import { Button } from '@/shared/components/ui/button';
import { cn } from '@/shared/utils/cn';
import { useI18n } from '@/shared/hooks/useI18n';
import { useToast } from '@/shared/components/ui/use-toast';
import { useWorkspace } from '../../providers/WorkspaceProvider';
import { workspaceLifecycleApi } from '../../services/workspaceLifecycleApi';
import { resolvePreferredWorkspaceUrl, toWebSocketUrl } from '../../services/workspacePublicUrl';
import { useNekoStream } from './hooks/useNekoStream';
import { createLogger } from '@/shared/services/logger';

const logger = createLogger('BrowserFeature');

export const BrowserFeature: React.FC = () => {
  const { t } = useI18n();
  const { toast } = useToast();
  const { workspaceRuntime } = useWorkspace();

  const [isFullscreen, setIsFullscreen] = useState(false);
  const [isRestarting, setIsRestarting] = useState(false);

  // 從 workspaceRuntime 獲取 Browser 資訊
  const workspaceId = workspaceRuntime.workspaceId;
  const browserStatus = workspaceRuntime.runtimeStatus?.browserStatus || 'stopped';
  const browserWebrtcBaseUrl = resolvePreferredWorkspaceUrl(
    workspaceRuntime.runtimeStatus?.browserWebrtcExternalUrl,
    workspaceRuntime.runtimeStatus?.browserWebrtcInternalUrl
  );

  // neko WebSocket 連接 URL
  const wsUrl = browserStatus === 'running' && browserWebrtcBaseUrl
    ? toWebSocketUrl(browserWebrtcBaseUrl, '/ws')
    : null;

  const {
    connectionState,
    isConnected,
    error: streamError,
    videoRef,
    audioRef,
    reconnect,
  } = useNekoStream({
    url: wsUrl,
    password: 'neko',
    displayname: 'user',
  });

  const handleReload = async () => {
    if (!workspaceId) {
      toast({
        title: t('workspace.canvas.browser.restart.failed'),
        description: t('workspace.canvas.browser.error.noWorkspace'),
        variant: 'destructive',
      });
      return;
    }

    setIsRestarting(true);

    try {
      await workspaceLifecycleApi.restartBrowserContainer(workspaceId);
      toast({
        title: t('workspace.canvas.browser.restart.started'),
        description: t('workspace.canvas.browser.restart.description'),
      });
      logger.info('Chrome 容器重啟請求已發送', { workspaceId });
    } catch (error) {
      logger.error('Chrome 容器重啟失敗', { error, workspaceId });
      toast({
        title: t('workspace.canvas.browser.restart.failed'),
        description: error instanceof Error ? error.message : String(error),
        variant: 'destructive',
      });
    } finally {
      setIsRestarting(false);
    }
  };

  const isLoading = connectionState === 'connecting';
  const shouldShowStream = browserStatus === 'running' && wsUrl;

  return (
    <div
      className={cn(
        'flex h-full flex-col bg-background',
        isFullscreen && 'fixed inset-0 z-50 bg-background'
      )}
    >
      <FeatureHeader
        title={t('workspace.canvas.browser.title')}
        icon={Globe}
        actions={
          <div className="flex items-center gap-1">
            {(isConnected || isRestarting || browserStatus === 'restarting') && (
              <Button
                variant="ghost"
                size="sm"
                className="h-7 px-2 text-xs"
                onClick={handleReload}
                disabled={isRestarting || browserStatus === 'restarting'}
                title={t('workspace.canvas.browser.actions.restartContainer')}
              >
                {isRestarting || browserStatus === 'restarting' ? (
                  <Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" />
                ) : (
                  <RotateCw className="h-3.5 w-3.5 mr-1.5" />
                )}
                {t('workspace.canvas.browser.actions.restartContainer')}
              </Button>
            )}
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7"
              onClick={() => setIsFullscreen((prev) => !prev)}
              title={
                isFullscreen
                  ? t('workspace.canvas.header.actions.fullscreen.exit')
                  : t('workspace.canvas.header.actions.fullscreen.enter')
              }
            >
              {isFullscreen ? (
                <Minimize2 className="h-3.5 w-3.5" />
              ) : (
                <Maximize2 className="h-3.5 w-3.5" />
              )}
            </Button>
          </div>
        }
      />

      <div className="flex-1 overflow-hidden relative bg-black">
        {/* 載入狀態覆蓋層 */}
        {shouldShowStream && isLoading && (
          <div className="absolute inset-0 flex items-center justify-center bg-background/80 backdrop-blur-sm z-10">
            <div className="text-center space-y-4">
              <Loader2 className="h-8 w-8 mx-auto animate-spin" />
              <div className="text-sm text-muted-foreground">
                {t('workspace.canvas.browser.connecting')}
              </div>
            </div>
          </div>
        )}

        {/* 重啟中狀態 */}
        {browserStatus === 'restarting' && (
          <div className="absolute inset-0 flex items-center justify-center bg-background">
            <div className="text-center space-y-4 max-w-md">
              <Loader2 className="h-16 w-16 mx-auto text-muted-foreground animate-spin" />
              <div className="text-lg font-semibold">
                {t('workspace.canvas.browser.restart.inProgress')}
              </div>
              <div className="text-sm text-muted-foreground">
                {t('workspace.canvas.browser.restart.description')}
              </div>
            </div>
          </div>
        )}

        {/* 未啟動狀態 */}
        {!shouldShowStream && browserStatus !== 'restarting' && (
          <div className="absolute inset-0 flex items-center justify-center bg-background">
            <div className="text-center space-y-4 max-w-md">
              <Globe className="h-16 w-16 mx-auto text-muted-foreground" />
              <div className="text-lg font-semibold">
                {t('workspace.canvas.browser.notReady.title')}
              </div>
              <div className="text-sm text-muted-foreground">
                {t('workspace.canvas.browser.notReady.description')}
              </div>
              {browserStatus === 'stopped' && (
                <div className="text-xs text-muted-foreground mt-4">
                  <div className="bg-muted p-3 rounded-md text-left">
                    <div className="font-mono text-xs">
                      {t('workspace.canvas.browser.notReady.hint')}
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* WebRTC 錯誤顯示 */}
        {streamError && connectionState === 'failed' && (
          <div className="absolute inset-0 flex items-center justify-center bg-background">
            <div className="text-center space-y-4 max-w-md">
              <Globe className="h-16 w-16 mx-auto text-destructive" />
              <div className="text-lg font-semibold">
                {t('workspace.canvas.browser.error.connectionFailed')}
              </div>
              <div className="text-sm text-muted-foreground">{t(streamError)}</div>
              <Button onClick={reconnect}>
                <RotateCw className="h-4 w-4 mr-2" />
                {t('workspace.canvas.browser.actions.retry')}
              </Button>
            </div>
          </div>
        )}

        {/* WebRTC 串流 — video + audio */}
        {shouldShowStream && (
          <>
            <video
              ref={videoRef}
              autoPlay
              playsInline
              muted
              style={{
                width: '100%',
                height: '100%',
                objectFit: 'contain',
                background: '#000',
                outline: 'none',
              }}
            />
            <audio ref={audioRef} autoPlay />
          </>
        )}
      </div>
    </div>
  );
};

export default BrowserFeature;
