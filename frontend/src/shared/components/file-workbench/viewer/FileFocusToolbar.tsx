import type React from 'react';
import { Minimize2 } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import { cn } from '@/shared/utils/cn';

interface FileFocusToolbarProps {
  icon?: React.ReactNode;
  title: React.ReactNode;
  subtitle?: React.ReactNode;
  metadata?: React.ReactNode;
  actions?: React.ReactNode;
  exitLabel: string;
  onExit: () => void;
  className?: string;
}

export const FileFocusToolbar: React.FC<FileFocusToolbarProps> = ({
  icon,
  title,
  subtitle,
  metadata,
  actions,
  exitLabel,
  onExit,
  className,
}) => (
  <div className={cn('h-10 flex-shrink-0 border-b border-border bg-card px-3', className)}>
    <div className="flex h-full min-w-0 items-center justify-between gap-3">
      <div className="flex min-w-0 items-center gap-2">
        {icon ? <span className="flex-shrink-0 text-muted-foreground">{icon}</span> : null}
        <div className="min-w-0">
          <div className="truncate text-sm font-medium text-foreground">{title}</div>
          {subtitle ? (
            <div className="truncate text-xs text-muted-foreground">{subtitle}</div>
          ) : null}
        </div>
        {metadata ? (
          <div className="ml-2 hidden min-w-0 items-center gap-2 text-xs text-muted-foreground md:flex">
            {metadata}
          </div>
        ) : null}
      </div>

      <div className="flex flex-shrink-0 items-center gap-1">
        {actions}
        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={onExit}
          title={exitLabel}
          aria-label={exitLabel}
        >
          <Minimize2 className="h-4 w-4" />
        </Button>
      </div>
    </div>
  </div>
);

export default FileFocusToolbar;
