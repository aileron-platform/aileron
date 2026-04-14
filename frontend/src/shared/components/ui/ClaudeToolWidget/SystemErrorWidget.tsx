/**
 * SystemErrorWidget - 系統錯誤顯示組件
 *
 * 當 Claude SDK 執行失敗時顯示錯誤訊息
 */

import React from 'react';
import { AlertCircle, X } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import { cn } from '@/shared/utils/cn';

export interface SystemErrorWidgetProps {
  /** 錯誤訊息 */
  error?: string;
  /** 錯誤代碼 */
  code?: string;
  /** 是否可折疊 */
  collapsible?: boolean;
  /** 預設是否展開 */
  defaultExpanded?: boolean;
}

export const SystemErrorWidget: React.FC<SystemErrorWidgetProps> = ({
  error,
  code,
  collapsible = true,
  defaultExpanded = true,
}) => {
  const [isExpanded, setIsExpanded] = React.useState(defaultExpanded);

  if (!error && !code) {
    return null;
  }

  return (
    <div className="bg-destructive/10 border border-destructive/30 rounded-lg overflow-hidden">
      {/* Header */}
      <div
        className={cn(
          'flex items-center justify-between px-3 py-2 bg-destructive/5 cursor-pointer select-none',
          !collapsible && 'cursor-default'
        )}
        onClick={() => collapsible && setIsExpanded(!isExpanded)}
      >
        <div className="flex items-center gap-2">
          <AlertCircle className="h-4 w-4 text-destructive flex-shrink-0" />
          <span className="text-sm font-medium text-destructive">
            執行失敗
          </span>
          {code && (
            <code className="text-xs bg-destructive/20 text-destructive/80 px-1.5 py-0.5 rounded">
              {code}
            </code>
          )}
        </div>
        {collapsible && (
          <Button
            variant="ghost"
            size="icon"
            className="h-5 w-5 text-destructive/70 hover:text-destructive"
            onClick={(e) => {
              e.stopPropagation();
              setIsExpanded(!isExpanded);
            }}
          >
            {isExpanded ? (
              <X className="h-3.5 w-3.5" />
            ) : (
              <AlertCircle className="h-3.5 w-3.5" />
            )}
          </Button>
        )}
      </div>

      {/* Content */}
      {(isExpanded || !collapsible) && (
        <div className="px-3 py-2 border-t border-destructive/20">
          <div className="text-sm text-destructive/90 whitespace-pre-wrap break-words font-mono">
            {error}
          </div>
        </div>
      )}
    </div>
  );
};

export default SystemErrorWidget;
