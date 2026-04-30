/**
 * Shared ACP tool widget type definitions.
 */

import type { ToolStatus, WidgetProps } from '../ClaudeToolWidget/types';

export type { ToolStatus, WidgetProps };

export type AcpToolWidgetType = 'read' | 'write' | 'terminal' | 'generic';

export interface AcpToolWidgetProps extends WidgetProps {
  toolName: string;
  widgetType: AcpToolWidgetType;
  collapsible?: boolean;
  defaultExpanded?: boolean;
}
