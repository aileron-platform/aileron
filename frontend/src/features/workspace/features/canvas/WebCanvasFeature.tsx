import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  AlertTriangle,
  ChevronDown,
  ChevronUp,
  Crosshair,
  GripHorizontal,
  Maximize2,
  MessageSquare,
  Minimize2,
  Monitor,
  RefreshCw,
  Trash2,
  X,
} from 'lucide-react';

import { FeatureHeader } from '@/shared/components/layout/FeatureHeader';
import { Button } from '@/shared/components/ui/button';
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
  syncCanvas,
  updateCanvasReviewNoteStatus,
  type CanvasRoute,
  type CanvasReviewNote,
  type CanvasReviewTarget,
} from '../../services/workspaceRuntimeApi';
import {
  AILERON_CANVAS_BRIDGE_SOURCE,
  AILERON_CANVAS_BRIDGE_VERSION,
  createAileronCanvasBridgeMessageHandler,
} from './lib/aileronCanvasBridgeClient';

const logger = createLogger('WebCanvas');
const CANVAS_REVIEW_ENABLED = import.meta.env.VITE_ENABLE_CANVAS_REVIEW !== 'false';

type BridgeMode = 'default' | 'select';
type CanvasResolvedTheme = 'light' | 'dark';

const getTargetRect = (target: CanvasReviewTarget | null | undefined) => target?.rect ?? null;
const getResolvedCanvasTheme = (): CanvasResolvedTheme => (
  typeof document !== 'undefined' && document.documentElement.classList.contains('dark') ? 'dark' : 'light'
);

type ReviewPanelPosition = {
  x: number;
  y: number;
};

type ReviewPanelDragState = {
  pointerId: number;
  startX: number;
  startY: number;
  panelX: number;
  panelY: number;
};

