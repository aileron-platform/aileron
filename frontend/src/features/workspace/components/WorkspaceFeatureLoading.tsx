import type React from 'react';
import { cn } from '@/shared/utils/cn';
import { useI18n } from '@/shared/hooks/useI18n';

interface WorkspaceFeatureLoadingProps {
  labelKey?: string;
  className?: string;
}

export const WorkspaceFeatureLoading: React.FC<WorkspaceFeatureLoadingProps> = ({
  labelKey = 'workspace.layout.loading.workspace',
  className,
}) => {
  const { t } = useI18n();
  const label = t(labelKey);

  return (
    <div
      data-testid="workspace-feature-loading"
      className={cn('flex h-full min-h-0 w-full flex-col gap-4 bg-background p-4', className)}
      role="status"
      aria-busy="true"
      aria-live="polite"
      aria-label={label}
    >
      <div className="h-8 w-48 animate-pulse rounded-md bg-muted/60" aria-hidden="true" />
      <div className="h-4 w-72 max-w-full animate-pulse rounded bg-muted/40" aria-hidden="true" />
      <div className="flex min-h-0 flex-1 flex-col gap-3 rounded-lg border border-border/60 p-4" aria-hidden="true">
        <div className="h-10 w-full animate-pulse rounded-md bg-muted/50" />
        <div className="h-8 w-5/6 animate-pulse rounded-md bg-muted/40" />
        <div className="h-8 w-4/6 animate-pulse rounded-md bg-muted/40" />
      </div>
    </div>
  );
};
