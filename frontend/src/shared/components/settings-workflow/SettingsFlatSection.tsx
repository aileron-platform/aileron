import type { ReactNode } from 'react';
import { Separator } from '@/shared/components/ui/separator';
import { cn } from '@/shared/utils/cn';

export interface SettingsFlatSectionProps {
  title: ReactNode;
  description?: ReactNode;
  children: ReactNode;
  className?: string;
}

export interface SettingsFlatRowProps {
  label: ReactNode;
  description?: ReactNode;
  children: ReactNode;
  className?: string;
}

export const SettingsFlatSection = ({
  title,
  description,
  children,
  className,
}: SettingsFlatSectionProps) => (
  <section className={cn('space-y-4', className)}>
    <div className="space-y-1">
      <h3 className="text-sm font-semibold text-foreground">{title}</h3>
      {description && <p className="text-sm text-muted-foreground">{description}</p>}
    </div>
    <div className="space-y-4">{children}</div>
  </section>
);

export const SettingsFlatRow = ({
  label,
  description,
  children,
  className,
}: SettingsFlatRowProps) => (
  <div
    className={cn(
      'grid gap-3 md:grid-cols-[minmax(10rem,12rem)_minmax(0,1fr)] md:items-start',
      className,
    )}
  >
    <div className="space-y-1">
      <div className="text-sm font-medium text-foreground">{label}</div>
      {description && <p className="text-xs text-muted-foreground">{description}</p>}
    </div>
    <div className="min-w-0 space-y-3">{children}</div>
  </div>
);

export const SettingsFlatField = ({
  label,
  description,
  children,
  className,
}: SettingsFlatRowProps) => (
  <div className={cn('space-y-2', className)}>
    <div className="space-y-1">
      <div className="text-sm font-medium text-foreground">{label}</div>
      {description && <p className="text-xs text-muted-foreground">{description}</p>}
    </div>
    {children}
  </div>
);

export const SettingsSectionDivider = () => <Separator className="my-6" />;
