/**
 * TodoWriteWidget - 任務列表（緊湊設計）
 */
import React from 'react';
import { CheckCircle2, Clock, Circle } from 'lucide-react';
import { cn } from '@/shared/utils/cn';
import { WidgetProps } from './types';

export const TodoWriteWidget: React.FC<WidgetProps> = ({ input }) => {
  const todos = input?.todos || [];

  const statusIcons: Record<string, React.ReactNode> = {
    completed: <CheckCircle2 className="h-3.5 w-3.5 text-green-500 flex-shrink-0" />,
    in_progress: <Clock className="h-3.5 w-3.5 text-blue-500 animate-pulse flex-shrink-0" />,
    pending: <Circle className="h-3.5 w-3.5 text-gray-400 flex-shrink-0" />,
  };

  return (
    <div className="bg-white dark:bg-zinc-900 divide-y divide-gray-100 dark:divide-zinc-800">
      {todos.map((todo: any, idx: number) => (
        <div
          key={todo.id || idx}
          className={cn(
            'flex items-center gap-1.5 px-2 py-1',
            todo.status === 'completed' && 'opacity-60',
            todo.status === 'in_progress' && 'bg-blue-50/50 dark:bg-blue-950/30'
          )}
        >
          {statusIcons[todo.status] || statusIcons.pending}
          <span className={cn(
            'flex-1 text-xs truncate text-gray-900 dark:text-zinc-100',
            todo.status === 'completed' && 'line-through text-gray-500 dark:text-zinc-500',
            todo.status === 'in_progress' && 'text-blue-700 dark:text-blue-400 font-medium'
          )}>
            {/* 進行中顯示 activeForm，其他狀態顯示 content */}
            {todo.status === 'in_progress' && todo.activeForm
              ? todo.activeForm
              : todo.content}
          </span>
        </div>
      ))}
      {todos.length === 0 && (
        <div className="text-xs text-gray-500 dark:text-zinc-400 text-center py-2">
          沒有任務
        </div>
      )}
    </div>
  );
};

export default TodoWriteWidget;
