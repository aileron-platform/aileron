import React, { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { FileText, Minus, Plus, Trash2, Undo } from 'lucide-react';
import { useI18n } from '@/shared/hooks/useI18n';
import type { VersionControlFileChange } from '@/shared/types/versionControl';

interface VersionControlFileChangeItemProps {
  file: VersionControlFileChange;
  isSelected: boolean;
  isMultiSelected: boolean;
  type: 'staged' | 'unstaged';
  onSelect: (file: VersionControlFileChange, type: 'staged' | 'unstaged', event?: React.MouseEvent) => void;
  onStageToggle: (file: VersionControlFileChange) => void;
  onDiscard?: (file: VersionControlFileChange) => void;
  selectedCount: number;
  i18nPrefix?: string;
  readOnly?: boolean;
}

export const VersionControlFileChangeItem: React.FC<VersionControlFileChangeItemProps> = ({
  file,
  isSelected,
  isMultiSelected,
  type,
  onSelect,
  onStageToggle,
  onDiscard,
  selectedCount,
  i18nPrefix = 'shared.versionControl',
  readOnly = false,
}) => {
  const [showContextMenu, setShowContextMenu] = useState(false);
  const [contextMenuPosition, setContextMenuPosition] = useState({ x: 0, y: 0 });
  const contextMenuRef = useRef<HTMLDivElement>(null);
  const { t } = useI18n();

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

  useEffect(() => {
    if (showContextMenu && contextMenuRef.current) {
      const menu = contextMenuRef.current;
      const menuRect = menu.getBoundingClientRect();
      const viewportHeight = window.innerHeight;
      const viewportWidth = window.innerWidth;
      let { x, y } = contextMenuPosition;
      if (menuRect.right > viewportWidth) x = viewportWidth - menuRect.width - 10;
      if (menuRect.bottom > viewportHeight) y = viewportHeight - menuRect.height - 10;
      if (y < 10) y = 10;
      if (x < 10) x = 10;
      if (x !== contextMenuPosition.x || y !== contextMenuPosition.y) {
        setContextMenuPosition({ x, y });
      }
    }
  }, [showContextMenu, contextMenuPosition]);

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
        return t(`${i18nPrefix}.commitFiles.status.modified`);
      case 'A':
        return t(`${i18nPrefix}.commitFiles.status.added`);
      case 'D':
        return t(`${i18nPrefix}.commitFiles.status.deleted`);
      case 'R':
        return t(`${i18nPrefix}.commitFiles.status.renamed`);
      default:
        return t(`${i18nPrefix}.commitFiles.status.unknown`);
    }
  };

  const handleContextMenu = (event: React.MouseEvent) => {
    event.preventDefault();
    event.stopPropagation();
    if (!isMultiSelected) {
      onSelect(file, type);
    }
    const menuHeight = type === 'unstaged' ? 120 : 60;
    const spaceBelow = window.innerHeight - event.clientY;
    const spaceAbove = event.clientY;
    const yPosition = spaceBelow < menuHeight && spaceAbove > spaceBelow
      ? event.clientY - menuHeight
      : event.clientY;
    setContextMenuPosition({ x: event.clientX, y: yPosition });
    setShowContextMenu(true);
  };

  const handleStageToggle = (event: React.MouseEvent) => {
    event.stopPropagation();
    onStageToggle(file);
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
        onClick={(event) => onSelect(file, type, event)}
        onContextMenu={handleContextMenu}
        style={{ userSelect: 'none', WebkitUserSelect: 'none' } as React.CSSProperties}
      >
        <FileText className="w-4 h-4 text-muted-foreground flex-shrink-0" />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium text-foreground truncate">{file.name}</span>
            <span
              className={`text-xs px-1.5 py-0.5 rounded font-mono ${getStatusColor(file.status)}`}
              title={getStatusText(file.status)}
            >
              {file.status}
            </span>
          </div>
          <div className="text-xs text-muted-foreground truncate">{file.path}</div>
        </div>
        <div className="flex items-center gap-2 text-xs flex-shrink-0">
          {(file.additions ?? 0) > 0 && <span className="text-green-600">+{file.additions}</span>}
          {(file.deletions ?? 0) > 0 && <span className="text-red-600">-{file.deletions}</span>}
        </div>
        {!readOnly && (
          <button
            onClick={handleStageToggle}
            className="p-1 hover:bg-muted rounded text-muted-foreground hover:text-foreground flex-shrink-0"
            title={type === 'staged'
              ? t(`${i18nPrefix}.fileItem.unstageTooltip`)
              : t(`${i18nPrefix}.fileItem.stageTooltip`)}
          >
            {type === 'staged' ? <Minus className="w-3 h-3" /> : <Plus className="w-3 h-3" />}
          </button>
        )}
      </div>

      {!readOnly && showContextMenu && createPortal(
        <div
          ref={contextMenuRef}
          className="fixed bg-background border border-border rounded-md shadow-lg py-1 z-50 min-w-36"
          style={{ left: `${contextMenuPosition.x}px`, top: `${contextMenuPosition.y}px` }}
        >
          {selectedCount > 1 && (
            <div className="px-3 py-1 text-xs text-muted-foreground border-b border-border">
              {t(`${i18nPrefix}.fileItem.selectedCount`, { count: selectedCount })}
            </div>
          )}
          {type === 'unstaged' ? (
            <>
              <button
                onClick={() => {
                  setShowContextMenu(false);
                  onStageToggle(file);
                }}
                className="w-full text-left px-3 py-2 text-sm hover:bg-muted/50 transition-colors flex items-center gap-2 text-foreground"
              >
                <Plus className="h-3 w-3" />
                {selectedCount > 1
                  ? t(`${i18nPrefix}.fileItem.stageMultiple`, { count: selectedCount })
                  : t(`${i18nPrefix}.fileItem.stage`)}
              </button>
              <button
                onClick={() => {
                  setShowContextMenu(false);
                  onDiscard?.(file);
                }}
                className="w-full text-left px-3 py-2 text-sm hover:bg-destructive/10 hover:text-destructive transition-colors flex items-center gap-2"
              >
                <Trash2 className="h-3 w-3" />
                {selectedCount > 1
                  ? t(`${i18nPrefix}.fileItem.discardMultiple`, { count: selectedCount })
                  : t(`${i18nPrefix}.fileItem.discard`)}
              </button>
            </>
          ) : (
            <button
              onClick={() => {
                setShowContextMenu(false);
                onStageToggle(file);
              }}
              className="w-full text-left px-3 py-2 text-sm hover:bg-muted/50 transition-colors flex items-center gap-2 text-foreground"
            >
              <Undo className="h-3 w-3" />
              {selectedCount > 1
                ? t(`${i18nPrefix}.fileItem.unstageMultiple`, { count: selectedCount })
                : t(`${i18nPrefix}.fileItem.unstage`)}
            </button>
          )}
        </div>,
        document.body,
      )}
    </>
  );
};
