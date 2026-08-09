import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type DragEvent as ReactDragEvent,
  type ReactNode,
} from 'react';
import type { CodeTextEditorRef } from './CodeTextEditor';
import {
  DEFAULT_FORMAT_ACTIONS_KEY,
  DEFAULT_FORMAT_ACTIONS_OWNER_KEY,
  EMPTY_FORMAT_ACTIONS_KEY,
  FILE_WORKBENCH_TAB_DND_MIME,
  getPointerDropPosition,
  getStats,
  getViewerOwnerKey,
  reorderTabs,
} from './model/fileViewerWorkbenchModel';
import type {
  FileViewerWorkbenchAdapter,
  FileViewerWorkbenchCapabilities,
  FileViewerWorkbenchProps,
  FileViewerWorkbenchTab,
} from './types';

interface RegisteredFormatActions {
  key: string;
  ownerKey: string;
  node: ReactNode | null;
}

interface UseFileViewerWorkbenchControllerOptions {
  tabs: FileViewerWorkbenchTab[];
  activeTabId: string | null;
  adapter: FileViewerWorkbenchAdapter;
  capabilities: FileViewerWorkbenchCapabilities;
  readOnly: boolean;
  isExpanded?: boolean;
  onExpandedChange?: (expanded: boolean) => void;
  isPathWritable?: (path: string) => boolean;
  renderReadOnlyBadge?: FileViewerWorkbenchProps['renderReadOnlyBadge'];
  onTabsChange: (tabs: FileViewerWorkbenchTab[]) => void;
  onActiveTabChange: (tabId: string | null) => void;
  onSplitTab?: (tabId: string) => void;
  canSplitTab?: (tabId: string) => boolean;
  onForeignTabDrop?: (draggedTabId: string, targetTabId: string | null, position: 'before' | 'after') => void;
}

