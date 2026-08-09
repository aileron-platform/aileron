/**
 * TerminalPanel - Shared full and compact terminal component
 */

import React, { useCallback, useEffect, useMemo, useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Plus,
  SquareTerminal,
  Copy,
  Clipboard,
  RotateCcw,
  Maximize2,
  Minimize2,
  MoreVertical,
  ExternalLink,
  Moon,
  Sun,
  PanelBottom,
  PanelRight,
} from 'lucide-react';
import { Panel, PanelGroup, PanelResizeHandle } from 'react-resizable-panels';

import { FeatureHeader } from '@/shared/components/layout/FeatureHeader';
import { WorkspaceStatusBar } from '@/shared/components/layout/WorkspaceStatusBar';
import { Button } from '@/shared/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/shared/components/ui/dropdown-menu';
import { useToast } from '@/shared/components/ui/use-toast';
import { useI18n } from '@/shared/hooks/useI18n';
import { cn } from '@/shared/utils/cn';
import { createLogger } from '@/shared/services/logger';
import { ROUTES } from '@/shared/constants/routes';

const logger = createLogger('TerminalPanel');

import { useWorkspace } from '../../../providers/WorkspaceProvider';
import { useTerminalStream } from '@/features/workspace/realtime/useTerminalStream';
import { useWorkspaceVersionControlSession } from '../../../integrations/version-control/workspaceVersionControlSession';
import { TerminalTab } from './TerminalTab';
import type { TerminalResolvedTheme } from '../../../realtime/terminalInstanceRegistry';
import { TerminalLayoutSelector } from './TerminalLayoutSelector';
import {
  LAYOUT_DEFINITIONS,
  getPaneCount,
  type LayoutNode,
  type TerminalLayoutType,
} from '../model/terminalLayoutModel';
import { TERMINAL_MAX_TABS } from '../../../realtime/terminalPolicy';
import { TerminalTabBar } from './TerminalTabBar';
import { resolveDefaultTerminalWorkspacePath } from '../model/terminalContextModel';
import { getTerminalTabTitle } from '../model/terminalTabModel';
import {
  TerminalContextMenu,
  ContextMenuState,
  INITIAL_CONTEXT_MENU_STATE,
} from './TerminalContextMenu';

type PaneSize = { cols: number; rows: number };

export type TerminalPanelVariant = 'full' | 'compact';
type TerminalPanelPlacement = 'side' | 'bottom';
type TerminalThemePreference = TerminalResolvedTheme | null;

export interface TerminalPanelProps {
  variant?: TerminalPanelVariant;
  terminalPlacement?: TerminalPanelPlacement;
  onTerminalPlacementChange?: (placement: TerminalPanelPlacement) => void;
}

const resolveSystemTerminalTheme = (): TerminalResolvedTheme => (
  typeof document !== 'undefined' && document.documentElement.classList.contains('dark')
    ? 'dark'
    : 'light'
);

const TERMINAL_THEME_STORAGE_KEY = 'workspace.terminal.theme';

const isTerminalTheme = (value: string | null): value is TerminalResolvedTheme => (
  value === 'light' || value === 'dark'
);

const readStoredTerminalTheme = (): TerminalThemePreference => {
  if (typeof window === 'undefined') return null;
  try {
    const storedTheme = window.localStorage.getItem(TERMINAL_THEME_STORAGE_KEY);
    return isTerminalTheme(storedTheme) ? storedTheme : null;
  } catch (error) {
    logger.warn('Unable to read terminal theme preference', { error });
    return null;
  }
};

const storeTerminalTheme = (theme: TerminalResolvedTheme) => {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.setItem(TERMINAL_THEME_STORAGE_KEY, theme);
  } catch (error) {
    logger.warn('Unable to store terminal theme preference', { error });
  }
};

const useSystemTerminalTheme = () => {
  const [systemTheme, setSystemTheme] = useState<TerminalResolvedTheme>(() => resolveSystemTerminalTheme());

  useEffect(() => {
    if (typeof document === 'undefined' || typeof MutationObserver === 'undefined') {
      return undefined;
    }

    const updateTheme = () => setSystemTheme(resolveSystemTerminalTheme());
    const observer = new MutationObserver(updateTheme);
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ['class'],
    });
    updateTheme();

    return () => observer.disconnect();
  }, []);

  return systemTheme;
};

