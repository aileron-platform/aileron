/**
 * FileChangeItem - 檔案變更項目組件
 * 
 * 顯示單個檔案的變更資訊，包含狀態、名稱和操作按鈕
 */

import React, { useState, useRef, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { Plus, Minus, FileText, Trash2, Undo } from 'lucide-react';
import type { VersionControlFileChange } from '../types';
import { useI18n } from '@/shared/hooks/useI18n';

interface FileChangeItemProps {
  file: VersionControlFileChange;
  isSelected: boolean;
  isMultiSelected: boolean;
  type: 'staged' | 'unstaged';
  onSelect: (file: VersionControlFileChange, type: 'staged' | 'unstaged', event?: React.MouseEvent) => void;
  onStageToggle: (file: VersionControlFileChange) => void;
  onDiscard?: (file: VersionControlFileChange) => void;
  selectedCount: number;
}

export const FileChangeItem: React.FC<FileChangeItemProps> = ({
  file,
  isSelected,
  isMultiSelected,
  type,
  onSelect,
  onStageToggle,
  onDiscard,
  selectedCount,
}) => {
  const [showContextMenu, setShowContextMenu] = useState(false);
  const [contextMenuPosition, setContextMenuPosition] = useState({ x: 0, y: 0 });
  const contextMenuRef = useRef<HTMLDivElement>(null);
  const { t } = useI18n();

  // 點擊外部關閉右鍵選單
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (contextMenuRef.current && !contextMenuRef.current.contains(event.target as Node)) {
        setShowContextMenu(false);
      }
    };

    if (showContextMenu) {
      document.addEventListener('mousedown', handleClickOutside);
      return () => document.removeEventListener('mousedown', handleClickOutside);
    }
  }, [showContextMenu]);

  // 調整選單位置以避免超出視窗
  useEffect(() => {
    if (showContextMenu && contextMenuRef.current) {
      const menu = contextMenuRef.current;
      const menuRect = menu.getBoundingClientRect();
      const viewportHeight = window.innerHeight;
      const viewportWidth = window.innerWidth;

      let { x, y } = contextMenuPosition;

      // 檢查右側是否超出
      if (menuRect.right > viewportWidth) {
        x = viewportWidth - menuRect.width - 10;
      }

      // 檢查底部是否超出
      if (menuRect.bottom > viewportHeight) {
        y = viewportHeight - menuRect.height - 10;
      }

      // 檢查頂部是否超出
      if (y < 10) {
        y = 10;
      }

      // 檢查左側是否超出
      if (x < 10) {
        x = 10;
      }

      // 如果位置需要調整，更新位置
      if (x !== contextMenuPosition.x || y !== contextMenuPosition.y) {
        setContextMenuPosition({ x, y });
      }
    }
  }, [showContextMenu, contextMenuPosition]);

  // 獲取檔案狀態顏色
  const getStatusColor = (status: string) => {
    switch (status) {
      case 'M': return 'text-blue-500';
      case 'A': return 'text-green-500';
      case 'D': return 'text-red-500';
      case 'R': return 'text-yellow-500';
      default: return 'text-muted-foreground';
    }
  };

  const getStatusText = (status: string) => {
    switch (status) {
      case 'M':
        return t('workspace.versionControl.commitFiles.status.modified');
      case 'A':
        return t('workspace.versionControl.commitFiles.status.added');
      case 'D':
        return t('workspace.versionControl.commitFiles.status.deleted');
      case 'R':
        return t('workspace.versionControl.commitFiles.status.renamed');
      default:
        return t('workspace.versionControl.commitFiles.status.unknown');
    }
  };

  const handleStageToggle = (e: React.MouseEvent) => {
    e.stopPropagation();
    onStageToggle(file);
  };

  const handleContextMenu = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();

    // 如果右鍵點擊的檔案不在多選範圍內，先選擇它
    if (!isMultiSelected) {
      onSelect(file, type, e);
    }

    // 計算選單高度（預估）
    const menuHeight = type === 'unstaged' ? 120 : 60; // unstaged 有兩個選項，staged 只有一個
    const viewportHeight = window.innerHeight;
    const spaceBelow = viewportHeight - e.clientY;
    const spaceAbove = e.clientY;

    // 如果下方空間不足且上方空間更多，則向上顯示
    let yPosition = e.clientY;
    if (spaceBelow < menuHeight && spaceAbove > spaceBelow) {
      yPosition = e.clientY - menuHeight;
    }

    setContextMenuPosition({
      x: e.clientX,
      y: yPosition
    });
    setShowContextMenu(true);
  };

  const handleDiscardChanges = () => {
    setShowContextMenu(false);
    onDiscard?.(file);
  };

  const handleStage = () => {
    setShowContextMenu(false);
    onStageToggle(file);
  };

  const handleUnstage = () => {
    setShowContextMenu(false);
    onStageToggle(file);
  };

  const handleClick = (e: React.MouseEvent) => {
    onSelect(file, type, e);
  };

  return (
    <>
      <div
        className={`flex items-center gap-2 p-2 rounded cursor-pointer transition-colors select-none ${
          isMultiSelected
            ? 'bg-primary/20 ring-1 ring-inset ring-primary/30'
            : isSelected
            ? 'bg-muted/70'
            : 'hover:bg-muted/50'
        }`}
        onClick={handleClick}
        onContextMenu={handleContextMenu}
        style={{ userSelect: 'none', WebkitUserSelect: 'none' } as React.CSSProperties}
      >
      {/* 檔案圖示 */}
      <FileText className="w-4 h-4 text-muted-foreground flex-shrink-0" />
      
      {/* 檔案資訊 */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-foreground truncate">
            {file.name}
          </span>
          <span
            className={`text-xs px-1.5 py-0.5 rounded font-mono ${getStatusColor(file.status)}`}
            title={getStatusText(file.status)}
          >
            {file.status}
          </span>
        </div>
        <div className="text-xs text-muted-foreground truncate">
          {file.path}
        </div>
      </div>

      {/* 變更統計 */}
      <div className="flex items-center gap-2 text-xs flex-shrink-0">
        {(file.additions ?? 0) > 0 && (
          <span className="text-green-600">+{file.additions}</span>
        )}
        {(file.deletions ?? 0) > 0 && (
          <span className="text-red-600">-{file.deletions}</span>
        )}
      </div>

      {/* 暫存/取消暫存按鈕 */}
      <button
        onClick={handleStageToggle}
        className="p-1 hover:bg-muted rounded text-muted-foreground hover:text-foreground flex-shrink-0"
        title={type === 'staged'
          ? t('workspace.versionControl.fileItem.unstageTooltip')
          : t('workspace.versionControl.fileItem.stageTooltip')}
      >
        {type === 'staged' ? (
          <Minus className="w-3 h-3" />
        ) : (
          <Plus className="w-3 h-3" />
        )}
      </button>
    </div>

    {/* 右鍵選單 - 使用 Portal 渲染到 body */}
    {showContextMenu && createPortal(
      <div
        ref={contextMenuRef}
        className="fixed bg-background border border-border rounded-md shadow-lg py-1 z-50 min-w-36"
        style={{
          left: `${contextMenuPosition.x}px`,
          top: `${contextMenuPosition.y}px`,
        }}
      >
        {selectedCount > 1 && (
          <div className="px-3 py-1 text-xs text-muted-foreground border-b border-border">
            {t('workspace.versionControl.fileItem.selectedCount', { count: selectedCount })}
          </div>
        )}
        {type === 'unstaged' ? (
          <>
            <button
              onClick={handleStage}
              className="w-full text-left px-3 py-2 text-sm hover:bg-muted/50 transition-colors flex items-center gap-2 text-foreground"
            >
              <Plus className="h-3 w-3" />
              {selectedCount > 1
                ? t('workspace.versionControl.fileItem.stageMultiple', { count: selectedCount })
                : t('workspace.versionControl.fileItem.stage')}
            </button>
            <button
              onClick={handleDiscardChanges}
              className="w-full text-left px-3 py-2 text-sm hover:bg-destructive/10 hover:text-destructive transition-colors flex items-center gap-2"
            >
              <Trash2 className="h-3 w-3" />
              {selectedCount > 1
                ? t('workspace.versionControl.fileItem.discardMultiple', { count: selectedCount })
                : t('workspace.versionControl.fileItem.discard')}
            </button>
          </>
        ) : (
          <button
            onClick={handleUnstage}
            className="w-full text-left px-3 py-2 text-sm hover:bg-muted/50 transition-colors flex items-center gap-2 text-foreground"
          >
            <Undo className="h-3 w-3" />
            {selectedCount > 1
              ? t('workspace.versionControl.fileItem.unstageMultiple', { count: selectedCount })
              : t('workspace.versionControl.fileItem.unstage')}
          </button>
        )}
      </div>,
      document.body
    )}
  </>
  );
};
