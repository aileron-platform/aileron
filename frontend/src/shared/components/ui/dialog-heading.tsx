import type { ComponentType, ReactNode } from 'react';
import type { LucideProps } from 'lucide-react';
import { AlertDialogTitle } from './alert-dialog';
import { DialogTitle } from './dialog';
import { cn } from '@/shared/utils/cn';

type DialogHeadingTone = 'default' | 'primary' | 'destructive';

interface BaseHeadingProps {
  icon: ComponentType<LucideProps>;
  children: ReactNode;
  className?: string;
  iconClassName?: string;
  tone?: DialogHeadingTone;
}

const toneIconClassName: Record<DialogHeadingTone, string> = {
  default: 'text-foreground',
  primary: 'text-primary',
  destructive: 'text-destructive',
};

const renderIcon = (
  Icon: ComponentType<LucideProps>,
  tone: DialogHeadingTone,
  iconClassName?: string,
) => (
  <Icon
    aria-hidden="true"
    className={cn('h-5 w-5 shrink-0', toneIconClassName[tone], iconClassName)}
  />
);

export const DialogHeading = ({
  icon,
  children,
  className,
  iconClassName,
  tone = 'primary',
}: BaseHeadingProps) => (
  <DialogTitle className={cn('flex items-center gap-2', className)}>
    {renderIcon(icon, tone, iconClassName)}
    {children}
  </DialogTitle>
);

export const AlertDialogHeading = ({
  icon,
  children,
  className,
  iconClassName,
  tone = 'destructive',
}: BaseHeadingProps) => (
  <AlertDialogTitle className={cn('flex items-center gap-2', className)}>
    {renderIcon(icon, tone, iconClassName)}
    {children}
  </AlertDialogTitle>
);