const TerminalThemeSelector = ({
  value,
  onChange,
  labels,
}: {
  value: TerminalResolvedTheme;
  onChange: (value: TerminalResolvedTheme) => void;
  labels: {
    label: string;
    light: string;
    dark: string;
  };
}) => {
  const options: Array<{
    value: TerminalResolvedTheme;
    label: string;
    icon: React.ComponentType<{ className?: string; 'aria-hidden'?: boolean | 'true' | 'false' }>;
  }> = [
    { value: 'light', label: labels.light, icon: Sun },
    { value: 'dark', label: labels.dark, icon: Moon },
  ];

  return (
    <div
      aria-label={labels.label}
      className="flex h-7 shrink-0 items-center rounded-md border border-border bg-background p-0.5"
    >
      {options.map(({ value: optionValue, label, icon: Icon }) => (
        <button
          key={optionValue}
          type="button"
          aria-label={label}
          aria-pressed={value === optionValue}
          title={label}
          className={cn(
            'inline-flex h-6 w-6 items-center justify-center rounded text-muted-foreground hover:bg-muted hover:text-foreground',
            value === optionValue && 'bg-muted text-foreground',
          )}
          onClick={() => onChange(optionValue)}
        >
          <Icon className="h-3.5 w-3.5" aria-hidden="true" />
        </button>
      ))}
    </div>
  );
};

