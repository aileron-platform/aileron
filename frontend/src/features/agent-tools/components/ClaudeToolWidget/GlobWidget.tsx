import { DialogHeading } from '@/shared/components/ui/dialog-heading';
/**
 * GlobWidget - file search display.
 */
import React from 'react';
import { FolderSearch, Maximize2, Folder, FileText } from 'lucide-react';
import { cn } from '@/shared/utils/cn';
import { useI18n } from '@/shared/hooks/useI18n';
import { Dialog, DialogContent, DialogHeader } from '@/shared/components/ui/dialog';
import { WidgetProps } from './types';
import { ErrorDisplay } from './ErrorDisplay';

export const GlobWidget: React.FC<WidgetProps> = ({ input, output, error, status }) => {
  const { t } = useI18n();
  const [showFullscreen, setShowFullscreen] = React.useState(false);
  const pattern = input?.pattern || '';
  const content = typeof output === 'string' ? output : '';
  const files = content.split('\n').filter(line => line.trim());
  const PREVIEW_COUNT = 15;

  if (error) {
    return <ErrorDisplay error={error} />;
  }

  if (status === 'in_progress') {
    return null;
  }

  const getFileIcon = (file: string) => {
    if (file.endsWith('/')) return <Folder className="h-3.5 w-3.5 text-blue-500" />;
    const ext = file.split('.').pop()?.toLowerCase();
    const colors: Record<string, string> = {
      ts: 'text-blue-500', tsx: 'text-blue-500',
      js: 'text-yellow-500', jsx: 'text-yellow-500',
      py: 'text-green-500', md: 'text-gray-500',
      json: 'text-yellow-600', yaml: 'text-orange-500',
    };
    return <FileText className={cn('h-3.5 w-3.5', colors[ext || ''] || 'text-gray-400')} />;
  };

  const renderFileList = (fileList: string[], limit?: number) => {
    const displayFiles = limit ? fileList.slice(0, limit) : fileList;
    return (
      <div className="space-y-1">
        {displayFiles.map((file, index) => (
          <div
            key={index}
            className="flex items-center gap-2 py-1 px-2 rounded hover:bg-gray-50 dark:hover:bg-zinc-800 transition-colors"
          >
            {getFileIcon(file)}
            <span className="text-xs font-mono text-gray-900 dark:text-zinc-100">{file}</span>
          </div>
        ))}
      </div>
    );
  };

  return (
    <>
      <div className="bg-white dark:bg-zinc-900 p-3">
        <div className="max-h-48 overflow-y-auto">
          {files.length > 0 ? (
            renderFileList(files, PREVIEW_COUNT)
          ) : (
            <div className="text-xs text-gray-500 dark:text-zinc-400 text-center py-4">
              {t('workspace.chat.widgets.agentTools.noMatchingFiles')}
            </div>
          )}
        </div>
        {files.length > PREVIEW_COUNT && (
          <div className="pt-2 mt-2 border-t border-gray-200 dark:border-zinc-700 text-center">
            <button
              onClick={() => setShowFullscreen(true)}
              className="text-xs text-blue-600 hover:text-blue-700 dark:text-blue-400 dark:hover:text-blue-300 inline-flex items-center gap-1"
            >
              <Maximize2 className="h-3 w-3" />
              {t('workspace.chat.widgets.agentTools.viewFullContentFiles', { count: files.length })}
            </button>
          </div>
        )}
      </div>

      <Dialog open={showFullscreen} onOpenChange={setShowFullscreen}>
        <DialogContent className="max-w-4xl max-h-[80vh] overflow-hidden flex flex-col">
          <DialogHeader>
            <DialogHeading icon={FolderSearch} className="font-mono text-sm" iconClassName="h-4 w-4">
              {pattern}
            </DialogHeading>
          </DialogHeader>
          <div className="flex-1 overflow-auto p-4 bg-gray-50 dark:bg-zinc-900 rounded">
            {renderFileList(files)}
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
};

export default GlobWidget;
