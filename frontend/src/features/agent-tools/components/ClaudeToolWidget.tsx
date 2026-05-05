/**
 * ClaudeToolWidget - Claude Code tool-specific widget.
 *
 * Each tool type has a dedicated visual representation.
 */

import * as React from 'react';
import { useI18n } from '@/shared/hooks/useI18n';
import { cn } from '@/shared/utils/cn';
import {
  Terminal,
  FileText,
  Edit3,
  FilePlus,
  SearchCode,
  FolderSearch,
  CheckSquare,
  Bot,
  Globe,
  ExternalLink,
  Code,
  Activity,
  XCircle,
  Zap,
  Award,
  LogOut,
  ChevronDown,
  ChevronUp,
  Folder,
  ShieldAlert,
  Settings,
  HelpCircle,
  Clock,
  Trash2,
  FileOutput,
  StopCircle
} from 'lucide-react';

import {
  PermissionRequestWidget,
  PermissionScope,
  PermissionStatus,
} from './PermissionRequestWidget';
import type {
  AgentToolType,
  GeminiPermissionMode,
  OpenCodePermissionMode
} from './PermissionRequestWidget';

// Import extracted widgets
import { ReadWidget } from './ClaudeToolWidget/ReadWidget';
import { WriteWidget } from './ClaudeToolWidget/WriteWidget';
import { EditWidget } from './ClaudeToolWidget/EditWidget';
import { GlobWidget } from './ClaudeToolWidget/GlobWidget';
import { GrepWidget } from './ClaudeToolWidget/GrepWidget';
import { BashWidget } from './ClaudeToolWidget/BashWidget';
import { LSWidget } from './ClaudeToolWidget/LSWidget';
import { TodoWriteWidget } from './ClaudeToolWidget/TodoWriteWidget';
import { TaskWidget } from './ClaudeToolWidget/TaskWidget';
import { WebSearchWidget } from './ClaudeToolWidget/WebSearchWidget';
import { WebFetchWidget } from './ClaudeToolWidget/WebFetchWidget';
import { MCPWidget } from './ClaudeToolWidget/MCPWidget';
import { GenericWidget } from './ClaudeToolWidget/GenericWidget';
import { ThinkingWidget } from './ClaudeToolWidget/ThinkingWidget';
import { SystemInitWidget } from './ClaudeToolWidget/SystemInitWidget';
import { SystemErrorWidget } from './ClaudeToolWidget/SystemErrorWidget';
import { AskUserQuestionWidget } from './ClaudeToolWidget/AskUserQuestionWidget';
import { SkillWidget } from './ClaudeToolWidget/SkillWidget';
import { CronCreateWidget } from './ClaudeToolWidget/CronCreateWidget';
import { CronDeleteWidget } from './ClaudeToolWidget/CronDeleteWidget';
import { TaskOutputWidget } from './ClaudeToolWidget/TaskOutputWidget';
import { TaskStopWidget } from './ClaudeToolWidget/TaskStopWidget';
import { AgentWidget } from './ClaudeToolWidget/AgentWidget';
import { ToolStatus, ToolResultBlock, ClaudeToolType, extractToolResultContent } from './ClaudeToolWidget/types';

export type { ClaudeToolType, ToolStatus, ToolResultBlock };
export { extractToolResultContent };

export interface ClaudeToolWidgetProps {
  toolType: ClaudeToolType;
  toolId?: string;
  status?: ToolStatus;
  input?: Record<string, any>;
  output?: string | Record<string, any>;
  error?: string;
  /** Direct tool_result payload. */
  result?: ToolResultBlock | null;
  collapsible?: boolean;
  defaultExpanded?: boolean;
  className?: string;
  /** PermissionRequest: Agent SDK type. */
  agentTool?: AgentToolType;
  /** PermissionRequest: Claude Code approve callback. */
  onApprove?: (messageId: string, scope: PermissionScope) => void;
  /** PermissionRequest: Codex approve callback. */
  onCodexApprove?: (messageId: string, scope: PermissionScope) => void;
  /** PermissionRequest: Gemini approve callback. */
  onGeminiApprove?: (messageId: string, mode: GeminiPermissionMode) => void;
  /** PermissionRequest: OpenCode approve callback. */
  onOpenCodeApprove?: (messageId: string, mode: OpenCodePermissionMode) => void;
  /** PermissionRequest: deny callback. */
  onDeny?: (messageId: string) => void;
  /** PermissionRequest: request timestamp. */
  requested_at?: string;
  /** PermissionRequest: whether a previous permission request must finish first. */
  isWaiting?: boolean;
  /** AskUserQuestion: submit callback. */
  onAskUserQuestionSubmit?: (answers: Record<string, string | string[]>) => void;
  /** AskUserQuestion: cancel callback. */
  onAskUserQuestionCancel?: () => void;
  /** AskUserQuestion: whether answers were submitted. */
  isAskUserQuestionSubmitted?: boolean;
  /** AskUserQuestion: selected answers. */
  askUserQuestionAnswers?: Record<string, string | string[]>;
}

