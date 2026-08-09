import React, { useState } from 'react';
import { ChevronDown, GitBranch, MoreHorizontal } from 'lucide-react';
import { useI18n } from '@/shared/hooks/useI18n';
import type { VersionControlBranch } from '@/shared/version-control';
import { cn } from '@/shared/utils/cn';
import {
  ContextMenu,
  ContextMenuContent,
  ContextMenuItem,
  ContextMenuTrigger,
} from '@/shared/components/ui/context-menu';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/shared/components/ui/dropdown-menu';

interface VersionControlBranchSelectorProps {
  branches: VersionControlBranch[];
  currentBranch: string;
  onBranchChange?: (branch: string) => void;
  onCreateBranch?: () => void;
  onRenameBranch?: (branch: VersionControlBranch) => void;
  onDeleteBranch?: (branch: VersionControlBranch) => void;
  onCreateTrackingBranch?: (branch: VersionControlBranch) => void;
  disabled?: boolean;
  hideLabel?: boolean;
  className?: string;
  buttonClassName?: string;
}

interface BranchActionItemsProps {
  branch: VersionControlBranch;
  disabled: boolean;
  kind: 'dropdown' | 'context';
  onCloseSelector: () => void;
  onBranchChange?: (branch: string) => void;
  onRenameBranch?: (branch: VersionControlBranch) => void;
  onDeleteBranch?: (branch: VersionControlBranch) => void;
  onCreateTrackingBranch?: (branch: VersionControlBranch) => void;
}

const BranchActionItems: React.FC<BranchActionItemsProps> = ({
  branch,
  disabled,
  kind,
  onCloseSelector,
  onBranchChange,
  onRenameBranch,
  onDeleteBranch,
  onCreateTrackingBranch,
}) => {
  const { t } = useI18n();
  const Item = kind === 'dropdown' ? DropdownMenuItem : ContextMenuItem;
  const run = (callback: () => void) => {
    onCloseSelector();
    callback();
  };

  if (branch.kind === 'remote') {
    return (
      <Item onSelect={() => run(() => onCreateTrackingBranch?.(branch))}>
        {t('shared.versionControl.branch.actions.createTracking')}
      </Item>
    );
  }

  return (
    <>
      <Item
        disabled={disabled || !branch.capabilities.switch.allowed}
        title={branch.capabilities.switch.disabledReasonKey
          ? t(branch.capabilities.switch.disabledReasonKey)
          : undefined}
        onSelect={() => run(() => onBranchChange?.(branch.name))}
      >
        {t('shared.versionControl.branch.actions.switch')}
      </Item>
      <Item
        disabled={disabled || !branch.capabilities.rename.allowed}
        title={branch.capabilities.rename.disabledReasonKey
          ? t(branch.capabilities.rename.disabledReasonKey)
          : undefined}
        onSelect={() => run(() => onRenameBranch?.(branch))}
      >
        {t('shared.versionControl.branch.actions.rename')}
      </Item>
      <Item
        disabled={disabled || !branch.capabilities.delete.allowed}
        title={branch.capabilities.delete.disabledReasonKey
          ? t(branch.capabilities.delete.disabledReasonKey)
          : undefined}
        className="text-destructive focus:text-destructive"
        onSelect={() => run(() => onDeleteBranch?.(branch))}
      >
        {t('shared.versionControl.branch.actions.delete')}
      </Item>
    </>
  );
};

