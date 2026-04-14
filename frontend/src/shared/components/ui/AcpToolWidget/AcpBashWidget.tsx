/**
 * AcpBashWidget - ACP terminal/batch 輸出展示
 */
import React from 'react';
import { Terminal, Maximize2 } from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '../dialog';
import type { WidgetProps } from '../ClaudeToolWidget/types';
import { ErrorDisplay } from '../ClaudeToolWidget/ErrorDisplay';
import { extractAcpCommand, extractAcpErrorText, extractAcpOutputText } from './acpRawPayload';

const resolveCommand = (input: Record<string, any> | undefined, toolType?: string): string =>
  extractAcpCommand(input, toolType || '');

const resolveOutput = (output?: string | Record<string, any>): string => {
  const extracted = extractAcpOutputText(output);
  if (extracted) return extracted;
  if (output && typeof output === 'object') return JSON.stringify(output, null, 2);
  return '';
};

const resolveErrorFromOutput = (output?: string | Record<string, any>): string | null => {
  const error = extractAcpErrorText(output);
  return error || null;
};

export const AcpBashWidget: React.FC<WidgetProps> = ({ input, output, error, status, toolType }) => {
  const [showFullscreen, setShowFullscreen] = React.useState(false);
  const command = resolveCommand(input, toolType);
  const content = resolveOutput(output);
  const outputError = resolveErrorFromOutput(output);
  const lines = content.split('\n');
  const PREVIEW_LINES = 8;

  if (error) {
    return <ErrorDisplay error={error} />;
  }

  if (outputError) {
    return <ErrorDisplay error={outputError} />;
  }

  if (status === 'in_progress' && !content) return null;

  return (
    <>
      <div className="bg-zinc-900 text-zinc-100 overflow-hidden">
        <div className="px-3 py-1.5 border-b border-zinc-700 bg-zinc-800/50">
          <div className="flex items-center gap-2">
            <span className="text-green-400 text-xs">$</span>
            <code className="text-xs text-green-400 break-all">{command || '(無命令)'}</code>
          </div>
        </div>

        {content ? (
          <>
            <div className="p-3 max-h-48 overflow-y-auto">
              <pre className="text-xs font-mono whitespace-pre-wrap break-all text-zinc-300">
                {lines.slice(0, PREVIEW_LINES).join('\n')}
              </pre>
            </div>

            {lines.length > PREVIEW_LINES && (
              <div className="px-3 py-1.5 bg-zinc-800/50 border-t border-zinc-700 text-center">
                <button
                  onClick={() => setShowFullscreen(true)}
                  className="text-xs text-blue-400 hover:text-blue-300 inline-flex items-center gap-1"
                >
                  <Maximize2 className="h-3 w-3" />
                  查看完整輸出 ({lines.length} 行)
                </button>
              </div>
            )}
          </>
        ) : null}
      </div>

      <Dialog open={showFullscreen} onOpenChange={setShowFullscreen}>
        <DialogContent className="max-w-4xl max-h-[80vh] overflow-hidden flex flex-col">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-sm font-mono">
              <Terminal className="h-4 w-4" />
              {command || '(無命令)'}
            </DialogTitle>
          </DialogHeader>
          <div className="flex-1 overflow-auto rounded border border-zinc-700 bg-zinc-900 p-4">
            <pre className="text-xs font-mono whitespace-pre-wrap break-all text-zinc-300">
              {content}
            </pre>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
};

export default AcpBashWidget;
