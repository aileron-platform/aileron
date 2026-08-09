import * as React from 'react';

export interface SwitchProps extends Omit<React.ButtonHTMLAttributes<HTMLButtonElement>, 'onChange'> {
  checked?: boolean;
  onCheckedChange?: (checked: boolean) => void;
  disabled?: boolean;
}

export const Switch = React.forwardRef<HTMLButtonElement, SwitchProps>(
  ({ checked = false, onCheckedChange, disabled = false, className = '', ...props }, ref) => {
    const handleClick = (e: React.MouseEvent<HTMLButtonElement>) => {
      if (disabled) return;
      onCheckedChange?.(!checked);
      props.onClick?.(e);
    };

    const base = 'relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2';
    const state = checked ? 'bg-primary' : 'bg-muted';
    const disabledCls = disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer';

    return (
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        aria-disabled={disabled}
        data-state={checked ? 'checked' : 'unchecked'}
        onClick={handleClick}
        ref={ref}
        className={[base, state, disabledCls, className].filter(Boolean).join(' ')}
        {...props}
      >
        <span
          className={[
            'inline-block h-5 w-5 transform rounded-full bg-background shadow transition-transform',
            checked ? 'translate-x-6' : 'translate-x-1',
          ].join(' ')}
        />
      </button>
    );
  }
);

Switch.displayName = 'Switch';
