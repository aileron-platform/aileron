/**
 * CronDeleteWidget - 刪除排程任務
 */
import React from 'react';
import { Trash2, Clock } from 'lucide-react';
import { WidgetProps } from './types';
import { ErrorDisplay } from './ErrorDisplay';

export const CronDeleteWidget: React.FC<WidgetProps> = ({ input, output, error, status }) => {
  const jobId = input?.id || '';
  const content = typeof output === 'string' ? output : '';

  if (error) {
    return <ErrorDisplay error={error} />;
  }

  if (status === 'in_progress') {
    return null;
  }

  return (
    <div className="bg-white dark:bg-zinc-900">
      <div className="p-3 flex items-center gap-2">
        <div className="flex items-center justify-center h-6 w-6 rounded bg-red-50 dark:bg-red-950/30 flex-shrink-0">
          <Trash2 className="h-3.5 w-3.5 text-red-500" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-xs text-gray-500 dark:text-zinc-400">排程</span>
            <code className="text-xs font-mono bg-gray-100 dark:bg-zinc-800 text-gray-700 dark:text-zinc-300 px-1.5 py-0.5 rounded">
              {jobId}
            </code>
          </div>
          {content && (
            <p className="text-xs text-gray-600 dark:text-zinc-300 mt-1">{content}</p>
          )}
        </div>
      </div>
    </div>
  );
};

export default CronDeleteWidget;