const normalizeBridgeRoutePath = (routePath: unknown): string | null => {
  if (typeof routePath !== 'string') return null;
  const trimmed = routePath.trim();
  if (!trimmed || trimmed.length > 512) return null;
  return trimmed.startsWith('/') ? trimmed : `/${trimmed}`;
};

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
  const [manifestStatus, setManifestStatus] = useState<string>('missing');
  const [runtimeStatus, setRuntimeStatus] = useState<string>('unhealthy');
  const [canvasTitle, setCanvasTitle] = useState<string | null>(null);
  const [canvasOwner, setCanvasOwner] = useState<{ skillName?: string | null } | null>(null);
  const [reviewMode, setReviewMode] = useState<BridgeMode>('default');
  const [bridgeReady, setBridgeReady] = useState(false);
  const [selectedTarget, setSelectedTarget] = useState<CanvasReviewTarget | null>(null);
  const [bridgeInteractionPaused, setBridgeInteractionPaused] = useState(false);
  const [reviewInstruction, setReviewInstruction] = useState('');
  const [reviewNotes, setReviewNotes] = useState<CanvasReviewNote[]>([]);
  const [reviewNotesExpanded, setReviewNotesExpanded] = useState(true);
  const [reviewErrorKey, setReviewErrorKey] = useState<string | null>(null);
  const [isReviewSaving, setIsReviewSaving] = useState(false);
  const [reviewPanelPosition, setReviewPanelPosition] = useState<ReviewPanelPosition | null>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const reviewPanelRef = useRef<HTMLDivElement>(null);
  const reviewPanelDragRef = useRef<ReviewPanelDragState | null>(null);
  const pendingReviewNotes = useMemo(
    () => reviewNotes.filter((note) => note.status === 'open'),
    [reviewNotes]
  );
  const watchedReviewTargets = useMemo(
    () => pendingReviewNotes
      .filter((note) => note.target.type === 'element')
      .map((note) => ({
        id: note.id,
        selector: note.target.type === 'element' ? note.target.selector : '',
      }))
      .filter((item) => item.selector),
    [pendingReviewNotes]
  );
  const postBridgeCommand = useCallback((type: string, payload: Record<string, unknown> = {}) => {
    iframeRef.current?.contentWindow?.postMessage({
      source: AILERON_CANVAS_BRIDGE_SOURCE,
      version: AILERON_CANVAS_BRIDGE_VERSION,
      type,
      payload,
    }, '*');
  }, []);

  const postCanvasTheme = useCallback(() => {
    postBridgeCommand('SET_THEME', { theme: getResolvedCanvasTheme() });
  }, [postBridgeCommand]);

  const clearTransientReviewState = () => {
    setBridgeReady(false);
    setSelectedTarget(null);
    setBridgeInteractionPaused(false);
    setReviewInstruction('');
    setReviewErrorKey(null);
  };

  const clampReviewPanelPosition = (x: number, y: number): ReviewPanelPosition => {
    const panel = reviewPanelRef.current;
    const container = panel?.parentElement;
    if (!panel || !container) {
      return { x, y };
    }
    const containerRect = container.getBoundingClientRect();
    const panelRect = panel.getBoundingClientRect();
    return {
      x: Math.max(0, Math.min(x, containerRect.width - panelRect.width)),
      y: Math.max(0, Math.min(y, containerRect.height - panelRect.height)),
    };
  };

  const handleReviewPanelDragStart = (event: React.PointerEvent<HTMLDivElement>) => {
    if (event.button > 0) return;
    const panel = reviewPanelRef.current;
    const container = panel?.parentElement;
    if (!panel || !container) return;
    const panelRect = panel.getBoundingClientRect();
    const containerRect = container.getBoundingClientRect();
    const panelPosition = {
      x: panelRect.left - containerRect.left,
      y: panelRect.top - containerRect.top,
    };
    reviewPanelDragRef.current = {
      pointerId: event.pointerId,
      startX: event.clientX,
      startY: event.clientY,
      panelX: panelPosition.x,
      panelY: panelPosition.y,
    };
    setReviewPanelPosition(clampReviewPanelPosition(panelPosition.x, panelPosition.y));
    setBridgeInteractionPaused(true);
    event.currentTarget.setPointerCapture?.(event.pointerId);
    event.preventDefault();
  };

  const handleReviewPanelDragMove = (event: React.PointerEvent<HTMLDivElement>) => {
    const dragState = reviewPanelDragRef.current;
    if (!dragState || dragState.pointerId !== event.pointerId) return;
    setReviewPanelPosition(clampReviewPanelPosition(
      dragState.panelX + event.clientX - dragState.startX,
      dragState.panelY + event.clientY - dragState.startY
    ));
  };

  const handleReviewPanelDragEnd = (event: React.PointerEvent<HTMLDivElement>) => {
    const dragState = reviewPanelDragRef.current;
    if (!dragState || dragState.pointerId !== event.pointerId) return;
    reviewPanelDragRef.current = null;
    if (event.currentTarget.hasPointerCapture?.(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
  };

  const handleReviewPanelDragKeyDown = (event: React.KeyboardEvent<HTMLDivElement>) => {
    const step = event.shiftKey ? 24 : 8;
    const movement: Record<string, ReviewPanelPosition> = {
      ArrowDown: { x: 0, y: step },
      ArrowLeft: { x: -step, y: 0 },
      ArrowRight: { x: step, y: 0 },
      ArrowUp: { x: 0, y: -step },
    };
    const delta = movement[event.key];
    if (!delta) return;
    event.preventDefault();
    const panel = reviewPanelRef.current;
    const container = panel?.parentElement;
    if (!panel || !container) return;
    const panelRect = panel.getBoundingClientRect();
    const containerRect = container.getBoundingClientRect();
    const current = reviewPanelPosition ?? {
      x: panelRect.left - containerRect.left,
      y: panelRect.top - containerRect.top,
    };
    setReviewPanelPosition(clampReviewPanelPosition(current.x + delta.x, current.y + delta.y));
  };

  const syncRouteFromBridge = useCallback((routePath: unknown, options: { resetReviewState?: boolean } = {}) => {
    const normalized = normalizeBridgeRoutePath(routePath);
    if (!normalized) return;
    const routeChanged = selectedPath !== normalized;
    setSelectedPath((current) => (current === normalized ? current : normalized));
    setFilteredRoutes(routes.filter((route) => route.path.toLowerCase().includes(normalized.toLowerCase())));
    setShowDropdown(false);
    if (routeChanged && options.resetReviewState !== false) {
      setSelectedTarget(null);
      setBridgeInteractionPaused(false);
      setReviewInstruction('');
    }
    setReviewErrorKey(null);
  }, [routes, selectedPath]);

  const buildCanvasUrl = (path: string, urlBase = baseUrl) => {
    const nextUrl = new URL(path || '/', `${urlBase}/`);
    nextUrl.searchParams.set('lang', state.currentLanguage);
    return nextUrl.toString();
  };

  const reloadIframe = (src = iframeSrc) => {
    if (!iframeRef.current || !src) {
      return;
    }
    clearTransientReviewState();
    iframeRef.current.src = 'about:blank';
    window.setTimeout(() => {
      if (iframeRef.current) {
        iframeRef.current.src = src;
      }
    }, 100);
  };

  const loadCanvasData = async (preferredPath?: string) => {
    if (!workspaceRuntime.workspaceId || !workspaceRuntime.runtimeBaseUrl) {
      setIsLoading(false);
      return undefined;
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
      setManifestStatus(routesData.manifestStatus);
      setRuntimeStatus(routesData.runtimeStatus ?? 'unhealthy');
      setCanvasTitle(routesData.title ?? null);
      setCanvasOwner(routesData.owner ?? null);

      const availablePaths = new Set(routesData.routes.map((route) => route.path));
      const defaultPath = routesData.defaultPath || routesData.routes[0]?.path || '/';
      const nextPath = preferredPath && (availablePaths.size === 0 || availablePaths.has(preferredPath))
        ? preferredPath
        : defaultPath;
      setSelectedPath(nextPath);
      setFilteredRoutes(routesData.routes.filter((route) => route.path.toLowerCase().includes(nextPath.toLowerCase())));
      let nextIframeSrc: string | undefined;
      if (canvasUrl) {
        nextIframeSrc = buildCanvasUrl(nextPath, canvasUrl);
        setIframeSrc(nextIframeSrc);
      }

      const health = await checkCanvasHealth(
        workspaceRuntime.runtimeBaseUrl,
        workspaceRuntime.workspaceId
      );
      setHealthStatus(health.status);
      setHealthMessage(health.message || '');
      if (health.manifestStatus) {
        setManifestStatus(health.manifestStatus);
      }
      if (health.runtimeStatus) {
        setRuntimeStatus(health.runtimeStatus);
      }
      await loadReviewNotes(nextPath);
      return nextIframeSrc;
    } catch (error) {
      logger.error('Failed to load Web Canvas data', { error });
      setHealthStatus('unhealthy');
      setHealthMessage(error instanceof Error ? error.message : '');
    } finally {
      setIsLoading(false);
    }
    return undefined;
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
      createAileronCanvasBridgeMessageHandler(iframeRef.current, {
        onBridgeReady: (payload) => {
          syncRouteFromBridge(payload?.routePath);
          setBridgeReady(true);
          postCanvasTheme();
          postBridgeCommand('SET_MODE', { mode: reviewMode });
          postBridgeCommand('SET_INTERACTION_PAUSED', { paused: bridgeInteractionPaused });
        },
        onRouteChanged: (payload) => {
          syncRouteFromBridge(payload?.routePath);
        },
        onTargetSelected: (payload) => {
          syncRouteFromBridge(payload?.routePath);
          const target = payload?.target;
          setSelectedTarget(target ?? null);
          setReviewInstruction('');
          setReviewErrorKey(null);
        },
        onTargetRects: (payload) => {
          syncRouteFromBridge(payload?.routePath, { resetReviewState: false });
          const updates = payload?.rects ?? [];
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
        },
        onBridgeError: () => {
          setReviewErrorKey('workspace.canvas.webCanvas.review.errors.bridge');
        },
      })(event);
    };
    window.addEventListener('message', handleBridgeMessage);
    return () => window.removeEventListener('message', handleBridgeMessage);
  }, [bridgeInteractionPaused, postBridgeCommand, postCanvasTheme, reviewMode, syncRouteFromBridge]);

  useEffect(() => {
    if (typeof document === 'undefined') return;
    const root = document.documentElement;
    const observer = new MutationObserver(() => {
      postCanvasTheme();
    });
    observer.observe(root, { attributes: true, attributeFilter: ['class'] });
    postCanvasTheme();
    return () => observer.disconnect();
  }, [postCanvasTheme]);

  useEffect(() => {
    if (!bridgeReady) return;
    postBridgeCommand('SET_MODE', { mode: reviewMode });
    if (reviewMode === 'default') {
      setSelectedTarget(null);
    }
  }, [bridgeReady, postBridgeCommand, reviewMode]);

  useEffect(() => {
    if (!bridgeReady) return;
    postBridgeCommand('SET_INTERACTION_PAUSED', { paused: bridgeInteractionPaused });
  }, [bridgeReady, bridgeInteractionPaused, postBridgeCommand]);

  useEffect(() => {
    if (!bridgeReady || reviewMode !== 'select') return;
    postBridgeCommand('WATCH_TARGETS', { targets: watchedReviewTargets });
  }, [bridgeReady, postBridgeCommand, reviewMode, watchedReviewTargets]);

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

  const handleSyncCanvas = async () => {
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
      const syncResult = await syncCanvas(workspaceRuntime.runtimeBaseUrl, workspaceRuntime.workspaceId);
      const currentPath = selectedPath;
      const nextSrc = buildCanvasUrl(currentPath);
      if (syncResult.rendererAction === 'reused') {
        const loadedSrc = await loadCanvasData(currentPath);
        if (syncResult.manifestStatus) {
          setManifestStatus(syncResult.manifestStatus);
        }
        if (syncResult.runtimeStatus) {
          setRuntimeStatus(syncResult.runtimeStatus);
        }
        setHealthStatus('healthy');
        setHealthMessage(syncResult.message || '');
        reloadIframe(loadedSrc || nextSrc);
      } else {
        const loadedSrc = await loadCanvasData(currentPath);
        reloadIframe(loadedSrc || nextSrc);
      }
      toast({
        title: t('workspace.canvas.webCanvas.actions.sync.successTitle'),
        description: t('workspace.canvas.webCanvas.actions.sync.successDescription'),
        variant: 'success',
      });
    } catch (error) {
      toast({
        title: t('workspace.canvas.webCanvas.actions.sync.errorTitle'),
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
          canvasUrl: buildCanvasUrl(selectedPath),
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

  const composeReviewNotePayload = (note: CanvasReviewNote) => {
    const lines = [
      `noteId: ${note.id}`,
      `routePath: ${note.routePath}`,
      `targetType: ${note.target.type}`,
      `instruction: ${note.instruction}`,
    ];
    if (note.target.type === 'element') {
      lines.splice(3, 0, `selector: ${note.target.selector}`, `tagName: ${note.target.tagName}`, `textPreview: ${note.target.textPreview}`);
    } else if (note.target.type === 'multi-element') {
      lines.splice(3, 0, `elements: ${note.target.elements.map((item) => item.selector).join(', ')}`);
    } else {
      lines.splice(3, 0, `area: ${JSON.stringify(note.target.rect)}`);
    }
    return lines.join('\n');
  };

  const composeReviewBatchPrompt = (notes: CanvasReviewNote[]) => {
    return [
      '/canvas-review',
      '',
      ...notes.flatMap((note, index) => [
        `#${index + 1}`,
        composeReviewNotePayload(note),
        '',
      ]),
    ].join('\n').trim();
  };

  const handoffReviewNote = async (note: CanvasReviewNote) => {
    dispatchInsertDraftEvent({
      content: composeReviewBatchPrompt([note]),
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

  const handoffPendingReviewNotes = async () => {
    if (pendingReviewNotes.length === 0) return;
    dispatchInsertDraftEvent({
      content: composeReviewBatchPrompt(pendingReviewNotes),
      mode: 'replace',
    });
    if (!workspaceRuntime.runtimeBaseUrl || !workspaceRuntime.workspaceId) return;
    try {
      const updatedNotes = await Promise.all(
        pendingReviewNotes.map((note) => updateCanvasReviewNoteStatus(
          workspaceRuntime.runtimeBaseUrl,
          workspaceRuntime.workspaceId,
          note.id,
          'seen'
        ))
      );
      const updatedById = new Map(updatedNotes.map((note) => [note.id, note]));
      setReviewNotes((prev) => prev.map((item) => updatedById.get(item.id) ?? item));
    } catch (error) {
      logger.warn('Failed to mark Canvas review notes as seen', { error });
    }
  };

  const removeReviewNote = async (note: CanvasReviewNote) => {
    if (!workspaceRuntime.runtimeBaseUrl || !workspaceRuntime.workspaceId) return;
    await deleteCanvasReviewNote(workspaceRuntime.runtimeBaseUrl, workspaceRuntime.workspaceId, note.id);
    setReviewNotes((prev) => prev.filter((item) => item.id !== note.id));
  };

  const statusNoticeTitleKey = manifestStatus === 'valid'
    ? canvasOwner?.skillName
      ? 'workspace.canvas.webCanvas.manifest.statusNotice.skill.title'
      : 'workspace.canvas.webCanvas.manifest.statusNotice.user.title'
    : manifestStatus === 'invalid'
      ? 'workspace.canvas.webCanvas.manifest.errors.invalid.title'
      : 'workspace.canvas.webCanvas.default.guidance.title';
  const statusNoticeDescriptionKey = manifestStatus === 'valid'
    ? canvasOwner?.skillName
      ? 'workspace.canvas.webCanvas.manifest.statusNotice.skill.description'
      : 'workspace.canvas.webCanvas.manifest.statusNotice.user.description'
    : manifestStatus === 'invalid'
      ? 'workspace.canvas.webCanvas.manifest.errors.invalid.description'
      : 'workspace.canvas.webCanvas.default.guidance.description';
  const showStatusNotice = (
    !isLoading
    && healthStatus !== 'checking'
    && healthStatus !== 'starting'
    && healthStatus !== 'unhealthy'
    && manifestStatus !== 'valid'
  );

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
              size="sm"
              className="h-7 gap-1.5 px-2 text-xs"
              onClick={() => {
                void handleSyncCanvas();
              }}
              disabled={isWorking}
              title={t('workspace.canvas.webCanvas.actions.sync.label')}
            >
              <RefreshCw className={cn('h-3.5 w-3.5', isWorking && 'animate-spin')} />
              {t('workspace.canvas.webCanvas.actions.sync.label')}
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

        {showStatusNotice && (
          <div
            className="pointer-events-none absolute left-4 top-4 z-[5] max-w-md rounded-md border bg-background/95 p-3 text-sm shadow-sm backdrop-blur"
            role="status"
          >
            <div className="flex items-start gap-2">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
              <div className="min-w-0 space-y-1">
                <div className="font-medium text-foreground">
                  {t(statusNoticeTitleKey, {
                    title: canvasTitle ?? '',
                    skillName: canvasOwner?.skillName ?? '',
                  })}
                </div>
                <div className="text-muted-foreground">
                  {t(statusNoticeDescriptionKey, {
                    title: canvasTitle ?? '',
                    skillName: canvasOwner?.skillName ?? '',
                  })}
                </div>
                <div className="text-xs text-muted-foreground">
                  {t('workspace.canvas.webCanvas.manifest.statusNotice.details', {
                    manifest: t(`workspace.canvas.webCanvas.manifest.status.${manifestStatus}`),
                    runtime: runtimeStatus === 'starting'
                      ? t('workspace.canvas.webCanvas.runtime.starting')
                      : runtimeStatus === 'unhealthy'
                        ? t('workspace.canvas.webCanvas.runtime.errors.startupFailed')
                        : t('workspace.canvas.webCanvas.runtime.healthy'),
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
          onLoad={postCanvasTheme}
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
                className="pointer-events-auto absolute w-[min(360px,calc(100%-2rem))] rounded-md border bg-background p-3 shadow-lg"
                style={reviewPanelPosition
                  ? { left: reviewPanelPosition.x, top: reviewPanelPosition.y }
                  : { right: 16, top: 16 }}
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
                  <div
                    className="flex min-w-0 flex-1 cursor-move touch-none items-start gap-2"
                    onPointerDown={handleReviewPanelDragStart}
                    onPointerMove={handleReviewPanelDragMove}
                    onPointerUp={handleReviewPanelDragEnd}
                    onPointerCancel={handleReviewPanelDragEnd}
                    onKeyDown={handleReviewPanelDragKeyDown}
                    role="button"
                    tabIndex={0}
                    aria-label={t('workspace.canvas.webCanvas.review.form.dragHandle')}
                  >
                    <GripHorizontal className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
                    <div className="min-w-0">
                      <div className="text-sm font-medium">{t('workspace.canvas.webCanvas.review.form.title')}</div>
                      <div className="truncate text-xs text-muted-foreground">{targetLabel(selectedTarget)}</div>
                    </div>
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

            {pendingReviewNotes.map((note) => {
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

        {CANVAS_REVIEW_ENABLED && pendingReviewNotes.length > 0 && (
          <div
            className={cn(
              'absolute bottom-4 right-4 z-[7] w-[min(380px,calc(100%-2rem))] rounded-md border bg-background/95 p-3 shadow-lg backdrop-blur',
              reviewNotesExpanded && 'flex max-h-[42%] flex-col overflow-hidden'
            )}
          >
            <div className={cn('flex items-center justify-between gap-2', reviewNotesExpanded && 'mb-2')}>
              <div className="flex min-w-0 items-center gap-2 text-sm font-medium">
                <MessageSquare className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                <span className="min-w-0 truncate">
                  {t('workspace.canvas.webCanvas.review.notes.title')}
                  <span className="ml-1 text-xs font-normal text-muted-foreground">({pendingReviewNotes.length})</span>
                </span>
              </div>
              <div className="flex shrink-0 items-center gap-1">
                <Button
                  variant="outline"
                  size="sm"
                  className="h-7 px-2 text-xs"
                  onClick={() => void handoffPendingReviewNotes()}
                  aria-label={t('workspace.canvas.webCanvas.review.notes.sendAllToAi')}
                >
                  <MessageSquare className="mr-1 h-3 w-3" />
                  {t('workspace.canvas.webCanvas.review.notes.sendAllToAi')}
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-7 w-7"
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
            </div>
            {reviewNotesExpanded && (
              <div className="min-h-0 flex-1 space-y-2 overflow-y-auto pr-1">
                {pendingReviewNotes.map((note) => (
                  <div key={note.id} className="rounded-md border p-2 text-xs">
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <div className="font-medium">{targetLabel(note.target)}</div>
                        <div className="mt-1 line-clamp-2 text-muted-foreground">{note.instruction}</div>
                      </div>
                    </div>
                    <div className="mt-2 flex flex-wrap justify-end gap-1">
                      <Button variant="outline" size="sm" className="h-7 px-2 text-xs" onClick={() => void handoffReviewNote(note)}>
                        <MessageSquare className="mr-1 h-3 w-3" />
                        {t('workspace.canvas.webCanvas.review.notes.sendToAi')}
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
