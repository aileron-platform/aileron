import React from 'react';
import { Minus, Plus } from 'lucide-react';
import { useI18n } from '@/shared/hooks/useI18n';
import type { VersionControlBranch, VersionControlFileChange } from '@/shared/types/versionControl';
import { VersionControlBranchActionHeader } from './VersionControlBranchActionHeader';
import type { VersionControlActionMenuItem } from './VersionControlActionMenu';
import { VersionControlCommitForm } from './VersionControlCommitForm';
import { VersionControlFileChangeItem } from './VersionControlFileChangeItem';
import { VersionControlFilePanelSection } from './VersionControlFilePanelSection';
import { VersionControlResizablePanels } from './VersionControlResizablePanels';

type FileGroup = 'staged' | 'unstaged';

interface VersionControlChangesSidebarProps {
  contextSlot?: React.ReactNode;
  branches: VersionControlBranch[];
  currentBranch: string;
  actions: VersionControlActionMenuItem[];
  stagedFiles: VersionControlFileChange[];
  unstagedFiles: VersionControlFileChange[];
  selectedStagedPath?: string | null;
  selectedUnstagedPath?: string | null;
  selectedStagedPaths?: Set<string>;
  selectedUnstagedPaths?: Set<string>;
  isMutating?: boolean;
  onBranchChange: (branch: string) => void;
  onCreateBranch?: () => void;
  onCommit: (data: { message: string }) => void;
  onFileSelect: (file: VersionControlFileChange, group: FileGroup, event?: React.MouseEvent) => void;
  onStageToggle: (file: VersionControlFileChange, group: FileGroup) => void;
  onDiscard?: (file: VersionControlFileChange) => void;
  onStageAll: () => void;
  onUnstageAll: () => void;
  unstagedFooter?: React.ReactNode;
}

export const VersionControlChangesSidebar: React.FC<VersionControlChangesSidebarProps> = ({
  contextSlot,
  branches,
  currentBranch,
  actions,
  stagedFiles,
  unstagedFiles,
  selectedStagedPath = null,
  selectedUnstagedPath = null,
  selectedStagedPaths = new Set(),
  selectedUnstagedPaths = new Set(),
  isMutating = false,
  onBranchChange,
  onCreateBranch,
  onCommit,
  onFileSelect,
  onStageToggle,
  onDiscard,
  onStageAll,
  onUnstageAll,
  unstagedFooter,
}) => {
  const { t } = useI18n();

  const renderFileList = (group: FileGroup, files: VersionControlFileChange[]) => {
    const selectedPath = group === 'staged' ? selectedStagedPath : selectedUnstagedPath;
    const selectedPaths = group === 'staged' ? selectedStagedPaths : selectedUnstagedPaths;

    return (
      <VersionControlFilePanelSection
        title={group === 'staged'
          ? t('shared.versionControl.fileChanges.stagedTitle')
          : t('shared.versionControl.fileChanges.unstagedTitle')}
        count={files.length}
        selectedCount={selectedPaths.size}
        actionIcon={group === 'staged' ? <Minus className="h-3 w-3" /> : <Plus className="h-3 w-3" />}
        actionTitle={group === 'staged'
          ? t('shared.versionControl.fileChanges.unstageAllTooltip')
          : t('shared.versionControl.fileChanges.stageAllTooltip')}
        actionDisabled={files.length === 0 || isMutating}
        onAction={(event) => {
          event.stopPropagation();
          if (group === 'staged') {
            onUnstageAll();
          } else {
            onStageAll();
          }
        }}
      >
        {files.length === 0 ? (
          <div className="flex h-28 items-center justify-center text-sm text-muted-foreground">
            {t('shared.versionControl.fileChanges.empty')}
          </div>
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
            />
          ))
        )}
        {group === 'unstaged' && unstagedFooter}
      </VersionControlFilePanelSection>
    );
  };

  return (
    <div className="h-full flex flex-col version-control-container">
      {contextSlot}
      <VersionControlBranchActionHeader
        branches={branches}
        currentBranch={currentBranch}
        onBranchChange={onBranchChange}
        onCreateBranch={onCreateBranch}
        actions={actions}
        disabled={isMutating}
      />
      <VersionControlCommitForm
        onCommit={onCommit}
        isLoading={isMutating}
        stagedCount={stagedFiles.length}
      />
      <VersionControlResizablePanels
        top={renderFileList('staged', stagedFiles)}
        bottom={renderFileList('unstaged', unstagedFiles)}
      />
    </div>
  );
};

export default VersionControlChangesSidebar;
