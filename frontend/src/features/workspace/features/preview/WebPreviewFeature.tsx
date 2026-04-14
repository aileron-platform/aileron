/**
 * WebPreviewFeature - 網頁預覽功能
 *
 * 提供即時網頁預覽功能，支援 Next.js 路由 autocomplete
 */

import React, { useState, useEffect, useRef } from 'react';
import { createLogger } from '@/shared/services/logger';

const logger = createLogger('WebPreview');
import { Monitor, Maximize2, Minimize2, RotateCw, ChevronDown, Rocket, PackageOpen, AlertTriangle } from 'lucide-react';
import { FeatureHeader } from '@/shared/components/layout/FeatureHeader';
import { Input } from '@/shared/components/ui/input';
import { Button } from '@/shared/components/ui/button';
import { cn } from '@/shared/utils/cn';
import { useI18n } from '@/shared/hooks/useI18n';
import { useWorkspace } from '../../providers/WorkspaceContext';
import { useToast } from '@/shared/components/ui/use-toast';
import {
  fetchWorkspaceDetail,
  fetchNextJsRoutes,
  syncPreview,
  fetchPreviewSyncStatus,
  checkPreviewHealth,
  type NextJsRoute
} from '../../services/workspaceRuntimeApi';
import { resolvePreferredWorkspaceUrl } from '../../services/workspacePublicUrl';

