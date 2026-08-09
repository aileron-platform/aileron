/**
 *
 */

import React, { useEffect, useState } from 'react';
import { Globe, Maximize2, Minimize2, RotateCw, Loader2 } from 'lucide-react';
import { FeatureHeader } from '@/shared/components/layout/FeatureHeader';
import { Button } from '@/shared/components/ui/button';
import { cn } from '@/shared/utils/cn';
import { useI18n } from '@/shared/hooks/useI18n';
import { useToast } from '@/shared/components/ui/use-toast';
import { useWorkspace } from '../../providers/WorkspaceProvider';
import { workspaceLifecycleApi } from '../../api/workspaceLifecycleApi';
import {
  toSameOriginWebSocketUrl,
} from '@/shared/utils/workspaceGateway';
import { useNekoStream } from './hooks/useNekoStream';
import { useBrowserAccessRecovery } from './hooks/useBrowserAccessRecovery';
import type { NekoConnectionState } from './lib/nekoProtocol';
import { createLogger } from '@/shared/services/logger';
import { BrowserExtensionPairingButton } from './components/BrowserExtensionPairingButton';

const logger = createLogger('BrowserPage');
const EMPTY_ICE_SERVERS: RTCIceServer[] = [];

export const BrowserPage: React.FC = () => {
  const { t } = useI18n();
  const { toast } = useToast();
  const { workspaceRuntime } = useWorkspace();

  const [isFullscreen, setIsFullscreen] = useState(false);
  const [isRestarting, setIsRestarting] = useState(false);
  const [observedConnectionState, setObservedConnectionState] =
    useState<NekoConnectionState>('disconnected');

  const workspaceId = workspaceRuntime.workspaceId;
  const browserStatus = workspaceRuntime.runtimeStatus?.browserStatus || 'stopped';
  const connectivityState = workspaceRuntime.browserConnectivity?.state;
  const recovery = useBrowserAccessRecovery({
    workspaceId: workspaceId || null,
    enabled: browserStatus === 'running',
    connectionState: observedConnectionState,
    requestAccess: workspaceLifecycleApi.accessBrowser,
  });
  const wsUrl = browserStatus === 'running' && recovery.access
    ? toSameOriginWebSocketUrl(`${recovery.access.browserUrl.replace(/\/+$/, '')}/ws`)
    : null;

  const {
    connectionState,
    isConnected,
    error: streamError,
    videoRef,
    audioRef,
  } = useNekoStream({
    url: wsUrl,
    password: recovery.access?.password ?? null,
    iceServers: recovery.access?.iceServers ?? EMPTY_ICE_SERVERS,
    displayname: 'user',
    generation: recovery.generation,
  });

  useEffect(() => {
    setObservedConnectionState(connectionState);
  }, [connectionState]);

  const handleReload = async () => {
    if (!workspaceId) {
      toast({
        title: t('workspace.browser.restart.failed'),
        description: t('workspace.browser.error.noWorkspace'),
        variant: 'destructive',
      });
      return;
    }

    setIsRestarting(true);

    try {
      await workspaceLifecycleApi.restartComponent(workspaceId, 'browser');
      toast({
        title: t('workspace.browser.restart.started'),
        description: t('workspace.browser.restart.description'),
      });
      logger.info('Chrome container restart request sent', { workspaceId });
    } catch (error) {
      logger.error('Chrome container restart failed', { error, workspaceId });
      toast({
        title: t('workspace.browser.restart.failed'),
        description: error instanceof Error ? error.message : String(error),
        variant: 'destructive',
      });
    } finally {
      setIsRestarting(false);
    }
  };

  const isLoading = connectionState === 'connecting'
    || recovery.state === 'requesting'
    || recovery.state === 'recovering';
  const shouldShowStream = browserStatus === 'running' && wsUrl;
  const displayedError = recovery.errorKey ?? streamError;
  const recoveryFailed = recovery.state === 'exhausted';
  const isPreparingAccess = browserStatus === 'running' && !wsUrl && !recoveryFailed;

  return (
    <div
      className={cn(
        'flex h-full flex-col bg-background',
        isFullscreen && 'fixed inset-0 z-50 bg-background'
      )}
    >
      <FeatureHeader
        title={t('workspace.browser.title')}
        icon={Globe}
        actions={
          <div className="flex items-center gap-1">
            {connectivityState && (
              <span
                className="mr-2 text-xs text-muted-foreground"
                data-testid="browser-connectivity-state"
              >
                {t(`workspace.browser.connectivity.state.${connectivityState}`)}
              </span>
            )}
            <BrowserExtensionPairingButton
              workspaceId={workspaceId}
              disabled={browserStatus !== 'running' || isRestarting}
            />
            {(isConnected || isRestarting || browserStatus === 'restarting') && (
              <Button
                variant="ghost"
                size="sm"
                className="h-7 px-2 text-xs"
                onClick={handleReload}
                disabled={isRestarting || browserStatus === 'restarting'}
                title={t('workspace.browser.actions.restartContainer')}
              >
                {isRestarting || browserStatus === 'restarting' ? (
                  <Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" />
                ) : (
                  <RotateCw className="h-3.5 w-3.5 mr-1.5" />
                )}
                {t('workspace.browser.actions.restartContainer')}
              </Button>
            )}
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7"
              onClick={() => setIsFullscreen((prev) => !prev)}
              title={
                isFullscreen
                  ? t('workspace.browser.actions.fullscreen.exit')
                  : t('workspace.browser.actions.fullscreen.enter')
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
        {shouldShowStream && isLoading && (
          <div className="absolute inset-0 flex items-center justify-center bg-background/80 backdrop-blur-sm z-10">
            <div className="text-center space-y-4">
              <Loader2 className="h-8 w-8 mx-auto animate-spin" />
              <div className="text-sm text-muted-foreground">
                {t('workspace.browser.connecting')}
              </div>
            </div>
          </div>
        )}

        {browserStatus === 'restarting' && (
          <div className="absolute inset-0 flex items-center justify-center bg-background">
            <div className="text-center space-y-4 max-w-md">
              <Loader2 className="h-16 w-16 mx-auto text-muted-foreground animate-spin" />
              <div className="text-lg font-semibold">
                {t('workspace.browser.restart.inProgress')}
              </div>
              <div className="text-sm text-muted-foreground">
                {t('workspace.browser.restart.description')}
              </div>
            </div>
          </div>
        )}

        {isPreparingAccess && (
          <div className="absolute inset-0 flex items-center justify-center bg-background">
            <div className="text-center space-y-4 max-w-md">
              <Loader2 className="h-16 w-16 mx-auto text-muted-foreground animate-spin" />
              <div className="text-lg font-semibold">
                {t('workspace.browser.connectivity.preparing')}
              </div>
            </div>
          </div>
        )}

        {!shouldShowStream && !isPreparingAccess && !recoveryFailed && browserStatus !== 'restarting' && (
          <div className="absolute inset-0 flex items-center justify-center bg-background">
            <div className="text-center space-y-4 max-w-md">
              <Globe className="h-16 w-16 mx-auto text-muted-foreground" />
              <div className="text-lg font-semibold">
                {t('workspace.browser.notReady.title')}
              </div>
              <div className="text-sm text-muted-foreground">
                {t('workspace.browser.notReady.description')}
              </div>
              {browserStatus === 'stopped' && (
                <div className="text-xs text-muted-foreground mt-4">
                  <div className="bg-muted p-3 rounded-md text-left">
                    <div className="font-mono text-xs">
                      {t('workspace.browser.notReady.hint')}
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {displayedError && recoveryFailed && (
          <div className="absolute inset-0 flex items-center justify-center bg-background">
            <div className="text-center space-y-4 max-w-md">
              <Globe className="h-16 w-16 mx-auto text-destructive" />
              <div className="text-lg font-semibold">
                {t('workspace.browser.error.connectionFailed')}
              </div>
              <div className="text-sm text-muted-foreground">{t(displayedError)}</div>
              <Button onClick={recovery.retry}>
                <RotateCw className="h-4 w-4 mr-2" />
                {t('workspace.browser.actions.retry')}
              </Button>
            </div>
          </div>
        )}

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
                objectPosition: 'center center',
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

export default BrowserPage;
