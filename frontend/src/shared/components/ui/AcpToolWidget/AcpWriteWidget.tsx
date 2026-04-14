/**
 * AcpWriteWidget - ACP 檔案寫入展示
 */
import React from 'react';
import { FilePenLine, Maximize2 } from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '../dialog';
import type { WidgetProps } from '../ClaudeToolWidget/types';
import { ErrorDisplay } from '../ClaudeToolWidget/ErrorDisplay';
import { extractAcpDiff, extractAcpOutputText, extractAcpPath } from './acpRawPayload';

const firstString = (...values: Array<unknown>): string => {
  for (const value of values) {
    if (typeof value === 'string' && value.trim()) return value;
  }
  return '';
};

const resolveFilePath = (
  input: Record<string, any> | undefined,
  output?: string | Record<string, any>,
  toolName?: string
): string => extractAcpPath(input, output, toolName || '');

const resolveContent = (input?: Record<string, any>, output?: string | Record<string, any>): string => {
  const diff = extractAcpDiff(output);
  return firstString(
    diff?.newText,
    input?.content,
    input?.text,
    input?.new_string,
    input?.newString
  );
};

const resolveOldContent = (input?: Record<string, any>, output?: string | Record<string, any>): string => {
  const diff = extractAcpDiff(output);
  return firstString(
    diff?.oldText,
    input?.old_string,
    input?.oldString
  );
};

const renderOutput = (output?: string | Record<string, any>): string => {
  if (typeof output === 'string') return output;
  const extracted = extractAcpOutputText(output);
  if (extracted) return extracted;
  if (!output || typeof output !== 'object') return '';
  if (typeof output.status === 'string') return output.status;
  return JSON.stringify(output, null, 2);
};

export const AcpWriteWidget: React.FC<WidgetProps> = ({ input, output, error, status, toolType }) => {
  const [showFullscreen, setShowFullscreen] = React.useState(false);

  const filePath = resolveFilePath(input, output, toolType);
  const content = resolveContent(input, output);
  const oldContent = resolveOldContent(input, output);
  const outputText = renderOutput(output);
  const lines = (content || oldContent).split('\n');
  const PREVIEW_LINES = 10;
  // 當外層 AcpToolWidget header 已顯示檔名時，避免內文重複顯示。
  const showInlinePath = !toolType;

  if (error) {
    return <ErrorDisplay error={error} />;
  }

  if (status === 'in_progress' && !content && !oldContent) return null;

  const hasEditPair = !!oldContent && !!content;

  return (
    <>
      <div className="bg-gray-50 dark:bg-zinc-900 overflow-hidden">
        {showInlinePath && (
          <div className="px-3 py-1.5 border-b border-gray-200 dark:border-zinc-700">
            <code className="text-xs text-gray-600 dark:text-zinc-300 truncate block">
              {filePath || '未知檔案'}
            </code>
          </div>
        )}

        {hasEditPair ? (
          <div className="grid gap-2 p-3 md:grid-cols-2">
            <div>
              <div className="mb-1 text-[11px] font-medium text-gray-500 dark:text-zinc-400">舊內容</div>
              <pre className="max-h-44 overflow-auto rounded border border-gray-200 dark:border-zinc-700 bg-white dark:bg-zinc-900 p-2 text-xs font-mono whitespace-pre-wrap break-all text-gray-800 dark:text-zinc-200">
                {oldContent}
              </pre>
            </div>
            <div>
              <div className="mb-1 text-[11px] font-medium text-gray-500 dark:text-zinc-400">新內容</div>
              <pre className="max-h-44 overflow-auto rounded border border-gray-200 dark:border-zinc-700 bg-white dark:bg-zinc-900 p-2 text-xs font-mono whitespace-pre-wrap break-all text-green-700 dark:text-green-400">
                {content}
              </pre>
            </div>
          </div>
        ) : (
          <div className="overflow-x-auto max-h-48">
            <table className="w-full text-xs font-mono">
              <tbody>
                {lines.slice(0, PREVIEW_LINES).map((line, index) => (
                  <tr key={index} className="hover:bg-gray-100/50 dark:hover:bg-zinc-800/50">
                    <td className="w-12 px-3 py-0.5 text-right text-gray-400 dark:text-zinc-500 border-r border-gray-200 dark:border-zinc-700 select-none">
                      {index + 1}
                    </td>
                    <td className="px-3 py-0.5 whitespace-pre-wrap break-all text-green-700 dark:text-green-400">
                      {line || ' '}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {outputText && (
          <div className="border-t border-gray-200 dark:border-zinc-700 px-3 py-2">
            <div className="mb-1 text-[11px] font-medium text-gray-500 dark:text-zinc-400">執行結果</div>
            <pre className="max-h-28 overflow-auto rounded border border-gray-200 dark:border-zinc-700 bg-white dark:bg-zinc-900 p-2 text-xs font-mono whitespace-pre-wrap break-all text-gray-800 dark:text-zinc-200">
              {outputText}
            </pre>
          </div>
        )}

        {lines.length > PREVIEW_LINES && (
          <div className="px-3 py-1.5 bg-gray-100/50 dark:bg-zinc-800/50 border-t border-gray-200 dark:border-zinc-700 text-center">
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

      <Dialog open={showFullscreen} onOpenChange={setShowFullscreen}>
        <DialogContent className="max-w-4xl max-h-[80vh] overflow-hidden flex flex-col">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-sm font-mono">
              <FilePenLine className="h-4 w-4" />
              {filePath || '未知檔案'}
            </DialogTitle>
          </DialogHeader>
          <div className="flex-1 overflow-auto bg-gray-50 dark:bg-zinc-900 rounded">
            <table className="w-full text-xs font-mono">
              <tbody>
                {lines.map((line, index) => (
                  <tr key={index} className="hover:bg-gray-100/50 dark:hover:bg-zinc-800/50">
                    <td className="w-12 px-3 py-0.5 text-right text-gray-400 dark:text-zinc-500 border-r border-gray-200 dark:border-zinc-700 select-none">
                      {index + 1}
                    </td>
                    <td className="px-3 py-0.5 whitespace-pre-wrap break-all text-green-700 dark:text-green-400">
                      {line || ' '}
                    </td>
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

export default AcpWriteWidget;
