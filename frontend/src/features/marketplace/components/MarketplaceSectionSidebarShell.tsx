import React from 'react';
import { FileTreeSearchBar } from '@/shared/components/file-workbench';
import { ResourceSidebarShell } from '@/shared/components/resource-workflow';
import { cn } from '@/shared/utils/cn';

interface MarketplaceSectionSidebarShellProps {
  title: string;
  icon?: React.ReactNode;
  actions?: React.ReactNode;
  searchValue?: string;
  onSearchChange?: (value: string) => void;
  onSearchClear?: () => void;
  searchPlaceholder?: string;
  body: React.ReactNode;
  className?: string;
  bodyClassName?: string;
}

export const MarketplaceSectionSidebarShell: React.FC<MarketplaceSectionSidebarShellProps> = ({
  title,
  icon,
  actions,
  searchValue,
  onSearchChange,
  onSearchClear,
  searchPlaceholder,
  body,
  className,
  bodyClassName,
}) => {
  const showSearch = typeof onSearchChange === 'function';

  const header = (
    <div className="flex h-10 items-center justify-between border-b border-border bg-muted/30 px-3">
      <div className="flex min-w-0 items-center gap-2">
        {icon ? <div className="flex shrink-0 items-center text-primary">{icon}</div> : null}
        <span className="truncate text-sm font-medium">{title}</span>
      </div>
      {actions ? <div className="flex shrink-0 items-center gap-1">{actions}</div> : null}
    </div>
  );

  const search = showSearch ? (
    <FileTreeSearchBar
      value={searchValue ?? ''}
      onChange={onSearchChange!}
      onClear={onSearchClear}
      placeholder={searchPlaceholder}
      showClearButton
      containerClassName="border-b border-border bg-muted/20"
    />
  ) : undefined;

  return (
    <ResourceSidebarShell
      className={cn('border-r border-border bg-background text-foreground', className)}
      header={header}
      search={search}
      body={body}
      bodyClassName={cn('min-h-0 flex-1 overflow-hidden', bodyClassName)}
    />
  );
};
