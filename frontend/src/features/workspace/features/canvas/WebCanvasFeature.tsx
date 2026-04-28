import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  AlertTriangle,
  ChevronDown,
  ChevronUp,
  Check,
  Crosshair,
  Maximize2,
  MessageSquare,
  MoreHorizontal,
  Minimize2,
  Monitor,
  RefreshCw,
  RotateCw,
  SendToBack,
  Trash2,
  X,
} from 'lucide-react';

import { FeatureHeader } from '@/shared/components/layout/FeatureHeader';
import { Button } from '@/shared/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/shared/components/ui/dropdown-menu';
import { Input } from '@/shared/components/ui/input';
import { useToast } from '@/shared/components/ui/use-toast';
import { useI18n } from '@/shared/hooks/useI18n';
import { createLogger } from '@/shared/services/logger';
import { cn } from '@/shared/utils/cn';
import { useWorkspace } from '../../providers/WorkspaceContext';
import { dispatchInsertDraftEvent } from '../../components/ChatPanel/chatEvents';
import { resolvePreferredWorkspaceUrl } from '../../services/workspacePublicUrl';
import {
  createCanvasReviewNote,
  deleteCanvasReviewNote,
  fetchCanvasReviewNotes,
  checkCanvasHealth,
  fetchCanvasRoutes,
  fetchWorkspaceDetail,
  resetCanvas,
  syncCanvas,
  updateCanvasReviewNoteStatus,
  type CanvasRoute,
  type CanvasReviewNote,
  type CanvasReviewTarget,
  type CanvasType,
} from '../../services/workspaceRuntimeApi';

const logger = createLogger('WebCanvas');
const REVIEW_BRIDGE_SOURCE = 'aileron-web-canvas-review';
const REVIEW_BRIDGE_VERSION = 1;
const CANVAS_REVIEW_ENABLED = import.meta.env.VITE_ENABLE_CANVAS_REVIEW !== 'false';

type BridgeMode = 'default' | 'select';

type BridgeMessage =
  | { source: typeof REVIEW_BRIDGE_SOURCE; version: typeof REVIEW_BRIDGE_VERSION; type: 'BRIDGE_READY'; payload?: { routePath?: string } }
  | { source: typeof REVIEW_BRIDGE_SOURCE; version: typeof REVIEW_BRIDGE_VERSION; type: 'TARGET_SELECTED'; payload?: { routePath?: string; target?: CanvasReviewTarget | null } }
  | { source: typeof REVIEW_BRIDGE_SOURCE; version: typeof REVIEW_BRIDGE_VERSION; type: 'TARGET_RECTS'; payload?: { rects?: BridgeRectUpdate[] } }
  | { source: typeof REVIEW_BRIDGE_SOURCE; version: typeof REVIEW_BRIDGE_VERSION; type: 'BRIDGE_ERROR'; payload?: { errorCode?: string } };

type BridgeRectUpdate = {
  id?: string;
  selector?: string;
  resolved?: boolean;
  rect?: CanvasReviewTarget['rect'];
  documentRect?: CanvasReviewTarget['rect'];
};

const isBridgeMessage = (value: unknown): value is BridgeMessage => {
  if (!value || typeof value !== 'object') return false;
  const candidate = value as { source?: unknown; version?: unknown; type?: unknown };
  return (
    candidate.source === REVIEW_BRIDGE_SOURCE
    && candidate.version === REVIEW_BRIDGE_VERSION
    && typeof candidate.type === 'string'
  );
};

