/**
 * AcpReadWidget - ACP file read display.
 */
import React from 'react';
import { FileText, Maximize2 } from 'lucide-react';
import { useI18n } from '@/shared/hooks/useI18n';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/shared/components/ui/dialog';
import type { WidgetProps } from '../ClaudeToolWidget/types';
import { ErrorDisplay } from '../ClaudeToolWidget/ErrorDisplay';
import { extractAcpOutputText, extractAcpPath, extractTextFromAcpNode } from './acpRawPayload';

const resolveFilePath = (
  input: Record<string, any> | undefined,
  output?: string | Record<string, any>,
  toolName?: string
): string => extractAcpPath(input, output, toolName || '') || (toolName || '');

const resolveContent = (
  output?: string | Record<string, any>,
  input?: Record<string, any>
): string => {
  const fromOutput = extractAcpOutputText(output);
  if (fromOutput) return fromOutput;

  // ACP raw payloads may include displayable content in input.content/_acp_content when output is empty.
  const inputNodes = Array.isArray(input?.content)
    ? input.content
    : (Array.isArray(input?._acp_content) ? input._acp_content : null);
  if (inputNodes) {
    return inputNodes.map((node: unknown) => extractTextFromAcpNode(node)).filter(Boolean).join('\n');
  }

  if (!output || typeof output !== 'object') return '';
  if (typeof output.content === 'string') return output.content;
  if (Array.isArray(output.lines)) return output.lines.join('\n');
  return JSON.stringify(output, null, 2);
};

export const AcpReadWidget: React.FC<WidgetProps> = ({ input, output, error, status, toolType }) => {
  const { t } = useI18n();
  const [showFullscreen, setShowFullscreen] = React.useState(false);
  const filePath = resolveFilePath(input, output, toolType);
  const content = resolveContent(output, input);
  const hasContent = content.trim().length > 0;
  const lines = hasContent ? content.split('\n') : [];
  const PREVIEW_LINES = 10;
  // Avoid repeating the path when the outer AcpToolWidget header already shows it.
  const showInlinePath = !toolType;

  if (error) {
    return <ErrorDisplay error={error} />;
  }

  if (status === 'in_progress' && !hasContent) return null;

  return (
    <>
      <div className="bg-gray-50 dark:bg-zinc-900 overflow-hidden">
        {showInlinePath && (
          <div className="px-3 py-1.5 border-b border-gray-200 dark:border-zinc-700">
            <code className="text-xs text-gray-600 dark:text-zinc-300 truncate block">
              {filePath || t('workspace.chat.widgets.agentTools.unknownFile')}
            </code>
          </div>
        )}

        {hasContent ? (
          <div className="overflow-x-auto max-h-80">
            <table className="w-full text-xs font-mono">
              <tbody>
                {lines.slice(0, PREVIEW_LINES).map((line, index) => (
                  <tr key={index} className="hover:bg-gray-100/50 dark:hover:bg-zinc-800/50">
                    <td className="w-12 px-3 py-0.5 text-right text-gray-400 dark:text-zinc-500 border-r border-gray-200 dark:border-zinc-700 select-none">
                      {index + 1}
                    </td>
                    <td className="px-3 py-0.5 whitespace-pre-wrap break-all text-gray-900 dark:text-zinc-200">
                      {line || ' '}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="px-3 py-2 text-xs text-gray-500 dark:text-zinc-400">
            {t('workspace.chat.widgets.agentTools.noDisplayableContent')}
          </div>
        )}

        {hasContent && lines.length > PREVIEW_LINES && (
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

      <Dialog open={showFullscreen && hasContent} onOpenChange={setShowFullscreen}>
        <DialogContent className="max-w-4xl max-h-[80vh] overflow-hidden flex flex-col">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-sm font-mono">
              <FileText className="h-4 w-4" />
              {filePath || t('workspace.chat.widgets.agentTools.unknownFile')}
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
                    <td className="px-3 py-0.5 whitespace-pre-wrap break-all text-gray-900 dark:text-zinc-200">
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

export default AcpReadWidget;
