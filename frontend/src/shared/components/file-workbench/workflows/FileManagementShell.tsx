import React from 'react';
import { cn } from '@/shared/utils/cn';

export interface FileManagementShellProps {
  sidebar: React.ReactNode;
  mainContent: React.ReactNode;
  overlay?: React.ReactNode;
  className?: string;
  sidebarClassName?: string;
  mainClassName?: string;
}

export const FileManagementShell = ({
  sidebar,
  mainContent,
  overlay,
  className,
  sidebarClassName,
  mainClassName,
}: FileManagementShellProps) => (
  <div className={cn('relative flex h-full min-h-0 w-full min-w-0 overflow-hidden bg-background', className)}>
    <div className={cn('flex-shrink-0 min-h-0', sidebarClassName)}>
      {sidebar}
    </div>
    <div className={cn('flex min-w-0 flex-1 flex-col', mainClassName)}>
      {mainContent}
    </div>
    {overlay}
  </div>
);
