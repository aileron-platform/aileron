/**
 * FeatureHeader - 統一的功能區域標題列組件
 * 提供一致的視覺設計和工具列支援
 */

import React from 'react';
import { LucideIcon } from 'lucide-react';
import { cn } from '../../utils/cn';

export interface FeatureHeaderProps {
  /** 功能標題 */
  title: string;
  /** 功能圖示 */
  icon: LucideIcon;
  /** 工具按鈕組 */
  actions?: React.ReactNode;
  /** 額外資訊顯示 */
  info?: React.ReactNode;
  /** 自定義樣式 */
  className?: string;
  /** 是否收折（隱藏標題和圖示，只顯示 actions） */
  isCollapsed?: boolean;
}

export const FeatureHeader: React.FC<FeatureHeaderProps> = ({
  title,
  icon: Icon,
  actions,
  info,
  className,
  isCollapsed = false,
}) => {
  return (
    <div className={cn(
      "h-10 px-3 border-b border-border bg-card flex items-center",
      isCollapsed ? "justify-center" : "justify-between",
      className
    )}>
      {/* 左側：標題區域（收折時隱藏） */}
      {!isCollapsed && (
        <div className="flex items-center gap-2 min-w-0 flex-1">
          <Icon className="h-4 w-4 text-primary flex-shrink-0" />
          <h2 className="text-sm font-medium text-foreground flex-shrink-0">{title}</h2>

          {/* 額外資訊 */}
          {info && (
            <div className="min-w-0 flex-1">
              {info}
            </div>
          )}
        </div>
      )}

      {/* 右側：工具按鈕區域 */}
      {actions && (
        <div className="flex items-center gap-1.5 flex-shrink-0">
          {actions}
        </div>
      )}
    </div>
  );
};

export default FeatureHeader;
