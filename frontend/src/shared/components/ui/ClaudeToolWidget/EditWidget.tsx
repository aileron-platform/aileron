/**
 * EditWidget - 文件編輯（單欄式差異顯示）
 */
import React from 'react';
import { Edit3, Maximize2 } from 'lucide-react';
import { cn } from '@/shared/utils/cn';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '../dialog';
import { WidgetProps } from './types';
import { ErrorDisplay } from './ErrorDisplay';

export const EditWidget: React.FC<WidgetProps> = ({ input, output, error, status, isExpanded }) => {
  const [showFullscreen, setShowFullscreen] = React.useState(false);
  const filePath = input?.file_path || '';
  const oldStr = input?.old_string || '';
  const newStr = input?.new_string || '';
  const oldLines = oldStr.split('\n');
  const newLines = newStr.split('\n');
  const PREVIEW_LINES = 8;
  const totalLines = oldLines.length + newLines.length;
  const showExpandButton = totalLines > PREVIEW_LINES * 2;

  if (error) {
    return <ErrorDisplay error={error} />;
  }

  if (status === 'in_progress') {
    return null;
  }

  const renderDiffTable = (lines: string[], isOld: boolean, limit?: number) => {
    const displayLines = limit ? lines.slice(0, limit) : lines;
    const symbol = isOld ? '-' : '+';

    return (
      <table className="w-full text-xs font-mono">
        <tbody>
          {displayLines.map((line, index) => (
            <tr key={index} className={isOld ? 'hover:bg-red-100/50 dark:hover:bg-red-900/30' : 'hover:bg-green-100/50 dark:hover:bg-green-900/30'}>
              <td className={cn(
                'px-2 py-0.5 text-right select-none border-r w-8',
                isOld ? 'text-red-400 border-red-200 dark:border-red-800' : 'text-green-400 border-green-200 dark:border-green-800'
              )}>
                {index + 1}
              </td>
              <td className={cn(
                'px-2 py-0.5 whitespace-pre',
                isOld ? 'text-red-700 dark:text-red-300' : 'text-green-700 dark:text-green-300'
              )}>
                <span className={cn(
                  'select-none mr-1',
                  isOld ? 'text-red-400' : 'text-green-400'
                )}>{symbol}</span>
                {line || ' '}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    );
  };

  return (
    <>
      <div className="bg-white dark:bg-zinc-900 p-3 space-y-3">
        {/* Old String - 刪除的內容 */}
        <div>
          <div className="text-xs font-medium text-red-600 dark:text-red-400 mb-2 flex items-center gap-1">
            <span>−</span>
            <span>刪除 ({oldLines.length} 行)</span>
          </div>
          <div className="bg-red-50 dark:bg-red-950/30 rounded border border-red-200 dark:border-red-800 overflow-hidden">
            <div className={showExpandButton ? 'max-h-32 overflow-hidden' : ''}>
              {renderDiffTable(oldLines, true, showExpandButton ? PREVIEW_LINES : undefined)}
            </div>
          </div>
        </div>

        {/* New String - 新增的內容 */}
        <div>
          <div className="text-xs font-medium text-green-600 dark:text-green-400 mb-2 flex items-center gap-1">
            <span>+</span>
            <span>新增 ({newLines.length} 行)</span>
          </div>
          <div className="bg-green-50 dark:bg-green-950/30 rounded border border-green-200 dark:border-green-800 overflow-hidden">
            <div className={showExpandButton ? 'max-h-32 overflow-hidden' : ''}>
              {renderDiffTable(newLines, false, showExpandButton ? PREVIEW_LINES : undefined)}
            </div>
          </div>
        </div>

        {/* 查看完整內容按鈕 */}
        {showExpandButton && (
          <div className="pt-2 border-t border-gray-200 dark:border-zinc-700 text-center">
            <button
              onClick={() => setShowFullscreen(true)}
              className="text-xs text-blue-600 hover:text-blue-700 dark:text-blue-400 dark:hover:text-blue-300 inline-flex items-center gap-1"
            >
              <Maximize2 className="h-3 w-3" />
              查看完整內容 (總計 {totalLines} 行)
            </button>
          </div>
        )}

        {/* Result */}
        {output && (
          <div className="pt-2 border-t border-gray-200 dark:border-zinc-700">
            <div className="text-xs text-gray-500 dark:text-zinc-400">
              ✓ {typeof output === 'string' ? output : '編輯完成'}
            </div>
          </div>
        )}
      </div>

      {/* 全螢幕對話框 */}
      <Dialog open={showFullscreen} onOpenChange={setShowFullscreen}>
        <DialogContent className="max-w-4xl max-h-[80vh] overflow-hidden flex flex-col">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 font-mono text-sm">
              <Edit3 className="h-4 w-4" />
              {filePath}
            </DialogTitle>
          </DialogHeader>
          <div className="flex-1 overflow-auto p-4 space-y-4">
            {/* Old String - 完整內容 */}
            <div>
              <div className="text-xs font-medium text-red-600 dark:text-red-400 mb-2 flex items-center gap-1">
                <span>−</span>
                <span>刪除 ({oldLines.length} 行)</span>
              </div>
              <div className="bg-red-50 dark:bg-red-950/30 rounded border border-red-200 dark:border-red-800 overflow-hidden">
                {renderDiffTable(oldLines, true)}
              </div>
            </div>

            {/* New String - 完整內容 */}
            <div>
              <div className="text-xs font-medium text-green-600 dark:text-green-400 mb-2 flex items-center gap-1">
                <span>+</span>
                <span>新增 ({newLines.length} 行)</span>
              </div>
              <div className="bg-green-50 dark:bg-green-950/30 rounded border border-green-200 dark:border-green-800 overflow-hidden">
                {renderDiffTable(newLines, false)}
              </div>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
};

export default EditWidget;
