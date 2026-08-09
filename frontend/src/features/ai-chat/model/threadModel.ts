import type { ChatAttachmentReference } from '../attachments/attachmentModel';
import type { AgenticToolId, AgentMode } from './threadCapabilitiesModel';
import type { ThreadExecutionMetadata, ThreadTurnMetadata } from './threadTimelineModel';

export type ThreadStatus =
  | 'draft'
  | 'queued'
  | 'booting'
  | 'working'
  | 'stopping'
  | 'complete'
  | 'stopped'
  | 'error'
  | 'canceled';

export interface ThreadSummary {
  id: string;
  workspaceId: string;
  userId: string;
  origin: 'user' | 'automation';
  automationJobId: string | null;
  automationExecutionId: string | null;
  title: string;
  agenticTool: AgenticToolId;
  model: string;
  claudeMode: AgentMode | null;
  status: ThreadStatus;
  version: number;
  activeTurnId: string | null;
  activeTurnExecutionId: string | null;
  archived: boolean;
  errorCode: string | null;
  errorInfo: Record<string, unknown> | null;
  errorMessage: string | null;
  contextTokens: number | null;
  contextWindow: number | null;
  createdAt: string;
  updatedAt: string;
}

export interface OutgoingMessage {
  text: string;
  attachments: ChatAttachmentReference[];
}

export interface QueuedMessage extends OutgoingMessage {
  id: string;
}

export interface Thread extends ThreadSummary {
  queuedMessages: QueuedMessage[];
  draftMessage: OutgoingMessage | null;
}

export interface ThreadMutation extends Thread {
  createdItemIds: string[];
  changedItemIds: string[];
  turns: ThreadTurnMetadata[];
  executions: ThreadExecutionMetadata[];
}
