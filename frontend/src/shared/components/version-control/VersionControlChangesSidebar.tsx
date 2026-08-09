import React from 'react';
import { CircleStop, FileText, Loader2, Minus, Plus } from 'lucide-react';
import { EmptyState } from '@/shared/components/ui/empty-state';
import { useI18n } from '@/shared/hooks/useI18n';
import type { VersionControlBranch, VersionControlFileChange, VersionControlOperationStatus } from '@/shared/version-control';
import { VersionControlBranchActionHeader } from './VersionControlBranchActionHeader';
import type { VersionControlActionMenuExtensionItem, VersionControlActionMenuItem } from './VersionControlActionMenu';
import { VersionControlCommitForm } from './VersionControlCommitForm';
import { VersionControlFileChangeItem } from './VersionControlFileChangeItem';
import { VersionControlFilePanelSection } from './VersionControlFilePanelSection';
import { VersionControlForceUnlockDialog } from './VersionControlForceUnlockDialog';
import { VersionControlResizablePanels } from './VersionControlResizablePanels';

type FileGroup = 'staged' | 'unstaged';

interface VersionControlChangesSidebarProps {
  contextSlot?: React.ReactNode;
  branches: VersionControlBranch[];
  currentBranch: string;
  actions: VersionControlActionMenuItem[];
  actionExtensions?: VersionControlActionMenuExtensionItem[];
  stagedFiles: VersionControlFileChange[];
  unstagedFiles: VersionControlFileChange[];
  stagedCount?: number;
  unstagedCount?: number;
  conflictFiles?: VersionControlFileChange[];
  selectedStagedPath?: string | null;
  selectedUnstagedPath?: string | null;
  selectedStagedPaths?: Set<string>;
  selectedUnstagedPaths?: Set<string>;
  pendingStagedPaths?: Set<string>;
  pendingUnstagedPaths?: Set<string>;
  isMutating?: boolean;
  isCommitting?: boolean;
  isStageAllPending?: boolean;
  isUnstageAllPending?: boolean;
  mutationDisabled?: boolean;
  operationStatus?: VersionControlOperationStatus | null;
  onForceUnlock?: () => Promise<void>;
  onBranchChange?: (branch: string) => void;
  onCreateBranch?: () => void;
  onRenameBranch?: (branch: VersionControlBranch) => void;
  onDeleteBranch?: (branch: VersionControlBranch) => void;
  onCreateTrackingBranch?: (branch: VersionControlBranch) => void;
  onCommit: (data: { message: string }) => void;
  onFileSelect: (file: VersionControlFileChange, group: FileGroup, event?: React.MouseEvent) => void;
  onStageToggle: (file: VersionControlFileChange, group: FileGroup) => void;
  onMarkResolved?: (file: VersionControlFileChange) => void;
  onAbortConflict?: () => void;
  onDiscard?: (file: VersionControlFileChange) => void;
  onStageAll: () => void;
  onUnstageAll: () => void;
  stagedFooter?: React.ReactNode;
  unstagedFooter?: React.ReactNode;
}

