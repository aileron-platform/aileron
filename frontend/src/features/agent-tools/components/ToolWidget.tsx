import * as React from 'react';
import { cn } from '@/shared/utils/cn';
import { Terminal, ChevronDown, ChevronRight, Maximize2 } from 'lucide-react';
import { useI18n } from '@/shared/hooks/useI18n';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/shared/components/ui/dialog';

export interface ToolWidgetProps {
  title?: string;
  showStatus?: boolean;
  statusColor?: 'green' | 'yellow' | 'red';
  dark?: boolean;
  children?: React.ReactNode;
  className?: string;
  collapsible?: boolean;
  defaultExpanded?: boolean;
  commandPreview?: string;
  maxContentHeight?: number;
  enableMore?: boolean;
}

/**
 * ToolWidget - terminal-style tool display component.
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
    const { t } = useI18n();
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
                  <span className={cn('text-xs ml-1', dark ? 'text-zinc-400' : 'text-gray-500')}>
                    {t('workspace.chat.widgets.toolWidget.more')}
                  </span>
                </div>
              )}
            </div>
          )}
        </div>

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
 * ToolWidgetHeader - tool widget header.
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
      {collapsible && (
        <div className="flex-shrink-0">
          {isExpanded ? (
            <ChevronDown className={cn('w-4 h-4', dark ? 'text-zinc-400' : 'text-gray-500')} />
          ) : (
            <ChevronRight className={cn('w-4 h-4', dark ? 'text-zinc-400' : 'text-gray-500')} />
          )}
        </div>
      )}

      <Terminal className="w-4 h-4 flex-shrink-0" />

      <span className="font-semibold text-sm flex-shrink-0">{title}</span>

      <span className="text-zinc-500 text-xs flex-shrink-0">$</span>

      {!isExpanded && commandPreview && (
        <span className={cn('text-xs truncate flex-1 min-w-0', dark ? 'text-zinc-400' : 'text-gray-500')}>
          {truncateText(commandPreview)}
        </span>
      )}

      {(isExpanded || !commandPreview) && <div className="flex-1" />}

      {showStatus && (
        <div className={cn('w-2 h-2 rounded-full flex-shrink-0', statusColorMap[statusColor])} />
      )}
    </div>
  );
};

/**
 * ToolWidgetCommand - command display area.
 */
interface ToolWidgetCommandProps {
  children: React.ReactNode;
  className?: string;
  dark?: boolean;
}

const ToolWidgetCommand: React.FC<ToolWidgetCommandProps> = ({ children, className, dark = false }) => {
  const { t } = useI18n();
  return (
    <div className={cn('mb-4', className)}>
      <div className={cn('text-xs font-semibold mb-2', dark ? 'text-zinc-400' : 'text-gray-600')}>
        {t('workspace.chat.widgets.toolWidget.command')}
      </div>
      <div className={cn('whitespace-pre-wrap break-all', dark ? 'text-zinc-300' : 'text-gray-700')}>
        {children}
      </div>
    </div>
  );
};

/**
 * ToolWidgetOutput - output display area.
 */
interface ToolWidgetOutputProps {
  children: React.ReactNode;
  className?: string;
  dark?: boolean;
}

const ToolWidgetOutput: React.FC<ToolWidgetOutputProps> = ({ children, className, dark = false }) => {
  const { t } = useI18n();
  return (
    <div className={className}>
      <div className={cn('text-xs font-semibold mb-2', dark ? 'text-zinc-400' : 'text-gray-600')}>
        {t('workspace.chat.widgets.toolWidget.output')}
      </div>
      <div className={cn('whitespace-pre-wrap break-all', dark ? 'text-zinc-300' : 'text-gray-700')}>
        {children}
      </div>
    </div>
  );
};

/**
 * ToolWidgetSection - custom section.
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

ToolWidget.Command = ToolWidgetCommand;
ToolWidget.Output = ToolWidgetOutput;
ToolWidget.Section = ToolWidgetSection;

export default ToolWidget;
