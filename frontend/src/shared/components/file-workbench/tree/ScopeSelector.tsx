/**
 * 
 */

import React from 'react';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/shared/components/ui/select';
import { cn } from '@/shared/utils/cn';

export interface ScopeOption {
  value: string;
  
  label: string;
  
  icon?: React.ReactNode;
  
  disabled?: boolean;
}

export interface ScopeSelectorProps {
  value: string;
  
  onChange: (value: string) => void;
  
  options: ScopeOption[];
  
  label?: string;
  
  width?: string | number;
  
  disabled?: boolean;
  
  className?: string;
}

export const ScopeSelector: React.FC<ScopeSelectorProps> = ({
  value,
  onChange,
  options,
  label,
  width = 160,
  disabled = false,
  className,
}) => {
  const widthStyle = typeof width === 'number' ? `${width}px` : width;

  return (
    <div className={cn('flex items-center gap-2', className)}>
      {label && (
        <span className="text-xs text-muted-foreground whitespace-nowrap">
          {label}
        </span>
      )}
      <Select value={value} onValueChange={onChange} disabled={disabled}>
        <SelectTrigger className="h-7 text-xs" style={{ width: widthStyle }}>
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {options.map((option) => (
            <SelectItem
              key={option.value}
              value={option.value}
              disabled={option.disabled}
            >
              <div className="flex items-center gap-2">
                {option.icon}
                <span>{option.label}</span>
              </div>
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
};