/**
 * ClaudeToolWidget main component.
 */
export const ClaudeToolWidget = React.forwardRef<HTMLDivElement, ClaudeToolWidgetProps>(
  ({
    toolType,
    toolId,
    status = 'completed',
    input,
    output,
    error,
    result,
    collapsible = true,
    defaultExpanded = true,
    className,
    agentTool,
    onApprove,
    onCodexApprove,
    onGeminiApprove,
    onOpenCodeApprove,
    onDeny,
    requested_at,
    isWaiting,
    onAskUserQuestionSubmit,
    onAskUserQuestionCancel,
    isAskUserQuestionSubmitted,
    askUserQuestionAnswers
  }, ref) => {
    const { t } = useI18n();
    const [isExpanded, setIsExpanded] = React.useState(defaultExpanded);
    const [isHovered, setIsHovered] = React.useState(false);

    // Extract output and error from tool_result payloads.
    const resolvedOutput = React.useMemo(() => {
      if (result) {
        const { content, isError } = extractToolResultContent(result);
        if (isError) {
          return { output: undefined, error: content };
        }
        return { output: content, error: undefined };
      }
      return { output, error };
    }, [result, output, error]);

    const finalOutput = resolvedOutput.output;
    const finalError = resolvedOutput.error || error;

    // Derive status from result payloads when available.
    const finalStatus = React.useMemo(() => {
      if (result) {
        return result.is_error ? 'error' : 'completed';
      }
      return status;
    }, [result, status]);

    // Render the dedicated widget for each tool type.
    const renderWidget = () => {
      const widgetProps = {
        input,
        output: finalOutput,
        error: finalError,
        status: finalStatus,
        isExpanded,
      };

      switch (toolType) {
        case 'Read':
          return <ReadWidget {...widgetProps} />;
        case 'Write':
          return <WriteWidget {...widgetProps} />;
        case 'Edit':
          return <EditWidget {...widgetProps} />;
        case 'Glob':
          return <GlobWidget {...widgetProps} />;
        case 'Grep':
          return <GrepWidget {...widgetProps} />;
        case 'Bash':
        case 'BashOutput':
          return <BashWidget {...widgetProps} />;
        case 'LS':
          return <LSWidget {...widgetProps} />;
        case 'TodoWrite':
          return <TodoWriteWidget {...widgetProps} />;
        case 'Task':
          return <TaskWidget {...widgetProps} />;
        case 'WebSearch':
          return <WebSearchWidget {...widgetProps} />;
        case 'WebFetch':
          return <WebFetchWidget {...widgetProps} />;
        case 'Skill':
          return <SkillWidget {...widgetProps} />;
        case 'CronCreate':
          return <CronCreateWidget {...widgetProps} />;
        case 'CronDelete':
          return <CronDeleteWidget {...widgetProps} />;
        case 'TaskOutput':
          return <TaskOutputWidget {...widgetProps} />;
        case 'TaskStop':
          return <TaskStopWidget {...widgetProps} />;
        case 'Agent':
          return <AgentWidget {...widgetProps} />;
        case 'PermissionRequest':
          return (
            <PermissionRequestWidget
              {...widgetProps}
              agentTool={agentTool}
              onApprove={onApprove}
              onCodexApprove={onCodexApprove}
              onGeminiApprove={onGeminiApprove}
              onOpenCodeApprove={onOpenCodeApprove}
              onDeny={onDeny}
              requested_at={requested_at}
              isWaiting={isWaiting}
            />
          );
        case 'Thinking':
          return <ThinkingWidget {...widgetProps} />;
        case 'SystemInit':
          return (
            <SystemInitWidget
              sessionId={input?.sessionId}
              model={input?.model}
              cwd={input?.cwd}
              tools={input?.tools}
              slash_commands={input?.slash_commands}
              output_style={input?.output_style}
              agents={input?.agents}
              skills={input?.skills}
              plugins={input?.plugins}
            />
          );
        case 'SystemError':
          return (
            <SystemErrorWidget
              error={input?.error || error}
              code={input?.code}
              collapsible={collapsible}
              defaultExpanded={defaultExpanded}
            />
          );
        case 'AskUserQuestion':
          return (
            <AskUserQuestionWidget
              {...widgetProps}
              onSubmit={onAskUserQuestionSubmit}
              onCancel={onAskUserQuestionCancel}
              isSubmitted={isAskUserQuestionSubmitted}
              submittedAnswers={askUserQuestionAnswers}
            />
          );
        default:
          // MCP tools
          if (toolType.startsWith('mcp__')) {
            return <MCPWidget toolType={toolType} {...widgetProps} />;
          }
          return <GenericWidget toolType={toolType} {...widgetProps} />;
      }
    };

    // Resolve header metadata for the current tool.
    const getHeaderInfo = () => {
      switch (toolType) {
        case 'Read':
          return { icon: FileText, label: t('workspace.chat.widgets.labels.fileContent'), detail: input?.file_path };
        case 'Write':
          return { icon: FilePlus, label: t('workspace.chat.widgets.labels.writingFile'), detail: input?.file_path };
        case 'Edit':
          return { icon: Edit3, label: t('workspace.chat.widgets.labels.editingFile'), detail: input?.file_path };
        case 'Glob':
          return { icon: FolderSearch, label: t('workspace.chat.widgets.labels.filesMatching'), detail: input?.pattern };
        case 'Grep':
          return { icon: SearchCode, label: t('workspace.chat.widgets.labels.searchingFor'), detail: input?.pattern };
        case 'Bash':
        case 'BashOutput':
          return { icon: Terminal, label: t('workspace.chat.widgets.labels.terminal'), detail: input?.description || input?.command };
        case 'LS':
          return { icon: Folder, label: t('workspace.chat.widgets.labels.directoryListing'), detail: input?.path };
        case 'TodoWrite':
          return { icon: CheckSquare, label: t('workspace.chat.widgets.labels.todoList'), detail: t('workspace.chat.widgets.labels.items', { count: input?.todos?.length || 0 }) };
        case 'Task':
          return { icon: Bot, label: t('workspace.chat.widgets.labels.task'), detail: input?.description || input?.prompt?.substring(0, 50) };
        case 'WebSearch':
          return { icon: Globe, label: t('workspace.chat.widgets.labels.webSearch'), detail: input?.query };
        case 'WebFetch':
          return { icon: Globe, label: t('workspace.chat.widgets.labels.webFetch'), detail: input?.url };
        case 'NotebookEdit':
          return { icon: Code, label: t('workspace.chat.widgets.labels.notebookEdit'), detail: input?.notebook_path };
        case 'KillShell':
          return { icon: XCircle, label: t('workspace.chat.widgets.labels.killShell'), detail: input?.shell_id };
        case 'SlashCommand':
          return { icon: Zap, label: t('workspace.chat.widgets.labels.slashCommand'), detail: input?.command };
        case 'Skill':
          return { icon: Award, label: t('workspace.chat.widgets.labels.skill'), detail: input?.skill };
        case 'ExitPlanMode':
          return { icon: LogOut, label: t('workspace.chat.widgets.labels.exitPlanMode'), detail: null };
        case 'CronCreate':
          return { icon: Clock, label: t('workspace.chat.widgets.labels.cronCreate'), detail: input?.cron };
        case 'CronDelete':
          return { icon: Trash2, label: t('workspace.chat.widgets.labels.cronDelete'), detail: input?.id };
        case 'TaskOutput':
          return { icon: FileOutput, label: t('workspace.chat.widgets.labels.taskOutput'), detail: input?.task_id };
        case 'TaskStop':
          return { icon: StopCircle, label: t('workspace.chat.widgets.labels.taskStop'), detail: input?.task_id };
        case 'Agent':
          return { icon: Bot, label: t('workspace.chat.widgets.labels.agent'), detail: input?.description };
        case 'PermissionRequest':
          return { icon: ShieldAlert, label: t('workspace.chat.widgets.labels.permissionRequest'), detail: input?.tool_name };
        case 'Thinking':
          return { icon: Bot, label: t('workspace.chat.widgets.labels.thinkingProcess'), detail: null };
        case 'SystemInit':
          return { icon: Settings, label: t('workspace.chat.widgets.labels.systemInitialization'), detail: null };
        case 'SystemError':
          return { icon: XCircle, label: t('workspace.chat.widgets.labels.executionFailed'), detail: input?.code };
        case 'AskUserQuestion':
          return { icon: HelpCircle, label: t('workspace.chat.widgets.labels.question'), detail: input?.questions?.[0]?.header || t('workspace.chat.widgets.labels.question') };
        default:
          // MCP tools
          if (toolType.startsWith('mcp__')) {
            const parts = toolType.split('__');
            const namespace = parts[1] || 'Unknown';
            const method = parts[2] || 'Unknown';

            // Convert snake_case or kebab-case identifiers to Title Case.
            const formatName = (name: string) => {
              return name
                .replace(/-/g, ' ')
                .replace(/_/g, ' ')
                .split(' ')
                .map(word => word.charAt(0).toUpperCase() + word.slice(1))
                .join(' ');
            };

            const formattedNamespace = formatName(namespace);
            const formattedMethod = formatName(method);
            const detail = `${formattedNamespace} • ${formattedMethod}`;

            return { icon: Activity, label: 'MCP', detail };
          }
          return { icon: Terminal, label: toolType, detail: null };
      }
    };

    const headerInfo = getHeaderInfo();
    const Icon = headerInfo.icon;

    // Status dot color.
    const getStatusDotClass = () => {
      switch (finalStatus) {
        case 'in_progress':
          return 'bg-blue-500 animate-pulse';
        case 'completed':
          return 'bg-green-500';
        case 'error':
          return 'bg-red-500';
        default:
          return 'bg-gray-400';
      }
    };

    return (
      <div
        ref={ref}
        className={cn(
          'rounded border overflow-hidden font-mono text-sm',
          'bg-white dark:bg-zinc-900 border-gray-200 dark:border-zinc-700 text-gray-900 dark:text-zinc-100',
          className
        )}
      >
        <div
          className={cn(
            'flex items-center gap-2 px-2 py-1 border-b',
            'bg-gray-50/80 dark:bg-zinc-800/50 border-gray-200 dark:border-zinc-700',
            collapsible && 'cursor-pointer hover:bg-gray-100 dark:hover:bg-zinc-800 transition-colors'
          )}
          onClick={() => collapsible && setIsExpanded(!isExpanded)}
          onMouseEnter={() => setIsHovered(true)}
          onMouseLeave={() => setIsHovered(false)}
        >
          {isHovered && collapsible ? (
            isExpanded ? (
              <ChevronUp className="h-3.5 w-3.5 text-gray-600 dark:text-zinc-400 flex-shrink-0" />
            ) : (
              <ChevronDown className="h-3.5 w-3.5 text-gray-600 dark:text-zinc-400 flex-shrink-0" />
            )
          ) : (
            <Icon className="h-3.5 w-3.5 text-gray-600 dark:text-zinc-400 flex-shrink-0" />
          )}
          <span className="text-xs text-gray-700 dark:text-zinc-300">{headerInfo.label}:</span>
          {headerInfo.detail && (
            <code className="text-xs font-mono bg-white dark:bg-zinc-800 px-1.5 py-0.5 border border-gray-200 dark:border-zinc-600 flex-1 truncate">
              {headerInfo.detail}
            </code>
          )}
          {toolType === 'WebFetch' && input?.url && (
            <a
              href={input.url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-gray-400 hover:text-gray-600 dark:text-zinc-500 dark:hover:text-zinc-300 flex-shrink-0"
              onClick={(e) => e.stopPropagation()}
            >
              <ExternalLink className="h-3 w-3" />
            </a>
          )}
          <div className="flex items-center ml-auto">
            <div className={cn('h-2 w-2 rounded-full', getStatusDotClass())} />
          </div>
        </div>

        {isExpanded && renderWidget()}
      </div>
    );
  }
);

ClaudeToolWidget.displayName = 'ClaudeToolWidget';

export default ClaudeToolWidget;
export { PermissionScopeEnum as PermissionScope, PermissionStatusValues as PermissionStatus, PermissionRequestWidget } from './PermissionRequestWidget';
export type { PermissionScope, PermissionStatus } from './PermissionRequestWidget';
export type {
  AgentToolType,
  GeminiPermissionMode,
  OpenCodePermissionMode,
  PermissionRequestWidgetProps,
} from './PermissionRequestWidget';
