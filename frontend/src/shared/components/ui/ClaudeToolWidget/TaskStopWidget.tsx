/**
 * TaskStopWidget - 停止任務
 */
import React from 'react';
import { StopCircle, Terminal } from 'lucide-react';
import { WidgetProps } from './types';
import { ErrorDisplay } from './ErrorDisplay';

export const TaskStopWidget: React.FC<WidgetProps> = ({ input, output, error, status }) => {
  const taskId = input?.task_id || '';
  const content = typeof output === 'string' ? output : '';

  // 嘗試解析 JSON output
  const parsed = React.useMemo(() => {
    try {
      return JSON.parse(content);
    } catch {
      return null;
    }
  }, [content]);

  const message = parsed?.message || content;
  const taskType = parsed?.task_type;
  const command = parsed?.command;

  if (error) {
    return <ErrorDisplay error={error} />;
  }

  if (status === 'in_progress') {
    return null;
  }

  return (
    <div className="bg-white dark:bg-zinc-900">
      <div className="p-3 space-y-2">
        {/* 停止狀態 */}
        <div className="flex items-center gap-2">
          <div className="flex items-center justify-center h-6 w-6 rounded bg-red-50 dark:bg-red-950/30 flex-shrink-0">
            <StopCircle className="h-3.5 w-3.5 text-red-500" />
          </div>
          <code className="text-xs font-mono bg-gray-100 dark:bg-zinc-800 text-gray-700 dark:text-zinc-300 px-1.5 py-0.5 rounded">
            {taskId}
          </code>
          {taskType && (
            <span className="text-xs text-gray-500 dark:text-zinc-400">{taskType}</span>
          )}
        </div>

        {/* 指令 */}
        {command && (
          <div className="flex items-center gap-1.5 text-xs">
            <Terminal className="h-3 w-3 text-gray-400 flex-shrink-0" />
            <code className="font-mono text-gray-600 dark:text-zinc-300 truncate">{command}</code>
          </div>
        )}

        {/* 結果訊息 */}
        {message && (
          <p className="text-xs text-gray-600 dark:text-zinc-300">{message}</p>
        )}
      </div>
    </div>
  );
};

export default TaskStopWidget;
