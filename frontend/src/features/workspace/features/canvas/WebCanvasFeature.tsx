import React, { useEffect, useRef, useState } from 'react';
import {
  AlertTriangle,
  ChevronDown,
  Maximize2,
  Minimize2,
  Monitor,
  RefreshCw,
  RotateCw,
  SendToBack,
} from 'lucide-react';

import { FeatureHeader } from '@/shared/components/layout/FeatureHeader';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { useToast } from '@/shared/components/ui/use-toast';
import { useI18n } from '@/shared/hooks/useI18n';
import { createLogger } from '@/shared/services/logger';
import { cn } from '@/shared/utils/cn';
import { useWorkspace } from '../../providers/WorkspaceContext';
import { resolvePreferredWorkspaceUrl } from '../../services/workspacePublicUrl';
import {
  checkCanvasHealth,
  fetchCanvasRoutes,
  fetchWorkspaceDetail,
  resetCanvas,
  syncCanvas,
  type CanvasRoute,
  type CanvasType,
} from '../../services/workspaceRuntimeApi';

const logger = createLogger('WebCanvas');

export const WebCanvasFeature: React.FC = () => {
  const { t, state } = useI18n();
  const { toast } = useToast();
  const { workspaceRuntime } = useWorkspace();
  const [selectedPath, setSelectedPath] = useState('/');
  const [baseUrl, setBaseUrl] = useState('');
  const [iframeSrc, setIframeSrc] = useState('');
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [routes, setRoutes] = useState<CanvasRoute[]>([]);
  const [filteredRoutes, setFilteredRoutes] = useState<CanvasRoute[]>([]);
  const [showDropdown, setShowDropdown] = useState(false);
  const [isWorking, setIsWorking] = useState(false);
  const [healthStatus, setHealthStatus] = useState<string>('checking');
  const [healthMessage, setHealthMessage] = useState('');
  const [canvasType, setCanvasType] = useState<CanvasType>('default');
  const [manifestStatus, setManifestStatus] = useState<string>('missing');
  const dropdownRef = useRef<HTMLDivElement>(null);
  const iframeRef = useRef<HTMLIFrameElement>(null);

  const buildCanvasUrl = (path: string, urlBase = baseUrl) => {
    const nextUrl = new URL(path || '/', `${urlBase}/`);
    nextUrl.searchParams.set('lang', state.currentLanguage);
    return nextUrl.toString();
  };

  const reloadIframe = () => {
    if (!iframeRef.current || !iframeSrc) {
      return;
    }
    iframeRef.current.src = 'about:blank';
    window.setTimeout(() => {
      if (iframeRef.current) {
        iframeRef.current.src = iframeSrc;
      }
    }, 100);
  };

  const loadCanvasData = async () => {
    if (!workspaceRuntime.workspaceId || !workspaceRuntime.runtimeBaseUrl) {
      setIsLoading(false);
      return;
    }

    setIsLoading(true);
    try {
      const detail = await fetchWorkspaceDetail(workspaceRuntime.workspaceId);
      const canvasUrl = resolvePreferredWorkspaceUrl(
        detail.runtimeStatus?.canvasExternalUrl,
        detail.runtimeStatus?.canvasInternalUrl
      );
      setBaseUrl(canvasUrl || '');

      const routesData = await fetchCanvasRoutes(
        workspaceRuntime.runtimeBaseUrl,
        workspaceRuntime.workspaceId
      );
      setRoutes(routesData.routes);
      setFilteredRoutes(routesData.routes);
      setCanvasType(routesData.type);
      setManifestStatus(routesData.manifestStatus);

      const defaultPath = routesData.defaultPath || routesData.routes[0]?.path || '/';
      setSelectedPath(defaultPath);
      if (canvasUrl) {
        setIframeSrc(buildCanvasUrl(defaultPath, canvasUrl));
      }

      const health = await checkCanvasHealth(
        workspaceRuntime.runtimeBaseUrl,
        workspaceRuntime.workspaceId
      );
      setHealthStatus(health.status);
      setHealthMessage(health.message || '');
      if (health.type) {
        setCanvasType(health.type);
      }
      if (health.manifestStatus) {
        setManifestStatus(health.manifestStatus);
      }
    } catch (error) {
      logger.error('Failed to load Web Canvas data', { error });
      setHealthStatus('unhealthy');
      setHealthMessage(error instanceof Error ? error.message : '');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    void loadCanvasData();
  }, [workspaceRuntime.workspaceId, workspaceRuntime.runtimeBaseUrl, state.currentLanguage]);

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
    setFilteredRoutes(routes.filter((route) => route.path.toLowerCase().includes(value.toLowerCase())));
    setShowDropdown(true);
  };

  const handleNavigate = (path = selectedPath) => {
    if (!baseUrl) {
      return;
    }
    setSelectedPath(path);
    setIframeSrc(buildCanvasUrl(path));
    setShowDropdown(false);
  };

  const handleAction = async (action: 'sync' | 'reset') => {
    if (!workspaceRuntime.runtimeBaseUrl || !workspaceRuntime.workspaceId) {
      toast({
        title: t('workspace.canvas.webCanvas.actions.errorTitle'),
        description: t('workspace.canvas.webCanvas.actions.missingWorkspace'),
        variant: 'destructive',
      });
      return;
    }

    setIsWorking(true);
    try {
      if (action === 'sync') {
        await syncCanvas(workspaceRuntime.runtimeBaseUrl, workspaceRuntime.workspaceId);
      } else {
        await resetCanvas(workspaceRuntime.runtimeBaseUrl, workspaceRuntime.workspaceId);
      }

      await loadCanvasData();
      reloadIframe();
      toast({
        title: t(`workspace.canvas.webCanvas.actions.${action}.successTitle`),
        description: t(`workspace.canvas.webCanvas.actions.${action}.successDescription`),
        variant: 'success',
      });
    } catch (error) {
      toast({
        title: t(`workspace.canvas.webCanvas.actions.${action}.errorTitle`),
        description: error instanceof Error ? error.message : t('workspace.canvas.webCanvas.actions.unknownError'),
        variant: 'destructive',
      });
    } finally {
      setIsWorking(false);
    }
  };

  const statusText = t(`workspace.canvas.webCanvas.types.${canvasType}`);
  const manifestText = t(`workspace.canvas.webCanvas.manifest.${manifestStatus}`);

  return (
    <div className={cn('flex h-full flex-col bg-background', isFullscreen && 'fixed inset-0 z-50 bg-background')}>
      <FeatureHeader
        title={t('workspace.canvas.webCanvas.title')}
        icon={Monitor}
        info={
          <div className="flex min-w-0 flex-1 items-center gap-2" ref={dropdownRef}>
            <span className="shrink-0 rounded border px-2 py-1 text-xs text-muted-foreground">
              {statusText}
            </span>
            <span className="shrink-0 rounded border px-2 py-1 text-xs text-muted-foreground">
              {manifestText}
            </span>
            <div className="relative min-w-[180px] flex-1">
              <Input
                value={selectedPath}
                onChange={handlePathChange}
                onKeyDown={(event) => {
                  if (event.key === 'Enter') {
                    event.preventDefault();
                    handleNavigate();
                  }
                }}
                onFocus={() => setShowDropdown(true)}
                placeholder={t('workspace.canvas.webCanvas.routePlaceholder')}
                className="h-7 pr-8 text-xs"
              />
              <Button
                variant="ghost"
                size="icon"
                className="absolute right-0 top-0 h-7 w-7"
                onClick={() => setShowDropdown((prev) => !prev)}
              >
                <ChevronDown className="h-3 w-3" />
              </Button>
              {showDropdown && filteredRoutes.length > 0 && (
                <div className="absolute left-0 right-0 top-full z-50 mt-1 max-h-60 overflow-y-auto rounded-md border bg-popover shadow-lg">
                  {filteredRoutes.map((route) => (
                    <button
                      key={route.path}
                      className="w-full px-3 py-2 text-left text-sm hover:bg-accent hover:text-accent-foreground"
                      onClick={() => handleNavigate(route.path)}
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
              onClick={() => handleAction('sync')}
              disabled={isWorking}
              title={t('workspace.canvas.webCanvas.actions.sync.label')}
            >
              <RefreshCw className={cn('h-3.5 w-3.5', isWorking && 'animate-spin')} />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7"
              onClick={() => handleAction('reset')}
              disabled={isWorking}
              title={t('workspace.canvas.webCanvas.actions.reset.label')}
            >
              <SendToBack className="h-3.5 w-3.5" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7"
              onClick={reloadIframe}
              title={t('workspace.canvas.header.actions.refresh')}
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
                  ? t('workspace.canvas.header.actions.fullscreen.exit')
                  : t('workspace.canvas.header.actions.fullscreen.enter')
              }
            >
              {isFullscreen ? <Minimize2 className="h-3.5 w-3.5" /> : <Maximize2 className="h-3.5 w-3.5" />}
            </Button>
          </div>
        }
      />

      <div className="relative flex-1 overflow-hidden">
        {(isLoading || healthStatus === 'starting' || healthStatus === 'checking') && (
          <div className="absolute inset-0 z-10 flex items-center justify-center bg-background/80 backdrop-blur-sm">
            <div className="space-y-4 text-center">
              <div className="mx-auto h-12 w-12 animate-spin rounded-full border-b-2 border-primary" />
              <div className="text-sm text-muted-foreground">{t('workspace.canvas.webCanvas.loading')}</div>
            </div>
          </div>
        )}

        {healthStatus === 'unhealthy' && !isLoading && (
          <div className="absolute inset-0 z-10 flex items-center justify-center bg-background/80 backdrop-blur-sm">
            <div className="max-w-md space-y-4 p-6 text-center">
              <div className="flex justify-center">
                <div className="rounded-full bg-destructive/10 p-4">
                  <AlertTriangle className="h-12 w-12 text-destructive" />
                </div>
              </div>
              <div className="text-lg font-semibold">{t('workspace.canvas.webCanvas.error.title')}</div>
              <div className="text-sm text-muted-foreground">
                {healthMessage || t('workspace.canvas.webCanvas.error.defaultMessage')}
              </div>
            </div>
          </div>
        )}

        <iframe
          ref={iframeRef}
          src={iframeSrc || undefined}
          title={t('workspace.canvas.webCanvas.iframeTitle')}
          sandbox="allow-scripts allow-same-origin allow-forms"
          className="h-full w-full border-0"
        />
      </div>
    </div>
  );
};

export default WebCanvasFeature;
