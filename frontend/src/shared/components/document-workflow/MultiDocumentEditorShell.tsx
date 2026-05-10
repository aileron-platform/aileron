import React from 'react';
import type { LucideIcon } from 'lucide-react';
import { FeatureHeader } from '@/shared/components/layout/FeatureHeader';
import { cn } from '@/shared/utils/cn';

export interface MultiDocumentEditorShellLabels {
  loading: string;
}

export interface MultiDocumentEditorShellProps {
  title: string;
  icon: LucideIcon;
  sidebar?: React.ReactNode;
  mainArea: React.ReactNode;
  headerActions?: React.ReactNode;
  emptyState?: React.ReactNode;
  isLoading?: boolean;
  labels: MultiDocumentEditorShellLabels;
  className?: string;
  sidebarClassName?: string;
  mainClassName?: string;
  contentClassName?: string;
}

export const MultiDocumentEditorShell: React.FC<MultiDocumentEditorShellProps> = ({
  title,
  icon,
  sidebar,
  mainArea,
  headerActions,
  emptyState,
  isLoading = false,
  labels,
  className,
  sidebarClassName,
  mainClassName,
  contentClassName,
}) => {
  const content = isLoading
    ? (
      <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
        {labels.loading}
      </div>
    )
    : (emptyState ?? mainArea);

  return (
    <div className={cn('flex h-full min-h-0 overflow-hidden bg-background text-foreground', className)}>
      {sidebar ? (
        <aside className={cn('w-80 flex-shrink-0 min-h-0 overflow-hidden', sidebarClassName)}>
          {sidebar}
        </aside>
      ) : null}
      <section className={cn('flex min-w-0 flex-1 flex-col overflow-hidden', mainClassName)}>
        <FeatureHeader title={title} icon={icon} actions={headerActions} />
        <div className={cn('flex flex-1 min-h-0 flex-col overflow-hidden', contentClassName)}>
          {content}
        </div>
      </section>
    </div>
  );
};

export default MultiDocumentEditorShell;
