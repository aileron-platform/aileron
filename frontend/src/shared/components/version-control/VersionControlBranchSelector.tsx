import React, { useEffect, useRef, useState } from 'react';
import { ChevronDown, GitBranch } from 'lucide-react';
import { useI18n } from '@/shared/hooks/useI18n';
import type { VersionControlBranch } from '@/shared/types/versionControl';
import { cn } from '@/shared/utils/cn';

interface VersionControlBranchSelectorProps {
  branches: VersionControlBranch[];
  currentBranch: string;
  onBranchChange: (branch: string) => void;
  onCreateBranch?: () => void;
  disabled?: boolean;
  hideLabel?: boolean;
  className?: string;
  buttonClassName?: string;
}

export const VersionControlBranchSelector: React.FC<VersionControlBranchSelectorProps> = ({
  branches,
  currentBranch,
  onBranchChange,
  onCreateBranch,
  disabled = false,
  hideLabel = false,
  className,
  buttonClassName,
}) => {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const currentBranchLabel = branches.find((branch) => branch.name === currentBranch)?.displayName ?? currentBranch;

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
    <div className={cn('flex min-w-0 items-center gap-2', className)}>
      {!hideLabel && (
        <span className="flex items-center gap-1 text-xs text-muted-foreground whitespace-nowrap">
          <GitBranch className="h-3 w-3" />
          {t('shared.versionControl.actions.branch.label')}
        </span>
      )}
      <div ref={containerRef} className="relative min-w-0 flex-1">
        <button
          type="button"
          onClick={() => setOpen((value) => !value)}
          className={cn(
            'flex min-w-0 items-center gap-2 px-3 py-1 bg-background border border-border rounded-md hover:bg-muted/30 transition-colors disabled:opacity-50',
            buttonClassName,
          )}
          disabled={disabled}
        >
          <GitBranch className="h-3 w-3 text-muted-foreground" />
          <span className="min-w-0 truncate text-sm font-medium text-foreground">{currentBranchLabel}</span>
          <ChevronDown className="h-3 w-3 text-muted-foreground" />
        </button>

        {open && (
          <div className="absolute top-full left-0 z-10 mt-1 w-full min-w-0 rounded-md border border-border bg-background shadow-lg">
            <div className="py-1">
              {onCreateBranch && (
                <button
                  type="button"
                  onClick={() => {
                    setOpen(false);
                    onCreateBranch();
                  }}
                  className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-primary transition-colors hover:bg-muted/50"
                >
                  <GitBranch className="h-3 w-3" />
                  {t('shared.versionControl.actions.branch.create')}
                </button>
              )}
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
