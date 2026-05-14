import { DialogHeading } from '@/shared/components/ui/dialog-heading';
/**
 * MCPWidget - MCP tool display.
 */

import React from 'react';
import { Package, Maximize2 } from 'lucide-react';
import { cn } from '@/shared/utils/cn';
import { useI18n } from '@/shared/hooks/useI18n';
import { Dialog, DialogContent, DialogHeader } from '@/shared/components/ui/dialog';
import { WidgetProps } from './types';
import { ErrorDisplay } from './ErrorDisplay';

export const MCPWidget: React.FC<WidgetProps & { toolType: string }> = ({
  toolType,
  input,
  output,
  error,
  status
}) => {
  const { t } = useI18n();
  const [showFullscreen, setShowFullscreen] = React.useState(false);

  // Parse MCP details from mcp__namespace__method names.
  const parts = toolType.split('__');
  const namespace = parts[1] || 'Unknown';
  const method = parts[2] || 'Unknown';

  // Format identifiers for display.
  const formatName = (name: string) => {
    return name
      .replace(/-/g, ' ')
      .replace(/_/g, ' ')
      .split(' ')
      .map(word => word.charAt(0).toUpperCase() + word.slice(1))
      .join(' ');
  };

  const mcpInfo = {
    server: formatName(namespace),
    method: formatName(method),
    params: input,
  };

  const content = typeof output === 'string' ? output : JSON.stringify(output, null, 2);

  if (error) {
    return <ErrorDisplay error={error} />;
  }

  if (status === 'in_progress') {
    return null;
  }

  return (
    <>
      <div className="bg-gray-50 dark:bg-zinc-900 overflow-hidden">
        {/* Parameters */}
        <div className="p-3 border-b border-gray-200 dark:border-zinc-700">
          <div className="text-xs font-medium text-gray-500 dark:text-zinc-400 mb-2">
            {t('workspace.chat.widgets.agentTools.parameters')}
          </div>
          <pre className="text-xs font-mono bg-white dark:bg-zinc-800 text-gray-900 dark:text-zinc-100 p-2 rounded border border-gray-200 dark:border-zinc-700 overflow-x-auto">
            {JSON.stringify(mcpInfo.params, null, 2)}
          </pre>
        </div>

        {/* Result */}
        {output && (
          <>
            <div className="p-3 max-h-48 overflow-y-auto">
              <div className="text-xs font-medium text-gray-500 dark:text-zinc-400 mb-2">
                {t('workspace.chat.widgets.agentTools.result')}
              </div>
              <pre className="text-xs font-mono bg-white dark:bg-zinc-800 text-gray-900 dark:text-zinc-100 p-2 rounded border border-gray-200 dark:border-zinc-700 whitespace-pre-wrap">
                {content}
              </pre>
            </div>
            {content.split('\n').length > 10 && (
              <div className="px-4 py-2 bg-gray-100/50 dark:bg-zinc-800/50 border-t border-gray-200 dark:border-zinc-700 text-center">
                <button
                  onClick={() => setShowFullscreen(true)}
                  className="text-xs text-blue-600 hover:text-blue-700 dark:text-blue-400 dark:hover:text-blue-300 inline-flex items-center gap-1"
                >
                  <Maximize2 className="h-3 w-3" />
                  {t('workspace.chat.widgets.agentTools.viewFullContentPlain')}
                </button>
              </div>
            )}
          </>
        )}
      </div>

      <Dialog open={showFullscreen} onOpenChange={setShowFullscreen}>
        <DialogContent className="max-w-4xl max-h-[80vh] overflow-hidden flex flex-col">
          <DialogHeader>
            <DialogHeading icon={Package} className="font-mono text-sm" iconClassName="h-4 w-4">
              {mcpInfo.server} • {mcpInfo.method}
            </DialogHeading>
          </DialogHeader>
          <div className="flex-1 overflow-auto bg-gray-50 dark:bg-zinc-900 rounded p-4">
            <pre className="text-xs font-mono whitespace-pre-wrap text-gray-900 dark:text-zinc-100">
              {content}
            </pre>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
};

export default MCPWidget;
