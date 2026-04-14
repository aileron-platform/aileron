/**
 * AcpGenericWidget - ACP 未知工具 fallback
 */
import React from 'react';
import type { WidgetProps } from '../ClaudeToolWidget/types';
import { GenericWidget } from '../ClaudeToolWidget/GenericWidget';

export const AcpGenericWidget: React.FC<WidgetProps & { toolType?: string }> = ({ toolType, ...props }) => {
  return <GenericWidget toolType={toolType || 'ACP'} {...props} />;
};

export default AcpGenericWidget;
