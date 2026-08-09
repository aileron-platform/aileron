import type { ChatAttachmentUploadOperation } from '../attachments/attachmentModel';
import type { AgenticToolId, AgentMode, WorkspaceCapabilities } from '../model/threadCapabilitiesModel';
import type {
  OutgoingMessage,
  Thread,
  ThreadMutation,
  ThreadSummary,
} from '../model/threadModel';
import type { ThreadTimelinePage, TimelineItems } from '../model/threadTimelineModel';

export interface CreateDraftPayload {
  agenticTool: AgenticToolId;
  model: string;
  claudeMode: AgentMode | null;
}

export type PatchDraftPayload = Partial<CreateDraftPayload> & {
  draftMessage?: OutgoingMessage | null;
};

export interface QuestionAnswerPayload {
  answers: Record<string, string | string[]>;
  text: string;
}

export interface ListThreadsQuery {
  archived?: boolean;
}

export interface ThreadApi {
  listThreads(workspaceId: string, filters?: ListThreadsQuery): Promise<ThreadSummary[]>;
  getThread(threadId: string): Promise<Thread>;
  getThreadByAutomationExecution(automationExecutionId: string): Promise<Thread>;
  getTimeline(threadId: string, beforeSequence?: number, limit?: number): Promise<ThreadTimelinePage>;
  getTimelineItems(threadId: string, itemIds: string[]): Promise<TimelineItems>;
  getToolResultContent(threadId: string, messageId: string): Promise<string>;
  createDraft(workspaceId: string, input: CreateDraftPayload): Promise<Thread>;
  patchDraft(threadId: string, input: PatchDraftPayload): Promise<Thread>;
  submit(threadId: string, message: OutgoingMessage): Promise<ThreadMutation>;
  postMessage(threadId: string, message: OutgoingMessage): Promise<ThreadMutation>;
  removeQueuedMessage(threadId: string, queuedMessageId: string): Promise<Thread>;
  answerQuestion(
    threadId: string,
    messageId: string,
    payload: QuestionAnswerPayload,
  ): Promise<ThreadMutation>;
  cancel(threadId: string): Promise<Thread>;
  retry(threadId: string): Promise<Thread>;
  archive(threadId: string): Promise<Thread>;
  deleteThread(threadId: string): Promise<void>;
  getCapabilities(workspaceId: string): Promise<WorkspaceCapabilities>;
  uploadAttachment(
    threadId: string,
    file: File,
    onProgress: (progress: number) => void,
  ): ChatAttachmentUploadOperation;
  deleteAttachment(threadId: string, attachmentId: string): Promise<void>;
  transcribeAudio(file: File): Promise<{ text: string }>;
}

export class ThreadApiError extends Error {
  readonly code: string;
  readonly info: Record<string, unknown>;
  readonly status: number | undefined;

  constructor(
    code: string,
    info: Record<string, unknown> = {},
    status?: number,
  ) {
    super(code);
    this.name = 'ThreadApiError';
    this.code = code;
    this.info = info;
    this.status = status;
  }
}
