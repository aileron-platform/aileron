import * as React from 'react';
import { cn } from '@/shared/utils/cn';
import { Terminal, ChevronDown, ChevronRight, Maximize2 } from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from './dialog';

export interface ToolWidgetProps {
  /**
   * 工具名稱（顯示在標題欄）
   */
  title?: string;
  /**
   * 是否顯示執行狀態指示器
   */
  showStatus?: boolean;
  /**
   * 狀態指示器顏色
   */
  statusColor?: 'green' | 'yellow' | 'red';
  /**
   * 是否為深色模式
   */
  dark?: boolean;
  /**
   * 子元件
   */
  children?: React.ReactNode;
  /**
   * 自訂樣式類名
   */
  className?: string;
  /**
   * 是否可收折
   */
  collapsible?: boolean;
  /**
   * 預設是否展開
   */
  defaultExpanded?: boolean;
  /**
   * 收折時顯示的命令預覽文字
   */
  commandPreview?: string;
  /**
   * 展開後內容區域的最大高度（px）
   */
  maxContentHeight?: number;
  /**
   * 是否啟用 "more" 功能顯示完整內容
   */
  enableMore?: boolean;
}

/**
 * ToolWidget - 終端風格的工具展示元件
 *
 * @example
 * ```tsx
 * <ToolWidget
 *   title="Terminal"
 *   showStatus
 *   statusColor="green"
 *   collapsible
 *   commandPreview="cat workspace-runtime/complete_claude_tools_test_final.json | jq '.items[]'"
 * >
 *   <ToolWidget.Command>
 *     cat workspace-runtime/complete_claude_tools_test_final.json | jq '.items[]'
 *   </ToolWidget.Command>
 *   <ToolWidget.Output>
 *     0
 *   </ToolWidget.Output>
 * </ToolWidget>
 * ```
 */