const getTargetRect = (target: CanvasReviewTarget | null | undefined) => target?.rect ?? null;

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
  const [reviewMode, setReviewMode] = useState<BridgeMode>('default');
  const [bridgeReady, setBridgeReady] = useState(false);
  const [selectedTarget, setSelectedTarget] = useState<CanvasReviewTarget | null>(null);
  const [bridgeInteractionPaused, setBridgeInteractionPaused] = useState(false);
  const [reviewInstruction, setReviewInstruction] = useState('');
  const [reviewNotes, setReviewNotes] = useState<CanvasReviewNote[]>([]);
  const [reviewNotesExpanded, setReviewNotesExpanded] = useState(true);
  const [reviewErrorKey, setReviewErrorKey] = useState<string | null>(null);
  const [isReviewSaving, setIsReviewSaving] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const reviewPanelRef = useRef<HTMLDivElement>(null);
  const watchedReviewTargets = useMemo(
    () => reviewNotes
      .filter((note) => note.target.type === 'element')
      .map((note) => ({
        id: note.id,
        selector: note.target.type === 'element' ? note.target.selector : '',
      }))
      .filter((item) => item.selector),
    [reviewNotes]
  );
  const postBridgeCommand = (type: string, payload: Record<string, unknown> = {}) => {
    iframeRef.current?.contentWindow?.postMessage({
      source: REVIEW_BRIDGE_SOURCE,
      version: REVIEW_BRIDGE_VERSION,
      type,
      payload,
    }, '*');
  };

  const clearTransientReviewState = () => {
    setBridgeReady(false);
    setSelectedTarget(null);
    setBridgeInteractionPaused(false);
    setReviewInstruction('');
    setReviewErrorKey(null);
  };

  const buildCanvasUrl = (path: string, urlBase = baseUrl) => {
    const nextUrl = new URL(path || '/', `${urlBase}/`);
    nextUrl.searchParams.set('lang', state.currentLanguage);
    return nextUrl.toString();
  };

  const reloadIframe = () => {
    if (!iframeRef.current || !iframeSrc) {
      return;
    }
    clearTransientReviewState();
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
      await loadReviewNotes(routesData.defaultPath || routesData.routes[0]?.path || '/');
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

  const loadReviewNotes = async (routePath = selectedPath) => {
    if (!workspaceRuntime.workspaceId || !workspaceRuntime.runtimeBaseUrl) {
      setReviewNotes([]);
      return;
    }
    try {
      const response = await fetchCanvasReviewNotes(
        workspaceRuntime.runtimeBaseUrl,
        workspaceRuntime.workspaceId,
        { routePath }
      );
      setReviewNotes(response.notes);
    } catch (error) {
      logger.warn('Failed to load Canvas review notes', { error });
      setReviewNotes([]);
    }
  };

  useEffect(() => {
    void loadReviewNotes(selectedPath);
  }, [selectedPath, workspaceRuntime.workspaceId, workspaceRuntime.runtimeBaseUrl]);

  useEffect(() => {
    const handleBridgeMessage = (event: MessageEvent) => {
      if (event.source !== iframeRef.current?.contentWindow || !isBridgeMessage(event.data)) {
        return;
      }
      if (event.data.type === 'BRIDGE_READY') {
        setBridgeReady(true);
        postBridgeCommand('SET_MODE', { mode: reviewMode });
        postBridgeCommand('SET_INTERACTION_PAUSED', { paused: bridgeInteractionPaused });
        return;
      }
      if (event.data.type === 'TARGET_SELECTED') {
        const target = event.data.payload?.target;
        setSelectedTarget(target ?? null);
        setReviewErrorKey(null);
        return;
      }
      if (event.data.type === 'TARGET_RECTS') {
        const updates = event.data.payload?.rects ?? [];
        setReviewNotes((prev) => {
          let changed = false;
          const next = prev.map((note) => {
            const update = updates.find((item) => item.id === note.id && item.resolved && item.rect);
            if (!update?.rect) return note;
            if (note.target.type === 'element') {
              const current = note.target.rect;
              if (
                current.x === update.rect.x
                && current.y === update.rect.y
                && current.width === update.rect.width
                && current.height === update.rect.height
              ) {
                return note;
              }
              changed = true;
              return { ...note, target: { ...note.target, rect: update.rect, documentRect: update.documentRect } };
            }
            return note;
          });
          return changed ? next : prev;
        });
        return;
      }
      if (event.data.type === 'BRIDGE_ERROR') {
        setReviewErrorKey('workspace.canvas.webCanvas.review.errors.bridge');
      }
    };
    window.addEventListener('message', handleBridgeMessage);
    return () => window.removeEventListener('message', handleBridgeMessage);
  }, [bridgeInteractionPaused, reviewMode]);

  useEffect(() => {
    if (!bridgeReady) return;
    postBridgeCommand('SET_MODE', { mode: reviewMode });
    if (reviewMode === 'default') {
      setSelectedTarget(null);
    }
  }, [bridgeReady, reviewMode]);

  useEffect(() => {
    if (!bridgeReady) return;
    postBridgeCommand('SET_INTERACTION_PAUSED', { paused: bridgeInteractionPaused });
  }, [bridgeReady, bridgeInteractionPaused]);

  useEffect(() => {
    if (!bridgeReady || reviewMode !== 'select') return;
    postBridgeCommand('WATCH_TARGETS', { targets: watchedReviewTargets });
  }, [bridgeReady, reviewMode, watchedReviewTargets]);

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
    clearTransientReviewState();
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
      clearTransientReviewState();
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

  const toggleReviewMode = () => {
    setReviewMode((prev) => {
      const next = prev === 'select' ? 'default' : 'select';
      if (next === 'default') {
        postBridgeCommand('CLEAR_SELECTION');
        setSelectedTarget(null);
        setBridgeInteractionPaused(false);
      }
      return next;
    });
  };

  const handleCreateReviewNote = async () => {
    if (!workspaceRuntime.runtimeBaseUrl || !workspaceRuntime.workspaceId || !selectedTarget) {
      setReviewErrorKey('workspace.canvas.webCanvas.review.errors.missingTarget');
      return;
    }
    if (!reviewInstruction.trim()) {
      setReviewErrorKey('workspace.canvas.webCanvas.review.errors.emptyInstruction');
      return;
    }
    setIsReviewSaving(true);
    try {
      const note = await createCanvasReviewNote(
        workspaceRuntime.runtimeBaseUrl,
        workspaceRuntime.workspaceId,
        {
          routePath: selectedPath,
          canvasUrl: iframeSrc,
          target: selectedTarget,
          instruction: reviewInstruction.trim(),
        }
      );
      setReviewNotes((prev) => [...prev, note]);
      setSelectedTarget(null);
      setBridgeInteractionPaused(false);
      setReviewInstruction('');
      postBridgeCommand('CLEAR_SELECTION');
      toast({
        title: t('workspace.canvas.webCanvas.review.toast.createdTitle'),
        description: t('workspace.canvas.webCanvas.review.toast.createdDescription'),
        variant: 'success',
      });
    } catch (error) {
      logger.error('Failed to create Canvas review note', { error });
      setReviewErrorKey('workspace.canvas.webCanvas.review.errors.createFailed');
    } finally {
      setIsReviewSaving(false);
    }
  };

  const targetLabel = (target: CanvasReviewTarget) => {
    if (target.type === 'element') {
      return `${target.tagName} ${target.selector}`;
    }
    if (target.type === 'multi-element') {
      return t('workspace.canvas.webCanvas.review.target.multi', { count: target.elements.length });
    }
    return t('workspace.canvas.webCanvas.review.target.area');
  };

  const composeReviewPrompt = (note: CanvasReviewNote) => {
    const lines = [
      t('workspace.canvas.webCanvas.review.prompt.title'),
      '',
      `noteId: ${note.id}`,
      `routePath: ${note.routePath}`,
      `targetType: ${note.target.type}`,
      `instruction: ${note.instruction}`,
      '',
      t('workspace.canvas.webCanvas.review.prompt.workflow'),
    ];
    if (note.target.type === 'element') {
      lines.splice(5, 0, `selector: ${note.target.selector}`, `tagName: ${note.target.tagName}`, `textPreview: ${note.target.textPreview}`);
    } else if (note.target.type === 'multi-element') {
      lines.splice(5, 0, `elements: ${note.target.elements.map((item) => item.selector).join(', ')}`);
    } else {
      lines.splice(5, 0, `area: ${JSON.stringify(note.target.rect)}`);
    }
    return lines.join('\n');
  };

  const handoffReviewNote = async (note: CanvasReviewNote) => {
    dispatchInsertDraftEvent({
      content: composeReviewPrompt(note),
      mode: 'replace',
    });
    if (!workspaceRuntime.runtimeBaseUrl || !workspaceRuntime.workspaceId) return;
    try {
      const updated = await updateCanvasReviewNoteStatus(
        workspaceRuntime.runtimeBaseUrl,
        workspaceRuntime.workspaceId,
        note.id,
        'seen'
      );
      setReviewNotes((prev) => prev.map((item) => (item.id === note.id ? updated : item)));
    } catch (error) {
      logger.warn('Failed to mark Canvas review note as seen', { error });
    }
  };

  const updateReviewStatus = async (note: CanvasReviewNote, status: 'applied' | 'dismissed') => {
    if (!workspaceRuntime.runtimeBaseUrl || !workspaceRuntime.workspaceId) return;
    const updated = await updateCanvasReviewNoteStatus(
      workspaceRuntime.runtimeBaseUrl,
      workspaceRuntime.workspaceId,
      note.id,
      status
    );
    setReviewNotes((prev) => prev.map((item) => (item.id === note.id ? updated : item)));
  };

  const removeReviewNote = async (note: CanvasReviewNote) => {
    if (!workspaceRuntime.runtimeBaseUrl || !workspaceRuntime.workspaceId) return;
    await deleteCanvasReviewNote(workspaceRuntime.runtimeBaseUrl, workspaceRuntime.workspaceId, note.id);
    setReviewNotes((prev) => prev.filter((item) => item.id !== note.id));
  };

  const statusText = t(`workspace.canvas.webCanvas.types.${canvasType}`);
  const manifestText = t(`workspace.canvas.webCanvas.manifest.${manifestStatus}`);
  const showStatusNotice = (
    !isLoading
    && healthStatus !== 'checking'
    && healthStatus !== 'starting'
    && healthStatus !== 'unhealthy'
    && (canvasType === 'default' || manifestStatus === 'missing' || manifestStatus === 'invalid')
  );
  const statusNoticeDescriptionKey = manifestStatus === 'invalid'
    ? 'workspace.canvas.webCanvas.statusNotice.invalidManifestDescription'
    : manifestStatus === 'missing'
      ? 'workspace.canvas.webCanvas.statusNotice.missingManifestDescription'
      : 'workspace.canvas.webCanvas.statusNotice.defaultDescription';

  return (
    <div className={cn('flex h-full flex-col bg-background', isFullscreen && 'fixed inset-0 z-50 bg-background')}>
      <FeatureHeader
        title={t('workspace.canvas.webCanvas.title')}
        icon={Monitor}
        info={
          <div className="flex min-w-0 flex-1 items-center gap-2 pr-2" ref={dropdownRef}>
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
            {CANVAS_REVIEW_ENABLED && (
              <Button
                variant={reviewMode === 'select' ? 'secondary' : 'ghost'}
                size="icon"
                className="h-7 w-7"
                onClick={toggleReviewMode}
                disabled={!iframeSrc || isLoading}
                title={t('workspace.canvas.webCanvas.review.toolbar.toggle')}
                aria-label={t('workspace.canvas.webCanvas.review.toolbar.toggle')}
                aria-pressed={reviewMode === 'select'}
              >
                <Crosshair className="h-3.5 w-3.5" />
              </Button>
            )}
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
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-7 w-7"
                  title={t('workspace.canvas.header.actions.menu')}
                  aria-label={t('workspace.canvas.header.actions.menu')}
                >
                  <MoreHorizontal className="h-3.5 w-3.5" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem
                  disabled={isWorking}
                  onSelect={() => {
                    void handleAction('sync');
                  }}
                >
                  <RefreshCw className={cn('mr-2 h-3.5 w-3.5', isWorking && 'animate-spin')} />
                  {t('workspace.canvas.webCanvas.actions.sync.label')}
                </DropdownMenuItem>
                <DropdownMenuItem
                  disabled={isWorking}
                  onSelect={() => {
                    void handleAction('reset');
                  }}
                >
                  <SendToBack className="mr-2 h-3.5 w-3.5" />
                  {t('workspace.canvas.webCanvas.actions.reset.label')}
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
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

        {showStatusNotice && (
          <div
            className="pointer-events-none absolute left-4 top-4 z-[5] max-w-md rounded-md border bg-background/95 p-3 text-sm shadow-sm backdrop-blur"
            role="status"
          >
            <div className="flex items-start gap-2">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
              <div className="min-w-0 space-y-1">
                <div className="font-medium text-foreground">
                  {t('workspace.canvas.webCanvas.statusNotice.title')}
                </div>
                <div className="text-muted-foreground">
                  {t(statusNoticeDescriptionKey)}
                </div>
                <div className="text-xs text-muted-foreground">
                  {t('workspace.canvas.webCanvas.statusNotice.details', {
                    type: statusText,
                    manifest: manifestText,
                  })}
                </div>
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

        {CANVAS_REVIEW_ENABLED && reviewMode === 'select' && (
          <div className="pointer-events-none absolute inset-0 z-[6]">
            {!bridgeReady && (
              <div className="pointer-events-auto absolute right-4 top-4 rounded-md border bg-background/95 px-3 py-2 text-xs text-muted-foreground shadow-sm">
                {t('workspace.canvas.webCanvas.review.bridgeWaiting')}
              </div>
            )}

            {selectedTarget && getTargetRect(selectedTarget) && (
              <div
                className="absolute border-2 border-primary bg-primary/10 shadow-[0_0_0_1px_rgba(255,255,255,.9)]"
                style={{
                  left: getTargetRect(selectedTarget)?.x,
                  top: getTargetRect(selectedTarget)?.y,
                  width: getTargetRect(selectedTarget)?.width,
                  height: getTargetRect(selectedTarget)?.height,
                }}
              />
            )}

            {selectedTarget && (
              <div
                ref={reviewPanelRef}
                className="pointer-events-auto absolute right-4 top-4 w-[min(360px,calc(100%-2rem))] rounded-md border bg-background p-3 shadow-lg"
                onPointerEnter={() => setBridgeInteractionPaused(true)}
                onPointerLeave={() => {
                  if (!reviewPanelRef.current?.contains(document.activeElement)) {
                    setBridgeInteractionPaused(false);
                  }
                }}
                onFocusCapture={() => setBridgeInteractionPaused(true)}
                onBlurCapture={(event) => {
                  if (!event.currentTarget.contains(event.relatedTarget as Node | null)) {
                    setBridgeInteractionPaused(false);
                  }
                }}
              >
                <div className="mb-2 flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <div className="text-sm font-medium">{t('workspace.canvas.webCanvas.review.form.title')}</div>
                    <div className="truncate text-xs text-muted-foreground">{targetLabel(selectedTarget)}</div>
                  </div>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-7 w-7 shrink-0"
                    onClick={() => {
                      setSelectedTarget(null);
                      setBridgeInteractionPaused(false);
                      setReviewInstruction('');
                      postBridgeCommand('CLEAR_SELECTION');
                    }}
                    aria-label={t('workspace.canvas.webCanvas.review.form.close')}
                  >
                    <X className="h-3.5 w-3.5" />
                  </Button>
                </div>
                <textarea
                  value={reviewInstruction}
                  onChange={(event) => setReviewInstruction(event.target.value)}
                  placeholder={t('workspace.canvas.webCanvas.review.form.placeholder')}
                  className="min-h-24 w-full resize-none rounded-md border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
                />
                {reviewErrorKey && (
                  <div className="mt-2 text-xs text-destructive">{t(reviewErrorKey)}</div>
                )}
                <div className="mt-3 flex justify-end gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      setSelectedTarget(null);
                      setBridgeInteractionPaused(false);
                      setReviewInstruction('');
                      postBridgeCommand('CLEAR_SELECTION');
                    }}
                  >
                    {t('workspace.canvas.webCanvas.review.form.cancel')}
                  </Button>
                  <Button size="sm" disabled={isReviewSaving} onClick={() => void handleCreateReviewNote()}>
                    <MessageSquare className="mr-2 h-3.5 w-3.5" />
                    {t('workspace.canvas.webCanvas.review.form.create')}
                  </Button>
                </div>
              </div>
            )}

            {reviewNotes.filter((note) => note.status === 'open' || note.status === 'seen').map((note) => {
              const rect = getTargetRect(note.target);
              if (!rect) return null;
              return (
                <div
                  key={note.id}
                  className="pointer-events-auto absolute rounded border border-amber-500 bg-amber-500/10"
                  style={{ left: rect.x, top: rect.y, width: rect.width, height: rect.height }}
                  title={note.instruction}
                >
                  <div className="absolute left-0 top-0 -translate-y-full rounded-t-md bg-amber-500 px-2 py-1 text-[11px] font-medium text-white">
                    {t(`workspace.canvas.webCanvas.review.status.${note.status}`)}
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {CANVAS_REVIEW_ENABLED && reviewNotes.length > 0 && (
          <div
            className={cn(
              'absolute bottom-4 right-4 z-[7] w-[min(380px,calc(100%-2rem))] rounded-md border bg-background/95 p-3 shadow-lg backdrop-blur',
              reviewNotesExpanded && 'flex max-h-[42%] flex-col overflow-hidden'
            )}
          >
            <div className={cn('flex items-center justify-between gap-2', reviewNotesExpanded && 'mb-2')}>
              <div className="min-w-0 text-sm font-medium">
                {t('workspace.canvas.webCanvas.review.notes.title')}
                <span className="ml-1 text-xs font-normal text-muted-foreground">({reviewNotes.length})</span>
              </div>
              <Button
                variant="ghost"
                size="icon"
                className="h-7 w-7 shrink-0"
                onClick={() => setReviewNotesExpanded((prev) => !prev)}
                aria-expanded={reviewNotesExpanded}
                aria-label={t(
                  reviewNotesExpanded
                    ? 'workspace.canvas.webCanvas.review.notes.collapse'
                    : 'workspace.canvas.webCanvas.review.notes.expand'
                )}
                title={t(
                  reviewNotesExpanded
                    ? 'workspace.canvas.webCanvas.review.notes.collapse'
                    : 'workspace.canvas.webCanvas.review.notes.expand'
                )}
              >
                {reviewNotesExpanded ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronUp className="h-3.5 w-3.5" />}
              </Button>
            </div>
            {reviewNotesExpanded && (
              <div className="min-h-0 flex-1 space-y-2 overflow-y-auto pr-1">
                {reviewNotes.map((note) => (
                  <div key={note.id} className="rounded-md border p-2 text-xs">
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <div className="font-medium">{targetLabel(note.target)}</div>
                        <div className="mt-1 line-clamp-2 text-muted-foreground">{note.instruction}</div>
                      </div>
                      <div className="shrink-0 text-muted-foreground">
                        {t(`workspace.canvas.webCanvas.review.status.${note.status}`)}
                      </div>
                    </div>
                    <div className="mt-2 flex flex-wrap gap-1">
                      <Button variant="outline" size="sm" className="h-7 px-2 text-xs" onClick={() => void handoffReviewNote(note)}>
                        <MessageSquare className="mr-1 h-3 w-3" />
                        {t('workspace.canvas.webCanvas.review.notes.sendToAi')}
                      </Button>
                      <Button variant="outline" size="icon" className="h-7 w-7" onClick={() => void updateReviewStatus(note, 'applied')} aria-label={t('workspace.canvas.webCanvas.review.notes.apply')}>
                        <Check className="h-3 w-3" />
                      </Button>
                      <Button variant="outline" size="icon" className="h-7 w-7" onClick={() => void updateReviewStatus(note, 'dismissed')} aria-label={t('workspace.canvas.webCanvas.review.notes.dismiss')}>
                        <X className="h-3 w-3" />
                      </Button>
                      <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => void removeReviewNote(note)} aria-label={t('workspace.canvas.webCanvas.review.notes.delete')}>
                        <Trash2 className="h-3 w-3" />
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default WebCanvasFeature;
