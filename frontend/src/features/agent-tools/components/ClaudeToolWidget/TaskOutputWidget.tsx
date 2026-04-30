/**
 * TaskOutputWidget - task output display.
 */
import React from 'react';
import { FileOutput, Maximize2 } from 'lucide-react';
import { cn } from '@/shared/utils/cn';
import { useI18n } from '@/shared/hooks/useI18n';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/shared/components/ui/dialog';
import { WidgetProps } from './types';
import { ErrorDisplay } from './ErrorDisplay';

/** Parse task status fields from XML-like output. */
function parseTaskOutputFields(content: string): Record<string, string> {
  const fields: Record<string, string> = {};
  const tagRegex = /<(\w+)>([\s\S]*?)<\/\1>/g;
  let match;
  while ((match = tagRegex.exec(content)) !== null) {
    fields[match[1]] = match[2].trim();
  }
  return fields;
}

const statusColors: Record<string, string> = {
  running: 'text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-950/30',
  completed: 'text-green-600 dark:text-green-400 bg-green-50 dark:bg-green-950/30',
  failed: 'text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-950/30',
  not_ready: 'text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-950/30',
};

export const TaskOutputWidget: React.FC<WidgetProps> = ({ input, output, error, status }) => {
  const { t } = useI18n();
  const [showFullscreen, setShowFullscreen] = React.useState(false);
  const taskId = input?.task_id || '';
  const blocking = input?.block ?? false;
  const timeout = input?.timeout;
  const content = typeof output === 'string' ? output : '';

  const fields = React.useMemo(() => parseTaskOutputFields(content), [content]);
  const hasFields = Object.keys(fields).length > 0;

  // Strip XML tags to get plain output content.
  const plainContent = content.replace(/<\/?[\w]+>/g, '').trim();
  const lines = plainContent.split('\n').filter(l => l.trim());
  const PREVIEW_LINES = 8;

  if (error) {
    return <ErrorDisplay error={error} />;
  }

  if (status === 'in_progress') {
    return null;
  }

  return (
    <>
      <div className="bg-white dark:bg-zinc-900">
        <div className="p-3 space-y-2">
          <div className="flex items-center gap-2 flex-wrap">
            <code className="text-xs font-mono bg-gray-100 dark:bg-zinc-800 text-gray-700 dark:text-zinc-300 px-1.5 py-0.5 rounded">
              {taskId}
            </code>
            {fields.status && (
              <span className={cn(
                'text-xs px-1.5 py-0.5 rounded font-medium',
                statusColors[fields.status] || 'text-gray-600 dark:text-zinc-400 bg-gray-100 dark:bg-zinc-800'
              )}>
                {fields.status}
              </span>
            )}
            {fields.task_type && (
              <span className="text-xs text-gray-500 dark:text-zinc-400">
                {fields.task_type}
              </span>
            )}
            {timeout && (
              <span className="text-xs text-gray-400 dark:text-zinc-500">
                timeout: {timeout}ms
              </span>
            )}
          </div>

          {!hasFields && lines.length > 0 && (
            <pre className="text-xs font-mono text-gray-700 dark:text-zinc-200 whitespace-pre-wrap bg-gray-50 dark:bg-zinc-800 p-2 rounded overflow-x-auto">
              {lines.slice(0, PREVIEW_LINES).join('\n')}
            </pre>
          )}
        </div>

        {lines.length > PREVIEW_LINES && (
          <div className="px-3 py-1.5 bg-gray-100/50 dark:bg-zinc-800/50 border-t border-gray-200 dark:border-zinc-700 text-center">
            <button
              onClick={() => setShowFullscreen(true)}
              className="text-xs text-blue-600 hover:text-blue-700 dark:text-blue-400 dark:hover:text-blue-300 inline-flex items-center gap-1"
            >
              <Maximize2 className="h-3 w-3" />
              {t('workspace.chat.widgets.agentTools.viewFullContent', { count: lines.length })}
            </button>
          </div>
        )}
      </div>

      <Dialog open={showFullscreen} onOpenChange={setShowFullscreen}>
        <DialogContent className="max-w-4xl max-h-[80vh] overflow-hidden flex flex-col">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 font-mono text-sm">
              <FileOutput className="h-4 w-4" />
              Task Output: {taskId}
            </DialogTitle>
          </DialogHeader>
          <div className="flex-1 overflow-auto p-4 bg-gray-50 dark:bg-zinc-900 rounded">
            <pre className="text-xs font-mono whitespace-pre-wrap text-gray-900 dark:text-zinc-100">
              {content}
            </pre>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
};

export default TaskOutputWidget;
