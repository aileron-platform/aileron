/**
 * WebFetchWidget - 網頁抓取組件
 */

import React from 'react';
import { Globe2, ExternalLink, Maximize2 } from 'lucide-react';
import { MarkdownContent } from '@/shared/components/markdown/MarkdownContent';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '../dialog';
import { WidgetProps } from './types';
import { ErrorDisplay } from './ErrorDisplay';

export const WebFetchWidget: React.FC<WidgetProps> = ({ input, output, error, status }) => {
  const [showFullscreen, setShowFullscreen] = React.useState(false);
  const url = input?.url || '';
  const content = typeof output === 'string' ? output : output != null ? JSON.stringify(output, null, 2) : '';

  // 預覽內容行數限制
  const lines = content.split('\n');
  const PREVIEW_LINES = 15;
  const previewContent = lines.slice(0, PREVIEW_LINES).join('\n');
  const hasMoreContent = lines.length > PREVIEW_LINES;

  if (error) {
    return <ErrorDisplay error={error} />;
  }

  if (status === 'in_progress') {
    return null;
  }

  return (
    <>
      <div className="bg-gray-50 dark:bg-zinc-900 overflow-hidden">
        {/* 內容預覽 */}
        <div className="overflow-x-auto max-h-80 p-4">
          <MarkdownContent content={previewContent || '無內容'} variant="compact" />
        </div>

        {/* 展開完整內容按鈕 */}
        {hasMoreContent && (
          <div className="px-4 py-2 bg-gray-100/50 dark:bg-zinc-800/50 border-t border-gray-200 dark:border-zinc-700 text-center">
            <button
              onClick={() => setShowFullscreen(true)}
              className="text-xs text-blue-600 hover:text-blue-700 dark:text-blue-400 dark:hover:text-blue-300 inline-flex items-center gap-1"
            >
              <Maximize2 className="h-3 w-3" />
              查看完整內容 ({lines.length} 行)
            </button>
          </div>
        )}
      </div>

      {/* 全螢幕對話框 */}
      <Dialog open={showFullscreen} onOpenChange={setShowFullscreen}>
        <DialogContent className="max-w-4xl max-h-[80vh] overflow-hidden flex flex-col">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 font-mono text-sm">
              <Globe2 className="h-4 w-4" />
              <span className="flex-1 truncate">{url}</span>
              <a
                href={url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-600 hover:text-blue-700 dark:text-blue-400 dark:hover:text-blue-300"
                onClick={(e) => e.stopPropagation()}
              >
                <ExternalLink className="h-3.5 w-3.5" />
              </a>
            </DialogTitle>
          </DialogHeader>
          <div className="flex-1 overflow-auto bg-white dark:bg-zinc-900 rounded p-6">
            <MarkdownContent content={content || '無內容'} variant="compact" />
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
};

export default WebFetchWidget;