export const useFileViewerWorkbenchController = ({
  tabs,
  activeTabId,
  adapter,
  capabilities,
  readOnly,
  isExpanded,
  onExpandedChange,
  isPathWritable,
  renderReadOnlyBadge,
  onTabsChange,
  onActiveTabChange,
  onSplitTab,
  canSplitTab,
  onForeignTabDrop,
}: UseFileViewerWorkbenchControllerOptions) => {
  const tabScrollRef = useRef<HTMLDivElement>(null);
  const codeEditorRef = useRef<CodeTextEditorRef>(null);
  const draggedTabIdRef = useRef<string | null>(null);
  const [showLeftScroll, setShowLeftScroll] = useState(false);
  const [showRightScroll, setShowRightScroll] = useState(false);
  const [uncontrolledExpanded, setUncontrolledExpanded] = useState(false);
  const [dropIndicator, setDropIndicator] = useState<{ tabId: string; position: 'before' | 'after' } | null>(null);
  const [formatActions, setFormatActions] = useState<RegisteredFormatActions>({
    key: EMPTY_FORMAT_ACTIONS_KEY,
    ownerKey: '',
    node: null,
  });
  const formatActionsRef = useRef<RegisteredFormatActions>({
    key: EMPTY_FORMAT_ACTIONS_KEY,
    ownerKey: '',
    node: null,
  });
  const activeTab = tabs.find((tab) => tab.id === activeTabId) ?? null;
  const effectiveExpanded = isExpanded ?? uncontrolledExpanded;
  const isTabWritable = useCallback((tab: FileViewerWorkbenchTab | null) => (
    tab ? (isPathWritable?.(tab.path) ?? true) : true
  ), [isPathWritable]);
  const activeTabWritable = isTabWritable(activeTab);
  const canMutate = !readOnly && capabilities.canEdit !== false && activeTabWritable;
  const canSave = canMutate && capabilities.canSave !== false && Boolean(adapter.saveFile);
  const canCloseTabs = capabilities.canCloseTabs !== false;

  const stats = useMemo(() => getStats(activeTab?.content ?? ''), [activeTab?.content]);
  const tabLayoutKey = useMemo(
    () => tabs.map((tab) => tab.id).join('|'),
    [tabs],
  );
  const activeViewerOwnerKey = useMemo(() => getViewerOwnerKey(activeTab), [activeTab]);
  const toolbarFormatActions = formatActions.ownerKey === activeViewerOwnerKey ? formatActions.node : null;

  const setExpanded = useCallback((next: boolean) => {
    if (onExpandedChange) {
      onExpandedChange(next);
    } else {
      setUncontrolledExpanded(next);
    }
  }, [onExpandedChange]);

  const registerFormatActions = useCallback((
    node: ReactNode | null,
    registrationKey = DEFAULT_FORMAT_ACTIONS_KEY,
    ownerKey = DEFAULT_FORMAT_ACTIONS_OWNER_KEY,
  ) => {
    const current = formatActionsRef.current;

    if (node === null) {
      if (current.key === registrationKey && current.ownerKey === ownerKey) {
        const next = { key: EMPTY_FORMAT_ACTIONS_KEY, ownerKey: '', node: null };
        formatActionsRef.current = next;
        setFormatActions(next);
      }
      return;
    }

    if (current.key === registrationKey && current.ownerKey === ownerKey) {
      return;
    }

    const next = { key: registrationKey, ownerKey, node };
    formatActionsRef.current = next;
    setFormatActions(next);
  }, []);

  const checkScroll = useCallback(() => {
    const element = tabScrollRef.current;
    if (!element) return;
    const { scrollLeft, scrollWidth, clientWidth } = element;
    const nextShowLeftScroll = scrollLeft > 0;
    const nextShowRightScroll = scrollLeft < scrollWidth - clientWidth - 1;

    setShowLeftScroll((current) => (
      current === nextShowLeftScroll ? current : nextShowLeftScroll
    ));
    setShowRightScroll((current) => (
      current === nextShowRightScroll ? current : nextShowRightScroll
    ));
  }, []);

  const scrollTabs = useCallback((direction: 'left' | 'right') => {
    tabScrollRef.current?.scrollBy({
      left: direction === 'left' ? -200 : 200,
      behavior: 'smooth',
    });
    window.setTimeout(checkScroll, 300);
  }, [checkScroll]);

  useEffect(() => {
    checkScroll();
    window.addEventListener('resize', checkScroll);
    return () => window.removeEventListener('resize', checkScroll);
  }, [checkScroll, tabLayoutKey]);

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setExpanded(false);
      }
    };

    if (effectiveExpanded) {
      document.addEventListener('keydown', handleKeyDown);
    }

    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [effectiveExpanded, setExpanded]);

  const updateTab = (tabId: string, updates: Partial<FileViewerWorkbenchTab>) => {
    onTabsChange(tabs.map((tab) => (tab.id === tabId ? { ...tab, ...updates } : tab)));
  };

  const setActiveContent = (content: string) => {
    if (!activeTab) return;
    updateTab(activeTab.id, {
      content,
      isModified: content !== activeTab.originalContent,
    });
  };

  const closeTab = (tabId: string) => {
    if (!canCloseTabs) return;
    const closingIndex = tabs.findIndex((tab) => tab.id === tabId);
    const nextTabs = tabs.filter((tab) => tab.id !== tabId);
    onTabsChange(nextTabs);

    if (activeTabId === tabId) {
      const nextActive = nextTabs[Math.min(closingIndex, nextTabs.length - 1)] ?? null;
      onActiveTabChange(nextActive?.id ?? null);
    }
  };

  const saveTab = async (tab: FileViewerWorkbenchTab) => {
    if (!adapter.saveFile || readOnly || capabilities.canEdit === false || capabilities.canSave === false || !isTabWritable(tab)) return;
    await adapter.saveFile(tab.path, tab.content);
    updateTab(tab.id, {
      originalContent: tab.content,
      isModified: false,
    });
  };

  const revertTab = (tab: FileViewerWorkbenchTab) => {
    updateTab(tab.id, {
      content: tab.originalContent,
      isModified: false,
    });
  };

  const saveAllTabs = async () => {
    if (!adapter.saveFile || readOnly || capabilities.canEdit === false || capabilities.canSave === false) return;
    const modifiedTabs = tabs.filter((tab) => tab.isModified && isTabWritable(tab));
    await Promise.all(modifiedTabs.map((tab) => adapter.saveFile?.(tab.path, tab.content)));
    onTabsChange(tabs.map((tab) => (
      tab.isModified && isTabWritable(tab)
        ? { ...tab, originalContent: tab.content, isModified: false }
        : tab
    )));
  };

  const revertAllTabs = () => {
    onTabsChange(tabs.map((tab) => (
      tab.isModified
        ? { ...tab, content: tab.originalContent, isModified: false }
        : tab
    )));
  };

  const closeAllTabs = () => {
    if (!canCloseTabs) return;
    onTabsChange([]);
    onActiveTabChange(null);
  };

  const closeOtherTabs = (tabId: string) => {
    const target = tabs.find((tab) => tab.id === tabId);
    if (!target) return;
    onTabsChange([target]);
    onActiveTabChange(target.id);
  };

  const closeTabsToRight = (tabId: string) => {
    const index = tabs.findIndex((tab) => tab.id === tabId);
    if (index < 0) return;
    const nextTabs = tabs.slice(0, index + 1);
    onTabsChange(nextTabs);
    if (activeTabId && !nextTabs.some((tab) => tab.id === activeTabId)) {
      onActiveTabChange(tabId);
    }
  };

  const closeSavedTabs = () => {
    const nextTabs = tabs.filter((tab) => tab.isModified);
    onTabsChange(nextTabs);
    if (activeTabId && !nextTabs.some((tab) => tab.id === activeTabId)) {
      onActiveTabChange(nextTabs[0]?.id ?? null);
    }
  };

  const handleTabDragStart = (event: ReactDragEvent, tabId: string) => {
    draggedTabIdRef.current = tabId;
    setDropIndicator(null);
    if (event.dataTransfer) {
      event.dataTransfer.effectAllowed = 'move';
      event.dataTransfer.setData(FILE_WORKBENCH_TAB_DND_MIME, tabId);
    }
  };

  // Foreign drags do not set this instance's ref, and their tab id is
  // unavailable until drop; only the dedicated MIME type is readable.
  const isForeignWorkbenchDrag = (event: ReactDragEvent) => (
    Boolean(onForeignTabDrop) && Boolean(event.dataTransfer?.types?.includes(FILE_WORKBENCH_TAB_DND_MIME))
  );

  // Container-level handlers must only react to the strip's empty area;
  // hovers over tabs bubble up and are already handled per tab.
  const isStripEmptyAreaEvent = (event: ReactDragEvent) => (
    !(event.target instanceof Element && event.target.closest('[draggable="true"]'))
  );

  const updateDropIndicator = (tabId: string, position: 'before' | 'after') => {
    setDropIndicator((current) => (
      current?.tabId === tabId && current.position === position
        ? current
        : { tabId, position }
    ));
  };

  const handleTabDragOver = (event: ReactDragEvent, targetTabId: string) => {
    const draggedTabId = draggedTabIdRef.current;
    if (!draggedTabId && !isForeignWorkbenchDrag(event)) return;

    // Preventing the default enables the drop.
    event.preventDefault();
    if (event.dataTransfer) {
      event.dataTransfer.dropEffect = 'move';
    }

    if (draggedTabId === targetTabId) {
      setDropIndicator(null);
      return;
    }

    const position = getPointerDropPosition(event.clientX, event.currentTarget.getBoundingClientRect());
    updateDropIndicator(targetTabId, position);
  };

  const handleTabDrop = (event: ReactDragEvent, targetTabId: string) => {
    const draggedTabId = draggedTabIdRef.current || event.dataTransfer?.getData(FILE_WORKBENCH_TAB_DND_MIME);
    draggedTabIdRef.current = null;
    setDropIndicator(null);
    if (!draggedTabId) return;

    event.preventDefault();
    event.stopPropagation();
    if (draggedTabId === targetTabId) return;

    const position = getPointerDropPosition(event.clientX, event.currentTarget.getBoundingClientRect());

    if (!tabs.some((tab) => tab.id === draggedTabId)) {
      onForeignTabDrop?.(draggedTabId, targetTabId, position);
      return;
    }

    const nextTabs = reorderTabs(tabs, draggedTabId, targetTabId, position);
    if (nextTabs !== tabs) {
      onTabsChange(nextTabs);
    }
  };

  const handleStripDragOver = (event: ReactDragEvent) => {
    if (!isStripEmptyAreaEvent(event)) return;
    const draggedTabId = draggedTabIdRef.current;
    if (!draggedTabId && !isForeignWorkbenchDrag(event)) return;

    event.preventDefault();
    if (event.dataTransfer) {
      event.dataTransfer.dropEffect = 'move';
    }

    const lastTab = tabs[tabs.length - 1];
    if (!lastTab || lastTab.id === draggedTabId) {
      setDropIndicator(null);
      return;
    }
    updateDropIndicator(lastTab.id, 'after');
  };

  const handleStripDrop = (event: ReactDragEvent) => {
    if (!isStripEmptyAreaEvent(event)) return;
    const draggedTabId = draggedTabIdRef.current || event.dataTransfer?.getData(FILE_WORKBENCH_TAB_DND_MIME);
    draggedTabIdRef.current = null;
    setDropIndicator(null);
    if (!draggedTabId) return;

    event.preventDefault();

    if (!tabs.some((tab) => tab.id === draggedTabId)) {
      onForeignTabDrop?.(draggedTabId, null, 'after');
      return;
    }

    const lastTab = tabs[tabs.length - 1];
    if (!lastTab || lastTab.id === draggedTabId) return;
    const nextTabs = reorderTabs(tabs, draggedTabId, lastTab.id, 'after');
    if (nextTabs !== tabs) {
      onTabsChange(nextTabs);
    }
  };

  const handleStripDragLeave = (event: ReactDragEvent) => {
    if (event.relatedTarget instanceof Node && event.currentTarget.contains(event.relatedTarget)) return;
    setDropIndicator(null);
  };

  const handleTabDragEnd = () => {
    draggedTabIdRef.current = null;
    setDropIndicator(null);
  };

  // A successful cross-pane drop unmounts the dragged tab before dragend can
  // fire on it, so drag state must also be reset when the tab leaves this pane.
  useEffect(() => {
    const hasTab = (tabId: string) => tabs.some((tab) => tab.id === tabId);
    if (draggedTabIdRef.current && !hasTab(draggedTabIdRef.current)) {
      draggedTabIdRef.current = null;
      setDropIndicator(null);
      return;
    }
    setDropIndicator((current) => (
      current && !hasTab(current.tabId) ? null : current
    ));
  }, [tabs]);

  const toggleExpanded = () => {
    setExpanded(!effectiveExpanded);
  };

  useEffect(() => {
    if (effectiveExpanded && tabs.length === 0) {
      setExpanded(false);
    }
  }, [effectiveExpanded, setExpanded, tabs.length]);

  return {
    activeTab,
    effectiveExpanded,
    canMutate,
    canSave,
    stats,
    activeViewerOwnerKey,
    toolbarFormatActions,
    codeEditorRef,
    registerFormatActions,
    updateTab,
    setActiveContent,
    saveTab,
    tabStripProps: {
      tabs,
      activeTabId,
      activeTab,
      adapter,
      capabilities,
      readOnly,
      effectiveExpanded,
      canMutate,
      canSave,
      canCloseTabs,
      showLeftScroll,
      showRightScroll,
      dropIndicator,
      tabScrollRef,
      codeEditorRef,
      isTabWritable,
      renderReadOnlyBadge,
      onActiveTabChange,
      onSplitTab,
      canSplitTab,
      onCheckScroll: checkScroll,
      onScrollTabs: scrollTabs,
      onCloseTab: closeTab,
      onTabDragStart: handleTabDragStart,
      onTabDragOver: handleTabDragOver,
      onTabDrop: handleTabDrop,
      onTabDragEnd: handleTabDragEnd,
      onStripDragOver: handleStripDragOver,
      onStripDrop: handleStripDrop,
      onStripDragLeave: handleStripDragLeave,
      onToggleExpanded: toggleExpanded,
      onSaveTab: saveTab,
      onSaveAllTabs: saveAllTabs,
      onRevertTab: revertTab,
      onRevertAllTabs: revertAllTabs,
      onCloseAllTabs: closeAllTabs,
      onCloseOtherTabs: closeOtherTabs,
      onCloseTabsToRight: closeTabsToRight,
      onCloseSavedTabs: closeSavedTabs,
    },
  };
};
