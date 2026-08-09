import React from 'react';
import type { LucideIcon } from 'lucide-react';
import { FeatureHeader } from '@/shared/components/layout/FeatureHeader';
import { Button } from '@/shared/components/ui/button';
import { Badge } from '@/shared/components/ui/badge';

export interface SettingsWorkflowShellProps {
  title: string;
  icon: LucideIcon;
  headerActions?: React.ReactNode;
  summary?: React.ReactNode;
  controls?: React.ReactNode;
  error?: React.ReactNode;
  isLoading?: boolean;
  loadingLabel?: string;
  hasItems: boolean;
  emptyIcon?: React.ReactNode;
  emptyTitle: string;
  emptyDescription: string;
  emptyActions?: React.ReactNode;
  children?: React.ReactNode;
  contentClassName?: string;
}

export const SettingsWorkflowShell: React.FC<SettingsWorkflowShellProps> = ({
  title,
  icon: Icon,
  headerActions,
  summary,
  controls,
  error,
  isLoading = false,
  loadingLabel,
  hasItems,
  emptyIcon,
  emptyTitle,
  emptyDescription,
  emptyActions,
  children,
  contentClassName = 'space-y-4 p-4',
}) => {
  const showControlsBar = Boolean(controls);

  return (
    <div className="flex h-full flex-col bg-background">
      <FeatureHeader
        title={title}
        icon={Icon}
        actions={headerActions}
        info={summary}
      />

      {error ? (
        <div className="border-b border-destructive/40 bg-destructive/10 px-4 py-2 text-xs text-destructive">
          {error}
        </div>
      ) : null}

      {showControlsBar ? (
        <div className="flex h-10 items-center border-b border-border bg-muted/20 px-3">
          <div className="flex w-full min-w-0 items-center gap-2">
            {controls}
          </div>
        </div>
      ) : null}

      <div className="flex-1 overflow-hidden">
        {isLoading ? (
          <div className="flex h-full items-center justify-center px-6 text-sm text-muted-foreground">
            {loadingLabel}
          </div>
        ) : hasItems ? (
          <div className={`h-full overflow-auto ${contentClassName}`}>{children}</div>
        ) : (
          <div className="flex h-full flex-col items-center justify-center gap-3 p-6 text-center">
            {emptyIcon ? (
              <div className="rounded-full bg-muted p-3">
                {emptyIcon}
              </div>
            ) : null}
            <div className="space-y-1">
              <p className="text-base font-medium text-foreground">{emptyTitle}</p>
              <p className="text-sm text-muted-foreground">{emptyDescription}</p>
            </div>
            {emptyActions}
          </div>
        )}
      </div>
    </div>
  );
};

export const SettingsWorkflowCountBadge: React.FC<{ label: string }> = ({ label }) => (
  <Badge variant="secondary" className="text-[11px]">
    {label}
  </Badge>
);

export const SettingsWorkflowActionButton: React.FC<React.ComponentProps<typeof Button>> = (props) => (
  <Button size="sm" className="h-7 px-2 text-xs" {...props} />
);