export const TerminalPanel: React.FC<TerminalPanelProps> = ({
  variant = 'full',
  terminalPlacement = 'side',
  onTerminalPlacementChange,
}) => {
  const isCompact = variant === 'compact';
  const isBottomPlacement = terminalPlacement === 'bottom';
  const { t } = useI18n();
  const navigate = useNavigate();
  const systemTerminalTheme = useSystemTerminalTheme();
  const [terminalThemePreference, setTerminalThemePreference] = useState<TerminalThemePreference>(() =>
    readStoredTerminalTheme(),
  );
  const resolvedTerminalTheme = terminalThemePreference ?? systemTerminalTheme;
  const { workspaceRuntime, state: workspaceState } = useWorkspace();
  const {
    state: terminalState,
    ensureConnected,
    ensureDefaultTab,
    createTab,
    closeTab,
    switchTab,
    sendInput,
    sendResize,
    attachXterm,
    clearTerminal,
  } = useTerminalStream();
  const { toast } = useToast();
  const versionControl = useWorkspaceVersionControlSession({
    workspaceId: workspaceRuntime.workspaceId ?? '',
    runtimeBaseUrl: workspaceRuntime.runtimeBaseUrl ?? '',
  });
  const { data: gitContextsResponse } = versionControl.history.useContextsQuery();

  const [isFullscreen, setIsFullscreen] = useState(false);
  const [selectedText, setSelectedText] = useState('');
  const [contextMenu, setContextMenu] = useState<ContextMenuState>(
    INITIAL_CONTEXT_MENU_STATE,
  );
  const [terminalSize, setTerminalSize] = useState({ cols: 0, rows: 0 });

  const defaultWorkspacePath = useMemo(() => {
    return resolveDefaultTerminalWorkspacePath(
      gitContextsResponse?.contexts,
      workspaceState.versionControl.selectedGitContextId,
    );
  }, [gitContextsResponse?.contexts, workspaceState.versionControl.selectedGitContextId]);

  // Layout State
  const [layout, setLayout] = useState<TerminalLayoutType>('single');
  const [activePaneIndex, setActivePaneIndex] = useState(0);
  // Maps pane index to tabId (or null if empty)
  const [paneMapping, setPaneMapping] = useState<(string | null)[]>([]);

  // Track the pane index where a new terminal was requested
  const pendingPaneIndexRef = useRef<number | null>(null);
  const prevLayoutRef = useRef<TerminalLayoutType>('single');
  const paneSizeMapRef = useRef<Map<number, PaneSize>>(new Map());
  const setActivePane = useCallback(
    (index: number) => {
      setActivePaneIndex((prev) => (prev === index ? prev : index));
    },
    [],
  );

  const layoutPaneCount = useMemo(() => getPaneCount(layout), [layout]);

  const tabLabels = useMemo(
    () => ({
      add: t('workspace.containerManagement.terminal.tabs.add'),
      empty: t('workspace.containerManagement.terminal.tabs.empty'),
      newTooltip: t('workspace.containerManagement.terminal.tabs.new'),
      close: t('workspace.containerManagement.terminal.tabs.close'),
      scrollLeft: t('workspace.containerManagement.terminal.tabs.scrollLeft'),
      scrollRight: t('workspace.containerManagement.terminal.tabs.scrollRight'),
    }),
    [t],
  );

  const menuLabels = useMemo(
    () => ({
      actionsTitle: t('workspace.containerManagement.terminal.menus.actions'),
      switchTitle: t('workspace.containerManagement.terminal.menus.context.switch'),
      unassign: t('workspace.containerManagement.terminal.menus.context.unassign'),
      copy: t('workspace.containerManagement.terminal.actions.copy'),
      paste: t('workspace.containerManagement.terminal.actions.paste'),
      restart: t('workspace.containerManagement.terminal.actions.restart'),
      fullscreenEnter: t('workspace.containerManagement.terminal.actions.enterFullscreen'),
      fullscreenExit: t('workspace.containerManagement.terminal.actions.exitFullscreen'),
      contextClear: t('workspace.containerManagement.terminal.menus.context.clear'),
      contextClose: t('workspace.containerManagement.terminal.menus.context.close'),
      active: t('workspace.containerManagement.terminal.tabs.active'),
      maxLimitTitle: t('workspace.containerManagement.terminal.limits.max.title'),
      maxLimitDescription: t('workspace.containerManagement.terminal.limits.max.description', {
        count: TERMINAL_MAX_TABS,
      }),
    }),
    [t],
  );

  const statusBarLabels = useMemo(
    () => ({
      rows: t('workspace.containerManagement.terminal.footer.rows', {
        count: terminalSize.rows,
      }),
      cols: t('workspace.containerManagement.terminal.footer.columns', {
        count: terminalSize.cols,
      }),
      encoding: t('workspace.containerManagement.terminal.footer.encoding'),
      selected: selectedText
        ? t('workspace.containerManagement.terminal.footer.selection', {
          count: selectedText.length,
        })
        : '',
    }),
    [t, terminalSize.rows, terminalSize.cols, selectedText],
  );

  const themeLabels = useMemo(
    () => ({
      label: t('workspace.containerManagement.terminal.theme.label'),
      light: t('workspace.containerManagement.terminal.theme.options.light'),
      dark: t('workspace.containerManagement.terminal.theme.options.dark'),
    }),
    [t],
  );

  const handleTerminalThemeChange = useCallback((theme: TerminalResolvedTheme) => {
    setTerminalThemePreference(theme);
    storeTerminalTheme(theme);
  }, []);

  const getPaneSize = useCallback((paneIndex: number): PaneSize | undefined => {
    const paneSize = paneSizeMapRef.current.get(paneIndex);
    if (paneSize && paneSize.cols > 0 && paneSize.rows > 0) return paneSize;
    if (terminalSize.cols > 0 && terminalSize.rows > 0) return terminalSize;
    return undefined;
  }, [terminalSize]);

  // Auto-connect without taking ownership of the shared socket lifecycle.
  useEffect(() => {
    if (workspaceRuntime.workspaceId && workspaceRuntime.runtimeBaseUrl) {
      ensureConnected();
    }
  }, [workspaceRuntime.workspaceId, workspaceRuntime.runtimeBaseUrl, ensureConnected]);

  const reconcilePaneMapping = useCallback(
    (prevMapping: (string | null)[]) => {
      const neededPanes = layoutPaneCount;
      let newMapping = [...prevMapping];

      const validTabIds = new Set(terminalState.tabs.map((tab) => tab.tabId));
      newMapping = newMapping.map((id) => (id && validTabIds.has(id) ? id : null));

      if (newMapping.length < neededPanes) {
        newMapping = [
          ...newMapping,
          ...Array(neededPanes - newMapping.length).fill(null),
        ];
      } else if (newMapping.length > neededPanes) {
        newMapping = newMapping.slice(0, neededPanes);
      }

      if (layout === 'single') {
        const focusedTabId = prevMapping[activePaneIndex];
        newMapping[0] =
          (focusedTabId && validTabIds.has(focusedTabId) ? focusedTabId : null) ??
          terminalState.activeTabId ??
          terminalState.tabs[0]?.tabId ??
          null;
        return newMapping;
      }

      const mappedTabs = new Set(newMapping.filter((id): id is string => Boolean(id)));
      const unmappedTabs = terminalState.tabs.filter(
        (tab) => !mappedTabs.has(tab.tabId),
      );

      if (pendingPaneIndexRef.current !== null && unmappedTabs.length > 0) {
        const targetIndex = pendingPaneIndexRef.current;
        if (targetIndex < neededPanes && !newMapping[targetIndex]) {
          const tab = unmappedTabs.shift();
          if (tab) {
            newMapping[targetIndex] = tab.tabId;
          }
        }
        pendingPaneIndexRef.current = null;
      }

      for (let i = 0; i < newMapping.length && unmappedTabs.length > 0; i += 1) {
        if (!newMapping[i]) {
          const tab = unmappedTabs.shift();
          newMapping[i] = tab?.tabId ?? null;
        }
      }

      return newMapping;
    },
    [layoutPaneCount, terminalState.tabs, layout, terminalState.activeTabId, activePaneIndex],
  );

  // Reconcile pane mapping when tabs or layout changes.
  useEffect(() => {
    setPaneMapping(reconcilePaneMapping);
  }, [reconcilePaneMapping]);

  // Attach the newest created tab to the requested pane.
  useEffect(() => {
    if (pendingPaneIndexRef.current === null) return;
    const targetIndex = pendingPaneIndexRef.current;
    const newestTab = terminalState.tabs[terminalState.tabs.length - 1];
    if (!newestTab) return;
    setPaneMapping((prev) => {
      if (targetIndex >= prev.length) return prev;
      if (prev[targetIndex]) return prev;
      const next = [...prev];
      next[targetIndex] = newestTab.tabId;
      return next;
    });
    pendingPaneIndexRef.current = null;
  }, [terminalState.tabs.length, terminalState.tabs]);

  useEffect(() => {
    const prevLayout = prevLayoutRef.current;
    if (prevLayout !== layout) {
      setActivePaneIndex((prev) => Math.min(prev, Math.max(getPaneCount(layout) - 1, 0)));
      prevLayoutRef.current = layout;
    }
  }, [layout]);

  // Sync local active tab with the focused pane.
  useEffect(() => {
    if (layout === 'single') return;

    const activeTabId = paneMapping[activePaneIndex];
    if (activeTabId && activeTabId !== terminalState.activeTabId) {
      switchTab(activeTabId);
    }
  }, [activePaneIndex, paneMapping, terminalState.activeTabId, switchTab, layout]);

  const handleCreateTab = useCallback(
    (paneIndex: number) => {
      if (terminalState.tabs.length >= TERMINAL_MAX_TABS) {
        toast({
          variant: 'destructive',
          title: menuLabels.maxLimitTitle,
          description: menuLabels.maxLimitDescription,
        });
        return;
      }

      pendingPaneIndexRef.current = paneIndex;
      setActivePane(paneIndex);
      createTab({
        workingDirectory: defaultWorkspacePath,
        size: getPaneSize(paneIndex),
      });
    },
    [
      createTab,
      defaultWorkspacePath,
      getPaneSize,
      toast,
      menuLabels.maxLimitDescription,
      menuLabels.maxLimitTitle,
      setActivePane,
      terminalState.tabs.length,
    ],
  );

  const handleCloseTab = useCallback(
    (tabId: string) => {
      closeTab(tabId);
      // Update mapping to remove the closed tab
      setPaneMapping((prev) => prev.map((id) => (id === tabId ? null : id)));
    },
    [closeTab],
  );

  const handleCopy = useCallback(async () => {
    if (!selectedText) return;
    try {
      if (navigator.clipboard) {
        await navigator.clipboard.writeText(selectedText);
      }
      setSelectedText('');
    } catch (error) {
      logger.error('Copy failed', { error });
    }
  }, [selectedText]);

  const getActiveTerminalTabId = useCallback(() => (
    isCompact ? terminalState.activeTabId : paneMapping[activePaneIndex]
  ), [activePaneIndex, isCompact, paneMapping, terminalState.activeTabId]);

  const handlePaste = useCallback(async () => {
    try {
      if (!navigator.clipboard) return;
      const text = await navigator.clipboard.readText();
      const activeTabId = getActiveTerminalTabId();
      if (!text || !activeTabId) return;
      sendInput(activeTabId, text);
    } catch (error) {
      logger.error('Paste failed', { error });
    }
  }, [sendInput, getActiveTerminalTabId]);

  const restartTerminal = useCallback(() => {
    const activeTabId = getActiveTerminalTabId();
    if (!activeTabId) return;

    const activeTab = terminalState.tabs.find((tab) => tab.tabId === activeTabId);
    if (!activeTab) return;

    const workingDirectory = activeTab.workingDirectory;

    closeTab(activeTabId);
    setPaneMapping((prev) => prev.map((id) => (id === activeTabId ? null : id)));
    pendingPaneIndexRef.current = activePaneIndex;

    window.setTimeout(() => {
      createTab({
        workingDirectory,
        size: getPaneSize(activePaneIndex),
        fallbackWorkingDirectory: defaultWorkspacePath,
      });
    }, 120);
  }, [
    activePaneIndex,
    terminalState.tabs,
    closeTab,
    createTab,
    setPaneMapping,
    defaultWorkspacePath,
    getActiveTerminalTabId,
    getPaneSize,
  ]);

  const requestLayoutChange = useCallback(
    (newLayout: TerminalLayoutType) => {
      setLayout(newLayout);
      const targetPaneCount = getPaneCount(newLayout);
      setActivePaneIndex((prev) =>
        prev >= targetPaneCount ? Math.max(targetPaneCount - 1, 0) : prev,
      );
    },
    [],
  );

  const handleAssignTabToPane = useCallback(
    (paneIndex: number, tabId: string) => {
      if (layout === 'single') {
        switchTab(tabId);
        setActivePaneIndex(0);
        return;
      }

      const clampedIndex = Math.min(
        Math.max(paneIndex, 0),
        Math.max(getPaneCount(layout) - 1, 0),
      );

      setPaneMapping((prev) => {
        if (clampedIndex >= prev.length) return prev;
        const next = [...prev];
        next[clampedIndex] = tabId;
        return next;
      });
      setActivePaneIndex(clampedIndex);
      switchTab(tabId);
    },
    [layout, switchTab],
  );

  const handleUnassignTabFromPane = useCallback(
    (paneIndex: number, tabId: string) => {
      if (layout === 'single') return;
      const clampedIndex = Math.min(
        Math.max(paneIndex, 0),
        Math.max(getPaneCount(layout) - 1, 0),
      );
      setPaneMapping((prev) => {
        if (clampedIndex >= prev.length) return prev;
        if (prev[clampedIndex] !== tabId) return prev;
        const next = [...prev];
        next[clampedIndex] = null;
        return next;
      });
    },
    [layout],
  );

  const openContextMenu = useCallback((event: React.MouseEvent, tabId?: string, paneIndex?: number) => {
    event.preventDefault();
    const x = event.clientX;
    const y = event.clientY;

    if (typeof paneIndex === 'number' && layout !== 'single') {
      setActivePane(paneIndex);
    }

    setContextMenu({
      x,
      y,
      visible: true,
      tabId,
      paneIndex,
    });
  }, [layout, setActivePane]);

  const closeContextMenu = useCallback(() => {
    setContextMenu(INITIAL_CONTEXT_MENU_STATE);
  }, []);

  useEffect(() => {
    if (!contextMenu.visible) return;
    const handleClick = () => closeContextMenu();
    document.addEventListener('click', handleClick);
    return () => document.removeEventListener('click', handleClick);
  }, [contextMenu.visible, closeContextMenu]);

  const assignedTabIds = useMemo(() => {
    const ids = new Set<string>();
    paneMapping.forEach((id) => {
      if (id) ids.add(id);
    });
    return ids;
  }, [paneMapping]);

  const handleTerminalResize = useCallback((cols: number, rows: number) => {
    paneSizeMapRef.current.set(activePaneIndex, { cols, rows });
    setTerminalSize({ cols, rows });
  }, [activePaneIndex]);

  // Create the default tab only after backend sync confirms there are no tabs.
  useEffect(() => {
    if (
      terminalState.status === 'open' &&
      terminalState.isSynced &&
      terminalState.tabs.length === 0
    ) {
      ensureDefaultTab(defaultWorkspacePath, getPaneSize(activePaneIndex));
    }
  }, [
    activePaneIndex,
    defaultWorkspacePath,
    ensureDefaultTab,
    getPaneSize,
    terminalState.status,
    terminalState.isSynced,
    terminalState.tabs.length,
  ]);

  // Handle connection errors
  useEffect(() => {
    if (terminalState.status === 'error') {
      logger.error('Terminal error', { error: terminalState.error });
    }
  }, [terminalState.status, terminalState.error]);

  const activeTabId = useMemo(() => {
    if (isCompact) return terminalState.activeTabId;
    if (layout === 'single') return terminalState.activeTabId;
    return paneMapping[activePaneIndex] ?? terminalState.activeTabId;
  }, [activePaneIndex, isCompact, layout, paneMapping, terminalState.activeTabId]);

  const activeTab = terminalState.tabs.find((t) => t.tabId === activeTabId);

  const statusInfo = useMemo(() => {
    if (terminalState.status === 'connecting') {
      return {
        color: 'bg-sky-500',
        label: t('workspace.containerManagement.terminal.status.connecting'),
      };
    }
    if (terminalState.status === 'reconnecting') {
      return {
        color: 'bg-amber-500',
        label: t('workspace.containerManagement.terminal.status.reconnecting'),
      };
    }
    if (terminalState.status === 'open' && !terminalState.isSynced) {
      return {
        color: 'bg-sky-500',
        label: t('workspace.containerManagement.terminal.status.syncing'),
      };
    }
    if (!activeTab) {
      return {
        color: 'bg-gray-500',
        label: t('workspace.containerManagement.terminal.status.unassigned'),
      };
    }
    if (terminalState.status === 'open') {
      return {
        color: 'bg-emerald-500',
        label: t('workspace.containerManagement.terminal.status.connected'),
      };
    }
    if (terminalState.error) {
      return { color: 'bg-red-500', label: terminalState.error };
    }
    return {
      color: 'bg-gray-400',
      label: t('workspace.containerManagement.terminal.status.disconnected'),
    };
  }, [terminalState.status, terminalState.error, terminalState.isSynced, t, activeTab]);

  const renderEmptyPane = useCallback(
    (paneIndex: number) => (
      <div
        className="flex h-full w-full items-center justify-center bg-gray-900/50"
        onContextMenu={(e) => openContextMenu(e, undefined, paneIndex)}
      >
        <Button
          variant="outline"
          onClick={(e) => {
            e.stopPropagation();
            handleCreateTab(paneIndex);
          }}
          className="gap-2"
        >
          <Plus className="h-4 w-4" />
          {tabLabels.add}
        </Button>
      </div>
    ),
    [handleCreateTab, tabLabels.add, openContextMenu],
  );

  // Recursive function to render panels based on layout definition
  const renderLayout = useCallback(
    (node: LayoutNode, isRoot: boolean = false) => {
      if (node.type === 'panel') {
        const paneIndex = parseInt(node.id || '0', 10);
        const tabId = paneMapping[paneIndex];
        const isFocused = paneIndex === activePaneIndex;
        const tab = terminalState.tabs.find((t) => t.tabId === tabId);

        const panelContent = (
          <Panel
            key={node.id}
            defaultSize={node.defaultSize}
            minSize={10}
            className={cn(
              'relative flex h-full w-full flex-col overflow-hidden border border-gray-800 transition-colors',
            )}
            onClick={() => setActivePaneIndex(paneIndex)}
            onContextMenu={(e) => openContextMenu(e, tabId, paneIndex)}
          >
            {tabId && tab ? (
              <TerminalTab
                tabId={tabId}
                isActive={isFocused}
                isVisible={true}
                onInput={sendInput}
                onResize={sendResize}
                onSelectionChange={setSelectedText}
                onTerminalResize={isFocused ? handleTerminalResize : undefined}
                onContextMenu={(e) => openContextMenu(e, tabId, paneIndex)}
                attachXterm={attachXterm}
                terminalTheme={resolvedTerminalTheme}
              />
            ) : (
              renderEmptyPane(paneIndex)
            )}
          </Panel>
        );

        if (isRoot) {
          return <PanelGroup direction="horizontal">{panelContent}</PanelGroup>;
        }

        return panelContent;
      }

      if (node.type === 'group' && node.children) {
        const groupContent = (
          <PanelGroup
            key={JSON.stringify(node)}
            direction={node.direction || 'horizontal'}
          >
            {node.children.map((child, index) => (
              <React.Fragment key={index}>
                {renderLayout(child, false)}
                {index < (node.children?.length || 0) - 1 && (
                  <PanelResizeHandle
                    className={cn(
                      'bg-gray-800 transition-colors hover:bg-blue-500',
                      node.direction === 'horizontal'
                        ? 'w-1 cursor-col-resize'
                        : 'h-1 cursor-row-resize',
                    )}
                  />
                )}
              </React.Fragment>
            ))}
          </PanelGroup>
        );

        if (isRoot) {
          return groupContent;
        }

        return (
          <Panel defaultSize={node.defaultSize} minSize={10}>
            {groupContent}
          </Panel>
        );
      }
      return null;
    },
    [
      activePaneIndex,
      attachXterm,
      handleTerminalResize,
      openContextMenu,
      paneMapping,
      renderEmptyPane,
      resolvedTerminalTheme,
      sendInput,
      sendResize,
      setActivePaneIndex,
      setSelectedText,
      terminalState.tabs,
    ],
  );

  const tabBar =
    layout === 'single' ? (
      <TerminalTabBar
        tabs={terminalState.tabs}
        activeTabId={terminalState.activeTabId}
        onSwitchTab={switchTab}
        onCloseTab={handleCloseTab}
        onAddTab={() => handleCreateTab(0)}
        onContextMenu={(e, tabId, paneIndex) => openContextMenu(
          e,
          tabId,
          isCompact ? undefined : paneIndex,
        )}
        contextPaneIndex={isCompact ? undefined : 0}
        closeLabel={tabLabels.close}
        newTooltip={tabLabels.newTooltip}
        scrollLeftLabel={tabLabels.scrollLeft}
        scrollRightLabel={tabLabels.scrollRight}
      />
    ) : null;

  const isBusy =
    terminalState.status === 'connecting' || terminalState.status === 'reconnecting';
  const terminalSurfaceClass = resolvedTerminalTheme === 'dark'
    ? 'bg-[#0f172a]'
    : 'bg-white';

  const openFullTerminal = useCallback(() => {
    if (workspaceRuntime.workspaceId) {
      navigate(ROUTES.workspace.containers(workspaceRuntime.workspaceId, 'terminal'));
    }
  }, [navigate, workspaceRuntime.workspaceId]);

  if (isCompact) {
    return (
      <div data-testid="compact-terminal-panel" className="flex h-full min-h-0 flex-col bg-background">
        <div
          data-testid="compact-terminal-second-layer"
          className="flex h-10 shrink-0 items-center gap-1 border-b border-border bg-card px-3"
        >
          <div
            data-testid="compact-terminal-header-icon"
            className="flex h-7 w-7 shrink-0 items-center justify-center text-muted-foreground"
          >
            <SquareTerminal className="h-3.5 w-3.5" aria-hidden="true" />
          </div>
          {tabBar}
          {onTerminalPlacementChange && (
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7"
              aria-label={t(isBottomPlacement
                ? 'aiChat.companion.undockTerminal'
                : 'aiChat.companion.dockTerminal')}
              title={t(isBottomPlacement
                ? 'aiChat.companion.undockTerminal'
                : 'aiChat.companion.dockTerminal')}
              onClick={() => onTerminalPlacementChange(isBottomPlacement ? 'side' : 'bottom')}
            >
              {isBottomPlacement ? (
                <PanelRight className="h-3.5 w-3.5" aria-hidden="true" />
              ) : (
                <PanelBottom className="h-3.5 w-3.5" aria-hidden="true" />
              )}
            </Button>
          )}
          <TerminalThemeSelector
            value={resolvedTerminalTheme}
            onChange={handleTerminalThemeChange}
            labels={themeLabels}
          />
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant="ghost"
                size="icon"
                className="h-7 w-7"
                aria-label={menuLabels.actionsTitle}
                title={menuLabels.actionsTitle}
              >
                <MoreVertical className="h-3.5 w-3.5" aria-hidden="true" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onClick={handleCopy} disabled={!selectedText}>
                <Copy className="mr-2 h-3.5 w-3.5" />
                {menuLabels.copy}
              </DropdownMenuItem>
              <DropdownMenuItem onClick={handlePaste}>
                <Clipboard className="mr-2 h-3.5 w-3.5" />
                {menuLabels.paste}
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={openFullTerminal}>
                <ExternalLink className="mr-2 h-3.5 w-3.5" />
                {t('aiChat.companion.terminal.openFull')}
              </DropdownMenuItem>
              <DropdownMenuItem onClick={restartTerminal} disabled={isBusy}>
                <RotateCcw
                  className={cn('mr-2 h-3.5 w-3.5', isBusy && 'animate-spin')}
                />
                {menuLabels.restart}
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
        {terminalState.status === 'error' && (
          <div
            data-testid="compact-terminal-error"
            className="border-b border-destructive/30 bg-destructive/10 px-3 py-2 text-xs text-destructive"
          >
            {terminalState.error ?? t('aiChat.companion.terminal.status.error')}
          </div>
        )}
        <div className={cn('min-h-0 flex-1 overflow-hidden', terminalSurfaceClass)}>
          {activeTab ? (
            <TerminalTab
              key={activeTab.tabId}
              tabId={activeTab.tabId}
              isActive
              isVisible
              onInput={sendInput}
              onResize={sendResize}
              onSelectionChange={setSelectedText}
              onTerminalResize={handleTerminalResize}
              onContextMenu={(event) => openContextMenu(event, activeTab.tabId)}
              attachXterm={attachXterm}
              terminalTheme={resolvedTerminalTheme}
            />
          ) : (
            renderEmptyPane(0)
          )}
        </div>
        <WorkspaceStatusBar
          left={
            <>
              <span className="truncate font-medium text-foreground">
                {activeTab
                  ? getTerminalTabTitle(activeTab.workingDirectory)
                  : tabLabels.empty}
              </span>
              <span className={cn('h-2 w-2 shrink-0 rounded-full', statusInfo.color)} />
              <span className="truncate">{statusInfo.label}</span>
            </>
          }
          right={
            selectedText ? (
              <span className="rounded bg-primary px-2 py-0.5 text-primary-foreground">
                {statusBarLabels.selected}
              </span>
            ) : null
          }
        />
        <TerminalContextMenu
          state={contextMenu}
          selectedText={selectedText}
          tabs={terminalState.tabs}
          assignedTabIds={new Set()}
          onCopy={handleCopy}
          onPaste={handlePaste}
          onCloseTab={handleCloseTab}
          onClear={clearTerminal}
          hidePaneActions
          onDismiss={closeContextMenu}
          labels={{
            copy: menuLabels.copy,
            paste: menuLabels.paste,
            close: menuLabels.contextClose,
            clear: menuLabels.contextClear,
            switchTitle: menuLabels.switchTitle,
            active: menuLabels.active,
            unassign: menuLabels.unassign,
          }}
        />
      </div>
    );
  }

  return (
    <div
      className={cn(
        'h-full flex flex-col bg-background',
        isFullscreen && 'fixed inset-0 z-50 bg-background',
      )}
    >
      <FeatureHeader
        title={t('workspace.containerManagement.terminal.header.title')}
        icon={SquareTerminal}
        info={tabBar}
        actions={
          <div className="flex items-center gap-1">
            <TerminalThemeSelector
              value={resolvedTerminalTheme}
              onChange={handleTerminalThemeChange}
              labels={themeLabels}
            />

            <TerminalLayoutSelector
              currentLayout={layout}
              onLayoutChange={requestLayoutChange}
            />

            <div className="h-5 w-px bg-border" />

            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7"
              onClick={() => setIsFullscreen((prev) => !prev)}
              title={isFullscreen ? menuLabels.fullscreenExit : menuLabels.fullscreenEnter}
              aria-label={isFullscreen ? menuLabels.fullscreenExit : menuLabels.fullscreenEnter}
            >
              {isFullscreen ? (
                <Minimize2 className="h-3.5 w-3.5" />
              ) : (
                <Maximize2 className="h-3.5 w-3.5" />
              )}
            </Button>

            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-7 w-7"
                  title={menuLabels.actionsTitle}
                  aria-label={menuLabels.actionsTitle}
                >
                  <MoreVertical className="h-3.5 w-3.5" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem onClick={handleCopy} disabled={!selectedText}>
                  <Copy className="mr-2 h-3.5 w-3.5" />
                  {menuLabels.copy}
                </DropdownMenuItem>
                <DropdownMenuItem onClick={handlePaste}>
                  <Clipboard className="mr-2 h-3.5 w-3.5" />
                  {menuLabels.paste}
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem onClick={restartTerminal} disabled={isBusy}>
                  <RotateCcw
                    className={cn('mr-2 h-3.5 w-3.5', isBusy && 'animate-spin')}
                  />
                  {menuLabels.restart}
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        }
      />

      <div className={cn('flex-1 overflow-hidden', terminalSurfaceClass)}>
        {layout === 'single' ? (
          // Single Layout: Render Active Tab
          <div className="h-full w-full">
            {terminalState.tabs.length > 0 ? (
              terminalState.tabs.map((tab) => (
                <TerminalTab
                  key={tab.tabId}
                  tabId={tab.tabId}
                  isActive={tab.tabId === terminalState.activeTabId}
                  isVisible={tab.tabId === terminalState.activeTabId}
                  onInput={sendInput}
                  onResize={sendResize}
                  onSelectionChange={setSelectedText}
                  onTerminalResize={handleTerminalResize}
                  onContextMenu={(e) => openContextMenu(e, tab.tabId, 0)}
                  attachXterm={attachXterm}
                  terminalTheme={resolvedTerminalTheme}
                />
              ))
            ) : (
              renderEmptyPane(0)
            )}
          </div>
        ) : (
          // Multi-Pane Layout
          renderLayout(LAYOUT_DEFINITIONS[layout], true)
        )}
      </div>

      {/* Status Bar */}
      <WorkspaceStatusBar
        left={
          <>
            <span className="truncate font-medium text-foreground">
              {activeTab
                ? getTerminalTabTitle(activeTab.workingDirectory)
                : tabLabels.empty}
            </span>
            <div className="h-3 w-px shrink-0 bg-border" />
            <span>{statusBarLabels.rows}</span>
            <span>{statusBarLabels.cols}</span>
            <span>{statusBarLabels.encoding}</span>
          </>
        }
        right={
          <>
            {selectedText && (
              <span className="rounded bg-primary px-2 py-0.5 text-primary-foreground">
                {statusBarLabels.selected}
              </span>
            )}
            <span className="flex items-center gap-1">
              <span className={cn('h-2 w-2 rounded-full', statusInfo.color)} />
              {statusInfo.label}
            </span>
          </>
        }
      />

      <TerminalContextMenu
        state={contextMenu}
        selectedText={selectedText}
        tabs={terminalState.tabs}
        assignedTabIds={assignedTabIds}
        onCopy={handleCopy}
        onPaste={handlePaste}
        onCloseTab={handleCloseTab}
        onClear={clearTerminal}
        onUnassign={handleUnassignTabFromPane}
        onAssignTab={handleAssignTabToPane}
        onDismiss={closeContextMenu}
        labels={{
          copy: menuLabels.copy,
          paste: menuLabels.paste,
          close: menuLabels.contextClose,
          clear: menuLabels.contextClear,
          switchTitle: menuLabels.switchTitle,
          active: menuLabels.active,
          unassign: menuLabels.unassign,
        }}
      />
    </div>
  );
};
