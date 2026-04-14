/**
 * 檔案編輯器組件
 * 顯示檔案內容和基本編輯功能
 * 完全按照原始設計重構，保持 UI 一致性
 */

import React, { useState, useEffect, useRef, useCallback } from 'react';
import { createPortal } from 'react-dom';
import { Loader2, X, FileText, ChevronLeft, ChevronRight, Save, RotateCcw } from 'lucide-react';
import { useWorkspace } from '../../../providers/WorkspaceProvider';
import { getFileIcon, getFileLanguage, isMermaidFile, isMarkdownFile, isDrawioFile } from '../utils/fileIconUtils';
import { formatFileSize, isImageFile } from '../utils/fileTypeUtils';
import { useI18n } from '@/shared/hooks/useI18n';
import { MermaidViewer } from './MermaidViewer';
import { MarkdownViewer } from './MarkdownViewer';
import { ImageViewer } from './ImageViewer';
import { DrawioViewer } from './DrawioViewer';
import { CodeEditor, type CodeEditorRef } from './CodeEditor';
import { EditorToolbar } from './EditorToolbar';
import { createLogger } from '@/shared/services/logger';
import { useToast } from '@/shared/components/ui/use-toast';

const logger = createLogger('FileEditor');
const SCROLL_AMOUNT = 200;

