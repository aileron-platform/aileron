/**
 * TerminalView - Multi-pane Terminal Component
 */

import React, { useCallback, useEffect, useMemo, useState, useRef } from 'react';
import {
  Plus,
  Terminal,
  Copy,
  Clipboard,
  RotateCcw,
  Maximize2,
  Minimize2,
  MoreVertical,
} from 'lucide-react';
import { Panel, PanelGroup, PanelResizeHandle } from 'react-resizable-panels';

import { FeatureHeader } from '@/shared/components/layout/FeatureHeader';
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

const logger = createLogger('TerminalView');

import { useWorkspace } from '../../../providers/WorkspaceProvider';
import { useTerminalStream } from '@/features/workspace/realtime';
import { useGitContextsQuery } from '@/features/workspace/features/version-control/hooks/useVersionControlQueries';
import { TerminalTab, disposeAllTerminalInstances, disposeTerminalInstance } from './TerminalTab';
import { TerminalLayoutSelector, TerminalLayoutType } from './TerminalLayoutSelector';
import { LAYOUT_DEFINITIONS, LayoutNode, getPaneCount } from './LayoutDefinitions';
import { TERMINAL_MAX_TABS } from '../config/terminalConfig';
import { TerminalTabBar } from './TerminalTabBar';
import { resolveDefaultTerminalWorkspacePath } from './terminalContext';
import {
  TerminalContextMenu,
  ContextMenuState,
  INITIAL_CONTEXT_MENU_STATE,
} from './TerminalContextMenu';

type PendingTabRequest = { paneIndex: number; name: string; workspacePath: string };
type PendingAssignQueue = number[];
type PaneSize = { cols: number; rows: number };

