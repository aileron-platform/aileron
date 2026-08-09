import type { UiMessagePart, UiToolResult, UiToolStatus } from './toUiMessages';

export interface ToolPartProps {
  id?: string;
  name: string;
  parameters: Record<string, unknown>;
  status: UiToolStatus;
  result?: UiToolResult;
  parts?: UiMessagePart[];
}
