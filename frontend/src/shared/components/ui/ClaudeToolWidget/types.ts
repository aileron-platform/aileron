/**
 * ClaudeToolWidget 共用類型定義
 */

/**
 * Claude Code 工具類型
 */
export type ClaudeToolType =
  | 'Read'
  | 'Write'
  | 'Edit'
  | 'Glob'
  | 'Grep'
  | 'Bash'
  | 'LS'
  | 'TodoWrite'
  | 'Task'
  | 'WebSearch'
  | 'WebFetch'
  | 'NotebookEdit'
  | 'BashOutput'
  | 'KillShell'
  | 'SlashCommand'
  | 'Skill'
  | 'ExitPlanMode'
  | 'CronCreate'
  | 'CronDelete'
  | 'TaskOutput'
  | 'TaskStop'
  | 'Agent'
  | 'SystemInit'
  | 'Thinking'
  | 'AskUserQuestion';

/**
 * 工具執行狀態
 */
export type ToolStatus = 'pending' | 'in_progress' | 'completed' | 'error';

/**
 * tool_result 資料結構（來自 Claude API）
 */
export interface ToolResultBlock {
  type: 'tool_result';
  tool_use_id: string;
  content: string | Array<{ type: string; text?: string; [key: string]: any }>;
  is_error?: boolean;
}

/**
 * Widget 共用 Props
 */
export interface WidgetProps {
  input?: Record<string, any>;
  output?: string | Record<string, any>;
  error?: string;
  status: ToolStatus;
  isExpanded: boolean;
}

/**
 * 從 tool_result 提取內容
 */
export function extractToolResultContent(result: ToolResultBlock | null | undefined): {
  content: string;
  isError: boolean;
} {
  if (!result) {
    return { content: '', isError: false };
  }

  const isError = result.is_error || false;

  if (typeof result.content === 'string') {
    return { content: result.content, isError };
  }

  if (Array.isArray(result.content)) {
    const textContent = result.content
      .map((item) => {
        if (typeof item === 'string') return item;
        if (item.text) return item.text;
        return JSON.stringify(item);
      })
      .join('\n');
    return { content: textContent, isError };
  }

  return { content: JSON.stringify(result.content, null, 2), isError };
}
