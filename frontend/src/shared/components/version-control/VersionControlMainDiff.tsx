import React from 'react';
import { GitBranch } from 'lucide-react';
import { useI18n } from '@/shared/hooks/useI18n';
import { VersionControlDiffContent } from './VersionControlDiffContent';

interface VersionControlMainDiffProps {
  selectedPath?: string | null;
  diffContent?: string | null;
  isLoading?: boolean;
  error?: string | null;
  emptyKey?: string;
}

export const VersionControlMainDiff: React.FC<VersionControlMainDiffProps> = ({
  selectedPath,
  diffContent,
  isLoading = false,
  error = null,
  emptyKey = 'shared.versionControl.main.selectFile',
}) => {
  const { t } = useI18n();

  return (
    <div className="flex h-full min-h-0 min-w-0 flex-col overflow-hidden">
      <div className="flex h-10 min-w-0 items-center gap-2 overflow-hidden border-b border-border bg-muted/30 px-3">
        <GitBranch className="h-4 w-4 shrink-0 text-primary" />
        <span className="min-w-0 truncate text-sm font-medium">
          {selectedPath ?? t(emptyKey)}
        </span>
      </div>
      <div className="min-h-0 flex-1 overflow-hidden">
        <VersionControlDiffContent
          diffContent={diffContent}
          selectedPath={selectedPath ?? null}
          isLoading={isLoading}
          error={error}
        />
      </div>
    </div>
  );
};
