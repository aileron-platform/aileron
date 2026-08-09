import * as React from 'react';

export interface SeparatorProps extends React.HTMLAttributes<HTMLDivElement> {
  orientation?: 'horizontal' | 'vertical';
}

export const Separator = React.forwardRef<HTMLDivElement, SeparatorProps>(
  ({ className = '', orientation = 'horizontal', role = 'separator', ...props }, ref) => {
    const isVertical = orientation === 'vertical';
    const base = isVertical ? 'w-px h-full' : 'h-px w-full';
    const color = 'bg-border';

    return (
      <div
        ref={ref}
        role={role}
        aria-orientation={orientation}
        className={[base, color, className].filter(Boolean).join(' ')}
        {...props}
      />
    );
  }
);

Separator.displayName = 'Separator';
