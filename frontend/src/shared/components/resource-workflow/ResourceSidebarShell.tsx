import React from 'react';
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
}) => {
  return (
    <div className={cn('flex h-full min-h-0 flex-col', className)}>
      {header ? <div className={headerClassName}>{header}</div> : null}
      {search ? <div className={searchClassName}>{search}</div> : null}
      {scopeFilter ? <div className={scopeFilterClassName}>{scopeFilter}</div> : null}
      {body ? <div className={bodyClassName}>{body}</div> : null}
      {footer ? <div className={footerClassName}>{footer}</div> : null}
    </div>
  );
};
