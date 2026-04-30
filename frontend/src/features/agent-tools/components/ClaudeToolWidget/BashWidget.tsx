/**
 * BashWidget - terminal command display.
 */
import React from 'react';
import { Terminal, Maximize2 } from 'lucide-react';
import { useI18n } from '@/shared/hooks/useI18n';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/shared/components/ui/dialog';
import { WidgetProps } from './types';

export const BashWidget: React.FC<WidgetProps> = ({ input, output, error, status }) => {
  const { t } = useI18n();
  const [showFullscreen, setShowFullscreen] = React.useState(false);
  const command = input?.command || '';
  const content = typeof output === 'string' ? output : '';
  const lines = content.split('\n');
  const PREVIEW_LINES = 8;

  if (status === 'in_progress') {
    return null;
  }

  return (
    <>
      <div className="bg-zinc-900 text-zinc-100 overflow-hidden">
        <div className="px-3 py-1.5 border-b border-zinc-700 bg-zinc-800/50">
          <div className="flex items-center gap-2">
            <span className="text-green-400 text-xs">$</span>
            <code className="text-xs text-green-400">{command}</code>
          </div>
        </div>

        {error ? (
          <div className="p-3 text-red-400">
            <pre className="text-xs font-mono whitespace-pre-wrap">{error}</pre>
          </div>
        ) : content ? (
          <>
            <div className="p-3 max-h-48 overflow-y-auto">
              <pre className="text-xs font-mono whitespace-pre-wrap text-zinc-300">
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
                  {t('workspace.chat.widgets.agentTools.viewFullContent', { count: lines.length })}
                </button>
              </div>
            )}
          </>
        ) : null}
      </div>

      <Dialog open={showFullscreen} onOpenChange={setShowFullscreen}>
        <DialogContent className="max-w-4xl max-h-[80vh] overflow-hidden flex flex-col">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 font-mono text-sm">
              <Terminal className="h-4 w-4" />
              {command}
            </DialogTitle>
          </DialogHeader>
          <div className="flex-1 overflow-auto bg-zinc-900 rounded">
            <pre className="text-xs font-mono whitespace-pre-wrap text-zinc-300 p-4">
              {content}
            </pre>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
};

export default BashWidget;
