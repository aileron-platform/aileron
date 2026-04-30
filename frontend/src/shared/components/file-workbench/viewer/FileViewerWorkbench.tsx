import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import {
  ChevronLeft,
  ChevronRight,
  Copy,
  FolderTree,
  Maximize2,
  Minimize2,
  MoreHorizontal,
  Redo2,
  RotateCcw,
  Save,
  SaveAll,
  Undo2,
  X,
} from 'lucide-react';
import { useI18n } from '@/shared/hooks/useI18n';
import { cn } from '@/shared/utils/cn';
import { formatFileSize, isImageFile } from '@/shared/utils/fileTypeUtils';
import {
  getFileIcon,
  getFileLanguage,
  isDrawioFile,
  isMarkdownFile,
  isMermaidFile,
} from '@/shared/utils/fileIconUtils';
import { CodeTextEditor, type CodeTextEditorRef } from './CodeTextEditor';
import { SharedDrawioViewer } from './SharedDrawioViewer';
import { SharedImageViewer } from './SharedImageViewer';
import { SharedMarkdownViewer } from './SharedMarkdownViewer';
import { SharedMermaidViewer } from './SharedMermaidViewer';
import type {
  FileViewerWorkbenchFocusToolbarParams,
  FileViewerWorkbenchProps,
  FileViewerWorkbenchTab,
} from './types';

const getStats = (content: string) => ({
  lines: content.split('\n').length,
  characters: content.length,
});

const MORE_MENU_WIDTH = 192;
const TAB_CONTEXT_MENU_WIDTH = 192;
const MENU_VIEWPORT_PADDING = 8;

const clampMenuLeft = (left: number, width: number) => {
  if (typeof window === 'undefined') return left;
  return Math.max(
    MENU_VIEWPORT_PADDING,
    Math.min(left, window.innerWidth - width - MENU_VIEWPORT_PADDING),
  );
};

