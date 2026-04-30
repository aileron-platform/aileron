/**
 * WriteWidget - file write display.
 */
import React from 'react';
import { FilePlus, Maximize2 } from 'lucide-react';
import { useI18n } from '@/shared/hooks/useI18n';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/shared/components/ui/dialog';
import { WidgetProps } from './types';
import { ErrorDisplay } from './ErrorDisplay';

export const WriteWidget: React.FC<WidgetProps> = ({ input, output, error, status }) => {
  const { t } = useI18n();
  const [showFullscreen, setShowFullscreen] = React.useState(false);
  const filePath = input?.file_path || '';
  const content = input?.content || '';
  const lines = content.split('\n');
  const PREVIEW_LINES = 10;

  if (error) {
    return <ErrorDisplay error={error} />;
  }

  if (status === 'in_progress') {
    return null;
  }

  return (
    <>
      <div className="bg-gray-50 dark:bg-zinc-900 overflow-hidden">
        <div className="overflow-x-auto max-h-48">
          <table className="w-full text-xs font-mono">
            <tbody>
              {lines.slice(0, PREVIEW_LINES).map((line, index) => (
                <tr key={index} className="hover:bg-gray-100/50 dark:hover:bg-zinc-800/50">
                  <td className="px-3 py-0.5 text-right text-gray-400 dark:text-zinc-500 select-none border-r border-gray-200 dark:border-zinc-700 w-12">
                    {index + 1}
                  </td>
                  <td className="px-3 py-0.5 whitespace-pre text-green-700 dark:text-green-400">{line || ' '}</td>
                </tr>
              ))}
            </tbody>
          </table>
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
              <FilePlus className="h-4 w-4" />
              {filePath}
            </DialogTitle>
          </DialogHeader>
          <div className="flex-1 overflow-auto bg-gray-50 dark:bg-zinc-900 rounded">
            <table className="w-full text-xs font-mono">
              <tbody>
                {lines.map((line, index) => (
                  <tr key={index} className="hover:bg-gray-100/50 dark:hover:bg-zinc-800/50">
                    <td className="px-3 py-0.5 text-right text-gray-400 dark:text-zinc-500 select-none border-r border-gray-200 dark:border-zinc-700 w-12">
                      {index + 1}
                    </td>
                    <td className="px-3 py-0.5 whitespace-pre text-green-700 dark:text-green-400">{line || ' '}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
};

export default WriteWidget;
