/**
 * SystemErrorWidget - system error display.
 *
 * Displays failures from Claude SDK execution.
 */

import React from 'react';

export interface SystemErrorWidgetProps {
  /** Error message. */
  error?: string;
  /** Error code. */
  code?: string;
  /** Whether the error body can collapse. */
  collapsible?: boolean;
  /** Whether the error body is expanded by default. */
  defaultExpanded?: boolean;
}

export const SystemErrorWidget: React.FC<SystemErrorWidgetProps> = ({
  error,
  code,
}) => {
  if (!error && !code) {
    return null;
  }

  return (
    <div className="px-3 py-2 text-sm leading-6 text-destructive whitespace-pre-wrap break-words">
      {error || code}
    </div>
  );
};

export default SystemErrorWidget;
