import React from 'react';
import { Check, Copy, ExternalLink, FileText, Loader2, Minus, Plus, Trash2, Undo } from 'lucide-react';
import { useI18n } from '@/shared/hooks/useI18n';
import type { VersionControlFileChange } from '@/shared/version-control';
import {
  ContextMenu,
  ContextMenuContent,
  ContextMenuItem,
  ContextMenuSeparator,
  ContextMenuTrigger,
} from '@/shared/components/ui/context-menu';

interface VersionControlFileChangeItemProps {
  file: VersionControlFileChange;
  isSelected: boolean;
  isMultiSelected: boolean;
  type: 'staged' | 'unstaged';
  onSelect: (file: VersionControlFileChange, type: 'staged' | 'unstaged', event?: React.MouseEvent) => void;
  onStageToggle: (file: VersionControlFileChange) => void;
  onDiscard?: (file: VersionControlFileChange) => void;
  onOpen?: (file: VersionControlFileChange) => void;
  onMarkResolved?: (file: VersionControlFileChange) => void;
  onCopyPath?: (path: string) => void;
  selectedCount: number;
  i18nPrefix?: string;
  readOnly?: boolean;
  actionPending?: boolean;
  conflict?: boolean;
}

export const VersionControlFileChangeItem: React.FC<VersionControlFileChangeItemProps> = ({
  file,
  isSelected,
  isMultiSelected,
  type,
  onSelect,
  onStageToggle,
  onDiscard,
  onOpen,
  onMarkResolved,
  onCopyPath,
  selectedCount,
  i18nPrefix = 'shared.versionControl',
  readOnly = false,
  actionPending = false,
  conflict = false,
}) => {
  const { t } = useI18n();

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
      case 'M': return t(`${i18nPrefix}.commitFiles.status.modified`);
      case 'A': return t(`${i18nPrefix}.commitFiles.status.added`);
      case 'D': return t(`${i18nPrefix}.commitFiles.status.deleted`);
      case 'R': return t(`${i18nPrefix}.commitFiles.status.renamed`);
      default: return t(`${i18nPrefix}.commitFiles.status.unknown`);
    }
  };

  const copyPath = () => {
    if (onCopyPath) {
      onCopyPath(file.path);
      return;
    }
    void navigator.clipboard?.writeText(file.path);
  };

  const row = (
    <div
      className={`flex min-w-0 items-center gap-2 rounded p-2 transition-colors select-none ${
        isMultiSelected
          ? 'bg-primary/20 ring-1 ring-inset ring-primary/30'
          : isSelected
            ? 'bg-muted/70'
            : 'hover:bg-muted/50'
      }`}
      onClick={(event) => onSelect(file, type, event)}
      style={{ userSelect: 'none', WebkitUserSelect: 'none' } as React.CSSProperties}
    >
      <FileText className="h-4 w-4 flex-shrink-0 text-muted-foreground" />
      <div className="min-w-0 flex-1">
        <div className="flex min-w-0 items-center gap-2">
          <span className="truncate text-sm font-medium text-foreground">{file.name}</span>
          <span
            className={`rounded px-1.5 py-0.5 font-mono text-xs ${getStatusColor(file.status)}`}
            title={getStatusText(file.status)}
          >
            {file.status}
          </span>
        </div>
        <div className="truncate text-xs text-muted-foreground">{file.path}</div>
      </div>
      <div className="flex flex-shrink-0 items-center gap-2 text-xs">
        {(file.additions ?? 0) > 0 && <span className="text-green-600">+{file.additions}</span>}
        {(file.deletions ?? 0) > 0 && <span className="text-red-600">-{file.deletions}</span>}
      </div>
      {!readOnly && (
        <button
          type="button"
          onClick={(event) => {
            event.stopPropagation();
            if (conflict) {
              onMarkResolved?.(file);
            } else {
              onStageToggle(file);
            }
          }}
          className="flex-shrink-0 rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
          disabled={actionPending}
          aria-busy={actionPending}
          title={conflict
            ? t(`${i18nPrefix}.fileItem.markResolved`)
            : type === 'staged'
              ? t(`${i18nPrefix}.fileItem.unstageTooltip`)
              : t(`${i18nPrefix}.fileItem.stageTooltip`)}
        >
          {actionPending
            ? <Loader2 className="h-3 w-3 animate-spin" />
            : conflict
              ? <Check className="h-3 w-3" />
              : type === 'staged'
              ? <Minus className="h-3 w-3" />
              : <Plus className="h-3 w-3" />}
        </button>
      )}
    </div>
  );

  return (
    <ContextMenu onOpenChange={(nextOpen) => {
      if (nextOpen && !isMultiSelected) {
        onSelect(file, type);
      }
    }}>
      <ContextMenuTrigger asChild>{row}</ContextMenuTrigger>
      <ContextMenuContent>
        {selectedCount > 1 && (
          <div className="px-2 py-1 text-xs text-muted-foreground">
            {t(`${i18nPrefix}.fileItem.selectedCount`, { count: selectedCount })}
          </div>
        )}
        <ContextMenuItem onSelect={() => onOpen?.(file)} disabled={!onOpen}>
          <ExternalLink className="h-3.5 w-3.5" />
          {t(`${i18nPrefix}.fileItem.open`)}
        </ContextMenuItem>
        <ContextMenuSeparator />
        {conflict ? (
          <ContextMenuItem
            disabled={readOnly || actionPending || !onMarkResolved}
            onSelect={() => onMarkResolved?.(file)}
          >
            <Check className="h-3.5 w-3.5" />
            {t(`${i18nPrefix}.fileItem.markResolved`)}
          </ContextMenuItem>
        ) : (
          <ContextMenuItem
            disabled={readOnly || actionPending}
            onSelect={() => onStageToggle(file)}
          >
            {type === 'staged'
              ? <Undo className="h-3.5 w-3.5" />
              : <Plus className="h-3.5 w-3.5" />}
            {selectedCount > 1
              ? t(`${i18nPrefix}.fileItem.${type === 'staged' ? 'unstageMultiple' : 'stageMultiple'}`, { count: selectedCount })
              : t(`${i18nPrefix}.fileItem.${type === 'staged' ? 'unstage' : 'stage'}`)}
          </ContextMenuItem>
        )}
        {type === 'unstaged' && (
          <ContextMenuItem
            disabled={readOnly || actionPending || !onDiscard}
            className="text-destructive focus:bg-destructive/10 focus:text-destructive"
            onSelect={() => onDiscard?.(file)}
          >
            <Trash2 className="h-3.5 w-3.5" />
            {selectedCount > 1
              ? t(`${i18nPrefix}.fileItem.discardMultiple`, { count: selectedCount })
              : t(`${i18nPrefix}.fileItem.discard`)}
          </ContextMenuItem>
        )}
        <ContextMenuSeparator />
        <ContextMenuItem onSelect={copyPath}>
          <Copy className="h-3.5 w-3.5" />
          {t(`${i18nPrefix}.fileItem.copyPath`)}
        </ContextMenuItem>
      </ContextMenuContent>
    </ContextMenu>
  );
};
