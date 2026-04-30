/**
 * GrepWidget - content search display.
 */
import React from 'react';
import { SearchCode, Maximize2, FileText } from 'lucide-react';
import { useI18n } from '@/shared/hooks/useI18n';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/shared/components/ui/dialog';
import { WidgetProps } from './types';
import { ErrorDisplay } from './ErrorDisplay';

export const GrepWidget: React.FC<WidgetProps> = ({ input, output, error, status }) => {
  const { t } = useI18n();
  const [showFullscreen, setShowFullscreen] = React.useState(false);
  const pattern = input?.pattern || '';
  const content = typeof output === 'string' ? output : '';
  const PREVIEW_COUNT = 10;

  // Parse grep results from file:line:content rows.
  const parseResults = () => {
    const lines = content.split('\n').filter(line => line.trim());
    return lines.map(line => {
      const match = line.match(/^(.+?):(\d+):(.*)$/);
      if (match) {
        return { file: match[1], line: parseInt(match[2], 10), content: match[3] };
      }
      return { file: '', line: 0, content: line };
    });
  };

  const matches = parseResults();

  if (error) {
    return <ErrorDisplay error={error} />;
  }

  if (status === 'in_progress') {
    return null;
  }

  const renderMatchList = (matchList: typeof matches, limit?: number) => {
    const displayMatches = limit ? matchList.slice(0, limit) : matchList;
    return (
      <div className="divide-y divide-gray-100 dark:divide-zinc-800">
        {displayMatches.map((match, index) => (
          <div key={index} className="p-3 hover:bg-gray-50 dark:hover:bg-zinc-800 transition-colors">
            <div className="flex items-center gap-2 mb-1">
              <FileText className="h-3.5 w-3.5 text-gray-400 dark:text-zinc-500" />
              <code className="text-xs font-mono text-blue-600 dark:text-blue-400">{match.file}</code>
              {match.line > 0 && (
                <>
                  <span className="text-xs text-gray-400 dark:text-zinc-500">:</span>
                  <span className="text-xs text-gray-500 dark:text-zinc-400">Line {match.line}</span>
                </>
              )}
            </div>
            <pre className="text-xs font-mono bg-gray-50 dark:bg-zinc-800 text-gray-900 dark:text-zinc-100 p-2 rounded overflow-x-auto">
              {match.content}
            </pre>
          </div>
        ))}
      </div>
    );
  };

  return (
    <>
      <div className="bg-white dark:bg-zinc-900 overflow-hidden">
        <div className="max-h-80 overflow-y-auto">
          {matches.length > 0 ? (
            renderMatchList(matches, PREVIEW_COUNT)
          ) : (
            <div className="p-4 text-center text-xs text-gray-500 dark:text-zinc-400">
              {t('workspace.chat.widgets.agentTools.noMatchingContent')}
            </div>
          )}
        </div>
        {matches.length > PREVIEW_COUNT && (
          <div className="px-3 py-1.5 bg-gray-100/50 dark:bg-zinc-800/50 border-t border-gray-200 dark:border-zinc-700 text-center">
            <button
              onClick={() => setShowFullscreen(true)}
              className="text-xs text-blue-600 hover:text-blue-700 dark:text-blue-400 dark:hover:text-blue-300 inline-flex items-center gap-1"
            >
              <Maximize2 className="h-3 w-3" />
              {t('workspace.chat.widgets.agentTools.viewFullContentResults', { count: matches.length })}
            </button>
          </div>
        )}
      </div>

      <Dialog open={showFullscreen} onOpenChange={setShowFullscreen}>
        <DialogContent className="max-w-4xl max-h-[80vh] overflow-hidden flex flex-col">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 font-mono text-sm">
              <SearchCode className="h-4 w-4" />
              {pattern}
            </DialogTitle>
          </DialogHeader>
          <div className="flex-1 overflow-auto bg-gray-50 dark:bg-zinc-900 rounded">
            {renderMatchList(matches)}
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
};

export default GrepWidget;