export const WebPreviewFeature: React.FC = () => {
  const { t, state } = useI18n();
  const { toast } = useToast();
  const { workspaceRuntime } = useWorkspace();
  const [selectedPath, setSelectedPath] = useState('/');
  const [baseUrl, setBaseUrl] = useState('');
  const [iframeSrc, setIframeSrc] = useState('');
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [routes, setRoutes] = useState<NextJsRoute[]>([]);
  const [showDropdown, setShowDropdown] = useState(false);
  const [filteredRoutes, setFilteredRoutes] = useState<NextJsRoute[]>([]);
  const [isSyncing, setIsSyncing] = useState(false);
  const [syncProgress, setSyncProgress] = useState(0);
  const [healthStatus, setHealthStatus] = useState<'healthy' | 'unhealthy' | 'standby' | 'starting' | 'checking'>('checking');
  const [healthMessage, setHealthMessage] = useState<string>('');
  const [workspaceHasNextjs, setWorkspaceHasNextjs] = useState<boolean | null>(null);
  const [iframeError, setIframeError] = useState(false);
  const [retryCount, setRetryCount] = useState(0);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const healthCheckIntervalRef = useRef<NodeJS.Timeout | null>(null);

  // 健康檢查
  const performHealthCheck = React.useCallback(async () => {
    if (!workspaceRuntime.workspaceId || !workspaceRuntime.runtimeBaseUrl) {
      return;
    }

    try {
      const health = await checkPreviewHealth(
        workspaceRuntime.runtimeBaseUrl,
        workspaceRuntime.workspaceId
      );

      setHealthStatus(health.status);
      setHealthMessage(health.message || '');
      setWorkspaceHasNextjs(health.workspace_has_nextjs ?? (health.source !== '/default-app' && health.source != null));

      // 如果服務健康且 iframe 有錯誤，嘗試重新載入
      if (health.status === 'healthy' && iframeError && retryCount < 3) {
        logger.debug('服務已恢復，重新載入 iframe...');
        setIframeError(false);
        setRetryCount(prev => prev + 1);
        if (iframeRef.current && iframeSrc) {
          iframeRef.current.src = 'about:blank';
          setTimeout(() => {
            if (iframeRef.current) {
              iframeRef.current.src = iframeSrc;
            }
          }, 100);
        }
      }
    } catch (error) {
      logger.error('健康檢查失敗', { error });
      setHealthStatus('unhealthy');
      setHealthMessage(t('common.messages.cannotConnect'));
    }
  }, [workspaceRuntime.workspaceId, workspaceRuntime.runtimeBaseUrl, iframeError, retryCount, iframeSrc, t]);

  // 從 workspace detail 獲取 web preview base URL 和路由列表
  useEffect(() => {
    const loadWebPreviewData = async () => {
      if (!workspaceRuntime.workspaceId || !workspaceRuntime.runtimeBaseUrl) {
        setIsLoading(false);
        return;
      }

      try {
        const detail = await fetchWorkspaceDetail(workspaceRuntime.workspaceId);
        const webPreviewUrl = resolvePreferredWorkspaceUrl(
          detail.runtimeStatus?.webPreviewExternalUrl,
          detail.runtimeStatus?.nextjsExternalUrl,
          detail.runtimeStatus?.webPreviewInternalUrl,
          detail.runtimeStatus?.nextjsInternalUrl
        );

        logger.debug('初始化 webPreviewUrl', { webPreviewUrl });

        if (webPreviewUrl) {
          setBaseUrl(webPreviewUrl);
          // 只在初始化時設定 iframe src，不要覆蓋用戶選擇的路由
          if (!iframeSrc) {
            const initUrl = new URL(webPreviewUrl + '/');
            initUrl.searchParams.set('lang', state.currentLanguage);
            setIframeSrc(initUrl.toString());
          }

          // 獲取 Next.js 路由列表
          try {
            const routesData = await fetchNextJsRoutes(
              workspaceRuntime.runtimeBaseUrl,
              workspaceRuntime.workspaceId
            );
            logger.debug('載入路由列表', { routes: routesData.routes });
            setRoutes(routesData.routes);
            setFilteredRoutes(routesData.routes);
          } catch (error) {
            logger.error('Failed to load Next.js routes', { error });
          }

          // 開始健康檢查
          performHealthCheck();
        }
      } catch (error) {
        logger.error('Failed to load web preview URL', { error });
      } finally {
        setIsLoading(false);
      }
    };

    loadWebPreviewData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [workspaceRuntime.workspaceId, workspaceRuntime.runtimeBaseUrl]);

  // 定期健康檢查
  useEffect(() => {
    if (!workspaceRuntime.workspaceId || !workspaceRuntime.runtimeBaseUrl) {
      return;
    }

    // 每 10 秒檢查一次
    healthCheckIntervalRef.current = setInterval(() => {
      performHealthCheck();
    }, 10000);

    return () => {
      if (healthCheckIntervalRef.current) {
        clearInterval(healthCheckIntervalRef.current);
      }
    };
  }, [workspaceRuntime.workspaceId, workspaceRuntime.runtimeBaseUrl, performHealthCheck]);

  // 語系變更時更新 iframe URL 的 lang 參數
  useEffect(() => {
    setIframeSrc(prev => {
      if (!prev) return prev;
      try {
        const url = new URL(prev);
        url.searchParams.set('lang', state.currentLanguage);
        return url.toString();
      } catch {
        return prev;
      }
    });
  }, [state.currentLanguage]);

  // 當 iframeSrc 改變時，更新 iframe 的 src
  useEffect(() => {
    if (iframeRef.current && iframeSrc) {
      logger.debug('更新 iframe src', { iframeSrc });
      iframeRef.current.src = iframeSrc;
    }
  }, [iframeSrc]);

  // 點擊外部關閉下拉選單
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setShowDropdown(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handlePathChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const value = event.target.value;
    setSelectedPath(value);

    // 過濾路由
    const filtered = routes.filter(route =>
      route.path.toLowerCase().includes(value.toLowerCase())
    );
    setFilteredRoutes(filtered);
    setShowDropdown(true);
  };

  const handlePathKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'Enter') {
      event.preventDefault();
      handleNavigate();
    }
  };

  const handleSelectRoute = (route: NextJsRoute) => {
    logger.debug('選擇路由', { path: route.path, baseUrl });
    setSelectedPath(route.path);
    setShowDropdown(false);
    // 自動導航
    const fullUrl = baseUrl + route.path;
    logger.debug('導航到', { fullUrl });
    setIframeSrc(fullUrl);
  };

  const handleNavigate = () => {
    if (!baseUrl) return;
    const fullUrl = baseUrl + selectedPath;
    setIframeSrc(fullUrl);
    setShowDropdown(false);
  };

  const handleRefresh = () => {
    // 強制重新載入 iframe
    if (iframeRef.current) {
      try {
        // 方法 1: 使用 contentWindow.location.reload()
        iframeRef.current.contentWindow?.location.reload();
      } catch (error) {
        // 如果跨域限制導致失敗，使用方法 2: 重新設定 src
        logger.debug('使用 src 重設方式重新載入');
        const currentSrc = iframeRef.current.src;
        iframeRef.current.src = 'about:blank';
        setTimeout(() => {
          if (iframeRef.current) {
            iframeRef.current.src = currentSrc;
          }
        }, 50);
      }
    }
  };

  const handleSync = async () => {
    if (!workspaceRuntime.runtimeBaseUrl || !workspaceRuntime.workspaceId) {
      toast({
        title: '同步失敗',
        description: 'Workspace 資訊不完整',
        variant: 'destructive',
      });
      return;
    }

    setIsSyncing(true);
    setSyncProgress(0);

    try {
      // 啟動同步
      const response = await syncPreview(
        workspaceRuntime.runtimeBaseUrl,
        workspaceRuntime.workspaceId
      );

      toast({
        title: '開始同步',
        description: '正在將 /workspace 複製到 /web-preview...',
        variant: 'info',
      });

      // 輪詢檢查同步狀態
      const pollInterval = setInterval(async () => {
        try {
          const status = await fetchPreviewSyncStatus(
            workspaceRuntime.runtimeBaseUrl!,
            workspaceRuntime.workspaceId!,
            response.operationId
          );

          setSyncProgress(status.progress);

          if (status.status === 'completed') {
            clearInterval(pollInterval);
            setIsSyncing(false);
            setSyncProgress(1);

            toast({
              title: '同步完成',
              description: '預覽環境已更新，正在重新載入...',
              variant: 'success',
            });

            // 重置重試計數
            setRetryCount(0);
            setIframeError(false);

            // 等待服務完全啟動後重新載入 iframe
            const waitForService = async () => {
              let attempts = 0;
              const maxAttempts = 10;

              while (attempts < maxAttempts) {
                try {
                  const health = await checkPreviewHealth(
                    workspaceRuntime.runtimeBaseUrl!,
                    workspaceRuntime.workspaceId!
                  );

                  if (health.status === 'healthy') {
                    logger.debug('服務已就緒，重新載入 iframe');
                    setHealthStatus('healthy');

                    // 重新載入 iframe
                    if (iframeRef.current) {
                      iframeRef.current.src = 'about:blank';
                      setTimeout(() => {
                        if (iframeRef.current) {
                          iframeRef.current.src = iframeSrc;
                        }
                      }, 100);
                    }

                    // 重新載入路由列表
                    try {
                      const routesData = await fetchNextJsRoutes(
                        workspaceRuntime.runtimeBaseUrl!,
                        workspaceRuntime.workspaceId!
                      );
                      setRoutes(routesData.routes);
                      setFilteredRoutes(routesData.routes);
                    } catch (error) {
                      logger.error('重新載入路由失敗', { error });
                    }

                    break;
                  }

                  setHealthStatus(health.status);
                  logger.debug('等待服務啟動', { attempt: attempts + 1, maxAttempts });
                } catch (error) {
                  logger.error('健康檢查失敗', { error });
                }

                attempts++;
                await new Promise(resolve => setTimeout(resolve, 2000));
              }

              if (attempts >= maxAttempts) {
                logger.error('服務啟動超時');
                toast({
                  title: '警告',
                  description: '預覽服務啟動時間較長，請稍後手動重新整理',
                  variant: 'destructive',
                });
              }
            };

            waitForService();
          } else if (status.status === 'failed') {
            clearInterval(pollInterval);
            setIsSyncing(false);

            toast({
              title: '同步失敗',
              description: status.error || '同步過程發生錯誤',
              variant: 'destructive',
            });
          }
        } catch (error) {
          logger.error('查詢同步狀態失敗', { error });
        }
      }, 1000); // 每秒檢查一次

      // 30 秒後停止輪詢
      setTimeout(() => {
        clearInterval(pollInterval);
        if (isSyncing) {
          setIsSyncing(false);
          toast({
            title: '同步超時',
            description: '同步操作超時，請稍後手動重新整理',
            variant: 'destructive',
          });
        }
      }, 30000);
    } catch (error) {
      setIsSyncing(false);
      toast({
        title: '同步失敗',
        description: error instanceof Error ? error.message : '未知錯誤',
        variant: 'destructive',
      });
    }
  };

  return (
    <div
      className={cn(
        'flex h-full flex-col bg-background',
        isFullscreen && 'fixed inset-0 z-50 bg-background'
      )}
    >
      <FeatureHeader
        title={t('workspace.preview.webPreview.title')}
        icon={Monitor}
        info={
          <div className="flex items-center gap-2 min-w-0 flex-1 relative" ref={dropdownRef}>
            <div className="flex-1 relative">
              <Input
                ref={inputRef}
                value={selectedPath}
                onChange={handlePathChange}
                onKeyDown={handlePathKeyDown}
                onFocus={() => setShowDropdown(true)}
                placeholder="選擇或輸入路徑，例如: /about"
                className="flex-1 h-7 text-xs min-w-0 pr-8"
              />
              <Button
                variant="ghost"
                size="icon"
                className="absolute right-0 top-0 h-7 w-7"
                onClick={() => setShowDropdown(!showDropdown)}
              >
                <ChevronDown className="h-3 w-3" />
              </Button>

              {/* Autocomplete Dropdown */}
              {showDropdown && filteredRoutes.length > 0 && (
                <div className="absolute top-full left-0 right-0 mt-1 bg-popover border rounded-md shadow-lg z-50 max-h-60 overflow-y-auto">
                  {filteredRoutes.map((route) => (
                    <button
                      key={route.path}
                      className="w-full px-3 py-2 text-left text-sm hover:bg-accent hover:text-accent-foreground"
                      onClick={() => handleSelectRoute(route)}
                    >
                      <span className="font-mono">{route.path}</span>
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
        }
        actions={
          <div className="flex items-center gap-1">
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7"
              onClick={handleSync}
              disabled={isSyncing}
              title="同步 /workspace 到 /web-preview"
            >
              <Rocket className={cn("h-3.5 w-3.5", isSyncing && "animate-spin")} />
            </Button>
            {isSyncing && (
              <span className="text-xs text-muted-foreground">
                {Math.round(syncProgress * 100)}%
              </span>
            )}
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7"
              onClick={handleRefresh}
              title={t('workspace.preview.header.actions.refresh')}
            >
              <RotateCw className="h-3.5 w-3.5" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7"
              onClick={() => setIsFullscreen((prev) => !prev)}
              title={
                isFullscreen
                  ? t('workspace.preview.header.actions.fullscreen.exit')
                  : t('workspace.preview.header.actions.fullscreen.enter')
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

      <div className="flex-1 overflow-hidden relative">
        {/* 載入/錯誤狀態覆蓋層 */}
        {(isLoading || healthStatus === 'starting' || healthStatus === 'checking') && (
          <div className="absolute inset-0 flex items-center justify-center bg-background/80 backdrop-blur-sm z-10">
            <div className="text-center space-y-4">
              <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mx-auto"></div>
              <div className="text-sm text-muted-foreground">
                {healthStatus === 'starting' ? '預覽服務正在啟動...' :
                 healthStatus === 'checking' ? '檢查服務狀態...' :
                 '載入中...'}
              </div>
              {healthMessage && (
                <div className="text-xs text-muted-foreground/70">
                  {healthMessage}
                </div>
              )}
            </div>
          </div>
        )}

        {healthStatus === 'standby' && !isLoading && (
          <div className="absolute inset-0 flex items-center justify-center bg-background/80 backdrop-blur-sm z-10">
            <div className="text-center space-y-4 max-w-md p-6">
              <div className="flex justify-center">
                <div className="rounded-full bg-muted p-4">
                  <PackageOpen className="h-12 w-12 text-muted-foreground" />
                </div>
              </div>
              <div className="text-lg font-semibold">{t('workspace.preview.webPreview.notFound.title')}</div>
              <div className="text-sm text-muted-foreground">
                {healthMessage || t('workspace.preview.webPreview.notFound.defaultMessage')}
              </div>
            </div>
          </div>
        )}

        {healthStatus === 'unhealthy' && !isLoading && (
          <div className="absolute inset-0 flex items-center justify-center bg-background/80 backdrop-blur-sm z-10">
            <div className="text-center space-y-4 max-w-md p-6">
              <div className="flex justify-center">
                <div className="rounded-full bg-destructive/10 p-4">
                  <AlertTriangle className="h-12 w-12 text-destructive" />
                </div>
              </div>
              <div className="text-lg font-semibold">預覽服務未運行</div>
              <div className="text-sm text-muted-foreground">
                {healthMessage || 'Next.js 服務可能未啟動或發生錯誤。請嘗試同步工作區或檢查容器狀態。'}
              </div>
              <div className="flex gap-2 justify-center">
                <Button
                  onClick={() => {
                    setRetryCount(0);
                    performHealthCheck();
                  }}
                  variant="outline"
                >
                  重新檢查
                </Button>
                <Button
                  onClick={handleSync}
                  disabled={isSyncing}
                  variant="default"
                >
                  <Rocket className={cn("h-4 w-4 mr-2", isSyncing && "animate-spin")} />
                  {isSyncing ? '啟動中...' : '啟動服務'}
                </Button>
              </div>
            </div>
          </div>
        )}

        {/* iframe 內容區域 - 佔滿全部空間 */}
        <iframe
          ref={iframeRef}
          src={iframeSrc || undefined}
          title={t('workspace.preview.webPreview.iframeTitle')}
          sandbox="allow-scripts allow-same-origin allow-forms"
          className="h-full w-full border-0"
          onLoad={() => {
            logger.debug('iframe 載入完成', { src: iframeRef.current?.src });
            setIframeError(false);
            setRetryCount(0);
          }}
          onError={() => {
            logger.error('iframe 載入錯誤', { src: iframeRef.current?.src });
            setIframeError(true);
          }}
        />
      </div>
    </div>
  );
};

export default WebPreviewFeature;