export const VersionControlBranchSelector: React.FC<VersionControlBranchSelectorProps> = ({
  branches,
  currentBranch,
  onBranchChange,
  onCreateBranch,
  onRenameBranch,
  onDeleteBranch,
  onCreateTrackingBranch,
  disabled = false,
  hideLabel = false,
  className,
  buttonClassName,
}) => {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const currentBranchLabel = branches.find((branch) => branch.name === currentBranch)?.displayName ?? currentBranch;
  const canChangeBranch = Boolean(onBranchChange || onCreateBranch);
  const closeSelector = () => setOpen(false);

  const renderActionItems = (branch: VersionControlBranch, kind: 'dropdown' | 'context') => (
    <BranchActionItems
      branch={branch}
      disabled={disabled}
      kind={kind}
      onCloseSelector={closeSelector}
      onBranchChange={onBranchChange}
      onRenameBranch={onRenameBranch}
      onDeleteBranch={onDeleteBranch}
      onCreateTrackingBranch={onCreateTrackingBranch}
    />
  );

  return (
    <div className={cn('flex w-full max-w-full min-w-0 items-center gap-2 overflow-hidden', className)}>
      {!hideLabel && (
        <span className="flex items-center gap-1 whitespace-nowrap text-xs text-muted-foreground">
          <GitBranch className="h-3 w-3" />
          {t('shared.versionControl.actions.branch.label')}
        </span>
      )}
      <div className="relative min-w-0 max-w-full flex-1 overflow-hidden">
        {canChangeBranch ? (
          <DropdownMenu open={open} onOpenChange={setOpen}>
            <DropdownMenuTrigger asChild>
              <button
                type="button"
                className={cn(
                  'flex w-full max-w-full min-w-0 items-center gap-2 overflow-hidden rounded-md border border-border bg-background px-3 py-1 transition-colors hover:bg-muted/30 disabled:opacity-50',
                  buttonClassName,
                )}
                disabled={disabled}
                aria-label={`${t('shared.versionControl.actions.branch.label')}: ${currentBranchLabel}`}
              >
                <GitBranch className="h-3 w-3 shrink-0 text-muted-foreground" />
                <span className="min-w-0 flex-1 truncate text-left text-sm font-medium text-foreground">
                  {currentBranchLabel}
                </span>
                <ChevronDown className="h-3 w-3 shrink-0 text-muted-foreground" />
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent
              align="start"
              collisionPadding={8}
              className="max-h-[min(24rem,calc(100vh-2rem))] min-w-64 overflow-y-auto"
            >
              {onCreateBranch && (
                <DropdownMenuItem
                  className="text-primary focus:text-primary"
                  onSelect={() => {
                    closeSelector();
                    onCreateBranch();
                  }}
                >
                  <GitBranch className="mr-2 h-3 w-3" />
                  {t('shared.versionControl.actions.branch.create')}
                </DropdownMenuItem>
              )}
              {branches.map((branch) => {
                const hasActions = branch.kind === 'remote'
                  ? Boolean(onCreateTrackingBranch)
                  : Boolean(onBranchChange || onRenameBranch || onDeleteBranch);
                return (
                  <ContextMenu key={branch.name}>
                    <ContextMenuTrigger asChild disabled={!hasActions}>
                      <div
                        className={cn(
                          'flex min-w-0 items-center rounded-sm',
                          branch.isCurrent && 'bg-primary/10 text-primary',
                        )}
                      >
                        <DropdownMenuItem
                          disabled={branch.kind === 'remote' || !onBranchChange || disabled}
                          className="min-w-0 flex-1"
                          onSelect={() => {
                            closeSelector();
                            onBranchChange?.(branch.name);
                          }}
                        >
                          <GitBranch className="mr-2 h-3 w-3 shrink-0" />
                          <span className="truncate">{branch.displayName}</span>
                        </DropdownMenuItem>
                        {hasActions && (
                          <DropdownMenu modal={false}>
                            <DropdownMenuTrigger asChild>
                              <button
                                type="button"
                                className="mr-1 shrink-0 rounded p-1 hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                                aria-label={t('shared.versionControl.branch.actions.menu', {
                                  branch: branch.displayName,
                                })}
                                onClick={(event) => event.stopPropagation()}
                              >
                                <MoreHorizontal className="h-3.5 w-3.5" />
                              </button>
                            </DropdownMenuTrigger>
                            <DropdownMenuContent
                              align="end"
                              collisionPadding={8}
                              className="w-52"
                              aria-label={t('shared.versionControl.branch.actions.menu', {
                                branch: branch.displayName,
                              })}
                            >
                              {renderActionItems(branch, 'dropdown')}
                            </DropdownMenuContent>
                          </DropdownMenu>
                        )}
                      </div>
                    </ContextMenuTrigger>
                    {hasActions && (
                      <ContextMenuContent
                        collisionPadding={8}
                        className="w-52"
                        aria-label={t('shared.versionControl.branch.actions.menu', {
                          branch: branch.displayName,
                        })}
                      >
                        {renderActionItems(branch, 'context')}
                      </ContextMenuContent>
                    )}
                  </ContextMenu>
                );
              })}
            </DropdownMenuContent>
          </DropdownMenu>
        ) : (
          <div className={cn(
            'flex w-full max-w-full min-w-0 items-center gap-2 overflow-hidden rounded-md border border-border bg-background px-3 py-1',
            buttonClassName,
          )}>
            <GitBranch className="h-3 w-3 shrink-0 text-muted-foreground" />
            <span className="min-w-0 truncate text-sm font-medium text-foreground">{currentBranchLabel}</span>
          </div>
        )}
      </div>
    </div>
  );
};
