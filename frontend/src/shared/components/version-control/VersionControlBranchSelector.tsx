import React, { useEffect, useRef, useState } from 'react';
import { ChevronDown, GitBranch } from 'lucide-react';
import { useI18n } from '@/shared/hooks/useI18n';
import type { VersionControlBranch } from '@/shared/types/versionControl';

interface VersionControlBranchSelectorProps {
  branches: VersionControlBranch[];
  currentBranch: string;
  onBranchChange: (branch: string) => void;
  disabled?: boolean;
}

export const VersionControlBranchSelector: React.FC<VersionControlBranchSelectorProps> = ({
  branches,
  currentBranch,
  onBranchChange,
  disabled = false,
}) => {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) {
      return;
    }

    const handlePointerDown = (event: MouseEvent) => {
      if (!containerRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    };

    document.addEventListener('mousedown', handlePointerDown);
    return () => document.removeEventListener('mousedown', handlePointerDown);
  }, [open]);

  return (
    <div className="flex items-center gap-2">
      <span className="flex items-center gap-1 text-xs text-muted-foreground whitespace-nowrap">
        <GitBranch className="h-3 w-3" />
        {t('shared.versionControl.actions.branch.label')}
      </span>
      <div ref={containerRef} className="relative">
        <button
          type="button"
          onClick={() => setOpen((value) => !value)}
          className="flex items-center gap-2 px-3 py-1 bg-background border border-border rounded-md hover:bg-muted/30 transition-colors disabled:opacity-50"
          disabled={disabled}
        >
          <GitBranch className="h-3 w-3 text-muted-foreground" />
          <span className="text-sm font-medium text-foreground">{currentBranch}</span>
          <ChevronDown className="h-3 w-3 text-muted-foreground" />
        </button>

        {open && (
          <div className="absolute top-full left-0 mt-1 w-48 bg-background border border-border rounded-md shadow-lg z-10">
            <div className="py-1">
              {branches.map((branch) => (
                <button
                  key={branch.name}
                  type="button"
                  onClick={() => {
                    setOpen(false);
                    onBranchChange(branch.name);
                  }}
                  className={`w-full text-left px-3 py-2 text-sm hover:bg-muted/50 transition-colors flex items-center gap-2 ${
                    branch.name === currentBranch ? 'bg-primary/10 text-primary' : 'text-foreground'
                  }`}
                >
                  <GitBranch className="h-3 w-3" />
                  {branch.displayName ?? branch.name}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default VersionControlBranchSelector;
