import type { ChatAttachmentKind } from '../attachments/attachmentModel';
import type { AgenticToolId } from './threadCapabilitiesModel';

export type MessagePart =
  | { type: 'text'; text: string }
  | {
      type: ChatAttachmentKind;
      attachmentId: string;
      name: string;
      mimeType: string;
      size: number;
    };

export interface ThreadSystemInitServer {
  name: string;
  status: string | null;
}

export interface ThreadGitDiffStats {
  files: number;
  additions: number;
  deletions: number;
}

export type TimelineMessageItem =
  | {
      id: string;
      sequence: number;
      itemVersion: number;
      turnId: string;
      turnExecutionId: string;
      type: 'user' | 'agent_text' | 'thinking';
      parentItemId: null;
      content: { parts: MessagePart[] };
      createdAt: string;
    }
  | {
      id: string;
      sequence: number;
      itemVersion: number;
      turnId: string;
      turnExecutionId: string;
      type: 'tool';
      parentItemId: string | null;
      content: null;
      call: { name: string; parameters: Record<string, unknown> };
      providerResult: TimelineToolResult | null;
      interactionAnswer: { messageId: string; answers: Record<string, string | string[]> } | null;
      createdAt: string;
    }
  | {
      id: string;
      sequence: number;
      itemVersion: number;
      turnId: string;
      turnExecutionId: string;
      type: 'system_init';
      parentItemId: null;
      content: {
        agentResumeId: string | null;
        model: string | null;
        cwd: string | null;
        tools: string[];
        slashCommands?: string[];
        outputStyle?: string | null;
        agents?: string[];
        skills?: string[];
        plugins?: string[];
        mcpServers: ThreadSystemInitServer[];
      };
      createdAt: string;
    }
  | {
      id: string;
      sequence: number;
      itemVersion: number;
      turnId: string;
      turnExecutionId: string;
      type: 'git_diff';
      parentItemId: null;
      content: {
        description: string | null;
        diff: string;
        diffStats: ThreadGitDiffStats;
      };
      createdAt: string;
    }
  | {
      id: string;
      sequence: number;
      itemVersion: number;
      turnId: string;
      turnExecutionId: string;
      type: 'system' | 'error';
      parentItemId: null;
      content: { text: string };
      createdAt: string;
    };

export interface TimelineToolResult {
  messageId: string;
  isError: boolean;
  preview: string;
  byteLength: number;
  lineCount: number | null;
  truncated: boolean;
  mediaType: string;
}

export type ThreadTurnStatus =
  | 'running'
  | 'waiting_for_input'
  | 'complete'
  | 'error'
  | 'stopped'
  | 'canceled';

export interface ThreadExecutionMetadata {
  id: string;
  sequence: number;
  agenticTool: AgenticToolId;
  agentResumeId: string | null;
  version: number;
  status: ThreadTurnStatus;
  errorCode: string | null;
  errorInfo: Record<string, unknown> | null;
  createdAt: string;
  completedAt: string | null;
}

export interface ThreadTurnMetadata {
  id: string;
  sequence: number;
  version: number;
  status: ThreadTurnStatus;
  errorCode: string | null;
  errorInfo: Record<string, unknown> | null;
  createdAt: string;
  completedAt: string | null;
}

export interface TimelineItems {
  items: TimelineMessageItem[];
  turns: ThreadTurnMetadata[];
  executions: ThreadExecutionMetadata[];
}

export interface ThreadTimelinePage extends TimelineItems {
  pageInfo: {
    oldestSequence: number | null;
    newestSequence: number | null;
    nextBeforeSequence: number | null;
    hasMoreBefore: boolean;
  };
}
