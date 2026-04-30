/**
 * GenericWidget - generic tool display.
 */
import React from 'react';
import { useI18n } from '@/shared/hooks/useI18n';
import { WidgetProps } from './types';
import { ErrorDisplay } from './ErrorDisplay';

export const GenericWidget: React.FC<WidgetProps & { toolType: string }> = ({ input, output, error, status }) => {
  const { t } = useI18n();
  const content = typeof output === 'string' ? output : JSON.stringify(output, null, 2);

  if (error) {
    return <ErrorDisplay error={error} />;
  }

  if (status === 'in_progress') {
    return null;
  }

  return (
    <div className="bg-white dark:bg-zinc-900 p-3">
      {input && (
        <div className="mb-3">
          <div className="text-xs font-medium text-gray-500 dark:text-zinc-400 mb-1">
            {t('workspace.chat.widgets.agentTools.input')}
          </div>
          <pre className="text-xs font-mono bg-gray-50 dark:bg-zinc-800 text-gray-900 dark:text-zinc-100 p-2 rounded overflow-x-auto">
            {JSON.stringify(input, null, 2)}
          </pre>
        </div>
      )}
      {content && (
        <div>
          <div className="text-xs font-medium text-gray-500 dark:text-zinc-400 mb-1">
            {t('workspace.chat.widgets.agentTools.output')}
          </div>
          <pre className="text-xs font-mono bg-gray-50 dark:bg-zinc-800 text-gray-900 dark:text-zinc-100 p-2 rounded overflow-x-auto">
            {content}
          </pre>
        </div>
      )}
    </div>
  );
};

export default GenericWidget;
