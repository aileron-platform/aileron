/**
 * CronCreateWidget - 建立排程任務
 */
import React from 'react';
import { Clock, Repeat, ArrowRight } from 'lucide-react';
import { cn } from '@/shared/utils/cn';
import { WidgetProps } from './types';
import { ErrorDisplay } from './ErrorDisplay';

export const CronCreateWidget: React.FC<WidgetProps> = ({ input, output, error, status }) => {
  const cronExpr = input?.cron || '';
  const prompt = input?.prompt || '';
  const recurring = input?.recurring ?? false;
  const content = typeof output === 'string' ? output : '';

  // 嘗試從 output 中提取 task ID
  const taskIdMatch = content.match(/task\s+([a-f0-9]+)/i);
  const taskId = taskIdMatch?.[1];

  if (error) {
    return <ErrorDisplay error={error} />;
  }

  if (status === 'in_progress') {
    return null;
  }

  return (
    <div className="bg-white dark:bg-zinc-900">
      {/* 排程資訊 */}
      <div className="p-3 space-y-2">
        {/* Cron 表達式 */}
        <div className="flex items-center gap-2">
          <Clock className="h-3.5 w-3.5 text-blue-500 flex-shrink-0" />
          <code className="text-xs font-mono bg-blue-50 dark:bg-blue-950/30 text-blue-700 dark:text-blue-300 px-1.5 py-0.5 rounded">
            {cronExpr}
          </code>
          <span className={cn(
            'text-xs px-1.5 py-0.5 rounded',
            recurring
              ? 'bg-purple-50 dark:bg-purple-950/30 text-purple-600 dark:text-purple-400'
              : 'bg-gray-100 dark:bg-zinc-800 text-gray-600 dark:text-zinc-400'
          )}>
            {recurring ? (
              <span className="inline-flex items-center gap-0.5">
                <Repeat className="h-3 w-3" /> 循環
              </span>
            ) : '單次'}
          </span>
        </div>

        {/* 提示內容 */}
        {prompt && (
          <div className="flex items-start gap-2">
            <ArrowRight className="h-3.5 w-3.5 text-gray-400 mt-0.5 flex-shrink-0" />
            <p className="text-xs text-gray-700 dark:text-zinc-200">{prompt}</p>
          </div>
        )}

        {/* 結果 */}
        {content && (
          <div className="text-xs text-gray-500 dark:text-zinc-400 border-t border-gray-100 dark:border-zinc-800 pt-2">
            {taskId && (
              <span className="font-mono text-green-600 dark:text-green-400 mr-1">✓ {taskId}</span>
            )}
            {content}
          </div>
        )}
      </div>
    </div>
  );
};

export default CronCreateWidget;
