/**
 * TaskWidget - 代理任務
 */
import React from 'react';
import { Bot, Maximize2 } from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '../dialog';
import { WidgetProps } from './types';
import { ErrorDisplay } from './ErrorDisplay';

export const TaskWidget: React.FC<WidgetProps> = ({ input, output, error, status }) => {
  const [showFullscreen, setShowFullscreen] = React.useState(false);
  const description = input?.description || input?.prompt || '';
  const content = typeof output === 'string' ? output : '';
  const lines = content.split('\n');
  const PREVIEW_LINES = 10;

  if (status === 'in_progress') {
    return null;
  }

  return (
    <>
      <div className="bg-white dark:bg-zinc-900">
        {/* 任務描述 */}
        <div className="p-3 border-b border-gray-100 dark:border-zinc-800">
          <div className="text-xs font-medium text-gray-500 dark:text-zinc-400 mb-1">任務描述:</div>
          <div className="text-xs text-gray-900 dark:text-zinc-100">{description}</div>
        </div>

        {/* 結果 */}
        {error ? (
          <ErrorDisplay error={error} />
        ) : content && (
          <>
            <div className="p-3 max-h-64 overflow-y-auto">
              <div className="text-xs font-medium text-gray-500 dark:text-zinc-400 mb-2">✓ 結果:</div>
              <div className="text-xs prose prose-sm dark:prose-invert max-w-none whitespace-pre-wrap text-gray-900 dark:text-zinc-100">
                {lines.slice(0, PREVIEW_LINES).join('\n')}
              </div>
            </div>
            {lines.length > PREVIEW_LINES && (
              <div className="px-3 py-1.5 bg-gray-100/50 dark:bg-zinc-800/50 border-t border-gray-200 dark:border-zinc-700 text-center">
                <button
                  onClick={() => setShowFullscreen(true)}
                  className="text-xs text-blue-600 hover:text-blue-700 dark:text-blue-400 dark:hover:text-blue-300 inline-flex items-center gap-1"
                >
                  <Maximize2 className="h-3 w-3" />
                  查看完整內容 ({lines.length} 行)
                </button>
              </div>
            )}
          </>
        )}
      </div>

      {/* 全螢幕對話框 */}
      <Dialog open={showFullscreen} onOpenChange={setShowFullscreen}>
        <DialogContent className="max-w-4xl max-h-[80vh] overflow-hidden flex flex-col">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 font-mono text-sm">
              <Bot className="h-4 w-4" />
              {description}
            </DialogTitle>
          </DialogHeader>
          <div className="flex-1 overflow-auto p-4 bg-gray-50 dark:bg-zinc-900 rounded">
            <div className="text-xs prose prose-sm dark:prose-invert max-w-none whitespace-pre-wrap text-gray-900 dark:text-zinc-100">
              {content}
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
};

export default TaskWidget;