export const ToolWidget = React.forwardRef<HTMLDivElement, ToolWidgetProps>(
  ({
    title = 'Terminal',
    showStatus = true,
    statusColor = 'green',
    dark = false,
    children,
    className,
    collapsible = false,
    defaultExpanded = true,
    commandPreview = '',
    maxContentHeight = 200,
    enableMore = false
  }, ref) => {
    const [isExpanded, setIsExpanded] = React.useState(defaultExpanded);
    const [showModal, setShowModal] = React.useState(false);
    const [isOverflowing, setIsOverflowing] = React.useState(false);
    const contentRef = React.useRef<HTMLDivElement>(null);

    const bgColor = dark ? 'bg-zinc-900' : 'bg-white';
    const borderColor = dark ? 'border-zinc-800' : 'border-zinc-200';
    const textColor = dark ? 'text-zinc-100' : 'text-zinc-900';

    const handleToggle = () => {
      if (collapsible) {
        setIsExpanded(!isExpanded);
      }
    };

    const handleShowMore = () => {
      setShowModal(true);
    };

    // 檢查內容是否超出高度限制
    React.useEffect(() => {
      if (isExpanded && enableMore && contentRef.current) {
        const element = contentRef.current;
        const isContentOverflowing = element.scrollHeight > maxContentHeight;
        setIsOverflowing(isContentOverflowing);
      }
    }, [isExpanded, enableMore, maxContentHeight, children]);

    return (
      <>
        <div
          ref={ref}
          className={cn(
            'rounded-lg border overflow-hidden font-mono text-sm',
            bgColor,
            borderColor,
            textColor,
            className
          )}
        >
          {/* 標題欄 */}
          <ToolWidgetHeader
            title={title}
            showStatus={showStatus}
            statusColor={statusColor}
            dark={dark}
            collapsible={collapsible}
            isExpanded={isExpanded}
            onToggle={handleToggle}
            commandPreview={commandPreview}
          />

          {/* 內容區域 */}
          {isExpanded && (
            <div className="relative">
              <div
                ref={contentRef}
                className={cn(
                  'p-4',
                  enableMore && 'overflow-hidden'
                )}
                style={enableMore ? { maxHeight: `${maxContentHeight}px` } : undefined}
              >
                {children}
              </div>

              {/* More 按鈕 */}
              {enableMore && isOverflowing && (
                <div className={cn(
                  'flex justify-center items-center py-2 border-t cursor-pointer transition-colors',
                  dark
                    ? 'border-zinc-700 bg-zinc-800/30 hover:bg-zinc-800/50'
                    : 'border-gray-200 bg-gray-50 hover:bg-gray-100'
                )}
                onClick={handleShowMore}
                >
                  <ChevronDown className={cn('w-4 h-4', dark ? 'text-zinc-400' : 'text-gray-500')} />
                  <span className={cn('text-xs ml-1', dark ? 'text-zinc-400' : 'text-gray-500')}>more</span>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Modal 顯示完整內容 */}
        {enableMore && (
          <Dialog open={showModal} onOpenChange={setShowModal}>
            <DialogContent className={cn(
              'max-w-4xl max-h-[80vh] overflow-hidden flex flex-col',
              dark ? 'bg-zinc-900 border-zinc-800 text-zinc-100' : 'bg-white'
            )}>
              <DialogHeader>
                <DialogTitle className="flex items-center gap-2 font-mono">
                  <Terminal className="w-4 h-4" />
                  {title}
                  {showStatus && (
                    <div className={cn(
                      'w-2 h-2 rounded-full',
                      statusColor === 'green' && 'bg-emerald-500',
                      statusColor === 'yellow' && 'bg-yellow-500',
                      statusColor === 'red' && 'bg-red-500'
                    )} />
                  )}
                </DialogTitle>
              </DialogHeader>
              <div className={cn(
                'flex-1 overflow-y-auto font-mono text-sm p-4 rounded',
                dark ? 'bg-zinc-950' : 'bg-zinc-50'
              )}>
                {children}
              </div>
            </DialogContent>
          </Dialog>
        )}
      </>
    );
  }
);
ToolWidget.displayName = 'ToolWidget';

/**
 * ToolWidgetHeader - 工具 Widget 標題欄
 */
interface ToolWidgetHeaderProps {
  title: string;
  showStatus: boolean;
  statusColor: 'green' | 'yellow' | 'red';
  dark: boolean;
  collapsible: boolean;
  isExpanded: boolean;
  onToggle: () => void;
  commandPreview: string;
}

const ToolWidgetHeader: React.FC<ToolWidgetHeaderProps> = ({
  title,
  showStatus,
  statusColor,
  dark,
  collapsible,
  isExpanded,
  onToggle,
  commandPreview
}) => {
  const headerBg = dark ? 'bg-zinc-800/50' : 'bg-gray-100';
  const statusColorMap = {
    green: 'bg-emerald-500',
    yellow: 'bg-yellow-500',
    red: 'bg-red-500',
  };

  // 截斷命令預覽文字
  const truncateText = (text: string, maxLength: number = 60) => {
    if (!text) return '';
    return text.length > maxLength ? text.substring(0, maxLength) + '...' : text;
  };

  return (
    <div
      className={cn(
        'flex items-center gap-2 px-4 py-2 border-b',
        headerBg,
        dark ? 'border-zinc-700' : 'border-gray-200',
        collapsible && (dark ? 'cursor-pointer hover:bg-zinc-800/70 transition-colors' : 'cursor-pointer hover:bg-gray-200 transition-colors')
      )}
      onClick={onToggle}
    >
      {/* 收折圖標 */}
      {collapsible && (
        <div className="flex-shrink-0">
          {isExpanded ? (
            <ChevronDown className={cn('w-4 h-4', dark ? 'text-zinc-400' : 'text-gray-500')} />
          ) : (
            <ChevronRight className={cn('w-4 h-4', dark ? 'text-zinc-400' : 'text-gray-500')} />
          )}
        </div>
      )}

      {/* Terminal 圖標 */}
      <Terminal className="w-4 h-4 flex-shrink-0" />

      {/* 標題 */}
      <span className="font-semibold text-sm flex-shrink-0">{title}</span>

      {/* $ 符號 */}
      <span className="text-zinc-500 text-xs flex-shrink-0">$</span>

      {/* 命令預覽（收折時顯示） */}
      {!isExpanded && commandPreview && (
        <span className={cn('text-xs truncate flex-1 min-w-0', dark ? 'text-zinc-400' : 'text-gray-500')}>
          {truncateText(commandPreview)}
        </span>
      )}

      {/* 間隔 */}
      {(isExpanded || !commandPreview) && <div className="flex-1" />}

      {/* 狀態指示器 */}
      {showStatus && (
        <div className={cn('w-2 h-2 rounded-full flex-shrink-0', statusColorMap[statusColor])} />
      )}
    </div>
  );
};

/**
 * ToolWidgetCommand - 命令顯示區域
 */
interface ToolWidgetCommandProps {
  children: React.ReactNode;
  className?: string;
  dark?: boolean;
}

const ToolWidgetCommand: React.FC<ToolWidgetCommandProps> = ({ children, className, dark = false }) => {
  return (
    <div className={cn('mb-4', className)}>
      <div className={cn('text-xs font-semibold mb-2', dark ? 'text-zinc-400' : 'text-gray-600')}>Command</div>
      <div className={cn('whitespace-pre-wrap break-all', dark ? 'text-zinc-300' : 'text-gray-700')}>
        {children}
      </div>
    </div>
  );
};

/**
 * ToolWidgetOutput - 輸出顯示區域
 */
interface ToolWidgetOutputProps {
  children: React.ReactNode;
  className?: string;
  dark?: boolean;
}

const ToolWidgetOutput: React.FC<ToolWidgetOutputProps> = ({ children, className, dark = false }) => {
  return (
    <div className={className}>
      <div className={cn('text-xs font-semibold mb-2', dark ? 'text-zinc-400' : 'text-gray-600')}>Output</div>
      <div className={cn('whitespace-pre-wrap break-all', dark ? 'text-zinc-300' : 'text-gray-700')}>
        {children}
      </div>
    </div>
  );
};

/**
 * ToolWidgetSection - 自訂區塊
 */
interface ToolWidgetSectionProps {
  title?: string;
  children: React.ReactNode;
  className?: string;
  dark?: boolean;
}

const ToolWidgetSection: React.FC<ToolWidgetSectionProps> = ({ title, children, className, dark = false }) => {
  return (
    <div className={className}>
      {title && <div className={cn('text-xs font-semibold mb-2', dark ? 'text-zinc-400' : 'text-gray-600')}>{title}</div>}
      <div className={cn(dark ? 'text-zinc-300' : 'text-gray-700')}>
        {children}
      </div>
    </div>
  );
};

// 附加子元件到主元件
ToolWidget.Command = ToolWidgetCommand;
ToolWidget.Output = ToolWidgetOutput;
ToolWidget.Section = ToolWidgetSection;

export default ToolWidget;
