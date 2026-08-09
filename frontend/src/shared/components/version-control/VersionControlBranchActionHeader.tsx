import React from 'react';
import { Clock3, Unlock } from 'lucide-react';
import type { VersionControlBranch, VersionControlOperationStatus } from '@/shared/version-control';
import { useI18n } from '@/shared/hooks/useI18n';
import { VersionControlActionMenu, type VersionControlActionMenuExtensionItem, type VersionControlActionMenuItem } from './VersionControlActionMenu';
import { VersionControlBranchSelector } from './VersionControlBranchSelector';

interface VersionControlBranchActionHeaderProps {
  branches: VersionControlBranch[];
  currentBranch: string;
  onBranchChange?: (branch: string) => void;
  onCreateBranch?: () => void;
  onRenameBranch?: (branch: VersionControlBranch) => void;
  onDeleteBranch?: (branch: VersionControlBranch) => void;
  onCreateTrackingBranch?: (branch: VersionControlBranch) => void;
  actions: VersionControlActionMenuItem[];
  actionExtensions?: VersionControlActionMenuExtensionItem[];
  branchDisabled?: boolean;
  operationStatus?: VersionControlOperationStatus | null;
  onForceUnlockRequest?: () => void;
}

export const VersionControlBranchActionHeader: React.FC<VersionControlBranchActionHeaderProps> = ({
  branches,
  currentBranch,
  onBranchChange,
  onCreateBranch,
  onRenameBranch,
  onDeleteBranch,
  onCreateTrackingBranch,
  actions,
  actionExtensions,
  branchDisabled = false,
  operationStatus,
  onForceUnlockRequest,
}) => {
  const { t } = useI18n();
  const scopeLabel = operationStatus?.blockingScope
    ? t(`shared.versionControl.operation.scope.${operationStatus.blockingScope}`)
    : '';

  return (
  <div className="flex h-10 w-full min-w-0 flex-shrink-0 items-center gap-2 overflow-hidden border-b border-border bg-muted/30 px-3">
    <VersionControlBranchSelector
      branches={branches}
      currentBranch={currentBranch}
      onBranchChange={onBranchChange}
      onCreateBranch={onCreateBranch}
      onRenameBranch={onRenameBranch}
      onDeleteBranch={onDeleteBranch}
      onCreateTrackingBranch={onCreateTrackingBranch}
      disabled={branchDisabled}
      className="min-w-0 max-w-full flex-1 overflow-hidden"
      buttonClassName="w-full max-w-full overflow-hidden"
    />
    <div className="flex min-w-0 shrink-0 items-center gap-2">
      {operationStatus?.isActive && (
        <div
          className="flex min-w-0 max-w-48 items-center gap-1.5 text-xs text-muted-foreground"
          title={t('shared.versionControl.operation.activeDetails', {
            actor: operationStatus.actorDisplayName ?? '',
            operation: operationStatus.operation ?? '',
            scope: scopeLabel,
          })}
          aria-live="polite"
        >
          <Clock3 className="h-3.5 w-3.5 shrink-0 animate-pulse" />
          <span className="truncate">
            {t('shared.versionControl.operation.activeCompact', {
              actor: operationStatus.actorDisplayName ?? '',
              operation: operationStatus.operation ?? '',
              scope: scopeLabel,
            })}
          </span>
        </div>
      )}
      {operationStatus?.stale && onForceUnlockRequest && (
        <button
          type="button"
          className="rounded p-1 text-destructive hover:bg-destructive/10"
          title={t('shared.versionControl.conflict.forceUnlock')}
          aria-label={t('shared.versionControl.conflict.forceUnlock')}
          onClick={onForceUnlockRequest}
        >
          <Unlock className="h-3.5 w-3.5" />
        </button>
      )}
      <VersionControlActionMenu actions={actions} extensionActions={actionExtensions} />
    </div>
  </div>
  );
};
