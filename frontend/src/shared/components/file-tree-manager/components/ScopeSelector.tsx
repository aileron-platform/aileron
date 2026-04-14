/**
 * 通用的 Scope 選擇器組件
 * 
 * 用於選擇不同的作用域（如 Project、User、Plugin）
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
  /** 選項值 */
  value: string;
  
  /** 顯示標籤 */
  label: string;
  
  /** 圖標（可選） */
  icon?: React.ReactNode;
  
  /** 是否禁用 */
  disabled?: boolean;
}

export interface ScopeSelectorProps {
  /** 當前選中的值 */
  value: string;
  
  /** 值變更回調 */
  onChange: (value: string) => void;
  
  /** 選項列表 */
  options: ScopeOption[];
  
  /** 標籤文字（如 "Scope:"） */
  label?: string;
  
  /** 選擇器寬度 */
  width?: string | number;
  
  /** 是否禁用 */
  disabled?: boolean;
  
  /** 自定義 className */
  className?: string;
}

export const ScopeSelector: React.FC<ScopeSelectorProps> = ({
  value,
  onChange,
  options,
  label,
  width = 120,
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

export default ScopeSelector;