export const FileViewerWorkbench: React.FC<FileViewerWorkbenchProps> = ({
  tabs,
  activeTabId,
  adapter,
  capabilities = {},
  statusMetadata,
  className,
  headerActions,
  readOnly = false,
  isExpanded,
  onExpandedChange,
  useViewportExpansion = true,
  hideChromeWhenExpanded = false,
  renderFocusToolbar,
  onTabsChange,
  onActiveTabChange,
}) => {
  const { t } = useI18n();
  const tabScrollRef = useRef<HTMLDivElement>(null);
  const tabContextMenuRef = useRef<HTMLDivElement>(null);
  const moreMenuRef = useRef<HTMLDivElement>(null);
  const moreButtonRef = useRef<HTMLButtonElement>(null);
  const codeEditorRef = useRef<CodeTextEditorRef>(null);
  const [showLeftScroll, setShowLeftScroll] = useState(false);
  const [showRightScroll, setShowRightScroll] = useState(false);
  const [tabContextMenuPosition, setTabContextMenuPosition] = useState<{ top: number; left: number } | null>(null);
  const [contextMenuTabId, setContextMenuTabId] = useState<string | null>(null);
  const [moreMenuPosition, setMoreMenuPosition] = useState<{ top: number; left: number } | null>(null);
  const [uncontrolledExpanded, setUncontrolledExpanded] = useState(false);
  const activeTab = tabs.find((tab) => tab.id === activeTabId) ?? null;
  const effectiveExpanded = isExpanded ?? uncontrolledExpanded;
  const hideChrome = effectiveExpanded && hideChromeWhenExpanded;
  const canMutate = !readOnly && capabilities.canEdit !== false;
  const canSave = canMutate && capabilities.canSave !== false && Boolean(adapter.saveFile);
  const canCloseTabs = capabilities.canCloseTabs !== false;

  const stats = useMemo(() => getStats(activeTab?.content ?? ''), [activeTab?.content]);

  const contextMenuTab = useMemo(
    () => tabs.find((tab) => tab.id === contextMenuTabId) ?? null,
    [contextMenuTabId, tabs],
  );

  const closeTabContextMenu = useCallback(() => {
    setTabContextMenuPosition(null);
    setContextMenuTabId(null);
  }, []);

  const closeToolbarMenus = useCallback(() => {
    setMoreMenuPosition(null);
  }, []);

  const checkScroll = useCallback(() => {
    const element = tabScrollRef.current;
    if (!element) return;
    const { scrollLeft, scrollWidth, clientWidth } = element;
    setShowLeftScroll(scrollLeft > 0);
    setShowRightScroll(scrollLeft < scrollWidth - clientWidth - 1);
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
  }, [checkScroll, tabs]);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      const target = event.target as Node;
      if (!tabContextMenuRef.current?.contains(target)) {
        closeTabContextMenu();
      }
    };

    if (tabContextMenuPosition) {
      document.addEventListener('mousedown', handleClickOutside);
    }

    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [closeTabContextMenu, tabContextMenuPosition]);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      const target = event.target as Node;
      const isInsideMore = moreButtonRef.current?.contains(target) || moreMenuRef.current?.contains(target);
      if (!isInsideMore) {
        closeToolbarMenus();
      }
    };

    if (moreMenuPosition) {
      document.addEventListener('mousedown', handleClickOutside);
    }

    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [closeToolbarMenus, moreMenuPosition]);

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setIsExpanded(false);
        closeToolbarMenus();
        closeTabContextMenu();
      }
    };

    if (effectiveExpanded) {
      document.addEventListener('keydown', handleKeyDown);
    }

    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [closeTabContextMenu, closeToolbarMenus, effectiveExpanded]);

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
    if (!canSave || !adapter.saveFile) return;
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
    if (!canSave || !adapter.saveFile) return;
    const modifiedTabs = tabs.filter((tab) => tab.isModified);
    await Promise.all(modifiedTabs.map((tab) => adapter.saveFile?.(tab.path, tab.content)));
    onTabsChange(tabs.map((tab) => (
      tab.isModified
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

  const handleTabContextMenu = (event: React.MouseEvent, tabId: string) => {
    event.preventDefault();
    event.stopPropagation();
    setTabContextMenuPosition({
      top: event.clientY,
      left: clampMenuLeft(event.clientX, TAB_CONTEXT_MENU_WIDTH),
    });
    setContextMenuTabId(tabId);
  };

  const openMoreMenu = () => {
    if (!moreButtonRef.current) return;
    const rect = moreButtonRef.current.getBoundingClientRect();
    setMoreMenuPosition((current) => (
      current
        ? null
        : { top: rect.bottom + 4, left: clampMenuLeft(rect.right - MORE_MENU_WIDTH, MORE_MENU_WIDTH) }
    ));
  };

  const toggleExpanded = () => {
    const nextExpanded = !effectiveExpanded;
    if (onExpandedChange) {
      onExpandedChange(nextExpanded);
    } else {
      setUncontrolledExpanded(nextExpanded);
    }
    closeToolbarMenus();
    closeTabContextMenu();
  };

  const renderSharedFocusToolbar = (params: FileViewerWorkbenchFocusToolbarParams) => (
    renderFocusToolbar?.(params)
  );

  const renderActiveViewer = () => {
    if (!activeTab) {
      return (
        <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
          {t('shared.fileViewer.emptyState.title')}
        </div>
      );
    }

    if (activeTab.isLoading) {
      return (
        <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
          {t('shared.fileViewer.loading')}
        </div>
      );
    }

    if (activeTab.error) {
      return (
        <div className="flex h-full items-center justify-center text-sm text-destructive">
          {activeTab.error}
        </div>
      );
    }

    if (isImageFile(activeTab.name)) {
      return (
        <SharedImageViewer
          filePath={activeTab.path}
          fileName={activeTab.name}
          adapter={adapter}
          isFocusMode={effectiveExpanded}
          renderFocusToolbar={renderSharedFocusToolbar}
        />
      );
    }

    if (isMermaidFile(activeTab.name)) {
      return (
        <SharedMermaidViewer
          content={activeTab.content}
          fileName={activeTab.name}
          isFocusMode={effectiveExpanded}
          renderFocusToolbar={renderSharedFocusToolbar}
        />
      );
    }

    if (isMarkdownFile(activeTab.name)) {
      return (
        <SharedMarkdownViewer
          content={activeTab.content}
          fileName={activeTab.name}
          readOnly={!canMutate}
          isFocusMode={effectiveExpanded}
          renderFocusToolbar={renderSharedFocusToolbar}
          onReload={() => adapter.readFile(activeTab.path)}
          onContentChange={setActiveContent}
        />
      );
    }

    if (isDrawioFile(activeTab.name)) {
      return (
        <SharedDrawioViewer
          filePath={activeTab.path}
          fileName={activeTab.name}
          content={activeTab.content}
          originalContent={activeTab.originalContent}
          readOnly={!canMutate}
          adapter={adapter}
          canPreview={capabilities.canPreviewDrawio !== false}
          isFocusMode={effectiveExpanded}
          renderFocusToolbar={renderSharedFocusToolbar}
          onContentChange={setActiveContent}
          onModifiedChange={(isModified) => updateTab(activeTab.id, { isModified })}
        />
      );
    }

    const editor = (
      <CodeTextEditor
        ref={codeEditorRef}
        fileName={activeTab.name}
        content={activeTab.content}
        originalContent={activeTab.originalContent}
        readOnly={!canMutate}
        onContentChange={setActiveContent}
        onModifiedChange={(isModified) => updateTab(activeTab.id, { isModified })}
      />
    );

    if (effectiveExpanded && renderFocusToolbar) {
      return (
        <div className="flex h-full min-h-0 flex-col">
          {renderFocusToolbar({
            icon: getFileIcon(activeTab.name),
            title: activeTab.name,
            subtitle: activeTab.path,
            metadata: (
              <>
                <span>{getFileLanguage(activeTab.name)}</span>
                <span>{formatFileSize(stats.characters)}</span>
                <span>{t('shared.fileViewer.status.lineCount', { count: stats.lines })}</span>
                {activeTab.isModified ? (
                  <span className="text-primary">{t('shared.fileViewer.status.modified')}</span>
                ) : null}
              </>
            ),
          })}
          <div className="min-h-0 flex-1">{editor}</div>
        </div>
      );
    }

    return editor;
  };

  const renderWorkbenchToolbar = () => (
    <div className="flex h-full items-center border-l border-border">
      {headerActions}
      <button
        ref={moreButtonRef}
        type="button"
        className="flex h-full items-center justify-center px-1.5 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
        onClick={openMoreMenu}
        title={t('shared.fileViewer.toolbar.more')}
        aria-label={t('shared.fileViewer.toolbar.more')}
      >
        <MoreHorizontal className="h-3.5 w-3.5" />
      </button>
    </div>
  );

  return (
    <div
      className={cn(
        'flex h-full min-h-0 flex-col bg-background',
        effectiveExpanded && useViewportExpansion && 'fixed inset-0 z-[99990] h-screen w-screen',
        className,
      )}
    >
      {tabs.length > 0 && !hideChrome && (
        <div className="relative flex h-10 shrink-0 border-b border-border bg-card" style={{ overflowY: 'visible' }}>
          <div className="relative flex min-w-0 flex-1">
            {showLeftScroll && (
              <button
                type="button"
                className="absolute left-0 top-0 z-20 flex h-full w-7 items-center justify-center border-r border-border bg-card/95 text-foreground shadow-sm transition-colors hover:bg-muted"
                onClick={() => scrollTabs('left')}
                aria-label={t('shared.fileViewer.tabs.scrollLeft')}
              >
                <ChevronLeft className="h-4 w-4" />
              </button>
            )}

            <div
              ref={tabScrollRef}
              className="flex min-w-0 flex-1 overflow-x-auto scrollbar-thin scrollbar-track-transparent scrollbar-thumb-muted-foreground/20"
              style={{ scrollbarWidth: 'thin' }}
              onScroll={checkScroll}
            >
              {tabs.map((tab) => (
                <div
                  key={tab.id}
                  onClick={() => onActiveTabChange(tab.id)}
                  onContextMenu={(event) => handleTabContextMenu(event, tab.id)}
                  className={cn(
                    'flex h-full min-w-0 flex-shrink-0 cursor-pointer items-center border-r border-border transition-colors hover:bg-muted/50',
                    activeTabId === tab.id
                      ? 'border-b-2 border-b-primary bg-background text-foreground'
                      : 'text-muted-foreground',
                  )}
                >
                  <div className="flex h-full min-w-0 items-center px-2.5">
                    <span className="mr-1.5 shrink-0">{getFileIcon(tab.name)}</span>
                    <span className="max-w-28 truncate text-sm" title={tab.path}>{tab.name}</span>
                    {tab.isModified && (
                      <span
                        className="ml-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-primary"
                        title={t('shared.fileViewer.status.modified')}
                      />
                    )}
                  </div>
                  {canCloseTabs && (
                    <button
                      type="button"
                      className="h-full px-1.5 text-muted-foreground hover:bg-muted/80 hover:text-foreground"
                      title={t('shared.fileViewer.tabs.close')}
                      aria-label={t('shared.fileViewer.tabs.close')}
                      onClick={(event) => {
                        event.stopPropagation();
                        closeTab(tab.id);
                      }}
                    >
                      <X className="h-3 w-3" />
                    </button>
                  )}
                </div>
              ))}
            </div>

            {showRightScroll && (
              <button
                type="button"
                className="absolute right-0 top-0 z-20 flex h-full w-7 items-center justify-center border-l border-border bg-card/95 text-foreground shadow-sm transition-colors hover:bg-muted"
                onClick={() => scrollTabs('right')}
                aria-label={t('shared.fileViewer.tabs.scrollRight')}
              >
                <ChevronRight className="h-4 w-4" />
              </button>
            )}
          </div>
          {renderWorkbenchToolbar()}
        </div>
      )}

      <div className="min-h-0 flex-1 overflow-hidden">{renderActiveViewer()}</div>

      {activeTab && !hideChrome && (
        <div className="flex h-7 shrink-0 items-center gap-3 border-t px-3 text-xs text-muted-foreground">
          <span>{getFileLanguage(activeTab.name)}</span>
          <span>{t('shared.fileViewer.status.lineCount', { count: stats.lines })}</span>
          <span>{formatFileSize(stats.characters)}</span>
          <span>{statusMetadata?.encoding ?? 'UTF-8'}</span>
          <span>{statusMetadata?.lineEnding ?? 'LF'}</span>
          {activeTab.isModified && <span className="text-primary">{t('shared.fileViewer.status.modified')}</span>}
          <div className="ml-auto" />
        </div>
      )}

      {tabContextMenuPosition && contextMenuTab && createPortal(
        <div
          ref={tabContextMenuRef}
          className="w-48 overflow-hidden rounded-lg border border-border bg-popover shadow-xl"
          style={{
            position: 'fixed',
            zIndex: 99999,
            top: `${tabContextMenuPosition.top}px`,
            left: `${tabContextMenuPosition.left}px`,
          }}
          onClick={(event) => event.stopPropagation()}
        >
          <button
            type="button"
            className="flex w-full cursor-pointer items-center border-none bg-transparent px-4 py-2.5 text-left text-sm text-popover-foreground transition-colors hover:bg-accent hover:text-accent-foreground disabled:cursor-not-allowed disabled:opacity-50"
            onClick={(event) => {
              event.preventDefault();
              event.stopPropagation();
              void saveTab(contextMenuTab);
              closeTabContextMenu();
            }}
            disabled={!canSave || !contextMenuTab.isModified}
          >
            <Save className="mr-2 h-4 w-4" />
            {t('shared.fileViewer.tabContextMenu.save')}
          </button>
          <button
            type="button"
            className="flex w-full cursor-pointer items-center border-none bg-transparent px-4 py-2.5 text-left text-sm text-popover-foreground transition-colors hover:bg-accent hover:text-accent-foreground disabled:cursor-not-allowed disabled:opacity-50"
            onClick={(event) => {
              event.preventDefault();
              event.stopPropagation();
              revertTab(contextMenuTab);
              closeTabContextMenu();
            }}
            disabled={!canMutate || !contextMenuTab.isModified}
          >
            <RotateCcw className="mr-2 h-4 w-4" />
            {t('shared.fileViewer.tabContextMenu.revert')}
          </button>
          <div className="my-1 border-t border-border" />
          <button
            type="button"
            className="flex w-full cursor-pointer items-center border-none bg-transparent px-4 py-2.5 text-left text-sm text-popover-foreground transition-colors hover:bg-accent hover:text-accent-foreground"
            onClick={(event) => {
              event.preventDefault();
              event.stopPropagation();
              closeTab(contextMenuTab.id);
              closeTabContextMenu();
            }}
          >
            {t('shared.fileViewer.tabContextMenu.close')}
          </button>
          <button
            type="button"
            className="flex w-full cursor-pointer items-center border-none bg-transparent px-4 py-3 text-left text-sm text-popover-foreground transition-colors hover:bg-accent hover:text-accent-foreground"
            onClick={(event) => {
              event.preventDefault();
              event.stopPropagation();
              closeOtherTabs(contextMenuTab.id);
              closeTabContextMenu();
            }}
          >
            {t('shared.fileViewer.tabContextMenu.closeOthers')}
          </button>
          <button
            type="button"
            className="flex w-full cursor-pointer items-center border-none bg-transparent px-4 py-3 text-left text-sm text-popover-foreground transition-colors hover:bg-accent hover:text-accent-foreground"
            onClick={(event) => {
              event.preventDefault();
              event.stopPropagation();
              closeTabsToRight(contextMenuTab.id);
              closeTabContextMenu();
            }}
          >
            {t('shared.fileViewer.tabContextMenu.closeToTheRight')}
          </button>
          <button
            type="button"
            className="flex w-full cursor-pointer items-center border-none bg-transparent px-4 py-3 text-left text-sm text-popover-foreground transition-colors hover:bg-accent hover:text-accent-foreground"
            onClick={(event) => {
              event.preventDefault();
              event.stopPropagation();
              closeSavedTabs();
              closeTabContextMenu();
            }}
          >
            {t('shared.fileViewer.tabContextMenu.closeSaved')}
          </button>
          <button
            type="button"
            className="flex w-full cursor-pointer items-center border-none bg-transparent px-4 py-3 text-left text-sm text-popover-foreground transition-colors hover:bg-accent hover:text-accent-foreground"
            onClick={(event) => {
              event.preventDefault();
              event.stopPropagation();
              closeAllTabs();
              closeTabContextMenu();
            }}
          >
            {t('shared.fileViewer.tabContextMenu.closeAll')}
          </button>
        </div>,
        document.body,
      )}

      {moreMenuPosition && createPortal(
        <div
          ref={moreMenuRef}
          className="w-48 overflow-hidden rounded-lg border border-border bg-popover shadow-xl"
          style={{
            position: 'fixed',
            zIndex: 99999,
            top: `${moreMenuPosition.top}px`,
            left: `${moreMenuPosition.left}px`,
          }}
          onClick={(event) => event.stopPropagation()}
        >
          {canSave && activeTab && (
            <>
              <button
                type="button"
                className="flex w-full cursor-pointer items-center border-none bg-transparent px-3 py-2 text-left text-xs text-popover-foreground transition-colors hover:bg-accent hover:text-accent-foreground disabled:cursor-not-allowed disabled:opacity-50"
                onClick={() => {
                  void saveTab(activeTab);
                  closeToolbarMenus();
                }}
                disabled={!activeTab.isModified}
              >
                <Save className="mr-2 h-3.5 w-3.5" />
                {t('shared.fileViewer.toolbar.save')}
                <span className="ml-auto text-[10px] text-muted-foreground">Ctrl+S</span>
              </button>
              <button
                type="button"
                className="flex w-full cursor-pointer items-center border-none bg-transparent px-3 py-2 text-left text-xs text-popover-foreground transition-colors hover:bg-accent hover:text-accent-foreground disabled:cursor-not-allowed disabled:opacity-50"
                onClick={() => {
                  void saveAllTabs();
                  closeToolbarMenus();
                }}
                disabled={!tabs.some((tab) => tab.isModified)}
              >
                <Save className="mr-2 h-3.5 w-3.5" />
                {t('shared.fileViewer.toolbar.saveAll')}
                <span className="ml-auto text-[10px] text-muted-foreground">Ctrl+Shift+S</span>
              </button>
              <div className="border-t border-border" />
              <button
                type="button"
                className="flex w-full cursor-pointer items-center border-none bg-transparent px-3 py-2 text-left text-xs text-popover-foreground transition-colors hover:bg-accent hover:text-accent-foreground disabled:cursor-not-allowed disabled:opacity-50"
                onClick={() => {
                  revertTab(activeTab);
                  closeToolbarMenus();
                }}
                disabled={!activeTab.isModified}
              >
                <RotateCcw className="mr-2 h-3.5 w-3.5" />
                {t('shared.fileViewer.toolbar.revert')}
              </button>
              <button
                type="button"
                className="flex w-full cursor-pointer items-center border-none bg-transparent px-3 py-2 text-left text-xs text-popover-foreground transition-colors hover:bg-accent hover:text-accent-foreground disabled:cursor-not-allowed disabled:opacity-50"
                onClick={() => {
                  revertAllTabs();
                  closeToolbarMenus();
                }}
                disabled={!tabs.some((tab) => tab.isModified)}
              >
                <RotateCcw className="mr-2 h-3.5 w-3.5" />
                {t('shared.fileViewer.toolbar.revertAll')}
              </button>
              <div className="my-1 border-t border-border" />
            </>
          )}
          <button
            type="button"
            className="flex w-full cursor-pointer items-center border-none bg-transparent px-3 py-2 text-left text-xs text-popover-foreground transition-colors hover:bg-accent hover:text-accent-foreground disabled:cursor-not-allowed disabled:opacity-50"
            onClick={toggleExpanded}
            disabled={!activeTab}
          >
            {effectiveExpanded ? <Minimize2 className="mr-2 h-3.5 w-3.5" /> : <Maximize2 className="mr-2 h-3.5 w-3.5" />}
            {effectiveExpanded ? t('shared.fileViewer.toolbar.collapse') : t('shared.fileViewer.toolbar.expand')}
          </button>
          <button
            type="button"
            className="flex w-full cursor-pointer items-center border-none bg-transparent px-3 py-2 text-left text-xs text-popover-foreground transition-colors hover:bg-accent hover:text-accent-foreground disabled:cursor-not-allowed disabled:opacity-50"
            onClick={() => {
              codeEditorRef.current?.undo();
              closeToolbarMenus();
            }}
            disabled={!activeTab}
          >
            <Undo2 className="mr-2 h-3.5 w-3.5" />
            {t('shared.fileViewer.toolbar.undo')}
          </button>
          <button
            type="button"
            className="flex w-full cursor-pointer items-center border-none bg-transparent px-3 py-2 text-left text-xs text-popover-foreground transition-colors hover:bg-accent hover:text-accent-foreground disabled:cursor-not-allowed disabled:opacity-50"
            onClick={() => {
              codeEditorRef.current?.redo();
              closeToolbarMenus();
            }}
            disabled={!activeTab}
          >
            <Redo2 className="mr-2 h-3.5 w-3.5" />
            {t('shared.fileViewer.toolbar.redo')}
          </button>
          <div className="my-1 border-t border-border" />
          <button
            type="button"
            className="flex w-full cursor-pointer items-center border-none bg-transparent px-3 py-2 text-left text-xs text-popover-foreground transition-colors hover:bg-accent hover:text-accent-foreground disabled:cursor-not-allowed disabled:opacity-50"
            onClick={() => {
              if (activeTab) void adapter.copyPath?.(activeTab.path);
              closeToolbarMenus();
            }}
            disabled={!activeTab || capabilities.canCopyPath === false || !adapter.copyPath}
          >
            <Copy className="mr-2 h-3.5 w-3.5" />
            {t('shared.fileViewer.toolbar.copyPath')}
          </button>
          <button
            type="button"
            className="flex w-full cursor-pointer items-center border-none bg-transparent px-3 py-2 text-left text-xs text-popover-foreground transition-colors hover:bg-accent hover:text-accent-foreground disabled:cursor-not-allowed disabled:opacity-50"
            onClick={() => {
              if (activeTab) adapter.revealInTree?.(activeTab.path);
              closeToolbarMenus();
            }}
            disabled={!activeTab || capabilities.canRevealInTree === false || !adapter.revealInTree}
          >
            <FolderTree className="mr-2 h-3.5 w-3.5" />
            {t('shared.fileViewer.toolbar.revealInTree')}
          </button>
          <div className="my-1 border-t border-border" />
          <button
            type="button"
            className="flex w-full cursor-pointer items-center border-none bg-transparent px-3 py-2 text-left text-xs text-popover-foreground transition-colors hover:bg-accent hover:text-accent-foreground"
            onClick={() => {
              closeAllTabs();
              closeToolbarMenus();
            }}
          >
            <X className="mr-2 h-3.5 w-3.5" />
            {t('shared.fileViewer.toolbar.closeAll')}
          </button>
          {canSave && (
            <button
              type="button"
              className="flex w-full cursor-pointer items-center border-none bg-transparent px-3 py-2 text-left text-xs text-popover-foreground transition-colors hover:bg-accent hover:text-accent-foreground"
              onClick={() => {
                void saveAllTabs().then(closeAllTabs);
                closeToolbarMenus();
              }}
            >
              <SaveAll className="mr-2 h-3.5 w-3.5" />
              {t('shared.fileViewer.toolbar.saveAndCloseAll')}
            </button>
          )}
        </div>,
        document.body,
      )}
    </div>
  );
};