export const TerminalView: React.FC = () => {
  const { t } = useI18n();
  const { workspaceRuntime, state: workspaceState } = useWorkspace();
  const {
    state: terminalState,
    connect,
    disconnect,
    createTab,
    closeTab,
    switchTab,
    sendInput,
    sendResize,
    attachXterm,
    clearHistory,
    renameTab,
  } = useTerminalStream();
  const { toast } = useToast();
  const { data: gitContextsResponse } = useGitContextsQuery({
    workspaceId: workspaceRuntime.workspaceId ?? '',
    runtimeBaseUrl: workspaceRuntime.runtimeBaseUrl,
  });

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
  const pendingTabQueueRef = useRef<PendingTabRequest[]>([]);
  const pendingAssignQueueRef = useRef<PendingAssignQueue>([]);
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
      add: t('workspace.containerManagement.terminal.tabs.add', {
        defaultValue: '新增終端機',
      }),
      empty: t('workspace.containerManagement.terminal.tabs.empty', {
        defaultValue: '沒有終端機',
      }),
      newTooltip: t('workspace.containerManagement.terminal.tabs.new', {
        defaultValue: '新增終端機',
      }),
      close: t('workspace.containerManagement.terminal.tabs.close', {
        defaultValue: '關閉終端機',
      }),
    }),
    [t],
  );

  const menuLabels = useMemo(
    () => ({
      actionsTitle: t('workspace.containerManagement.terminal.menus.actions', {
        defaultValue: '操作',
      }),
      switchTitle: t('workspace.containerManagement.terminal.menus.context.switch', {
        defaultValue: '切換終端機',
      }),
      rename: t('workspace.containerManagement.terminal.menus.context.rename', {
        defaultValue: '重新命名',
      }),
      unassign: t('workspace.containerManagement.terminal.menus.context.unassign', {
        defaultValue: '解除指派',
      }),
      renamePrompt: t('workspace.containerManagement.terminal.menus.context.renamePrompt', {
        defaultValue: '輸入新的終端機名稱',
      }),
      copy: t('workspace.containerManagement.terminal.actions.copy', {
        defaultValue: '複製',
      }),
      paste: t('workspace.containerManagement.terminal.actions.paste', {
        defaultValue: '貼上',
      }),
      restart: t('workspace.containerManagement.terminal.actions.restart', {
        defaultValue: '重新啟動終端',
      }),
      fullscreenEnter: t(
        'workspace.containerManagement.terminal.actions.enterFullscreen',
        { defaultValue: '全螢幕' },
      ),
      fullscreenExit: t(
        'workspace.containerManagement.terminal.actions.exitFullscreen',
        { defaultValue: '退出全螢幕' },
      ),
      contextClear: t('workspace.containerManagement.terminal.menus.context.clear', {
        defaultValue: '清除',
      }),
      contextClose: t('workspace.containerManagement.terminal.menus.context.close', {
        defaultValue: '關閉終端機',
      }),
      active: t('workspace.containerManagement.terminal.tabs.active', {
        defaultValue: '目前',
      }),
      maxLimitTitle: t('workspace.containerManagement.terminal.limits.max.title', {
        defaultValue: '已達終端機上限',
      }),
      maxLimitDescription: t(
        'workspace.containerManagement.terminal.limits.max.description',
        {
          count: TERMINAL_MAX_TABS,
          defaultValue: `最多可建立 ${TERMINAL_MAX_TABS} 個終端機。`,
        },
      ),
    }),
    [t],
  );

  const statusBarLabels = useMemo(
    () => ({
      rows: t('workspace.containerManagement.terminal.footer.rows', {
        count: terminalSize.rows,
        defaultValue: `列: ${terminalSize.rows}`,
      }),
      cols: t('workspace.containerManagement.terminal.footer.columns', {
        count: terminalSize.cols,
        defaultValue: `行: ${terminalSize.cols}`,
      }),
      encoding: t('workspace.containerManagement.terminal.footer.encoding', {
        defaultValue: 'UTF-8',
      }),
      selected: selectedText
        ? t('workspace.containerManagement.terminal.footer.selection', {
          count: selectedText.length,
          defaultValue: `選取 ${selectedText.length} 字元`,
        })
        : '',
    }),
    [t, terminalSize.rows, terminalSize.cols, selectedText],
  );

  const getPaneSize = useCallback((paneIndex: number): PaneSize | undefined => {
    const paneSize = paneSizeMapRef.current.get(paneIndex);
    if (paneSize && paneSize.cols > 0 && paneSize.rows > 0) return paneSize;
    if (terminalSize.cols > 0 && terminalSize.rows > 0) return terminalSize;
    return undefined;
  }, [terminalSize]);

  // Auto-connect.
  useEffect(() => {
    if (workspaceRuntime.workspaceId && workspaceRuntime.terminalExternalUrl) {
      const timer = setTimeout(() => {
        connect({ force: false });
      }, 100);
      return () => {
        clearTimeout(timer);
        disconnect({ allowReconnect: false });
      };
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [workspaceRuntime.workspaceId, workspaceRuntime.terminalExternalUrl]);

  useEffect(() => {
    return () => {
      disposeAllTerminalInstances();
    };
  }, []);

  // Flush queued tab creates after the socket is synced.
  useEffect(() => {
    if (terminalState.status !== 'open') return;
    if (!terminalState.isSynced) return;
    if (pendingTabQueueRef.current.length === 0) return;

    const queued = [...pendingTabQueueRef.current];
    pendingTabQueueRef.current = [];

    queued.forEach(({ paneIndex, name, workspacePath }) => {
      pendingPaneIndexRef.current = paneIndex;
      pendingAssignQueueRef.current.push(paneIndex);
      setActivePane(paneIndex);
      createTab(name, workspacePath, getPaneSize(paneIndex));
    });
  }, [terminalState.status, terminalState.isSynced, createTab, setActivePane, getPaneSize]);

  // Assign newly created tabs to requested panes.
  useEffect(() => {
    if (pendingAssignQueueRef.current.length === 0) return;

    const occupied = new Set(paneMapping.filter(Boolean) as string[]);
    const availableTabs = terminalState.tabs.filter((tab) => !occupied.has(tab.tabId));

    if (availableTabs.length === 0) return;

    let changed = false;
    const nextMapping = [...paneMapping];

    while (pendingAssignQueueRef.current.length > 0 && availableTabs.length > 0) {
      const paneIndex = pendingAssignQueueRef.current.shift() as number;
      if (paneIndex >= nextMapping.length) continue;
      if (nextMapping[paneIndex]) continue;
      const tab = availableTabs.shift();
      if (!tab) break;
      nextMapping[paneIndex] = tab.tabId;
      changed = true;
    }

    if (changed) {
      setPaneMapping(nextMapping);
    }

    if (pendingAssignQueueRef.current.length === 0) {
      pendingPaneIndexRef.current = null;
    }
  }, [terminalState.tabs, paneMapping]);

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
      const plannedTotal =
        terminalState.tabs.length + pendingTabQueueRef.current.length;
      if (plannedTotal >= TERMINAL_MAX_TABS) {
        toast({
          variant: 'destructive',
          title: menuLabels.maxLimitTitle,
          description: menuLabels.maxLimitDescription,
        });
        return;
      }

      pendingPaneIndexRef.current = paneIndex;
      const request: PendingTabRequest = {
        paneIndex,
        name: '',
        workspacePath: defaultWorkspacePath,
      };

      pendingPaneIndexRef.current = paneIndex;
      pendingAssignQueueRef.current.push(paneIndex);

      if (terminalState.status !== 'open' || !terminalState.isSynced) {
        pendingTabQueueRef.current.push(request);
        connect({ force: true });
      } else {
        createTab(request.name, request.workspacePath, getPaneSize(paneIndex));
      }

      setActivePane(paneIndex);
    },
    [
      createTab,
      terminalState.tabs,
      terminalState.status,
      terminalState.isSynced,
      connect,
      toast,
      menuLabels.maxLimitDescription,
      menuLabels.maxLimitTitle,
      setActivePane,
      defaultWorkspacePath,
      getPaneSize,
    ],
  );

  const handleCloseTab = useCallback(
    (tabId: string) => {
      closeTab(tabId);
      disposeTerminalInstance(tabId);
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

  const handlePaste = useCallback(async () => {
    try {
      if (!navigator.clipboard) return;
      const text = await navigator.clipboard.readText();
      const activeTabId = paneMapping[activePaneIndex];
      if (!text || !activeTabId) return;
      sendInput(activeTabId, text);
    } catch (error) {
      logger.error('Paste failed', { error });
    }
  }, [sendInput, paneMapping, activePaneIndex]);

  const restartTerminal = useCallback(() => {
    const activeTabId = paneMapping[activePaneIndex];
    if (!activeTabId) return;

    const activeTab = terminalState.tabs.find((tab) => tab.tabId === activeTabId);
    if (!activeTab) return;

    const tabName = activeTab.name;

    closeTab(activeTabId);
    disposeTerminalInstance(activeTabId);
    setPaneMapping((prev) => prev.map((id) => (id === activeTabId ? null : id)));
    pendingPaneIndexRef.current = activePaneIndex;
    pendingAssignQueueRef.current.push(activePaneIndex);

    const request: PendingTabRequest = {
      paneIndex: activePaneIndex,
      name: tabName,
      workspacePath: defaultWorkspacePath,
    };

    if (terminalState.status !== 'open') {
      pendingTabQueueRef.current.push(request);
      connect({ force: true });
      return;
    }

    window.setTimeout(() => {
      createTab(tabName, request.workspacePath, getPaneSize(activePaneIndex));
    }, 120);
  }, [
    paneMapping,
    activePaneIndex,
    terminalState.tabs,
    closeTab,
    createTab,
    terminalState.status,
    connect,
    setPaneMapping,
    defaultWorkspacePath,
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

  const handleRenameTab = useCallback(
    (tabId: string) => {
      const target = terminalState.tabs.find((tab) => tab.tabId === tabId);
      const nextName = window.prompt(menuLabels.renamePrompt, target?.name || '');
      if (!nextName) return;
      const trimmed = nextName.trim();
      if (!trimmed) return;
      renameTab(tabId, trimmed);
    },
    [menuLabels.renamePrompt, renameTab, terminalState.tabs],
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
  }, []);

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
      terminalState.tabs.length === 0 &&
      pendingTabQueueRef.current.length === 0
    ) {
      createTab('', defaultWorkspacePath, getPaneSize(activePaneIndex));
    }
  }, [
    terminalState.status,
    terminalState.isSynced,
    terminalState.tabs.length,
    createTab,
    defaultWorkspacePath,
    getPaneSize,
    activePaneIndex,
  ]);

  // Handle connection errors
  useEffect(() => {
    if (terminalState.status === 'error') {
      logger.error('Terminal error', { error: terminalState.error });
    }
  }, [terminalState.status, terminalState.error]);

  const activeTabId = useMemo(() => {
    if (layout === 'single') return terminalState.activeTabId;
    return paneMapping[activePaneIndex] ?? terminalState.activeTabId;
  }, [layout, paneMapping, activePaneIndex, terminalState.activeTabId]);

  const activeTab = terminalState.tabs.find((t) => t.tabId === activeTabId);

  const statusInfo = useMemo(() => {
    if (terminalState.status === 'connecting') {
      return {
        color: 'bg-sky-500',
        label: t('workspace.containerManagement.terminal.status.connecting', {
          defaultValue: '連線中...',
        }),
      };
    }
    if (terminalState.status === 'reconnecting') {
      return {
        color: 'bg-amber-500',
        label: t('workspace.containerManagement.terminal.status.reconnecting', {
          defaultValue: '重新連線中...',
        }),
      };
    }
    if (terminalState.status === 'open' && !terminalState.isSynced) {
      return {
        color: 'bg-sky-500',
        label: t('workspace.containerManagement.terminal.status.syncing', {
          defaultValue: '正在同步終端機工作階段...',
        }),
      };
    }
    if (!activeTab) {
      return {
        color: 'bg-gray-500',
        label: t('workspace.containerManagement.terminal.status.unassigned', {
          defaultValue: '未指派',
        }),
      };
    }
    if (terminalState.status === 'open') {
      return {
        color: 'bg-emerald-500',
        label: t('workspace.containerManagement.terminal.status.connected', {
          defaultValue: '已連線',
        }),
      };
    }
    if (terminalState.error) {
      return { color: 'bg-red-500', label: terminalState.error };
    }
    return {
      color: 'bg-gray-400',
      label: t('workspace.containerManagement.terminal.status.disconnected', {
        defaultValue: '已中斷連線',
      }),
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
        onContextMenu={(e, tabId, paneIndex) => openContextMenu(e, tabId, paneIndex)}
        contextPaneIndex={0}
        closeLabel={tabLabels.close}
        newTooltip={tabLabels.newTooltip}
      />
    ) : null;

  const isBusy =
    terminalState.status === 'connecting' || terminalState.status === 'reconnecting';

  return (
    <div
      className={cn(
        'h-full flex flex-col bg-background',
        isFullscreen && 'fixed inset-0 z-50 bg-background',
      )}
    >
      <FeatureHeader
        title={t('workspace.containerManagement.terminal.header.title', {
          defaultValue: '終端機',
        })}
        icon={Terminal}
        info={tabBar}
        actions={
          <div className="flex items-center gap-1">
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
          </div>
        }
      />

      <div className="flex-1 overflow-hidden bg-[#0f172a]">
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
      <div className="flex-shrink-0 border-t border-gray-800 bg-gray-900 px-4 py-1">
        <div className="flex items-center justify-between text-xs text-gray-400">
          <div className="flex items-center gap-4">
            {/* Active Terminal Name */}
            <span className="font-medium text-gray-300">
              {activeTab ? activeTab.name : tabLabels.empty}
            </span>
            <div className="h-3 w-px bg-gray-700" />
            <span>{statusBarLabels.rows}</span>
            <span>{statusBarLabels.cols}</span>
            <span>{statusBarLabels.encoding}</span>
          </div>
          <div className="flex items-center gap-2">
            {selectedText && (
              <span className="rounded bg-blue-600 px-2 py-0.5 text-white">
                {statusBarLabels.selected}
              </span>
            )}
            <span className="flex items-center gap-1 text-emerald-400">
              <span className={cn('h-2 w-2 rounded-full', statusInfo.color)} />
              {statusInfo.label}
            </span>
          </div>
        </div>
      </div>

      <TerminalContextMenu
        state={contextMenu}
        selectedText={selectedText}
        tabs={terminalState.tabs}
        assignedTabIds={assignedTabIds}
        onCopy={handleCopy}
        onPaste={handlePaste}
        onCloseTab={handleCloseTab}
        onClear={clearHistory}
        onRename={handleRenameTab}
        onUnassign={handleUnassignTabFromPane}
        onAssignTab={handleAssignTabToPane}
        onDismiss={closeContextMenu}
        labels={{
          copy: menuLabels.copy,
          paste: menuLabels.paste,
          close: menuLabels.contextClose,
          clear: menuLabels.contextClear,
          rename: menuLabels.rename,
          switchTitle: menuLabels.switchTitle,
          active: menuLabels.active,
          unassign: menuLabels.unassign,
        }}
      />
    </div>
  );
};
