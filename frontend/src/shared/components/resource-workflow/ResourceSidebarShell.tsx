import React from 'react';
import { FileTreeSearchBar } from '@/shared/components/file-workbench';
import { useI18n } from '@/shared/hooks/useI18n';
import { cn } from '@/shared/utils/cn';

export interface ResourceSidebarShellProps {
  header?: React.ReactNode;
  scopeFilter?: React.ReactNode;
  search?: React.ReactNode;
  body?: React.ReactNode;
  footer?: React.ReactNode;
  className?: string;
  headerClassName?: string;
  scopeFilterClassName?: string;
  searchClassName?: string;
  bodyClassName?: string;
  footerClassName?: string;
  searchValue?: string;
  onSearchChange?: (value: string) => void;
  onSearchClear?: () => void;
  searchPlaceholderKey?: string;
  searchPlaceholder?: string;
}

export const ResourceSidebarShell: React.FC<ResourceSidebarShellProps> = ({
  header,
  scopeFilter,
  search,
  body,
  footer,
  className,
  headerClassName,
  scopeFilterClassName,
  searchClassName,
  bodyClassName,
  footerClassName,
  searchValue,
  onSearchChange,
  onSearchClear,
  searchPlaceholderKey = 'resource.sidebar.search.placeholder',
  searchPlaceholder,
}) => {
  const { t } = useI18n();
  const resolvedSearch = search ?? (onSearchChange ? (
    <FileTreeSearchBar
      value={searchValue ?? ''}
      onChange={onSearchChange}
      onClear={onSearchClear}
      placeholder={searchPlaceholder ?? t(searchPlaceholderKey)}
      showClearButton
    />
  ) : undefined);

  return (
    <div className={cn('flex h-full min-h-0 flex-col', className)}>
      {header ? <div className={headerClassName}>{header}</div> : null}
      {scopeFilter ? <div className={scopeFilterClassName}>{scopeFilter}</div> : null}
      {resolvedSearch ? <div className={searchClassName}>{resolvedSearch}</div> : null}
      {body ? <div className={bodyClassName}>{body}</div> : null}
      {footer ? <div className={footerClassName}>{footer}</div> : null}
    </div>
  );
};

export default ResourceSidebarShell;