export const VersionControlChangesSidebar: React.FC<VersionControlChangesSidebarProps> = ({
  contextSlot,
  branches,
  currentBranch,
  actions,
  actionExtensions,
  stagedFiles,
  unstagedFiles,
  stagedCount,
  unstagedCount,
  conflictFiles = [],
  selectedStagedPath = null,
  selectedUnstagedPath = null,
  selectedStagedPaths = new Set(),
  selectedUnstagedPaths = new Set(),
  pendingStagedPaths = new Set(),
  pendingUnstagedPaths = new Set(),
  isMutating = false,
  isCommitting = isMutating,
  isStageAllPending = false,
  isUnstageAllPending = false,
  mutationDisabled = false,
  operationStatus,
  onForceUnlock,
  onBranchChange,
  onCreateBranch,
  onRenameBranch,
  onDeleteBranch,
  onCreateTrackingBranch,
  onCommit,
  onFileSelect,
  onStageToggle,
  onMarkResolved,
  onAbortConflict,
  onDiscard,
  onStageAll,
  onUnstageAll,
  stagedFooter,
  unstagedFooter,
}) => {
  const { t } = useI18n();
  const [forceUnlockOpen, setForceUnlockOpen] = React.useState(false);

  const renderFileList = (group: FileGroup, files: VersionControlFileChange[]) => {
    const selectedPath = group === 'staged' ? selectedStagedPath : selectedUnstagedPath;
    const selectedPaths = group === 'staged' ? selectedStagedPaths : selectedUnstagedPaths;
    const pendingPaths = group === 'staged' ? pendingStagedPaths : pendingUnstagedPaths;
    const actionPending = group === 'staged' ? isUnstageAllPending : isStageAllPending;
    const totalCount = group === 'staged'
      ? stagedCount ?? files.length
      : unstagedCount ?? files.length;

    return (
      <VersionControlFilePanelSection
        title={group === 'staged'
          ? t('shared.versionControl.fileChanges.stagedTitle')
          : t('shared.versionControl.fileChanges.unstagedTitle')}
        count={totalCount}
        selectedCount={selectedPaths.size}
        actionIcon={actionPending
          ? <Loader2 className="h-3 w-3 animate-spin" />
          : group === 'staged'
            ? <Minus className="h-3 w-3" />
            : <Plus className="h-3 w-3" />}
        actionTitle={group === 'staged'
          ? t('shared.versionControl.fileChanges.unstageAllTooltip')
          : t('shared.versionControl.fileChanges.stageAllTooltip')}
        actionDisabled={totalCount === 0 || actionPending || isMutating || mutationDisabled}
        actionBusy={actionPending}
        onAction={mutationDisabled
          ? undefined
          : (event) => {
              event.stopPropagation();
              if (group === 'staged') {
                onUnstageAll();
              } else {
                onStageAll();
              }
            }}
      >
        {files.length === 0 ? (
          <EmptyState
            className="h-full"
            icon={FileText}
            title={t('shared.versionControl.fileChanges.empty')}
          />
        ) : (
          files.map((file) => (
            <VersionControlFileChangeItem
              key={`${group}:${file.path}`}
              file={file}
              isSelected={selectedPath === file.path}
              isMultiSelected={selectedPaths.has(file.path)}
              type={group}
              onSelect={onFileSelect}
              onStageToggle={(nextFile) => onStageToggle(nextFile, group)}
              onDiscard={group === 'unstaged' ? onDiscard : undefined}
              selectedCount={selectedPaths.size}
              readOnly={mutationDisabled}
              actionPending={pendingPaths.has(file.path)}
            />
          ))
        )}
        {group === 'staged' ? stagedFooter : unstagedFooter}
      </VersionControlFilePanelSection>
    );
  };

  const renderConflictList = () => {
    if (conflictFiles.length === 0) {
      return null;
    }

    return (
      <VersionControlFilePanelSection
        title={t('shared.versionControl.fileChanges.conflictsTitle')}
        count={conflictFiles.length}
        className="h-auto max-h-40 shrink-0 border-b border-border"
        actionIcon={<CircleStop className="h-3 w-3" />}
        actionTitle={t('shared.versionControl.conflictResolution.abortAction')}
        onAction={onAbortConflict ? () => onAbortConflict() : undefined}
        actionDisabled={mutationDisabled || isMutating}
      >
        {conflictFiles.map((file) => (
          <VersionControlFileChangeItem
            key={`conflict:${file.path}`}
            file={file}
            isSelected={false}
            isMultiSelected={false}
            type="unstaged"
            onSelect={event => onFileSelect(file, 'unstaged', event)}
            onStageToggle={() => onStageToggle(file, 'unstaged')}
            onMarkResolved={() => onMarkResolved?.(file)}
            selectedCount={0}
            readOnly={mutationDisabled || !onMarkResolved}
            conflict
          />
        ))}
      </VersionControlFilePanelSection>
    );
  };

  const bottomPanel = (
    <div className="flex h-full min-h-0 flex-col">
      {renderConflictList()}
      <div className="min-h-0 flex-1">
        {renderFileList('unstaged', unstagedFiles)}
      </div>
    </div>
  );

  return (
    <div className="flex h-full min-w-0 max-w-full flex-col overflow-hidden version-control-container">
      {contextSlot}
      <VersionControlBranchActionHeader
        branches={branches}
        currentBranch={currentBranch}
        onBranchChange={onBranchChange}
        onCreateBranch={onCreateBranch}
        onRenameBranch={onRenameBranch}
        onDeleteBranch={onDeleteBranch}
        onCreateTrackingBranch={onCreateTrackingBranch}
        actions={actions}
        actionExtensions={actionExtensions}
        branchDisabled={isMutating || mutationDisabled}
        operationStatus={operationStatus}
        onForceUnlockRequest={onForceUnlock ? () => setForceUnlockOpen(true) : undefined}
      />
      <VersionControlCommitForm
        onCommit={onCommit}
        isLoading={isCommitting}
        disabled={mutationDisabled || isMutating}
        stagedCount={stagedCount ?? stagedFiles.length}
      />
      <VersionControlResizablePanels
        top={renderFileList('staged', stagedFiles)}
        bottom={bottomPanel}
      />
      {onForceUnlock && (
        <VersionControlForceUnlockDialog
          open={forceUnlockOpen}
          onOpenChange={setForceUnlockOpen}
          onConfirm={onForceUnlock}
        />
      )}
    </div>
  );
};
