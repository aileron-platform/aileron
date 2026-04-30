/**
 * AcpGenericWidget - fallback for unknown ACP tools.
 */
import React from 'react';
import type { WidgetProps } from '../ClaudeToolWidget/types';
import { GenericWidget } from '../ClaudeToolWidget/GenericWidget';

export const AcpGenericWidget: React.FC<WidgetProps & { toolType?: string }> = ({ toolType, ...props }) => {
  return <GenericWidget toolType={toolType || 'ACP'} {...props} />;
};

export default AcpGenericWidget;
