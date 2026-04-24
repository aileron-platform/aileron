import React from 'react';
import type { VersionControlBranch } from '@/shared/types/versionControl';
import { VersionControlActionMenu, type VersionControlActionMenuItem } from './VersionControlActionMenu';
import { VersionControlBranchSelector } from './VersionControlBranchSelector';

interface VersionControlBranchActionHeaderProps {
  branches: VersionControlBranch[];
  currentBranch: string;
  onBranchChange: (branch: string) => void;
  actions: VersionControlActionMenuItem[];
  disabled?: boolean;
}

export const VersionControlBranchActionHeader: React.FC<VersionControlBranchActionHeaderProps> = ({
  branches,
  currentBranch,
  onBranchChange,
  actions,
  disabled = false,
}) => (
  <div className="flex h-10 flex-shrink-0 items-center justify-between border-b border-border bg-muted/30 px-4">
    <VersionControlBranchSelector
      branches={branches}
      currentBranch={currentBranch}
      onBranchChange={onBranchChange}
      disabled={disabled}
    />
    <VersionControlActionMenu actions={actions} disabled={disabled} />
  </div>
);

export default VersionControlBranchActionHeader;
