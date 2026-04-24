/**
 * 編輯器工具列組件
 * 提供復原、重做、儲存、還原等功能按鈕
 */

import React, { useState, useRef, useEffect, useCallback } from 'react';
import { createPortal } from 'react-dom';
import {
  Undo2,
  Redo2,
  Save,
  ChevronDown,
  MoreHorizontal,
  Copy,
  FolderTree,
  RotateCcw,
  X,
  SaveAll,
} from 'lucide-react';
import { useI18n } from '@/shared/hooks/useI18n';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/shared/components/ui/alert-dialog';
import { type CodeEditorRef } from './CodeEditor';

interface EditorToolbarProps {
  activeTabId: string | null;
  modifiedTabs: string[];
  editorRef: React.RefObject<CodeEditorRef | null>;
  onSave: (tabId: string) => void;
  onSaveAll: () => void;
  onRevert: (tabId: string) => void;
  onRevertAll: () => void;
  onCopyPath: (tabId: string) => void;
  onRevealInTree: (tabId: string) => void;
  onCloseAll: () => void;
  onSaveAndCloseAll: () => void;
}

export const EditorToolbar: React.FC<EditorToolbarProps> = ({
  activeTabId,
  modifiedTabs,
  editorRef,
  onSave,
  onSaveAll,
  onRevert,
  onRevertAll,
  onCopyPath,
  onRevealInTree,
  onCloseAll,
  onSaveAndCloseAll,
}) => {
  const { t } = useI18n();
  const [showSaveMenu, setShowSaveMenu] = useState(false);
  const [showMoreMenu, setShowMoreMenu] = useState(false);
  const [saveMenuPosition, setSaveMenuPosition] = useState<{ top: number; left: number } | null>(null);
  const [moreMenuPosition, setMoreMenuPosition] = useState<{ top: number; left: number } | null>(null);
  const [showRevertDialog, setShowRevertDialog] = useState(false);
  const [revertTarget, setRevertTarget] = useState<'single' | 'all'>('single');

  const saveButtonRef = useRef<HTMLButtonElement>(null);
  const saveMenuRef = useRef<HTMLDivElement>(null);
  const moreButtonRef = useRef<HTMLButtonElement>(null);
  const moreMenuRef = useRef<HTMLDivElement>(null);

  const isCurrentModified = activeTabId ? modifiedTabs.includes(activeTabId) : false;
  const hasModifiedFiles = modifiedTabs.length > 0;

  // 點擊外部關閉選單
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      const target = event.target as Node;

      if (showSaveMenu) {
        const isClickInSaveButton = saveButtonRef.current?.contains(target);
        const isClickInSaveMenu = saveMenuRef.current?.contains(target);
        if (!isClickInSaveButton && !isClickInSaveMenu) {
          setShowSaveMenu(false);
          setSaveMenuPosition(null);
        }
      }

      if (showMoreMenu) {
        const isClickInMoreButton = moreButtonRef.current?.contains(target);
        const isClickInMoreMenu = moreMenuRef.current?.contains(target);
        if (!isClickInMoreButton && !isClickInMoreMenu) {
          setShowMoreMenu(false);
          setMoreMenuPosition(null);
        }
      }
    };

    if (showSaveMenu || showMoreMenu) {
      document.addEventListener('mousedown', handleClickOutside);
    }

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [showSaveMenu, showMoreMenu]);

  const handleUndo = useCallback(() => {
    editorRef.current?.undo();
  }, [editorRef]);

  const handleRedo = useCallback(() => {
    editorRef.current?.redo();
  }, [editorRef]);

  const handleSaveClick = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();

    if (!showSaveMenu && saveButtonRef.current) {
      const rect = saveButtonRef.current.getBoundingClientRect();
      setSaveMenuPosition({
        top: rect.bottom + 4,
        left: rect.left,
      });
    }
    setShowSaveMenu(!showSaveMenu);
  };

  const handleMoreClick = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();

    if (!showMoreMenu && moreButtonRef.current) {
      const rect = moreButtonRef.current.getBoundingClientRect();
      setMoreMenuPosition({
        top: rect.bottom + 4,
        left: rect.right - 180, // 180px = menu width
      });
    }
    setShowMoreMenu(!showMoreMenu);
  };

  const handleRevertClick = (target: 'single' | 'all') => {
    setRevertTarget(target);
    setShowRevertDialog(true);
    setShowSaveMenu(false);
    setSaveMenuPosition(null);
  };

  const handleRevertConfirm = () => {
    if (revertTarget === 'single' && activeTabId) {
      onRevert(activeTabId);
    } else if (revertTarget === 'all') {
      onRevertAll();
    }
    setShowRevertDialog(false);
  };

  return (
    <>
      <div className="flex items-center h-full border-l border-border">
        {/* 復原按鈕 */}
        <button
          className="px-1.5 h-full text-muted-foreground hover:text-foreground hover:bg-muted flex items-center justify-center transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          onClick={handleUndo}
          disabled={!activeTabId}
          title={t('workspace.fileManagement.editor.toolbar.undo')}
        >
          <Undo2 className="w-3.5 h-3.5" />
        </button>

        {/* 重做按鈕 */}
        <button
          className="px-1.5 h-full text-muted-foreground hover:text-foreground hover:bg-muted flex items-center justify-center transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          onClick={handleRedo}
          disabled={!activeTabId}
          title={t('workspace.fileManagement.editor.toolbar.redo')}
        >
          <Redo2 className="w-3.5 h-3.5" />
        </button>

        {/* 儲存下拉選單按鈕 */}
        <button
          ref={saveButtonRef}
          className="px-1.5 h-full text-muted-foreground hover:text-foreground hover:bg-muted flex items-center justify-center gap-0.5 transition-colors"
          onClick={handleSaveClick}
          title={t('workspace.fileManagement.editor.toolbar.save')}
        >
          <Save className="w-3.5 h-3.5" />
          <ChevronDown className="w-2.5 h-2.5" />
        </button>

        {/* 更多選單按鈕 */}
        <button
          ref={moreButtonRef}
          className="px-1.5 h-full text-muted-foreground hover:text-foreground hover:bg-muted flex items-center justify-center transition-colors"
          onClick={handleMoreClick}
          title={t('workspace.fileManagement.editor.toolbar.more')}
        >
          <MoreHorizontal className="w-3.5 h-3.5" />
        </button>
      </div>

      {/* 儲存下拉選單 */}
      {showSaveMenu && saveMenuPosition && createPortal(
        <div
          ref={saveMenuRef}
          className="w-44 bg-popover border border-border rounded-lg shadow-xl overflow-hidden"
          style={{
            position: 'fixed',
            zIndex: 99999,
            top: `${saveMenuPosition.top}px`,
            left: `${saveMenuPosition.left}px`,
          }}
          onClick={(e) => e.stopPropagation()}
        >
          {/* 儲存 */}
          <button
            className="w-full px-3 py-2 text-left text-xs border-none bg-transparent cursor-pointer flex items-center text-popover-foreground hover:bg-accent hover:text-accent-foreground transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            onClick={() => {
              if (activeTabId && isCurrentModified) {
                onSave(activeTabId);
              }
              setShowSaveMenu(false);
              setSaveMenuPosition(null);
            }}
            disabled={!isCurrentModified}
          >
            <Save className="w-3.5 h-3.5 mr-2" />
            {t('workspace.fileManagement.editor.toolbar.save')}
            <span className="ml-auto text-[10px] text-muted-foreground">Ctrl+S</span>
          </button>

          {/* 儲存全部 */}
          <button
            className="w-full px-3 py-2 text-left text-xs border-none bg-transparent cursor-pointer flex items-center text-popover-foreground hover:bg-accent hover:text-accent-foreground transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            onClick={() => {
              if (hasModifiedFiles) {
                onSaveAll();
              }
              setShowSaveMenu(false);
              setSaveMenuPosition(null);
            }}
            disabled={!hasModifiedFiles}
          >
            <Save className="w-3.5 h-3.5 mr-2" />
            {t('workspace.fileManagement.editor.toolbar.saveAll')}
            <span className="ml-auto text-[10px] text-muted-foreground">Ctrl+Shift+S</span>
          </button>

          <div className="border-t border-border" />

          {/* 還原 */}
          <button
            className="w-full px-3 py-2 text-left text-xs border-none bg-transparent cursor-pointer flex items-center text-popover-foreground hover:bg-accent hover:text-accent-foreground transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            onClick={() => handleRevertClick('single')}
            disabled={!isCurrentModified}
          >
            <RotateCcw className="w-3.5 h-3.5 mr-2" />
            {t('workspace.fileManagement.editor.toolbar.revert')}
          </button>

          {/* 還原全部 */}
          <button
            className="w-full px-3 py-2 text-left text-xs border-none bg-transparent cursor-pointer flex items-center text-popover-foreground hover:bg-accent hover:text-accent-foreground transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            onClick={() => handleRevertClick('all')}
            disabled={!hasModifiedFiles}
          >
            <RotateCcw className="w-3.5 h-3.5 mr-2" />
            {t('workspace.fileManagement.editor.toolbar.revertAll')}
          </button>
        </div>,
        document.body
      )}

      {/* 更多選單 */}
      {showMoreMenu && moreMenuPosition && createPortal(
        <div
          ref={moreMenuRef}
          className="w-48 bg-popover border border-border rounded-lg shadow-xl overflow-hidden"
          style={{
            position: 'fixed',
            zIndex: 99999,
            top: `${moreMenuPosition.top}px`,
            left: `${moreMenuPosition.left}px`,
          }}
          onClick={(e) => e.stopPropagation()}
        >
          {/* 複製檔案路徑 */}
          <button
            className="w-full px-3 py-2 text-left text-xs border-none bg-transparent cursor-pointer flex items-center text-popover-foreground hover:bg-accent hover:text-accent-foreground transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            onClick={() => {
              if (activeTabId) {
                onCopyPath(activeTabId);
              }
              setShowMoreMenu(false);
              setMoreMenuPosition(null);
            }}
            disabled={!activeTabId}
          >
            <Copy className="w-3.5 h-3.5 mr-2" />
            {t('workspace.fileManagement.editor.toolbar.copyPath')}
          </button>

          {/* 在檔案樹中顯示 */}
          <button
            className="w-full px-3 py-2 text-left text-xs border-none bg-transparent cursor-pointer flex items-center text-popover-foreground hover:bg-accent hover:text-accent-foreground transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            onClick={() => {
              if (activeTabId) {
                onRevealInTree(activeTabId);
              }
              setShowMoreMenu(false);
              setMoreMenuPosition(null);
            }}
            disabled={!activeTabId}
          >
            <FolderTree className="w-3.5 h-3.5 mr-2" />
            {t('workspace.fileManagement.editor.toolbar.revealInTree')}
          </button>

          <div className="border-t border-border my-1" />

          {/* 關閉所有分頁 */}
          <button
            className="w-full px-3 py-2 text-left text-xs border-none bg-transparent cursor-pointer flex items-center text-popover-foreground hover:bg-accent hover:text-accent-foreground transition-colors"
            onClick={() => {
              onCloseAll();
              setShowMoreMenu(false);
              setMoreMenuPosition(null);
            }}
          >
            <X className="w-3.5 h-3.5 mr-2" />
            {t('workspace.fileManagement.editor.menu.closeAll')}
          </button>

          {/* 儲存並關閉所有 */}
          <button
            className="w-full px-3 py-2 text-left text-xs border-none bg-transparent cursor-pointer flex items-center text-popover-foreground hover:bg-accent hover:text-accent-foreground transition-colors"
            onClick={() => {
              onSaveAndCloseAll();
              setShowMoreMenu(false);
              setMoreMenuPosition(null);
            }}
          >
            <SaveAll className="w-3.5 h-3.5 mr-2" />
            {t('workspace.fileManagement.editor.menu.saveAndCloseAll')}
          </button>
        </div>,
        document.body
      )}

      {/* 還原確認對話框 */}
      <AlertDialog open={showRevertDialog} onOpenChange={setShowRevertDialog}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle className="flex items-center gap-2">
              <RotateCcw className="h-5 w-5 text-primary" />
              {t('workspace.fileManagement.editor.dialogs.revertTitle')}
            </AlertDialogTitle>
            <AlertDialogDescription>
              {revertTarget === 'single'
                ? t('workspace.fileManagement.editor.dialogs.revertMessage')
                : t('workspace.fileManagement.editor.dialogs.revertAllMessage')}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>
              {t('workspace.fileManagement.editor.dialogs.revertCancel')}
            </AlertDialogCancel>
            <AlertDialogAction onClick={handleRevertConfirm}>
              {t('workspace.fileManagement.editor.dialogs.revertConfirm')}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
};
