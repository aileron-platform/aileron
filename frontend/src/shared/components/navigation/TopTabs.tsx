import * as React from 'react';
import { Badge } from '@/shared/components/ui/badge';
import { TabsList, TabsTrigger } from '@/shared/components/ui/tabs';
import { cn } from '@/shared/utils/cn';

export const TopTabsBar = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div
    ref={ref}
    className={cn('border-b bg-background px-3', className)}
    {...props}
  />
));
TopTabsBar.displayName = 'TopTabsBar';

export const TopTabsList = React.forwardRef<
  React.ElementRef<typeof TabsList>,
  React.ComponentPropsWithoutRef<typeof TabsList>
>(({ className, ...props }, ref) => (
  <TabsList
    ref={ref}
    className={cn(
      'flex h-10 w-full flex-nowrap justify-start overflow-x-auto bg-transparent p-0 text-foreground',
      className,
    )}
    {...props}
  />
));
TopTabsList.displayName = 'TopTabsList';

export const TopTabsTrigger = React.forwardRef<
  React.ElementRef<typeof TabsTrigger>,
  React.ComponentPropsWithoutRef<typeof TabsTrigger>
>(({ className, ...props }, ref) => (
  <TabsTrigger
    ref={ref}
    className={cn(
      'inline-flex h-10 flex-shrink-0 items-center gap-2 rounded-none border-b-2 border-transparent px-4 py-0 text-sm font-medium text-muted-foreground shadow-none whitespace-nowrap',
      'hover:bg-transparent hover:text-foreground',
      'focus-visible:ring-1 focus-visible:ring-ring focus-visible:ring-offset-0',
      'data-[state=active]:border-primary data-[state=active]:bg-transparent data-[state=active]:text-foreground data-[state=active]:shadow-none',
      className,
    )}
    {...props}
  />
));
TopTabsTrigger.displayName = 'TopTabsTrigger';

export interface TopTabsCountBadgeProps extends React.ComponentPropsWithoutRef<typeof Badge> {
  count: number;
}

export const TopTabsCountBadge: React.FC<TopTabsCountBadgeProps> = ({
  className,
  count,
  variant = 'secondary',
  ...props
}) => {
  if (count <= 0) {
    return null;
  }

  return (
    <Badge
      variant={variant}
      className={cn('ml-1 h-5 min-w-5 px-1.5 text-[11px]', className)}
      {...props}
    >
      {count}
    </Badge>
  );
};