export const FileEditor: React.FC = () => {
  const {
    workspace,
    workspaceRuntime,
    closeTab,
    switchToTab,
    closeAllTabs,
    fileTreeActions: actions,
    fileEditor
  } = useWorkspace();
  const { t } = useI18n();
  const { toast } = useToast();

  const [loadingFiles, setLoadingFiles] = useState<string[]>([]);
  const [showTabContextMenu, setShowTabContextMenu] = useState(false);
  const [tabContextMenuPosition, setTabContextMenuPosition] = useState<{ top: number; left: number } | null>(null);
  const [contextMenuTabId, setContextMenuTabId] = useState<string | null>(null);

  // Tab 捲動狀態
  const [showLeftScroll, setShowLeftScroll] = useState(false);
  const [showRightScroll, setShowRightScroll] = useState(false);

  // 追蹤當前 workspace ID，用於在切換 workspace 時清理
  const currentWorkspaceIdRef = useRef<string | null>(null);

  const tabContextMenuRef = useRef<HTMLDivElement>(null);
  const tabsListRef = useRef<HTMLDivElement>(null);

  // 存儲每個 CodeEditor 的 ref
  const editorRefsMap = useRef<Map<string, CodeEditorRef | null>>(new Map());
  // 當前活動編輯器的 ref
  const activeEditorRef = useRef<CodeEditorRef | null>(null);

  const activeTab = workspace.openTabs.find(tab => tab.id === workspace.activeTabId);

  // 更新當前活動編輯器的 ref
  useEffect(() => {
    if (workspace.activeTabId) {
      activeEditorRef.current = editorRefsMap.current.get(workspace.activeTabId) || null;
    } else {
      activeEditorRef.current = null;
    }
  }, [workspace.activeTabId]);

  // 檢查是否需要顯示捲動箭頭
  const checkScroll = useCallback(() => {
    if (tabsListRef.current) {
      const { scrollLeft, scrollWidth, clientWidth } = tabsListRef.current;
      setShowLeftScroll(scrollLeft > 0);
      setShowRightScroll(scrollLeft < scrollWidth - clientWidth - 1);
    }
  }, []);

  // 捲動 tabs 列表
  const scrollTabs = useCallback(
    (direction: 'left' | 'right') => {
      if (tabsListRef.current) {
        tabsListRef.current.scrollBy({
          left: direction === 'left' ? -SCROLL_AMOUNT : SCROLL_AMOUNT,
          behavior: 'smooth',
        });
        setTimeout(checkScroll, 300);
      }
    },
    [checkScroll],
  );

  // 監聽 tabs 變化和視窗大小變化，更新捲動狀態
  useEffect(() => {
    checkScroll();
    window.addEventListener('resize', checkScroll);
    return () => window.removeEventListener('resize', checkScroll);
  }, [checkScroll, workspace.openTabs]);

  // 當 workspace 變更時，記錄新的 workspace ID
  // CodeEditor 組件會在卸載時自動清理，所以我們不需要手動清理
  useEffect(() => {
    currentWorkspaceIdRef.current = workspaceRuntime.workspaceId;
  }, [workspaceRuntime.workspaceId]);

  // 點擊外部關閉右鍵選單
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      const target = event.target as Node;
      const isClickInTabContextMenu = tabContextMenuRef.current?.contains(target);

      if (!isClickInTabContextMenu) {
        setShowTabContextMenu(false);
        setTabContextMenuPosition(null);
        setContextMenuTabId(null);
      }
    };

    if (showTabContextMenu) {
      document.addEventListener('mousedown', handleClickOutside);
    }

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [showTabContextMenu]);

  // 添加快捷鍵支援 (Ctrl+S, Ctrl+Shift+S, Ctrl+Alt+Z)
  useEffect(() => {
    const handleKeyDown = async (event: KeyboardEvent) => {
      const isMod = event.ctrlKey || event.metaKey;

      // Ctrl+Shift+S - 儲存全部
      if (isMod && event.shiftKey && event.key === 's') {
        event.preventDefault();
        if (fileEditor.modifiedTabs.length > 0) {
          const result = await fileEditor.saveAllFiles();
          if (!result.success) {
            toast({
              title: t('workspace.fileManagement.tree.notifications.saveFailed'),
              variant: 'destructive',
            });
          }
        }
        return;
      }

      // Ctrl+S - 儲存當前檔案
      if (isMod && event.key === 's') {
        event.preventDefault();
        if (activeTab && fileEditor.modifiedTabs.includes(activeTab.id)) {
          const result = await fileEditor.saveFile(activeTab.id);
          if (!result.success) {
            toast({
              title: t('workspace.fileManagement.tree.notifications.saveFailed'),
              description: result.error,
              variant: 'destructive',
            });
          }
        }
        return;
      }

      // Ctrl+Alt+Z - 還原當前檔案
      if (isMod && event.altKey && event.key === 'z') {
        event.preventDefault();
        if (activeTab && fileEditor.modifiedTabs.includes(activeTab.id)) {
          const result = fileEditor.revertFile(activeTab.id);
          if (!result.success) {
            toast({
              title: t('workspace.fileManagement.editor.toolbar.revertFailed'),
              description: result.error,
              variant: 'destructive',
            });
          }
        }
        return;
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [activeTab, fileEditor, toast, t]);

  // 載入檔案內容
  const loadFileContent = async (filePath: string) => {
    const tab = workspace.openTabs.find(t => t.id === filePath);

    // 圖片檔案不需要載入文字內容
    if (tab && isImageFile(tab.name)) {
      setLoadingFiles(prev => prev.filter(id => id !== filePath));
      return;
    }

    // 檢查是否已經有真實內容載入（不是空字串且不是載入中占位符）
    const hasValidContent = tab && tab.content &&
      tab.content !== t('workspace.fileManagement.editor.loadingPlaceholder') &&
      tab.content !== t('workspace.fileManagement.editor.loadErrorPlaceholder');

    if (hasValidContent) {
      return;
    }

    if (loadingFiles.includes(filePath)) {
      return;
    }

    setLoadingFiles(prev => prev.includes(filePath) ? prev : [...prev, filePath]);

    try {
      const content = await actions.readFileContent(filePath);
      // 更新全域狀態中的檔案內容
      fileEditor.updateTabContent(filePath, content.content);
      // 設定原始內容
      fileEditor.setOriginalContent(filePath, content.content);
      // 清除修改狀態（因為剛載入的檔案不應該被標記為已修改）
      fileEditor.setTabModified(filePath, false);
    } catch (error) {
      logger.error('Failed to load file content', { error });
      // 設置預設內容
      const errorContent = t('workspace.fileManagement.editor.loadErrorPlaceholder');
      fileEditor.updateTabContent(filePath, errorContent);
      fileEditor.setOriginalContent(filePath, errorContent);
      fileEditor.setTabModified(filePath, false);
    } finally {
      setLoadingFiles(prev => prev.filter(id => id !== filePath));
    }
  };

  // 當活動標籤改變時載入檔案內容
  useEffect(() => {
    if (activeTab) {
      loadFileContent(activeTab.id);
    }
  }, [activeTab?.id]);



  // 處理標籤頁關閉時的清理工作
  const handleCloseTab = (tabId: string) => {
    closeTab(tabId);
    setLoadingFiles(prev => prev.filter(id => id !== tabId));
  };

  // 處理關閉所有標籤頁時的清理工作
  const handleCloseAllTabs = () => {
    closeAllTabs();
    setLoadingFiles([]);
  };

  // 保存並關閉所有標籤頁
  const closeAllAndSave = async () => {
    // 保存所有修改的檔案
    const result = await fileEditor.saveAllFiles();
    if (!result.success && result.failed.length > 0) {
      // 有檔案儲存失敗，顯示警告但不關閉標籤頁
      toast({
        title: t('workspace.fileManagement.tree.notifications.saveFailed'),
        description: t('workspace.fileManagement.editor.toolbar.someFilesSaveFailed'),
        variant: 'destructive',
      });
      return;
    }
    handleCloseAllTabs();
  };

  // 切換標籤頁並同步檔案樹選擇
  const handleSwitchToTab = useCallback((tabId: string) => {
    switchToTab(tabId);
    // 使用 tabId (即檔案路徑) 同步檔案樹選擇
    actions.selectFile(tabId);
  }, [switchToTab, actions]);

  // 標籤頁右鍵選單處理函數
  const handleTabContextMenu = (e: React.MouseEvent, tabId: string) => {
    e.preventDefault();
    e.stopPropagation();

    setTabContextMenuPosition({
      top: e.clientY,
      left: e.clientX
    });
    setContextMenuTabId(tabId);
    setShowTabContextMenu(true);
  };

  // 關閉其他標籤頁
  const closeOtherTabs = (tabId: string) => {
    workspace.openTabs.forEach(tab => {
      if (tab.id !== tabId) {
        handleCloseTab(tab.id);
      }
    });
    setShowTabContextMenu(false);
    setTabContextMenuPosition(null);
    setContextMenuTabId(null);
  };

  // 關閉右側標籤頁
  const closeTabsToTheRight = (tabId: string) => {
    const tabIndex = workspace.openTabs.findIndex(tab => tab.id === tabId);
    if (tabIndex !== -1) {
      workspace.openTabs.slice(tabIndex + 1).forEach(tab => {
        handleCloseTab(tab.id);
      });
    }
    setShowTabContextMenu(false);
    setTabContextMenuPosition(null);
    setContextMenuTabId(null);
  };

  // 關閉已儲存的標籤頁
  const closeSavedTabs = () => {
    workspace.openTabs.forEach(tab => {
      if (!fileEditor.modifiedTabs.includes(tab.id)) {
        handleCloseTab(tab.id);
      }
    });
    setShowTabContextMenu(false);
    setTabContextMenuPosition(null);
    setContextMenuTabId(null);
  };

  // 複製檔案路徑
  const handleCopyPath = useCallback((tabId: string) => {
    navigator.clipboard.writeText(tabId).then(() => {
      toast({
        title: t('workspace.fileManagement.editor.toolbar.pathCopied'),
        duration: 2000,
      });
    }).catch((err) => {
      logger.error('Failed to copy path', { error: err });
      toast({
        title: t('workspace.fileManagement.editor.toolbar.pathCopyFailed'),
        variant: 'destructive',
      });
    });
  }, [t, toast]);

  // 在檔案樹中顯示
  const handleRevealInTree = useCallback((tabId: string) => {
    actions.selectFile(tabId);
  }, [actions]);

  // 儲存標籤頁（從右鍵選單）
  const handleSaveFromContextMenu = useCallback(async (tabId: string) => {
    const result = await fileEditor.saveFile(tabId);
    if (!result.success) {
      toast({
        title: t('workspace.fileManagement.tree.notifications.saveFailed'),
        description: result.error,
        variant: 'destructive',
      });
    }
    setShowTabContextMenu(false);
    setTabContextMenuPosition(null);
    setContextMenuTabId(null);
  }, [fileEditor, toast, t]);

  // 還原標籤頁（從右鍵選單）
  const handleRevertFromContextMenu = useCallback((tabId: string) => {
    const result = fileEditor.revertFile(tabId);
    if (!result.success) {
      toast({
        title: t('workspace.fileManagement.editor.toolbar.revertFailed'),
        description: result.error,
        variant: 'destructive',
      });
    }
    setShowTabContextMenu(false);
    setTabContextMenuPosition(null);
    setContextMenuTabId(null);
  }, [fileEditor, toast, t]);

  // 獲取檔案統計資訊
  const getFileStats = (content: string) => {
    const lines = content.split('\n').length;
    const characters = content.length;
    return {
      lines,
      characters,
      formattedSize: formatFileSize(characters)
    };
  };

  return (
    <div className="h-full flex flex-col">
      {/* 標籤頁列表 - 始終顯示，包含選單，高度統一為 h-10 = 40px */}
      <div className="h-10 flex border-b border-border bg-card relative" style={{ overflowY: 'visible' }}>
        {/* 左側捲動箭頭 */}
        {showLeftScroll && (
          <button
            className="absolute left-0 top-0 z-20 h-full px-1 bg-gradient-to-r from-muted/80 to-transparent hover:from-muted flex items-center justify-center transition-colors"
            onClick={() => scrollTabs('left')}
            aria-label="Scroll tabs left"
          >
            <ChevronLeft className="w-3.5 h-3.5" />
          </button>
        )}

        {/* 可捲動的 tabs 列表區域 */}
        <div
          ref={tabsListRef}
          className="flex-1 flex overflow-x-auto scrollbar-thin scrollbar-thumb-muted-foreground/20 scrollbar-track-transparent"
          onScroll={checkScroll}
          style={{ scrollbarWidth: 'thin' }}
        >
          {workspace.openTabs.map((tab) => (
            <div
              key={tab.id}
              className={`flex items-center h-full min-w-0 flex-shrink-0 border-r border-border cursor-pointer transition-colors hover:bg-muted/50 ${
                tab.id === workspace.activeTabId
                  ? 'bg-background text-foreground border-b-2 border-b-primary'
                  : 'text-muted-foreground'
              }`}
              onClick={() => handleSwitchToTab(tab.id)}
              onContextMenu={(e) => handleTabContextMenu(e, tab.id)}
            >
              <div className="flex items-center px-2.5 h-full min-w-0">
                <span className="mr-1.5">{getFileIcon(tab.name)}</span>
                <span className="text-sm truncate max-w-28">{tab.name}</span>
              </div>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  handleCloseTab(tab.id);
                }}
                className="px-1.5 h-full hover:bg-muted/80 text-muted-foreground hover:text-foreground"
              >
                <X className="w-3 h-3" />
              </button>
            </div>
          ))}
        </div>

        {/* 右側捲動箭頭 */}
        {showRightScroll && (
          <button
            className="absolute right-28 top-0 z-20 h-full px-1 bg-gradient-to-l from-muted/80 to-transparent hover:from-muted flex items-center justify-center transition-colors"
            onClick={() => scrollTabs('right')}
            aria-label="Scroll tabs right"
          >
            <ChevronRight className="w-3.5 h-3.5" />
          </button>
        )}

        {/* 編輯器工具列 - 只有當有標籤頁時才顯示 */}
        {workspace.openTabs.length > 0 && (
          <EditorToolbar
            activeTabId={workspace.activeTabId}
            modifiedTabs={fileEditor.modifiedTabs}
            editorRef={activeEditorRef}
            onSave={(tabId) => fileEditor.saveFile(tabId)}
            onSaveAll={() => fileEditor.saveAllFiles()}
            onRevert={(tabId) => fileEditor.revertFile(tabId)}
            onRevertAll={() => fileEditor.revertAllFiles()}
            onCopyPath={handleCopyPath}
            onRevealInTree={handleRevealInTree}
            onCloseAll={handleCloseAllTabs}
            onSaveAndCloseAll={closeAllAndSave}
          />
        )}
      </div>

      {/* 檔案內容區域 */}
      {workspace.openTabs.length === 0 ? (
        <div className="flex-1 flex items-center justify-center text-muted-foreground">
          <div className="text-center">
            <FileText className="h-12 w-12 mx-auto mb-4 opacity-50" />
            <div className="text-sm">{t('workspace.fileManagement.editor.emptyState.title')}</div>
          </div>
        </div>
      ) : (
        <>
          {/* 檔案內容 - 渲染所有已開啟的標籤頁 */}
          <div className="flex-1 overflow-hidden min-w-0 relative">
            {workspace.openTabs.map((tab) => {
              const isActive = tab.id === workspace.activeTabId;
              const isLoading = loadingFiles.includes(tab.id);
              const content = tab.content || '';
              const isImage = isImageFile(tab.name);
              const isMermaid = isMermaidFile(tab.name);
              const isMarkdown = isMarkdownFile(tab.name);
              const isDrawio = isDrawioFile(tab.name);

              return (
                <div
                  key={tab.id}
                  className="absolute inset-0 w-full h-full"
                  style={{ display: isActive ? 'block' : 'none' }}
                >
                  {isLoading ? (
                    <div className="h-full flex items-center justify-center">
                      <div className="flex items-center gap-2 text-muted-foreground">
                        <Loader2 className="h-4 w-4 animate-spin" />
                        <span className="text-sm">{t('workspace.fileManagement.editor.loadingContent')}</span>
                      </div>
                    </div>
                  ) : isImage ? (
                    <ImageViewer
                      filePath={tab.path}
                      fileName={tab.name}
                    />
                  ) : isDrawio ? (
                    <DrawioViewer
                      content={content}
                      filePath={tab.path}
                      runtimeBaseUrl={workspaceRuntime.runtimeBaseUrl || ''}
                      onSave={(newContent) => {
                        fileEditor.updateTabContent(tab.id, newContent);
                        fileEditor.setTabModified(tab.id, true);
                      }}
                    />
                  ) : isMermaid ? (
                    <MermaidViewer
                      content={content}
                      fileName={tab.name}
                    />
                  ) : isMarkdown ? (
                    <MarkdownViewer
                      content={content}
                      fileName={tab.name}
                      filePath={tab.path}
                    />
                  ) : (
                    <CodeEditor
                      ref={(ref) => {
                        editorRefsMap.current.set(tab.id, ref);
                        if (isActive) {
                          activeEditorRef.current = ref;
                        }
                      }}
                      filePath={tab.id}
                      fileName={tab.name}
                      content={content}
                      visible={isActive}
                      onContentChange={(newContent) => {
                        fileEditor.updateTabContent(tab.id, newContent);
                      }}
                      onModifiedChange={(isModified) => {
                        fileEditor.setTabModified(tab.id, isModified);
                      }}
                      originalContent={fileEditor.originalContents[tab.id] || ''}
                    />
                  )}
                </div>
              );
            })}
          </div>

          {/* 狀態列 - 只顯示當前活動標籤的狀態 */}
          {activeTab && (
            <div className="h-8 px-4 bg-muted/30 border-t border-border flex items-center justify-between text-xs text-muted-foreground">
              <div className="flex items-center gap-4">
                <span className="flex items-center gap-1">
                  {getFileIcon(activeTab.name)}
                  {activeTab.name}
                </span>
                <span>
                  {getFileLanguage(activeTab.name)} •{' '}
                  {getFileStats(activeTab.content || '').formattedSize} •{' '}
                  {t('workspace.fileManagement.editor.status.lineCount', { count: getFileStats(activeTab.content || '').lines })}
                </span>
              </div>
              <div className="flex items-center gap-4">
                <span>UTF-8</span>
                <span>LF</span>
                {fileEditor.modifiedTabs.includes(activeTab.id) && (
                  <span className="text-primary">{t('workspace.fileManagement.editor.status.modified')}</span>
                )}
              </div>
            </div>
          )}
        </>
      )}

      {/* Portal 渲染的標籤頁右鍵選單 */}
      {showTabContextMenu && tabContextMenuPosition && contextMenuTabId && createPortal(
        <div
          ref={tabContextMenuRef}
          className="w-48 bg-popover border border-border rounded-lg shadow-xl overflow-hidden"
          style={{
            position: 'fixed',
            zIndex: 99999,
            top: `${tabContextMenuPosition.top}px`,
            left: `${tabContextMenuPosition.left}px`
          }}
          onClick={(e) => {
            e.stopPropagation();
          }}
        >
          {/* 儲存選項 */}
          <button
            className="w-full px-4 py-2.5 text-left text-sm border-none bg-transparent cursor-pointer flex items-center text-popover-foreground hover:bg-accent hover:text-accent-foreground transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            onClick={(e) => {
              e.preventDefault();
              e.stopPropagation();
              handleSaveFromContextMenu(contextMenuTabId);
            }}
            disabled={!fileEditor.modifiedTabs.includes(contextMenuTabId)}
          >
            <Save className="w-4 h-4 mr-2" />
            {t('workspace.fileManagement.editor.tabContextMenu.save')}
          </button>
          {/* 還原選項 */}
          <button
            className="w-full px-4 py-2.5 text-left text-sm border-none bg-transparent cursor-pointer flex items-center text-popover-foreground hover:bg-accent hover:text-accent-foreground transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            onClick={(e) => {
              e.preventDefault();
              e.stopPropagation();
              handleRevertFromContextMenu(contextMenuTabId);
            }}
            disabled={!fileEditor.modifiedTabs.includes(contextMenuTabId)}
          >
            <RotateCcw className="w-4 h-4 mr-2" />
            {t('workspace.fileManagement.editor.tabContextMenu.revert')}
          </button>
          <div className="border-t border-border my-1" />
          <button
            className="w-full px-4 py-2.5 text-left text-sm border-none bg-transparent cursor-pointer flex items-center text-popover-foreground hover:bg-accent hover:text-accent-foreground transition-colors"
            onClick={(e) => {
              e.preventDefault();
              e.stopPropagation();
              handleCloseTab(contextMenuTabId);
              setShowTabContextMenu(false);
              setTabContextMenuPosition(null);
              setContextMenuTabId(null);
            }}
          >
            {t('workspace.fileManagement.editor.tabContextMenu.close')}
          </button>
          <button
            className="w-full px-4 py-3 text-left text-sm border-none bg-transparent cursor-pointer flex items-center text-popover-foreground hover:bg-accent hover:text-accent-foreground transition-colors"
            onClick={(e) => {
              e.preventDefault();
              e.stopPropagation();
              closeOtherTabs(contextMenuTabId);
            }}
          >
            {t('workspace.fileManagement.editor.tabContextMenu.closeOthers')}
          </button>
          <button
            className="w-full px-4 py-3 text-left text-sm border-none bg-transparent cursor-pointer flex items-center text-popover-foreground hover:bg-accent hover:text-accent-foreground transition-colors"
            onClick={(e) => {
              e.preventDefault();
              e.stopPropagation();
              closeTabsToTheRight(contextMenuTabId);
            }}
          >
            {t('workspace.fileManagement.editor.tabContextMenu.closeToTheRight')}
          </button>
          <button
            className="w-full px-4 py-3 text-left text-sm border-none bg-transparent cursor-pointer flex items-center text-popover-foreground hover:bg-accent hover:text-accent-foreground transition-colors"
            onClick={(e) => {
              e.preventDefault();
              e.stopPropagation();
              closeSavedTabs();
            }}
          >
            {t('workspace.fileManagement.editor.tabContextMenu.closeSaved')}
          </button>
          <button
            className="w-full px-4 py-3 text-left text-sm border-none bg-transparent cursor-pointer flex items-center text-popover-foreground hover:bg-accent hover:text-accent-foreground transition-colors"
            onClick={(e) => {
              e.preventDefault();
              e.stopPropagation();
              handleCloseAllTabs();
              setShowTabContextMenu(false);
              setTabContextMenuPosition(null);
              setContextMenuTabId(null);
            }}
          >
            {t('workspace.fileManagement.editor.tabContextMenu.closeAll')}
          </button>
        </div>,
        document.body
      )}
    </div>
  );
};
