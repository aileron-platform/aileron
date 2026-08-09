import type { LucideIcon } from 'lucide-react';
import type { FC, ReactNode } from 'react';
import { cn } from '@/shared/utils/cn';

interface EmptyStateProps {
  icon: LucideIcon;
  title: ReactNode;
  description?: ReactNode;
  action?: ReactNode;
  tone?: 'default' | 'destructive';
  className?: string;
  iconClassName?: string;
}

export const EmptyState: FC<EmptyStateProps> = ({
  icon: Icon,
  title,
  description,
  action,
  tone = 'default',
  className,
  iconClassName,
}) => (
  <div className={cn('flex h-full items-center justify-center p-4', className)}>
    <div className="max-w-sm text-center">
      <Icon
        className={cn(
          'mx-auto mb-3 h-10 w-10 opacity-60',
          tone === 'destructive' ? 'text-destructive' : 'text-muted-foreground',
          iconClassName,
        )}
      />
      <p className="mb-1 text-sm font-medium text-foreground">{title}</p>
      {description !== undefined && (
        <p className="text-xs text-muted-foreground">{description}</p>
      )}
      {action !== undefined && <div className="mt-3">{action}</div>}
    </div>
  </div>
);
