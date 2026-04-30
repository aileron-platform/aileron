/**
 * ErrorDisplay - error display component.
 */

import React from 'react';
import { XCircle } from 'lucide-react';
import { useI18n } from '@/shared/hooks/useI18n';

export interface ErrorDisplayProps {
  error: string;
}

export const ErrorDisplay: React.FC<ErrorDisplayProps> = ({ error }) => {
  const { t } = useI18n();

  return (
    <div className="p-3 bg-red-50 dark:bg-red-950/30 border-t border-red-100 dark:border-red-900">
      <div className="flex items-start gap-2">
        <XCircle className="h-4 w-4 text-red-500 mt-0.5 flex-shrink-0" />
        <div className="flex-1">
          <p className="text-sm font-medium text-red-600 dark:text-red-400 mb-1">
            {t('workspace.chat.widgets.agentTools.error')}
          </p>
          <pre className="text-xs font-mono text-red-700 dark:text-red-300 whitespace-pre-wrap">
            {error}
          </pre>
        </div>
      </div>
    </div>
  );
};

export default ErrorDisplay;
