import React from 'react';
import { AlertCircle, CheckCircle, Info, X } from 'lucide-react';
import { cn } from '@/shared/utils/cn';
import { Button } from './button';

export type ToastVariant = 'default' | 'destructive' | 'success' | 'info';

export interface ToastProps {
  id: string;
  title?: string;
  description?: string;
  variant?: ToastVariant;
  onClose: (id: string) => void;
}

const variantStyles: Record<ToastVariant, string> = {
  default: 'bg-background text-foreground border-border',
  destructive: 'bg-red-50 text-red-800 border-red-200 dark:bg-red-900 dark:text-red-200 dark:border-red-800',
  success: 'bg-green-50 text-green-800 border-green-200 dark:bg-green-900 dark:text-green-200 dark:border-green-800',
  info: 'bg-blue-50 text-blue-800 border-blue-200 dark:bg-blue-900 dark:text-blue-200 dark:border-blue-800',
};

const getIcon = (variant: ToastVariant) => {
  switch (variant) {
    case 'destructive':
      return <AlertCircle className="h-4 w-4" />;
    case 'success':
      return <CheckCircle className="h-4 w-4" />;
    case 'info':
      return <Info className="h-4 w-4" />;
    default:
      return null;
  }
};

export const Toast: React.FC<ToastProps> = ({
  id,
  title,
  description,
  variant = 'default',
  onClose,
}) => {
  const icon = getIcon(variant);

  return (
    <div
      className={cn(
        'pointer-events-auto flex w-full max-w-md items-start gap-3 rounded-lg border p-4 shadow-lg',
        'animate-in slide-in-from-right-full duration-300',
        variantStyles[variant]
      )}
    >
      {icon && <div className="mt-0.5">{icon}</div>}
      <div className="flex-1 space-y-1">
        {title && <div className="text-sm font-semibold leading-5">{title}</div>}
        {description && <div className="text-sm">{description}</div>}
      </div>
      <Button
        variant="ghost"
        size="sm"
        className="h-6 w-6 p-0"
        onClick={() => onClose(id)}
      >
        <X className="h-3 w-3" />
      </Button>
    </div>
  );
};